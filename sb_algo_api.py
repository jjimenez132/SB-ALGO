#!/usr/bin/env python3
"""
================================================================================
SB-ALGO PICKS API v4.0 - FULL ENGINE INTEGRATION
================================================================================
UPDATED: Jan 27, 2026

NOW USING:
  - PlayerPropEngine: Stat-specific distributions, pace/defense adjustments
  - NBAMathEngine: Monte Carlo, matchup history, Kelly criterion
  - MetaMergeEngine: Orchestrates Uncertainty, Injury, CLV, Calibration engines

PROP PREDICTIONS:
  - Gaussian distribution for points
  - Poisson distribution for assists/steals/blocks
  - Negative Binomial for rebounds
  - Pace and defense adjustments per opponent

FILTERS: Applied LAST (after engine processing)
================================================================================
"""

import psycopg2
import os
import statistics
from collections import defaultdict
from datetime import datetime, date
import pytz
import sys

DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://sb_algo_db_user:0HDtYp4EY2Lo5At8iyf44PD1zDioSPK7@dpg-d495uhchg0os738l1a50-a.virginia-postgres.render.com/sb_algo_db')

_picks_cache = {}
_cache_time = None
CACHE_DURATION = 300

# =============================================================================
# PLAYER NAME NORMALIZATION
# Handles Jr/Jr., II/III suffixes, and common nickname variations
# =============================================================================
PLAYER_NAME_ALIASES = {
    # Nicknames to full names
    'herb jones': 'herbert jones',
    'gg jackson': 'g.g. jackson',
    'rj barrett': 'r.j. barrett',
    'pj washington': 'p.j. washington',
    'cj mccollum': 'c.j. mccollum',
    'tj mcconnell': 't.j. mcconnell',
    'tj warren': 't.j. warren',
    'oj anunoby': 'o.g. anunoby',
    'og anunoby': 'o.g. anunoby',
}

def normalize_player_name(name):
    """
    Normalize player name for consistent matching across tables.
    Handles: Jr/Jr., II/III, common nicknames
    """
    if not name:
        return name
    
    normalized = name.strip()
    
    # Lowercase for comparison
    lower = normalized.lower()
    
    # Check aliases first (Herb → Herbert, etc.)
    if lower in PLAYER_NAME_ALIASES:
        normalized = PLAYER_NAME_ALIASES[lower].title()
    
    # Normalize suffix variations: "Jr" → "Jr.", "Sr" → "Sr."
    import re
    # Add period after Jr/Sr if missing
    normalized = re.sub(r'\b(Jr|Sr)\b(?!\.)', r'\1.', normalized)
    # Remove extra suffixes for matching (keep original for display)
    # "Jr." and "Jr" should match, "II" and " II" should match
    
    return normalized


# =============================================================================
# ENGINE IMPORTS
# =============================================================================
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'engines'))

# PlayerPropEngine - Stat-specific distributions + pace/defense adjustments
try:
    from engines.player_prop_engine import PlayerPropEngine
    PROP_ENGINE_AVAILABLE = True
except ImportError:
    PROP_ENGINE_AVAILABLE = False
    print("⚠️ PlayerPropEngine not available - using fallback")

# NBAMathEngine - Monte Carlo, matchup history
try:
    from nba_math_engine import NBAMathEngine
    MATH_ENGINE_AVAILABLE = True
except ImportError:
    MATH_ENGINE_AVAILABLE = False
    print("⚠️ NBAMathEngine not available - using fallback")

# KellyEngine - Bet sizing with fractional Kelly
try:
    from kelly_engine import KellyEngine
    KELLY_ENGINE_AVAILABLE = True
except ImportError:
    KELLY_ENGINE_AVAILABLE = False
    print("⚠️ KellyEngine not available - using 1 unit default")

# CLVEngine - Closing Line Value tracking
try:
    from clv_engine import CLVEngine
    CLV_ENGINE_AVAILABLE = True
except ImportError:
    CLV_ENGINE_AVAILABLE = False
    print("⚠️ CLVEngine not available - CLV tracking disabled")

# InjuryEngine - Team injury impact
try:
    from injury_engine import InjuryEngine
    INJURY_ENGINE_AVAILABLE = True
except ImportError:
    INJURY_ENGINE_AVAILABLE = False
    print("⚠️ InjuryEngine not available - injury tracking disabled")

# Initialize engines (lazy load)
_prop_engine = None
_math_engine = None
_kelly_engine = None
_clv_engine = None
_injury_engine = None

# Health alert webhook for engine issues
HEALTH_WEBHOOK_URL = "https://discord.com/api/webhooks/1453117705984151724/22JltUkGycD-TyNUlzymZEN6D9UoJsmF_GH2v0Ctv8f77DvPFOqHQi0dxR4nZP7kK0WX"

