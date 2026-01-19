"""
fast_loader.py - Speed Layer for SB-ALGO
=========================================
Uses time-based caching to keep data fresh while staying fast.

UPDATED: Now uses sb_algo_api for game and prop edges (new engine)
"""

import functools
import os
import time
import pandas as pd
from sqlalchemy import create_engine, text
from datetime import datetime, timedelta
import pytz

# Cache expiration time (in seconds)
CACHE_TTL = 3600  # 1 hour

# Simple time-based cache storage
_cache = {}
_cache_times = {}

def get_engine():
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        # Fallback for local development
        database_url = "postgresql://sb_algo_db_user:0HDtYp4EY2Lo5At8iyf44PD1zDioSPK7@dpg-d495uhchg0os738l1a50-a.virginia-postgres.render.com/sb_algo_db"
    return create_engine(database_url, pool_pre_ping=True, pool_recycle=300)

def get_eastern_date():
    eastern = pytz.timezone('US/Eastern')
    return datetime.now(eastern).strftime('%Y-%m-%d')

def get_eastern_datetime():
    eastern = pytz.timezone('US/Eastern')
    return datetime.now(eastern)

def _is_cache_valid(key):
    """Check if cache entry is still valid"""
    if key not in _cache_times:
        return False
    # Also invalidate if the date changed
    cached_date = _cache.get(f"{key}_date")
    current_date = get_eastern_date()
    if cached_date != current_date:
        return False
    return (time.time() - _cache_times[key]) < CACHE_TTL

def _get_cached(key):
    """Get cached value if valid"""
    if _is_cache_valid(key):
        return _cache.get(key)
    return None

def _set_cached(key, value):
    """Set cache with timestamp"""
    _cache[key] = value
    _cache[f"{key}_date"] = get_eastern_date()
    _cache_times[key] = time.time()

def load_todays_games():
    """Load today's games with time-based cache"""
    cache_key = "todays_games"
    cached = _get_cached(cache_key)
    if cached is not None:
        return cached
    
    engine = get_engine()
    today = get_eastern_date()
    query = text("""
        SELECT date, home_team, visitor_team, home_pts, visitor_pts,
            start_time, home_win, home_days_rest, visitor_days_rest,
            home_is_b2b, visitor_is_b2b, season_avg_total, total_points,
            current_home_score, current_away_score, quarter, time_remaining, game_status
        FROM games WHERE date = :today ORDER BY start_time
    """)
    with engine.connect() as conn:
        result = conn.execute(query, {"today": today})
        games = []
        for row in result:
            games.append({
                'date': row[0], 'home_team': row[1], 'visitor_team': row[2],
                'home_pts': row[3], 'visitor_pts': row[4], 'start_time': row[5] or 'TBD',
                'home_win': row[6], 'home_days_rest': row[7] or 0, 'visitor_days_rest': row[8] or 0,
                'home_is_b2b': row[9] or False, 'visitor_is_b2b': row[10] or False,
                'season_avg_total': row[11] or 220, 'total_points': row[12],
                'current_home_score': row[13] or 0, 'current_away_score': row[14] or 0,
                'quarter': row[15] or '', 'time_remaining': row[16] or '', 'game_status': row[17] or 'Scheduled'
            })
        _set_cached(cache_key, games)
        return games

def load_todays_odds():
    """Load today's odds with time-based cache"""
    cache_key = "todays_odds"
    cached = _get_cached(cache_key)
    if cached is not None:
        return cached
    
    engine = get_engine()
    today = get_eastern_date()
    query = text("""
        SELECT home_team, away_team, home_spread, total, home_ml, away_ml, sportsbook
        FROM betting_odds WHERE game_date = :today ORDER BY updated_at DESC
    """)
    odds_map = {}
    with engine.connect() as conn:
        result = conn.execute(query, {"today": today})
        for row in result:
            key = (row[0], row[1])
            if key not in odds_map:
                odds_map[key] = {'home_spread': row[2], 'total': row[3], 'home_ml': row[4], 'away_ml': row[5], 'sportsbook': row[6]}
    _set_cached(cache_key, odds_map)
    return odds_map