def send_health_alert(message, alert_type="warning"):
    """Send health alert to Discord #algo-health channel"""
    import requests
    colors = {"error": 0xff0000, "warning": 0xffa500, "info": 0x00ff00}
    try:
        requests.post(HEALTH_WEBHOOK_URL, json={
            "embeds": [{
                "title": f"⚙️ Engine Health Alert",
                "description": message,
                "color": colors.get(alert_type, 0xffa500),
                "footer": {"text": f"SB-ALGO v4.0 • {datetime.now().strftime('%I:%M %p ET')}"}
            }]
        }, timeout=5)
    except:
        pass  # Don't fail main process if alert fails

def get_prop_engine():
    global _prop_engine
    if _prop_engine is None and PROP_ENGINE_AVAILABLE:
        _prop_engine = PlayerPropEngine()
    return _prop_engine

def get_math_engine():
    global _math_engine
    if _math_engine is None and MATH_ENGINE_AVAILABLE:
        _math_engine = NBAMathEngine()
    return _math_engine

# Kelly engine (conservative profile for safe bet sizing)
_kelly_engine = None
def get_kelly_engine():
    global _kelly_engine
    if _kelly_engine is None and KELLY_ENGINE_AVAILABLE:
        _kelly_engine = KellyEngine(risk_profile='conservative')
    return _kelly_engine

# InjuryEngine - Team injury impact analysis
try:
    from injury_engine import InjuryEngine
    INJURY_ENGINE_AVAILABLE = True
except ImportError:
    INJURY_ENGINE_AVAILABLE = False

_injury_engine = None
def get_injury_engine():
    global _injury_engine
    if _injury_engine is None and INJURY_ENGINE_AVAILABLE:
        _injury_engine = InjuryEngine()
    return _injury_engine

# CLV Engine - Closing Line Value tracking
def get_clv_engine():
    global _clv_engine
    if _clv_engine is None and CLV_ENGINE_AVAILABLE:
        _clv_engine = CLVEngine()
    return _clv_engine

# =============================================================================
# FILTERS - Imported from meta_merge_engine_v4.py (SINGLE SOURCE OF TRUTH)
# =============================================================================
from engines.meta_merge_engine_v4 import VEGAS_FILTERS as MASTER_FILTERS

# Convert from meta_merge format to sb_algo_api format
def _convert_filters():
    """Convert meta_merge filter format to sb_algo_api format"""
    prop_filters = {}
    vegas_filters = {}
    
    # ==========================================================================
    # TIERED PROP SYSTEM - T1 (81.8%) + T2 (72.3%) + T3 (69.4%)
    # Total: 72.8% at 4.53 picks/day
    # ==========================================================================
    
    # T1 ELITE FILTERS (5 filters, 81.8% win rate, 1.5 units)
    t1_mappings = {
        'prop_pts_under_t1': 'pts_under',
        'prop_reb_over_t1': 'reb_over',
        'prop_reb_under_t1': 'reb_under',
        'prop_ast_under_t1': 'ast_under',
        'prop_3pm_under_t1': '3pm_under',
    }
    
    # T2 STRONG FILTERS (4 filters, 72.3% win rate, 1.0 units)
    t2_mappings = {
        'prop_pts_under_t2': 'pts_under_t2',
        'prop_reb_under_t2': 'reb_under_t2',
        'prop_ast_over_t2': 'ast_over_t2',
        'prop_ast_under_t2': 'ast_under_t2',
    }
    
    # T3 VOLUME FILTERS (expanded with OVER filters for balance)
    t3_mappings = {
        'prop_pts_under_t3': 'pts_under_t3',
        'prop_reb_under_t3': 'reb_under_t3',
        'prop_ast_under_t3': 'ast_under_t3',
        'prop_pts_over_t3': 'pts_over_t3',
        'prop_reb_over_t3': 'reb_over_t3',
        'prop_ast_over_t3': 'ast_over_t3',
        'prop_3pm_under_t3': '3pm_under_t3',
    }
    
    # Process T1 filters
    for master_key, api_key in t1_mappings.items():
        if master_key in MASTER_FILTERS and MASTER_FILTERS[master_key].get('enabled', False):
            f = MASTER_FILTERS[master_key]
            prop_filters[api_key] = {
                'edge_min': abs(f.get('edge_min', f.get('edge_max', 15))) / 100,
                'cv_max': f.get('cv_max', 0.45),
                'proj_min': f.get('min_proj', 0),
                'tier': 1,
            }
    
    # Process T2 filters
    for master_key, api_key in t2_mappings.items():
        if master_key in MASTER_FILTERS and MASTER_FILTERS[master_key].get('enabled', False):
            f = MASTER_FILTERS[master_key]
            prop_filters[api_key] = {
                'edge_min': abs(f.get('edge_min', f.get('edge_max', 15))) / 100,
                'cv_max': f.get('cv_max', 0.45),
                'proj_min': f.get('min_proj', 0),
                'tier': 2,
            }
    
    # Process T3 filters
    for master_key, api_key in t3_mappings.items():
        if master_key in MASTER_FILTERS and MASTER_FILTERS[master_key].get('enabled', False):
            f = MASTER_FILTERS[master_key]
            prop_filters[api_key] = {
                'edge_min': abs(f.get('edge_min', f.get('edge_max', 10))) / 100,
                'cv_max': f.get('cv_max', 0.45),
                'proj_min': f.get('min_proj', 0),
                'tier': 3,
            }
    
    # Game filters - rename keys
    if 'game_moneyline' in MASTER_FILTERS and MASTER_FILTERS['game_moneyline'].get('enabled', True):
        f = MASTER_FILTERS['game_moneyline']
        vegas_filters['moneyline'] = {
            'net_min': f.get('net_diff_min', 5),
            'opp_def_min': f.get('opp_def_min', 114),
            'opp_off_max': f.get('opp_off_max', 112),
            'odds_min': f.get('odds_min', -300),
        }
    
    if 'game_under' in MASTER_FILTERS and MASTER_FILTERS['game_under'].get('enabled', True):
        f = MASTER_FILTERS['game_under']
        vegas_filters['under'] = {
            'comb_def_max': f.get('combined_def_max', 226),
            'comb_pace_max': f.get('combined_pace_max', 198),
            'book_min': f.get('book_total_min', 225),
            'book_max': f.get('book_total_max', 232),
        }
    
    if 'spread_favorite' in MASTER_FILTERS and MASTER_FILTERS['spread_favorite'].get('enabled', True):
        f = MASTER_FILTERS['spread_favorite']
        vegas_filters['spread_favorite'] = {
            'net_min': f.get('net_diff_min', 12),
            'spread_max': f.get('spread_max', 6),
            'opp_def_min': f.get('opp_def_min', 112),
        }
    
    if 'game_home_dog' in MASTER_FILTERS and MASTER_FILTERS['game_home_dog'].get('enabled', True):
        f = MASTER_FILTERS['game_home_dog']
        vegas_filters['spread_dog'] = {
            'spread_min': f.get('home_spread_min', 7),
            'opp_net_max': f.get('opp_net_max', 5),
        }
    
    return prop_filters, vegas_filters