def load_injuries():
    """Load injuries with time-based cache"""
    cache_key = "injuries"
    cached = _get_cached(cache_key)
    if cached is not None:
        return cached
    
    engine = get_engine()
    query = text("SELECT player_name, team_name, status, description FROM injuries LIMIT 150")
    with engine.connect() as conn:
        result = conn.execute(query)
        injuries = [{'player_name': row[0], 'team': row[1], 'status': row[2], 'description': row[3]} for row in result]
    _set_cached(cache_key, injuries)
    return injuries

def load_dashboard_metrics():
    """Load dashboard metrics with time-based cache"""
    cache_key = "dashboard_metrics"
    cached = _get_cached(cache_key)
    if cached is not None:
        return cached
    
    engine = get_engine()
    today = get_eastern_date()
    metrics = {
        'games_today': 0, 
        'active_injuries': 0, 
        'edges_found': 0, 
        'system_confidence': 75, 
        'best_play': 'See Games Tab', 
        'best_play_conf': 0
    }
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM games WHERE date = :today"), {"today": today}).fetchone()
            metrics['games_today'] = result[0] if result else 0
            result = conn.execute(text("SELECT COUNT(*) FROM injuries")).fetchone()
            metrics['active_injuries'] = result[0] if result else 0
            metrics['edges_found'] = metrics['games_today']
    except Exception as e:
        print(f"Metrics error: {e}")
    _set_cached(cache_key, metrics)
    return metrics

def get_team_record(team: str, days: int = 30):
    """Get team record - cached per team"""
    cache_key = f"team_record_{team}_{days}"
    cached = _get_cached(cache_key)
    if cached is not None:
        return cached
    
    engine = get_engine()
    today = get_eastern_date()
    start_date = (datetime.strptime(today, '%Y-%m-%d') - timedelta(days=days)).strftime('%Y-%m-%d')
    query = text("""
        SELECT SUM(CASE WHEN (home_team = :team AND home_win = 1) OR (visitor_team = :team AND home_win = 0) THEN 1 ELSE 0 END) as wins,
               SUM(CASE WHEN (home_team = :team AND home_win = 0) OR (visitor_team = :team AND home_win = 1) THEN 1 ELSE 0 END) as losses,
               SUM(CASE WHEN home_team = :team AND home_win = 1 THEN 1 ELSE 0 END) as home_wins,
               SUM(CASE WHEN home_team = :team AND home_win = 0 THEN 1 ELSE 0 END) as home_losses,
               SUM(CASE WHEN visitor_team = :team AND home_win = 0 THEN 1 ELSE 0 END) as away_wins,
               SUM(CASE WHEN visitor_team = :team AND home_win = 1 THEN 1 ELSE 0 END) as away_losses
        FROM games WHERE date >= :start_date AND date < :today AND (home_team = :team OR visitor_team = :team) AND home_win IS NOT NULL
    """)
    with engine.connect() as conn:
        result = conn.execute(query, {"team": team, "start_date": start_date, "today": today}).fetchone()
        if result and result[0] is not None:
            record = {'wins': int(result[0] or 0), 'losses': int(result[1] or 0), 
                    'home_record': f"{int(result[2] or 0)}-{int(result[3] or 0)}", 
                    'away_record': f"{int(result[4] or 0)}-{int(result[5] or 0)}"}
            _set_cached(cache_key, record)
            return record
    default = {'wins': 0, 'losses': 0, 'home_record': '0-0', 'away_record': '0-0'}
    _set_cached(cache_key, default)
    return default