PROP_FILTERS, VEGAS_FILTERS = _convert_filters()

NAME_TO_ABBR = {
    'Atlanta Hawks': 'ATL', 'Boston Celtics': 'BOS', 'Brooklyn Nets': 'BKN', 'Charlotte Hornets': 'CHA',
    'Chicago Bulls': 'CHI', 'Cleveland Cavaliers': 'CLE', 'Dallas Mavericks': 'DAL', 'Denver Nuggets': 'DEN',
    'Detroit Pistons': 'DET', 'Golden State Warriors': 'GSW', 'Houston Rockets': 'HOU', 'Indiana Pacers': 'IND',
    'LA Clippers': 'LAC', 'Los Angeles Lakers': 'LAL', 'Memphis Grizzlies': 'MEM', 'Miami Heat': 'MIA',
    'Milwaukee Bucks': 'MIL', 'Minnesota Timberwolves': 'MIN', 'New Orleans Pelicans': 'NOP', 'New York Knicks': 'NYK',
    'Oklahoma City Thunder': 'OKC', 'Orlando Magic': 'ORL', 'Philadelphia 76ers': 'PHI', 'Phoenix Suns': 'PHX',
    'Portland Trail Blazers': 'POR', 'Sacramento Kings': 'SAC', 'San Antonio Spurs': 'SAS', 'Toronto Raptors': 'TOR',
    'Utah Jazz': 'UTA', 'Washington Wizards': 'WAS'
}

MARKET_TO_STAT = {'player_points': 'pts', 'player_rebounds': 'reb', 'player_assists': 'ast', 'player_points_rebounds_assists': 'pra', 'player_rebounds_assists': 'ra', 'player_threes': '3pm'}

def get_eastern_date():
    eastern = pytz.timezone('US/Eastern')
    return datetime.now(eastern).date()

def calculate_kelly_grade(over_prob, odds=-110, edge=0.0):
    """
    Calculate Kelly bet sizing and grade.
    Uses fractional Kelly with conservative risk profile.
    
    Returns: (units, grade)
      - units: 0.5 to 2.0 units
      - grade: 'A+', 'A', 'B+', 'B', 'C'
    """
    kelly = get_kelly_engine()
    
    if kelly and over_prob and over_prob > 0.5:
        try:
            result = kelly.calculate_bet(over_prob, odds, 1000)  # using 1000 as bankroll reference
            kelly_pct = result.get('kelly_stake', 0.01)
            grade = result.get('grade', 'C')
            
            # Convert kelly percentage to units (0.5 to 2.0)
            if kelly_pct >= 0.04:  # 4%+ = 2 units
                units = 2.0
            elif kelly_pct >= 0.03:  # 3%+ = 1.5 units
                units = 1.5
            elif kelly_pct >= 0.02:  # 2%+ = 1 unit
                units = 1.0
            else:
                units = 0.5
            
            return units, grade
        except:
            pass
    
    # Fallback based on edge
    if edge >= 0.25:
        return 1.5, 'B+'
    elif edge >= 0.15:
        return 1.0, 'B'
    else:
        return 0.5, 'C'