def get_hot_teams(limit: int = 5):
    """Get hot teams with time-based cache"""
    cache_key = f"hot_teams_{limit}"
    cached = _get_cached(cache_key)
    if cached is not None:
        return cached
    
    engine = get_engine()
    today = get_eastern_date()
    start_date = (datetime.strptime(today, '%Y-%m-%d') - timedelta(days=30)).strftime('%Y-%m-%d')
    query = text("""
        WITH team_games AS (
            SELECT home_team as team, CASE WHEN home_win = 1 THEN 1 ELSE 0 END as win, home_pts - visitor_pts as margin
            FROM games WHERE date >= :start_date AND date < :today AND home_win IS NOT NULL
            UNION ALL
            SELECT visitor_team as team, CASE WHEN home_win = 0 THEN 1 ELSE 0 END as win, visitor_pts - home_pts as margin
            FROM games WHERE date >= :start_date AND date < :today AND home_win IS NOT NULL
        )
        SELECT team, SUM(win) as wins, COUNT(*) - SUM(win) as losses,
               ROUND((100.0 * SUM(win) / COUNT(*))::numeric, 1) as win_pct, ROUND(AVG(margin)::numeric, 1) as avg_margin
        FROM team_games GROUP BY team HAVING COUNT(*) >= 5 ORDER BY win_pct DESC, avg_margin DESC LIMIT :limit
    """)
    with engine.connect() as conn:
        df = pd.read_sql(query, conn, params={"start_date": start_date, "today": today, "limit": limit})
        _set_cached(cache_key, df)
        return df

def get_cold_teams(limit: int = 5):
    """Get cold teams with time-based cache"""
    cache_key = f"cold_teams_{limit}"
    cached = _get_cached(cache_key)
    if cached is not None:
        return cached
    
    engine = get_engine()
    today = get_eastern_date()
    start_date = (datetime.strptime(today, '%Y-%m-%d') - timedelta(days=30)).strftime('%Y-%m-%d')
    query = text("""
        WITH team_games AS (
            SELECT home_team as team, CASE WHEN home_win = 1 THEN 1 ELSE 0 END as win, home_pts - visitor_pts as margin
            FROM games WHERE date >= :start_date AND date < :today AND home_win IS NOT NULL
            UNION ALL
            SELECT visitor_team as team, CASE WHEN home_win = 0 THEN 1 ELSE 0 END as win, visitor_pts - home_pts as margin
            FROM games WHERE date >= :start_date AND date < :today AND home_win IS NOT NULL
        )
        SELECT team, SUM(win) as wins, COUNT(*) - SUM(win) as losses,
               ROUND((100.0 * SUM(win) / COUNT(*))::numeric, 1) as win_pct, ROUND(AVG(margin)::numeric, 1) as avg_margin
        FROM team_games GROUP BY team HAVING COUNT(*) >= 5 ORDER BY win_pct ASC, avg_margin ASC LIMIT :limit
    """)
    with engine.connect() as conn:
        df = pd.read_sql(query, conn, params={"start_date": start_date, "today": today, "limit": limit})
        _set_cached(cache_key, df)
        return df

def get_player_last_n_games(player_name: str, n: int = 20):
    """Get player stats with time-based cache"""
    cache_key = f"player_stats_{player_name}_{n}"
    cached = _get_cached(cache_key)
    if cached is not None:
        return cached
    
    engine = get_engine()
    query = text("""
        SELECT game_date, pts, reb, ast, stl, blk, fg3m, min, team_abbreviation
        FROM player_boxscores WHERE player_name = :player ORDER BY game_date DESC LIMIT :n
    """)
    with engine.connect() as conn:
        df = pd.read_sql(query, conn, params={"player": player_name, "n": n})
        _set_cached(cache_key, df)
        return df

def clear_all_caches():
    """Clear all caches"""
    global _cache, _cache_times
    _cache = {}
    _cache_times = {}
    print("All caches cleared")


# =============================================================================
# NEW ENGINE INTEGRATION - Uses sb_algo_api instead of algo_brain
# =============================================================================

def load_game_edges():
    """Load game edges using NEW SB-ALGO ENGINE"""
    cache_key = "game_edges"
    cached = _get_cached(cache_key)
    if cached is not None:
        return cached
    
    try:
        # Try new engine first
        from sb_algo_api import get_todays_picks
        algo_data = get_todays_picks()
        
        # Convert to old format for compatibility with premium_dashboard
        edges = []
        for pick in algo_data.get('game_picks', []):
            # Determine subtype from pick string
            pick_str = pick.get('pick', '')
            if 'UNDER' in pick_str or 'OVER' in pick_str:
                subtype = 'TOTAL'
            elif '+' in pick_str or '-' in pick_str:
                subtype = 'SPREAD'
            else:
                subtype = 'ML'
            
            edge_val = float(str(pick.get('edge', '0')).replace('+', '').replace('%', ''))
            conf_val = float(str(pick.get('confidence', '50')).replace('%', ''))
            
            edges.append({
                'type': 'GAME',
                'subtype': subtype,
                'game': pick.get('game_id', pick.get('matchup', '')),
                'pick': pick_str,
                'edge': edge_val,
                'confidence': conf_val,
                'start_time': 'TBD',
                'game_date': get_eastern_date(),
                'line': 0,
                'predicted': 0,
                'ev': pick.get('ev', '0%'),
                'grade': pick.get('grade', 'N/A'),
                'stake': pick.get('stake', '$0'),
            })
        
        _set_cached(cache_key, edges)
        return edges
        
    except Exception as e:
        import traceback
        print(f"NEW ENGINE Error, falling back to algo_brain: {e}")
        traceback.print_exc()
        
        # Fallback to old engine
        try:
            from algo_brain import analyze_games
            edges = analyze_games()
            _set_cached(cache_key, edges)
            return edges
        except Exception as e2:
            print(f"FALLBACK also failed: {e2}")
            return []


def load_prop_edges():
    """Load prop edges using NEW SB-ALGO ENGINE"""
    cache_key = "prop_edges"
    cached = _get_cached(cache_key)
    if cached is not None:
        return cached
    
    try:
        # Try new engine first
        from sb_algo_api import get_todays_picks
        algo_data = get_todays_picks()
        
        # Convert to old format for compatibility with premium_dashboard
        edges = []
        for pick in algo_data.get('prop_picks', []):
            hit_rate = pick.get('hit_rate', '0%')
            if isinstance(hit_rate, str):
                hit_rate_val = float(hit_rate.replace('%', ''))
            else:
                hit_rate_val = float(hit_rate) * 100
            
            edge_str = pick.get('edge', '0%')
            if isinstance(edge_str, str):
                edge_val = float(edge_str.replace('+', '').replace('%', ''))
            else:
                edge_val = float(edge_str)
            
            # Parse prop type from prop string (e.g., "REB UNDER 5.5" -> "rebounds")
            prop_str = pick.get('prop', '')
            if 'PTS' in prop_str.upper():
                prop_type = 'points'
            elif 'REB' in prop_str.upper():
                prop_type = 'rebounds'
            elif 'AST' in prop_str.upper():
                prop_type = 'assists'
            elif '3P' in prop_str.upper() or 'THREE' in prop_str.upper():
                prop_type = 'threes'
            else:
                prop_type = 'points'
            
            edges.append({
                'type': 'PROP',
                'subtype': prop_type,  # Added subtype
                'player': pick.get('player', ''),
                'prop_type': prop_type,
                'pick': f"{pick.get('player', '')} {pick.get('prop', '')}",
                'line': pick.get('line', 0),
                'projection': pick.get('model', 0),
                'edge': edge_val,
                'confidence': hit_rate_val,
                'hit_rate': hit_rate,
                'ev': pick.get('ev', '0%'),
                'grade': pick.get('grade', 'N/A'),
            })
        
        _set_cached(cache_key, edges)
        return edges
        
    except Exception as e:
        import traceback
        print(f"NEW ENGINE Error for props, falling back to algo_brain: {e}")
        traceback.print_exc()
        
        # Fallback to old engine
        try:
            from algo_brain import analyze_props
            edges = analyze_props()
            _set_cached(cache_key, edges)
            return edges
        except Exception as e2:
            print(f"FALLBACK also failed: {e2}")
            return []


def get_all_edges():
    """Get all edges using NEW ENGINE"""
    return load_game_edges(), load_prop_edges()


def get_all_edges_relaxed():
    """Get ALL edges with relaxed filters for dashboard view"""
    return load_game_edges_relaxed(), load_prop_edges_relaxed()