def get_proj(player_games, player, stat, game_date):
    """
    FALLBACK projection using L5/L10/L15 weighted average.
    Used when PlayerPropEngine is not available or fails.
    """
    if player not in player_games:
        return None, None
    games_list = sorted([g for g in player_games[player] if g['date'] < game_date], key=lambda x: x['date'], reverse=True)
    if len(games_list) < 5:
        return None, None
    
    # Handle combined stats
    def get_stat_value(g, stat):
        if stat == 'pra':
            return g['pts'] + g['reb'] + g['ast']
        elif stat == 'ra':
            return g['reb'] + g['ast']
        elif stat == '3pm':
            return g['3pm']
        else:
            return g[stat]
    
    values = [get_stat_value(g, stat) for g in games_list[:15]]
    l5 = sum(values[:5])/5
    l10 = sum(values[:10])/min(10,len(values))
    l15 = sum(values[:15])/min(15,len(values))
    season = sum(get_stat_value(g, stat) for g in games_list) / len(games_list)
    proj = 0.40*l5 + 0.30*l10 + 0.20*l15 + 0.10*season
    std = statistics.stdev(values[:10]) if len(values) >= 10 else statistics.stdev(values[:5])
    cv = std / proj if proj > 0 else 1
    return proj, cv

def get_engine_proj(player, stat, opponent_team, line, player_games=None, game_date=None):
    """
    FULL ENGINE projection using PlayerPropEngine.
    Returns: (proj, cv, over_prob, under_prob, ev, adjustments)
    
    Uses:
    - Stat-specific distributions (Gaussian/Poisson/NegBinom)
    - Pace adjustment vs opponent
    - Defense adjustment vs opponent
    - True probability curves
    """
    engine = get_prop_engine()
    
    if engine is None:
        # Fallback to simple method
        if player_games and game_date:
            proj, cv = get_proj(player_games, player, stat, game_date)
            if proj:
                edge = (proj - line) / line if line > 0 else 0
                return {
                    'proj': proj,
                    'cv': cv,
                    'over_prob': 0.5 + (edge * 2),  # Rough estimate
                    'under_prob': 0.5 - (edge * 2),
                    'ev': edge * 100,
                    'adjustments': {'method': 'fallback'},
                    'engine_used': False
                }
        return None
    
    # Map stat types
    stat_map = {'pts': 'points', 'reb': 'rebounds', 'ast': 'assists', '3pm': 'threes', 'pra': 'pra'}
    engine_stat = stat_map.get(stat, stat)
    
    try:
        # Get full engine prediction
        edge_result = engine.find_edge(player, opponent_team, engine_stat, line)
        
        if edge_result:
            result = {
                'proj': edge_result['expected'],
                'cv': edge_result.get('std', 5) / edge_result['expected'] if edge_result['expected'] > 0 else 0.5,
                'over_prob': edge_result['over_prob'] / 100,
                'under_prob': edge_result['under_prob'] / 100,
                'over_ev': edge_result['over_ev'],
                'under_ev': edge_result['under_ev'],
                'best_bet': edge_result['best_bet'],
                'adjustments': edge_result.get('adjustments', {}),
                'engine_used': True
            }
            
            # Fix 4: Blend with recent form (L5/L10/L15)
            # Engine uses season avg — blend with recent games for recency
            if player_games and game_date:
                fallback_proj, fallback_cv = get_proj(player_games, player, stat, game_date)
                if fallback_proj:
                    # 60% engine (has pace/defense adjustments) + 40% recent form
                    blended = 0.60 * result['proj'] + 0.40 * fallback_proj
                    result['proj'] = round(blended, 1)
                    # Use the better (lower) CV
                    result['cv'] = min(result['cv'], fallback_cv) if fallback_cv else result['cv']
                    result['adjustments']['recent_form'] = round(fallback_proj, 1)
                    result['adjustments']['blend'] = '60/40'
                    
                    # Recalculate probabilities with blended projection
                    blended_edge = (blended - line) / line if line > 0 else 0
                    # Shift probabilities proportionally to the blend shift
                    if blended > edge_result['expected']:
                        # Recent form is higher → shift toward OVER
                        shift = (blended - edge_result['expected']) / (edge_result['expected'] * 0.30) * 0.10
                        result['over_prob'] = min(0.95, result['over_prob'] + shift)
                        result['under_prob'] = max(0.05, 1 - result['over_prob'])
                    elif blended < edge_result['expected']:
                        # Recent form is lower → shift toward UNDER
                        shift = (edge_result['expected'] - blended) / (edge_result['expected'] * 0.30) * 0.10
                        result['under_prob'] = min(0.95, result['under_prob'] + shift)
                        result['over_prob'] = max(0.05, 1 - result['under_prob'])
            
            return result
    except Exception as e:
        fallback_reason = f"Engine error: {str(e)[:50]}"
        print(f"   ⚠️ {fallback_reason}")
    
    # Fallback
    if player_games and game_date:
        proj, cv = get_proj(player_games, player, stat, game_date)
        if proj:
            edge = (proj - line) / line if line > 0 else 0
            return {
                'proj': proj,
                'cv': cv,
                'over_prob': 0.5 + (edge * 2),
                'under_prob': 0.5 - (edge * 2),
                'ev': edge * 100,
                'adjustments': {'method': 'fallback'},
                'engine_used': False,
                'fallback_reason': fallback_reason if 'fallback_reason' in dir() else 'Player not in engine DB'
            }
    return None