def load_game_edges_relaxed():
    """Load game edges with RELAXED filters (for dashboard only)"""
    cache_key = "game_edges_relaxed"
    cached = _get_cached(cache_key)
    if cached is not None:
        return cached
    
    try:
        from sb_algo_api import SBAlgoAPI
        api = SBAlgoAPI()
        algo_data = api.get_all_picks_unfiltered()
        
        edges = []
        for pick in algo_data.get('game_picks', []):
            pick_str = pick.get('pick', '')
            if 'UNDER' in pick_str or 'OVER' in pick_str:
                subtype = 'TOTAL'
            elif '+' in pick_str or '-' in pick_str:
                subtype = 'SPREAD'
            else:
                subtype = 'ML'
            
            edge_val = float(str(pick.get('edge', '0')).replace('+', '').replace('%', ''))
            conf_val = float(str(pick.get('confidence', pick.get('calibrated_prob', 0.5) * 100)).replace('%', ''))
            
            # Relaxed filter: edge >= 15% (vs 30% for Discord)
            if edge_val >= 15:
                # Mark as OFFICIAL if passes strict filters (30% edge, 55% confidence)
                is_official = edge_val >= 30 and conf_val >= 55
                edges.append({
                    'type': 'GAME',
                    'subtype': subtype,
                    'game': pick.get('game_id', pick.get('game', pick.get('matchup', ''))),
                    'pick': pick_str,
                    'edge': edge_val,
                    'confidence': conf_val,
                    'start_time': 'TBD',
                    'game_date': get_eastern_date(),
                    'ev': pick.get('ev_pct', 0),
                    'grade': pick.get('grade', 'N/A'),
                    'stake': pick.get('stake', 0),
                    'is_official': is_official,
                    'tier': '🔥 OFFICIAL' if is_official else '📊 WATCHLIST',
                })
        
        # Sort by edge descending
        edges.sort(key=lambda x: x['edge'], reverse=True)
        _set_cached(cache_key, edges[:10])  # Top 10
        return edges[:10]
        
    except Exception as e:
        print(f"Relaxed game edges error: {e}")
        return []


def load_prop_edges_relaxed():
    """Load prop edges with RELAXED filters (for dashboard only)"""
    cache_key = "prop_edges_relaxed"
    cached = _get_cached(cache_key)
    if cached is not None:
        return cached
    
    try:
        from sb_algo_api import SBAlgoAPI
        api = SBAlgoAPI()
        algo_data = api.get_all_picks_unfiltered()
        
        edges = []
        for pick in algo_data.get('prop_picks', []):
            edge_val = float(str(pick.get('edge_pct', pick.get('edge', '0'))).replace('+', '').replace('%', ''))
            
            # Relaxed filter: edge >= 20% (vs 30% for Discord)
            if edge_val >= 20:
                hit_rate = pick.get('filters', {}).get('hit_rate', {}).get('hit_rate', 0) * 100
                # Mark as OFFICIAL if passes strict filters (30% edge, 60% hit rate)
                is_official = edge_val >= 30 and hit_rate >= 60
                edges.append({
                    'type': 'PROP',
                    'subtype': pick.get('stat', 'pts'),
                    'player': pick.get('player', 'Unknown'),
                    'pick': f"{pick.get('stat', 'pts').upper()} {pick.get('best_side', 'OVER')} {pick.get('book_line', 0)}",
                    'edge': edge_val,
                    'hit_rate': hit_rate,
                    'projection': pick.get('projection', {}).get('weighted', 0),
                    'ev': pick.get('ev_pct', 0),
                    'grade': pick.get('grade', 'N/A'),
                    'is_official': is_official,
                    'tier': '🔥 OFFICIAL' if is_official else '📊 WATCHLIST',
                })
        
        # Sort by edge descending
        edges.sort(key=lambda x: x['edge'], reverse=True)
        _set_cached(cache_key, edges[:10])  # Top 10
        return edges[:10]
        
    except Exception as e:
        print(f"Relaxed prop edges error: {e}")
        return []