def get_todays_picks(force_refresh=False, target_date=None):
    global _picks_cache, _cache_time
    
    if target_date:
        today = target_date
    else:
        today = get_eastern_date()
    
    today_str = str(today)
    
    if not force_refresh and today_str in _picks_cache:
        if _cache_time and (datetime.now() - _cache_time).seconds < CACHE_DURATION:
            return _picks_cache[today_str]
    
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    
    # Load player boxscores
    cur.execute("""
        SELECT player_name, game_date, pts, reb, ast, fg3m, min
        FROM player_boxscores WHERE game_date >= '2024-10-01' AND game_date < %s
    """, (today,))
    player_games = defaultdict(list)
    for row in cur.fetchall():
        player, gdate, pts, reb, ast, fg3m, mins = row
        # Parse minutes (handles "39:00" format)
        min_val = 0
        if mins:
            if ':' in str(mins):
                min_val = float(str(mins).split(':')[0])
            else:
                try: min_val = float(mins)
                except: min_val = 0
        # ONLY include games with 20+ minutes (filter injury exits)
        if min_val >= 20:
            player_games[player].append({'date': gdate, 'pts': float(pts or 0), 'reb': float(reb or 0), 'ast': float(ast or 0), '3pm': float(fg3m or 0), 'min': min_val})
    
    # Load today's props with team info
    cur.execute("""
        SELECT p.player_name, p.market, p.line, p.over_odds, p.under_odds, p.home_team, p.away_team
        FROM player_props p
        WHERE p.game_date = %s AND p.sportsbook = 'DraftKings'
        AND p.market IN ('player_points', 'player_rebounds', 'player_assists', 'player_points_rebounds_assists', 'player_rebounds_assists', 'player_threes')
    """, (today,))
    props = cur.fetchall()
    
    # Build player -> opponent mapping from props (we'll figure out which team they play for)
    # Since we have home_team and away_team, we'll look up the player's team from boxscores
    player_teams = {}
    for row in props:
        player, market, line, over_odds, under_odds, home_team, away_team = row
        # We'll set this up after processing boxscores
        player_teams[player] = {'home': home_team, 'away': away_team}
    
    # Load today's games
    cur.execute("""
        SELECT g.home_team, g.visitor_team, b.total, b.home_spread, b.home_ml, b.away_ml
        FROM games g
        JOIN betting_odds b ON g.date = b.game_date AND g.home_team = b.home_team
        WHERE g.date = %s AND b.sportsbook = 'draftkings'
    """, (today,))
    games = cur.fetchall()
    
    # Load team stats from nba_team_advanced_stats
    cur.execute("""
        SELECT "TEAM_NAME", "OFF_RATING", "DEF_RATING", "NET_RATING", "PACE"
        FROM nba_team_advanced_stats
        WHERE pull_date = (SELECT MAX(pull_date) FROM nba_team_advanced_stats)
    """)
    team_stats = {}
    for row in cur.fetchall():
        name, off, def_, net, pace = row
        abbr = NAME_TO_ABBR.get(name)
        if abbr:
            team_stats[abbr] = {'off': float(off or 0), 'def': float(def_ or 0), 'net': float(net or 0), 'pace': float(pace or 0)}
    
    conn.close()
    
    # Build team -> opponent mapping from today's games
    team_opponent = {}
    for row in games:
        home, away, *_ = row
        team_opponent[home] = away  # Home team plays away team
        team_opponent[away] = home  # Away team plays home team
    
    # Get opponent for a player using the prop's home/away team info
    def get_opponent(player):
        prop_teams = player_teams.get(player, {})
        home_team = prop_teams.get('home')
        away_team = prop_teams.get('away')
        
        if not home_team or not away_team:
            return None
        
        # Look up the player's actual team from the prop engine's DB
        normalized = normalize_player_name(player)
        engine = get_prop_engine()
        if engine:
            base = engine.get_player_base(normalized)
            if base and base.get('team'):
                player_team = base['team']
                # If player is on home team, opponent is away team, and vice versa
                if player_team == home_team:
                    return away_team
                elif player_team == away_team:
                    return home_team
        
        # Fallback: return away_team (assumes player is on home team)
        return away_team
    
    # GAME PICKS
    game_picks = []
    for row in games:
        home, away, total, spread, home_ml, away_ml = row
        total = float(total) if total else None
        spread = float(spread) if spread else None
        if not total or not spread:
            continue
        home_s = team_stats.get(home, {})
        away_s = team_stats.get(away, {})
        if not home_s or not away_s:
            continue
        
        # Get injury context for this game
        injury_note = ""
        if INJURY_ENGINE_AVAILABLE:
            try:
                inj_engine = get_injury_engine()
                home_injuries = inj_engine.get_team_injury_report(home)
                away_injuries = inj_engine.get_team_injury_report(away)
                notes = []
                if home_injuries and home_injuries.get('total_spread_impact', 0) > 1:
                    notes.append(f"{home} -{home_injuries['total_spread_impact']:.1f}")
                if away_injuries and away_injuries.get('total_spread_impact', 0) > 1:
                    notes.append(f"{away} -{away_injuries['total_spread_impact']:.1f}")
                if notes:
                    injury_note = "⚠️ " + ", ".join(notes)
            except:
                pass
        
        # ML Filter (73.3% backtest) - Added odds_min check
        f = VEGAS_FILTERS['moneyline']
        odds_min = f.get('odds_min', -300)
        if home_s.get('net', 0) >= f['net_min'] and away_s.get('def', 0) >= f['opp_def_min'] and away_s.get('off', 999) <= f['opp_off_max']:
            if home_ml and home_ml >= odds_min:  # Don't bet huge favorites
                game_picks.append({'type': 'GAME', 'subtype': 'ML', 'pick': f"{home} ML", 'matchup': f"{away} @ {home}", 'odds': home_ml, 'edge': round(home_s['net'] - away_s['net'], 1), 'tier': 1, 'injury_note': injury_note})
        if away_s.get('net', 0) >= f['net_min'] and home_s.get('def', 0) >= f['opp_def_min'] and home_s.get('off', 999) <= f['opp_off_max']:
            if away_ml and away_ml >= odds_min:  # Don't bet huge favorites
                game_picks.append({'type': 'GAME', 'subtype': 'ML', 'pick': f"{away} ML", 'matchup': f"{away} @ {home}", 'odds': away_ml, 'edge': round(away_s['net'] - home_s['net'], 1), 'tier': 1, 'injury_note': injury_note})
        
        # UNDER Filter
        f = VEGAS_FILTERS['under']
        comb_def = home_s.get('def', 0) + away_s.get('def', 0)
        comb_pace = home_s.get('pace', 0) + away_s.get('pace', 0)
        if comb_def <= f['comb_def_max'] and comb_pace <= f['comb_pace_max'] and f['book_min'] <= total <= f['book_max']:
            game_picks.append({'type': 'GAME', 'subtype': 'UNDER', 'pick': f"UNDER {total}", 'matchup': f"{away} @ {home}", 'odds': -110, 'edge': round(f['comb_def_max'] - comb_def, 1), 'tier': 1})
        
        # SPREAD FAVORITE Filter (72.7% backtest) - NEW
        if 'spread_favorite' in VEGAS_FILTERS:
            f = VEGAS_FILTERS['spread_favorite']
            net_diff = home_s.get('net', 0) - away_s.get('net', 0)
            # Home team is favorite (spread < 0)
            if spread and spread < 0 and abs(spread) <= f['spread_max']:
                if net_diff >= f['net_min'] and away_s.get('def', 0) >= f['opp_def_min']:
                    game_picks.append({'type': 'GAME', 'subtype': 'SPREAD', 'pick': f"{home} {spread}", 'matchup': f"{away} @ {home}", 'odds': -110, 'edge': round(net_diff, 1)})
            # Away team is favorite (spread > 0 means home is dog)
            elif spread and spread > 0:
                net_diff_away = away_s.get('net', 0) - home_s.get('net', 0)
                if spread <= f['spread_max'] and net_diff_away >= f['net_min'] and home_s.get('def', 0) >= f['opp_def_min']:
                    game_picks.append({'type': 'GAME', 'subtype': 'SPREAD', 'pick': f"{away} -{spread}", 'matchup': f"{away} @ {home}", 'odds': -110, 'edge': round(net_diff_away, 1)})
        
        # SPREAD HOME DOG Filter (75% backtest) - HOME DOGS ONLY
        f = VEGAS_FILTERS['spread_dog']
        # Only bet HOME underdogs (spread > 0 means home is getting points)
        if spread and spread > 0 and spread >= f['spread_min']:
            if away_s.get('net', 0) <= f['opp_net_max']:
                game_picks.append({'type': 'GAME', 'subtype': 'SPREAD', 'pick': f"{home} +{spread}", 'matchup': f"{away} @ {home}", 'odds': -110, 'edge': round(spread, 1), 'tier': 1})
    
    # PROP PICKS
    official_props = []
    watchlist_props = []
    engine_used_count = 0
    fallback_count = 0
    
    for row in props:
        player, market, line, over_odds, under_odds, home_team, away_team = row
        stat = MARKET_TO_STAT.get(market)
        if not stat:
            continue
        line = float(line)
        if line == 0:
            continue
        
        # Try engine-based projection first (with opponent adjustments)
        opponent = get_opponent(player)
        engine_result = None
        
        # Normalize player name to handle Jr/Jr., nicknames, etc.
        normalized_player = normalize_player_name(player)
        
        if opponent and PROP_ENGINE_AVAILABLE:
            engine_result = get_engine_proj(normalized_player, stat, opponent, line, player_games, today)
        
        if engine_result and engine_result.get('engine_used'):
            # Fix 6: Home/away adjustment
            prop_info = player_teams.get(player, {})
            engine = get_prop_engine()
            if engine:
                base = engine.get_player_base(normalized_player)
                if base and base.get('team'):
                    is_home = (base['team'] == prop_info.get('home'))
                    ha_factor = 1.015 if is_home else 0.985
                    engine_result['proj'] = round(engine_result['proj'] * ha_factor, 1)
            
            # Fix 7: Injury boost when opponent is missing key players
            if opponent and INJURY_ENGINE_AVAILABLE:
                try:
                    inj_engine = get_injury_engine()
                    opp_injuries = inj_engine.get_team_injury_report(opponent)
                    if opp_injuries and opp_injuries.get('total_spread_impact', 0) > 2:
                        # Opponent weakened → boost player projection slightly
                        injury_boost = 1 + (opp_injuries['total_spread_impact'] * 0.005)
                        engine_result['proj'] = round(engine_result['proj'] * injury_boost, 1)
                except:
                    pass
            
            # Use engine projection
            proj = engine_result['proj']
            cv = engine_result['cv']
            over_prob = engine_result.get('over_prob', 0.5)
            under_prob = engine_result.get('under_prob', 0.5)
            adjustments = engine_result.get('adjustments', {})
            engine_used_count += 1
        else:
            # Fallback - SKIP this prop (only push full-engine props)
            fallback_count += 1
            continue  # Don't add fallback props to official picks
        
        # OVER - Check all tiers (T1, T2, T3)
        edge = (proj - line) / line
        over_added = False
        for tier_suffix, tier_num in [('', 1), ('_t2', 2), ('_t3', 3)]:
            fkey = f"{stat}_over{tier_suffix}"
            if fkey in PROP_FILTERS and not over_added:
                f = PROP_FILTERS[fkey]
                e_pass = edge >= f['edge_min']
                c_pass = cv <= f['cv_max']
                p_pass = proj >= f['proj_min']
                if e_pass and c_pass and p_pass:
                    tier = f.get('tier', tier_num)
                    # Unit sizing by tier: T1=1.5u, T2=1.0u, T3=0.5u
                    tier_units = {1: 1.5, 2: 1.0, 3: 0.5}
                    units, grade = calculate_kelly_grade(over_prob, over_odds or -110, edge)
                    units = min(units, tier_units.get(tier, 1.0))
                    official_props.append({
                        'type': 'PROP', 'player': player, 
                        'pick': f"{stat.upper()} OVER {line}", 
                        'projection': round(proj, 1), 
                        'edge': round(edge * 100, 1), 
                        'cv': round(cv, 2), 
                        'odds': over_odds or -110, 
                        'tier': tier,
                        'units': units,
                        'grade': grade
                    })
                    over_added = True
                    break
        
        # OVER watchlist (T1 near-misses only)
        if not over_added:
            fkey = f"{stat}_over"
            if fkey in PROP_FILTERS:
                f = PROP_FILTERS[fkey]
                e_pass = edge >= f['edge_min']
                c_pass = cv <= f['cv_max']
                p_pass = proj >= f['proj_min']
                if sum([e_pass, c_pass, p_pass]) == 2:
                    near, reason = False, ""
                    if not e_pass and edge >= (f['edge_min'] - 0.03):
                        near, reason = True, f"Edge {edge*100:.1f}%"
                    elif not c_pass and cv <= (f['cv_max'] + 0.05):
                        near, reason = True, f"CV {cv:.2f}"
                    elif not p_pass and proj >= (f['proj_min'] - 2):
                        near, reason = True, f"Proj {proj:.1f}"
                    if near:
                        watchlist_props.append({'type': 'PROP', 'player': player, 'pick': f"{stat.upper()} OVER {line}", 'projection': round(proj, 1), 'edge': round(edge * 100, 1), 'cv': round(cv, 2), 'near_miss': reason})
        
        # UNDER - Check all tiers (T1, T2, T3)
        edge_u = (line - proj) / line
        under_added = False
        for tier_suffix, tier_num in [('', 1), ('_t2', 2), ('_t3', 3)]:
            fkey = f"{stat}_under{tier_suffix}"
            if fkey in PROP_FILTERS and not under_added:
                f = PROP_FILTERS[fkey]
                e_pass = edge_u >= f.get('edge_min', 0.15)
                c_pass = cv <= f['cv_max']
                p_pass = proj >= f['proj_min']
                if e_pass and c_pass and p_pass:
                    tier = f.get('tier', tier_num)
                    tier_units = {1: 1.5, 2: 1.0, 3: 0.5}
                    units, grade = calculate_kelly_grade(under_prob, under_odds or -110, edge_u)
                    units = min(units, tier_units.get(tier, 1.0))
                    official_props.append({
                        'type': 'PROP', 'player': player, 
                        'pick': f"{stat.upper()} UNDER {line}", 
                        'projection': round(proj, 1), 
                        'edge': round(edge_u * 100, 1), 
                        'cv': round(cv, 2), 
                        'odds': under_odds or -110, 
                        'tier': tier,
                        'units': units,
                        'grade': grade
                    })
                    under_added = True
                    break
        
        # UNDER watchlist (T1 near-misses only)
        if not under_added:
            fkey = f"{stat}_under"
            if fkey in PROP_FILTERS:
                f = PROP_FILTERS[fkey]
                e_pass = edge_u >= f.get('edge_min', 0.15)
                c_pass = cv <= f['cv_max']
                p_pass = proj >= f['proj_min']
                if sum([e_pass, c_pass, p_pass]) == 2:
                    near, reason = False, ""
                    if not e_pass and edge_u >= (f['edge_min'] - 0.03):
                        near, reason = True, f"Edge {edge_u*100:.1f}%"
                    elif not c_pass and cv <= (f['cv_max'] + 0.05):
                        near, reason = True, f"CV {cv:.2f}"
                    elif not p_pass and proj >= (f['proj_min'] - 2):
                        near, reason = True, f"Proj {proj:.1f}"
                    if near:
                        watchlist_props.append({'type': 'PROP', 'player': player, 'pick': f"{stat.upper()} UNDER {line}", 'projection': round(proj, 1), 'edge': round(edge_u * 100, 1), 'cv': round(cv, 2), 'near_miss': reason})
    
    watchlist_props.sort(key=lambda x: -abs(x['edge']))
    
    # Fix 3: XGBoost Gatekeeper — kill low-quality T3 picks
    try:
        from engines.xgboost_gatekeeper import XGBoostGatekeeper
        gatekeeper = XGBoostGatekeeper()
        if gatekeeper.is_loaded:
            pre_gate = len(official_props)
            official_props = gatekeeper.gate_picks(official_props, tier=3)
            killed = pre_gate - len(official_props)
            if killed > 0:
                print(f"   🛡️ XGBoost gatekeeper killed {killed} picks")
    except Exception as e:
        print(f"   ⚠️ XGBoost gatekeeper unavailable: {e}")
    
    result = {
        'date': today_str,
        'game_picks': game_picks,
        'prop_picks': official_props,
        'watchlist_props': watchlist_props[:7],
        'summary': {
            'games': len(game_picks), 
            'props': len(official_props), 
            'watchlist': len(watchlist_props),
            'engine_used': engine_used_count,
            'fallback_used': fallback_count,
            'engine_available': PROP_ENGINE_AVAILABLE,
        }
    }
    
    # Send health alert if engine issues detected
    total_props = engine_used_count + fallback_count
    if not PROP_ENGINE_AVAILABLE:
        send_health_alert("❌ **PlayerPropEngine OFFLINE**\n\nAll props using L5/L10/L15 fallback.\nPace/defense adjustments NOT applied.", "error")
    elif total_props > 0 and fallback_count > total_props * 0.3:
        pct = round(fallback_count / total_props * 100)
        send_health_alert(f"⚠️ **High Fallback Rate: {pct}%**\n\n• Engine: {engine_used_count} props\n• Fallback: {fallback_count} props\n\nSome players missing from engine DB.", "warning")
    
    _picks_cache[today_str] = result
    _cache_time = datetime.now()
    
    return result

def get_game_picks():
    return get_todays_picks().get('game_picks', [])

def get_prop_picks():
    return get_todays_picks().get('prop_picks', [])

def get_watchlist_picks():
    return get_todays_picks().get('watchlist_props', [])

if __name__ == "__main__":
    picks = get_todays_picks(force_refresh=True)
    
    print("=" * 70)
    print(f"🔥 OFFICIAL PICKS - {picks['date']}")
    print("=" * 70)
    
    print("\n🏀 GAMES (1u each)")
    print("-" * 70)
    for p in picks['game_picks']:
        print(f"  • {p['pick']} | {p['matchup']}")
    
    print("\n🎯 PROPS (1u each)")
    print("-" * 70)
    for p in picks['prop_picks']:
        print(f"  • {p['player']} {p['pick']}")
        print(f"    Proj: {p['projection']} | Edge: +{p['edge']}% | CV: {p['cv']}")
    
    print("\n👀 WATCHLIST (0.5u max)")
    print("-" * 70)
    for p in picks['watchlist_props'][:5]:
        print(f"  • {p['player']} {p['pick']} | Edge: {p['edge']}% | ⚠️ {p['near_miss']}")
    
    print("\n" + "=" * 70)
    print(f"Total: {picks['summary']['games']} games + {picks['summary']['props']} props")
    print("=" * 70)
