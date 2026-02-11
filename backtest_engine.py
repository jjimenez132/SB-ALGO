#!/usr/bin/env python3
"""
================================================================================
BACKTEST ENGINE v1.0 — Professional Historical Simulation
================================================================================
Simulates the SB-ALGO prop engine against historical data.
For each day: loads props, runs projections, applies filters, grades vs actuals.

Zero look-ahead bias: only uses data available BEFORE each simulated day.
================================================================================
"""

import os
import numpy as np
import pandas as pd
from datetime import date, timedelta, datetime
from collections import defaultdict
from sqlalchemy import create_engine, text
from scipy import stats
import statistics
import traceback

DATABASE_URL = os.environ.get('DATABASE_URL',
    "postgresql://sb_algo_db_user:0HDtYp4EY2Lo5At8iyf44PD1zDioSPK7@dpg-d495uhchg0os738l1a50-a.virginia-postgres.render.com/sb_algo_db")

# ============================================================
# STAT CV (same as player_prop_engine.py)
# ============================================================
STAT_CV = {
    'points': 0.30,
    'rebounds': 0.35,
    'assists': 0.40,
    'threes': 0.55,
}

MARKET_TO_STAT = {
    'player_points': 'pts',
    'player_rebounds': 'reb',
    'player_assists': 'ast',
    'player_threes': '3pm',
}

STAT_TO_ENGINE = {
    'pts': 'points',
    'reb': 'rebounds',
    'ast': 'assists',
    '3pm': 'threes',
}

STAT_TO_BOX = {
    'pts': 'pts',
    'reb': 'reb',
    'ast': 'ast',
    '3pm': 'fg3m',
}

LEAGUE_AVG = {
    'points': 114, 'rebounds': 44, 'assists': 26,
    'threes_pct': 0.36,
}

LEAGUE_AVG_PACE = 99.5

# ============================================================
# DEFAULT FILTERS (matches current VEGAS_FILTERS config)
# ============================================================
def get_default_filters():
    """Return the current production filter configuration."""
    return {
        # T1 ELITE (1.5 units)
        'pts_under':     {'edge_min': 0.15, 'cv_max': 0.40, 'proj_min': 20, 'tier': 1},
        'reb_over':      {'edge_min': 0.25, 'cv_max': 0.30, 'proj_min': 8,  'tier': 1},
        'reb_under':     {'edge_min': 0.20, 'cv_max': 0.35, 'proj_min': 5,  'tier': 1},
        'ast_under':     {'edge_min': 0.15, 'cv_max': 0.35, 'proj_min': 5,  'tier': 1},
        '3pm_under':     {'edge_min': 0.25, 'cv_max': 0.50, 'proj_min': 1,  'tier': 1},
        # T2 STRONG (1.0 units)
        'pts_under_t2':  {'edge_min': 0.15, 'cv_max': 0.35, 'proj_min': 18, 'tier': 2},
        'reb_under_t2':  {'edge_min': 0.20, 'cv_max': 0.45, 'proj_min': 5,  'tier': 2},
        'ast_over_t2':   {'edge_min': 0.30, 'cv_max': 0.30, 'proj_min': 8,  'tier': 2},
        'ast_under_t2':  {'edge_min': 0.10, 'cv_max': 0.35, 'proj_min': 5,  'tier': 2},
        # T3 VOLUME (0.5 units)
        'pts_under_t3':  {'edge_min': 0.10, 'cv_max': 0.40, 'proj_min': 20, 'tier': 3},
        'reb_under_t3':  {'edge_min': 0.20, 'cv_max': 0.45, 'proj_min': 5,  'tier': 3},
        'ast_under_t3':  {'edge_min': 0.10, 'cv_max': 0.45, 'proj_min': 6,  'tier': 3},
        'pts_over_t3':   {'edge_min': 0.25, 'cv_max': 0.55, 'proj_min': 12, 'tier': 3},
        'reb_over_t3':   {'edge_min': 0.25, 'cv_max': 0.30, 'proj_min': 8,  'tier': 3},
        'ast_over_t3':   {'edge_min': 0.30, 'cv_max': 0.55, 'proj_min': 6,  'tier': 3},
        '3pm_under_t3':  {'edge_min': 0.10, 'cv_max': 0.50, 'proj_min': 1,  'tier': 3},
    }


# ============================================================
# PROJECTION FUNCTIONS (self-contained, no engine import needed)
# ============================================================

def get_l5_l10_projection(games, stat):
    """L5/L10/L15 weighted projection from boxscores."""
    if len(games) < 5:
        return None, None
    
    def get_val(g, stat):
        return g.get(stat, 0)
    
    values = [get_val(g, stat) for g in games[:15]]
    l5 = sum(values[:5]) / 5
    l10 = sum(values[:min(10, len(values))]) / min(10, len(values))
    l15 = sum(values[:min(15, len(values))]) / min(15, len(values))
    season = sum(values) / len(values)
    
    proj = 0.40 * l5 + 0.30 * l10 + 0.20 * l15 + 0.10 * season
    std = statistics.stdev(values[:min(10, len(values))]) if len(values) >= 3 else 1.0
    cv = std / proj if proj > 0 else 1.0
    return proj, cv


def get_engine_projection(season_avg, pace_factor, def_factor, stat_type,
                          recent_proj=None, line=0):
    """
    Calculate projection using the same logic as PlayerPropEngine.
    Blends season-based engine projection with recent form.
    """
    # Season-based adjusted projection
    engine_proj = season_avg * pace_factor * def_factor
    
    # Blend with recent form (60/40)
    if recent_proj and recent_proj > 0:
        blended = 0.60 * engine_proj + 0.40 * recent_proj
    else:
        blended = engine_proj
    
    # Get CV
    cv_base = STAT_CV.get(stat_type, 0.35)
    
    # Calculate over/under probabilities
    if stat_type == 'points':
        # Gaussian
        std = blended * cv_base
        dist = stats.norm(loc=blended, scale=max(std, 0.1))
        over_prob = 1 - dist.cdf(line) if line > 0 else 0.5
    elif stat_type == 'assists' or stat_type == 'threes':
        # Poisson
        dist = stats.poisson(mu=max(0.1, blended))
        over_prob = dist.sf(line - 0.5) if line > 0 else 0.5
    elif stat_type == 'rebounds':
        # Negative Binomial
        variance = (blended * cv_base)**2 + blended
        if variance > blended and blended > 0:
            r = blended**2 / (variance - blended)
            p = blended / variance
            dist = stats.nbinom(n=max(1, r), p=max(0.01, min(0.99, p)))
        else:
            dist = stats.poisson(mu=max(0.1, blended))
        over_prob = dist.sf(line - 0.5) if line > 0 else 0.5
    else:
        over_prob = 0.5
    
    under_prob = 1 - over_prob
    
    return {
        'proj': round(blended, 1),
        'cv': round(cv_base, 3),
        'over_prob': round(over_prob, 4),
        'under_prob': round(under_prob, 4),
        'engine_proj': round(engine_proj, 1),
        'recent_proj': round(recent_proj, 1) if recent_proj else None,
    }


# ============================================================
# BACKTEST ENGINE
# ============================================================

class BacktestEngine:
    
    def __init__(self, db_url=None):
        self.db_url = db_url or DATABASE_URL
        self.engine = create_engine(self.db_url)
        self._cache = {}
    
    def get_available_dates(self):
        """Get dates where we have both props + boxscores + team stats."""
        with self.engine.connect() as conn:
            result = conn.execute(text("""
                SELECT DISTINCT p.game_date
                FROM player_props p
                WHERE p.sportsbook = 'DraftKings'
                AND p.game_date <= CURRENT_DATE
                AND EXISTS (
                    SELECT 1 FROM nba_team_advanced_stats t
                    WHERE t.pull_date::date <= p.game_date
                )
                ORDER BY p.game_date
            """))
            return [r[0] for r in result.fetchall()]
    
    def _load_team_stats(self, as_of_date):
        """Load team advanced stats as of a given date."""
        cache_key = f"team_stats_{as_of_date}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        with self.engine.connect() as conn:
            # Team advanced stats (pace, ratings)
            result = conn.execute(text("""
                SELECT "TEAM_NAME", "PACE", "OFF_RATING", "DEF_RATING", "NET_RATING"
                FROM nba_team_advanced_stats
                WHERE pull_date::date = (
                    SELECT MAX(pull_date::date) FROM nba_team_advanced_stats
                    WHERE pull_date::date <= :dt
                )
            """), {'dt': as_of_date})
            
            team_adv = {}
            for row in result.fetchall():
                name = row[0]
                abbr = self._team_name_to_abbr(name)
                if abbr:
                    team_adv[abbr] = {
                        'pace': float(row[1] or 100),
                        'off': float(row[2] or 110),
                        'def': float(row[3] or 110),
                        'net': float(row[4] or 0),
                    }
            
            # Team opponent stats (defense)
            result = conn.execute(text("""
                SELECT "TEAM_NAME", "OPP_PTS", "OPP_REB", "OPP_AST", "OPP_FG3_PCT"
                FROM nba_team_opponent_stats
                WHERE pull_date::date = (
                    SELECT MAX(pull_date::date) FROM nba_team_opponent_stats
                    WHERE pull_date::date <= :dt
                )
            """), {'dt': as_of_date})
            
            team_opp = {}
            for row in result.fetchall():
                name = row[0]
                abbr = self._team_name_to_abbr(name)
                if abbr:
                    team_opp[abbr] = {
                        'opp_pts': float(row[1] or 114),
                        'opp_reb': float(row[2] or 44),
                        'opp_ast': float(row[3] or 26),
                        'opp_fg3_pct': float(row[4] or 0.36),
                    }
        
        stats = {'adv': team_adv, 'opp': team_opp}
        self._cache[cache_key] = stats
        return stats
    
    def _load_player_season_stats(self, as_of_date):
        """Load player base stats (season averages) as of a given date."""
        cache_key = f"player_stats_{as_of_date}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        with self.engine.connect() as conn:
            result = conn.execute(text("""
                SELECT b."PLAYER_NAME", b."TEAM_ABBREVIATION",
                       b."PTS", b."REB", b."AST", b."FG3M", b."MIN",
                       a."USG_PCT"
                FROM nba_player_base_stats b
                LEFT JOIN nba_player_advanced_stats a 
                    ON b."PLAYER_NAME" = a."PLAYER_NAME" 
                    AND b.pull_date = a.pull_date
                WHERE b.pull_date::date = (
                    SELECT MAX(pull_date::date) FROM nba_player_base_stats
                    WHERE pull_date::date <= :dt
                )
            """), {'dt': as_of_date})
            
            players = {}
            for row in result.fetchall():
                name = row[0]
                players[name.lower()] = {
                    'name': name,
                    'team': row[1],
                    'pts': float(row[2] or 0),
                    'reb': float(row[3] or 0),
                    'ast': float(row[4] or 0),
                    'fg3m': float(row[5] or 0),
                    'min': float(row[6] or 0),
                    'usg': float(row[7] or 0.20) if row[7] else 0.20,
                }
            
        self._cache[cache_key] = players
        return players
    
    def _load_boxscores(self, before_date, limit_days=60):
        """Load recent boxscores for L5/L10/L15 calculations."""
        cache_key = f"boxscores_{before_date}_{limit_days}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        start = before_date - timedelta(days=limit_days)
        
        with self.engine.connect() as conn:
            result = conn.execute(text("""
                SELECT player_name, game_date, pts, reb, ast, fg3m, min
                FROM player_boxscores
                WHERE game_date >= :start AND game_date < :end
                ORDER BY game_date DESC
            """), {'start': start, 'end': before_date})
            
            player_games = defaultdict(list)
            for row in result.fetchall():
                name, gdate, pts, reb, ast, fg3m, mins = row
                min_val = 0
                if mins:
                    ms = str(mins)
                    if ':' in ms:
                        min_val = float(ms.split(':')[0])
                    else:
                        try: min_val = float(ms)
                        except: min_val = 0
                
                if min_val >= 20:
                    player_games[name].append({
                        'date': gdate, 'pts': float(pts or 0),
                        'reb': float(reb or 0), 'ast': float(ast or 0),
                        'fg3m': float(fg3m or 0), 'min': min_val,
                    })
            
            # Sort by date descending (most recent first)
            for p in player_games:
                player_games[p].sort(key=lambda x: x['date'], reverse=True)
        
        self._cache[cache_key] = dict(player_games)
        return dict(player_games)
    
    def _load_actual_boxscores(self, game_date):
        """Load actual game-day boxscores for grading."""
        with self.engine.connect() as conn:
            result = conn.execute(text("""
                SELECT player_name, pts, reb, ast, fg3m, min
                FROM player_boxscores
                WHERE game_date = :dt
            """), {'dt': game_date})
            
            actuals = {}
            for row in result.fetchall():
                name, pts, reb, ast, fg3m, mins = row
                min_val = 0
                if mins:
                    ms = str(mins)
                    if ':' in ms:
                        min_val = float(ms.split(':')[0])
                    else:
                        try: min_val = float(ms)
                        except: min_val = 0
                
                actuals[name.lower()] = {
                    'pts': float(pts or 0),
                    'reb': float(reb or 0),
                    'ast': float(ast or 0),
                    'fg3m': float(fg3m or 0),
                    'min': min_val,
                }
            return actuals
    
    def _load_props(self, game_date, sportsbook='DraftKings'):
        """Load props for a given day."""
        with self.engine.connect() as conn:
            result = conn.execute(text("""
                SELECT player_name, market, line, over_odds, under_odds,
                       home_team, away_team
                FROM player_props
                WHERE game_date = :dt AND sportsbook = :sb
                AND market IN ('player_points', 'player_rebounds',
                               'player_assists', 'player_threes')
            """), {'dt': game_date, 'sb': sportsbook})
            return result.fetchall()
    
    def _calc_pace_factor(self, team_stats, player_team, opp_team):
        """Calculate pace factor for a matchup."""
        adv = team_stats.get('adv', {})
        p1 = adv.get(player_team, {}).get('pace', 100)
        p2 = adv.get(opp_team, {}).get('pace', 100)
        
        if p1 >= p2:
            game_pace = 0.48 * p1 + 0.52 * p2
        else:
            game_pace = 0.52 * p1 + 0.48 * p2
        
        return game_pace / LEAGUE_AVG_PACE
    
    def _calc_def_factor(self, team_stats, opp_team, stat_type):
        """Calculate defensive adjustment factor."""
        opp = team_stats.get('opp', {}).get(opp_team, {})
        
        if stat_type == 'points':
            return opp.get('opp_pts', 114) / LEAGUE_AVG['points']
        elif stat_type == 'rebounds':
            return opp.get('opp_reb', 44) / LEAGUE_AVG['rebounds']
        elif stat_type == 'assists':
            return opp.get('opp_ast', 26) / LEAGUE_AVG['assists']
        elif stat_type == 'threes':
            return opp.get('opp_fg3_pct', 0.36) / LEAGUE_AVG['threes_pct']
        return 1.0
    
    def simulate_day(self, game_date, filters=None, sportsbook='DraftKings',
                     stat_types=None, tiers=None):
        """
        Simulate one day of picks.
        Returns list of simulated picks with projections and grades.
        """
        if filters is None:
            filters = get_default_filters()
        
        if stat_types is None:
            stat_types = ['pts', 'reb', 'ast', '3pm']
        
        if tiers is None:
            tiers = [1, 2, 3]
        
        # Load data (no look-ahead)
        team_stats = self._load_team_stats(game_date)
        player_stats = self._load_player_season_stats(game_date)
        boxscores = self._load_boxscores(game_date)
        actuals = self._load_actual_boxscores(game_date)
        props = self._load_props(game_date, sportsbook)
        
        if not props:
            return []
        
        picks = []
        
        for row in props:
            player, market, line, over_odds, under_odds, home_team, away_team = row
            stat = MARKET_TO_STAT.get(market)
            if not stat or stat not in stat_types:
                continue
            
            line = float(line)
            if line <= 0:
                continue
            
            player_lower = player.lower()
            engine_stat = STAT_TO_ENGINE.get(stat, stat)
            box_stat = STAT_TO_BOX.get(stat, stat)
            
            # Get player's team + opponent
            p_info = player_stats.get(player_lower)
            if not p_info:
                continue
            
            player_team = p_info['team']
            if player_team == home_team:
                opp_team = away_team
            elif player_team == away_team:
                opp_team = home_team
            else:
                # Team mismatch — try both
                opp_team = away_team
            
            # Season average
            season_avg = p_info.get(box_stat, 0)
            if season_avg <= 0:
                continue
            
            # Adjustments
            pace_factor = self._calc_pace_factor(team_stats, player_team, opp_team)
            def_factor = self._calc_def_factor(team_stats, opp_team, engine_stat)
            
            # Home/away
            is_home = (player_team == home_team)
            ha_factor = 1.015 if is_home else 0.985
            
            # Recent form (L5/L10/L15)
            recent_games = boxscores.get(player, [])
            recent_proj, recent_cv = get_l5_l10_projection(recent_games, box_stat)
            
            # Get full projection
            proj_result = get_engine_projection(
                season_avg * ha_factor,
                pace_factor, def_factor, engine_stat,
                recent_proj, line
            )
            
            proj = proj_result['proj']
            cv = proj_result['cv']
            over_prob = proj_result['over_prob']
            under_prob = proj_result['under_prob']
            
            # Check OVER filters
            over_edge = (proj - line) / line
            for tier_suffix, tier_num in [('', 1), ('_t2', 2), ('_t3', 3)]:
                if tier_num not in tiers:
                    continue
                fkey = f"{stat}_over{tier_suffix}"
                if fkey in filters:
                    f = filters[fkey]
                    if (over_edge >= f['edge_min'] and
                        cv <= f['cv_max'] and
                        proj >= f['proj_min']):
                        
                        # Grade against actual
                        actual = actuals.get(player_lower, {})
                        actual_val = actual.get(box_stat)
                        
                        result = 'no_data'
                        if actual_val is not None:
                            if actual_val > line:
                                result = 'win'
                            elif actual_val < line:
                                result = 'loss'
                            else:
                                result = 'push'
                        
                        picks.append({
                            'date': str(game_date),
                            'player': player,
                            'team': player_team,
                            'opponent': opp_team,
                            'stat': stat.upper(),
                            'direction': 'OVER',
                            'line': line,
                            'projection': proj,
                            'edge': round(over_edge * 100, 1),
                            'cv': round(cv, 3),
                            'over_prob': round(over_prob * 100, 1),
                            'tier': f.get('tier', tier_num),
                            'filter': fkey,
                            'actual': actual_val,
                            'result': result,
                            'is_home': is_home,
                            'pace_factor': round(pace_factor, 3),
                            'def_factor': round(def_factor, 3),
                            'season_avg': round(season_avg, 1),
                            'recent_proj': proj_result.get('recent_proj'),
                            'odds': over_odds or -110,
                        })
                        break  # Only pick from highest qualifying tier
            
            # Check UNDER filters
            under_edge = (line - proj) / line
            for tier_suffix, tier_num in [('', 1), ('_t2', 2), ('_t3', 3)]:
                if tier_num not in tiers:
                    continue
                fkey = f"{stat}_under{tier_suffix}"
                if fkey in filters:
                    f = filters[fkey]
                    if (under_edge >= f['edge_min'] and
                        cv <= f['cv_max'] and
                        proj >= f['proj_min']):
                        
                        actual = actuals.get(player_lower, {})
                        actual_val = actual.get(box_stat)
                        
                        result = 'no_data'
                        if actual_val is not None:
                            if actual_val < line:
                                result = 'win'
                            elif actual_val > line:
                                result = 'loss'
                            else:
                                result = 'push'
                        
                        picks.append({
                            'date': str(game_date),
                            'player': player,
                            'team': player_team,
                            'opponent': opp_team,
                            'stat': stat.upper(),
                            'direction': 'UNDER',
                            'line': line,
                            'projection': proj,
                            'edge': round(under_edge * 100, 1),
                            'cv': round(cv, 3),
                            'under_prob': round(under_prob * 100, 1),
                            'tier': f.get('tier', tier_num),
                            'filter': fkey,
                            'actual': actual_val,
                            'result': result,
                            'is_home': is_home,
                            'pace_factor': round(pace_factor, 3),
                            'def_factor': round(def_factor, 3),
                            'season_avg': round(season_avg, 1),
                            'recent_proj': proj_result.get('recent_proj'),
                            'odds': under_odds or -110,
                        })
                        break
        
        return picks
    
    def run_backtest(self, start_date, end_date, filters=None,
                     sportsbook='DraftKings', stat_types=None, tiers=None,
                     progress_callback=None):
        """
        Run full backtest across date range.
        Returns DataFrame of all picks with grades.
        """
        if filters is None:
            filters = get_default_filters()
        
        all_picks = []
        dates = self.get_available_dates()
        
        # Filter to requested range
        backtest_dates = [d for d in dates if start_date <= d <= end_date]
        
        for i, dt in enumerate(backtest_dates):
            if progress_callback:
                progress_callback(i / len(backtest_dates), f"Simulating {dt}...")
            
            try:
                day_picks = self.simulate_day(dt, filters, sportsbook,
                                              stat_types, tiers)
                all_picks.extend(day_picks)
            except Exception as e:
                print(f"  ⚠️ Error on {dt}: {e}")
                traceback.print_exc()
                continue
        
        if progress_callback:
            progress_callback(1.0, "Complete!")
        
        if not all_picks:
            return pd.DataFrame()
        
        df = pd.DataFrame(all_picks)
        return df
    
    def sweep_parameter(self, start_date, end_date, param_name, param_range,
                        base_filters=None, sportsbook='DraftKings',
                        stat_types=None, tiers=None,
                        progress_callback=None):
        """
        Sweep a filter parameter across a range and return results.
        param_name: e.g. 'edge_min' or 'cv_max'
        """
        if base_filters is None:
            base_filters = get_default_filters()
        
        results = []
        
        for i, val in enumerate(param_range):
            if progress_callback:
                progress_callback(i / len(param_range),
                                  f"Testing {param_name}={val:.2f}...")
            
            # Create modified filters
            modified = {}
            for k, v in base_filters.items():
                modified[k] = dict(v)
                if param_name in modified[k]:
                    modified[k][param_name] = val
            
            df = self.run_backtest(start_date, end_date, modified,
                                   sportsbook, stat_types, tiers)
            
            if len(df) == 0:
                results.append({
                    'param_value': val,
                    'total_picks': 0,
                    'wins': 0,
                    'losses': 0,
                    'win_rate': 0,
                    'ppd': 0,
                    'roi': 0,
                })
                continue
            
            graded = df[df['result'].isin(['win', 'loss'])]
            wins = len(graded[graded['result'] == 'win'])
            losses = len(graded[graded['result'] == 'loss'])
            n_days = df['date'].nunique()
            
            tier_units = {1: 1.5, 2: 1.0, 3: 0.5}
            total_risked = sum(tier_units.get(t, 1.0) for t in graded['tier'])
            total_won = sum(tier_units.get(t, 1.0) * 0.909
                           for t in graded[graded['result'] == 'win']['tier'])
            total_lost = sum(tier_units.get(t, 1.0)
                            for t in graded[graded['result'] == 'loss']['tier'])
            roi = ((total_won - total_lost) / total_risked * 100) if total_risked > 0 else 0
            
            results.append({
                'param_value': val,
                'total_picks': len(graded),
                'wins': wins,
                'losses': losses,
                'win_rate': round(wins / (wins + losses) * 100, 1) if (wins + losses) > 0 else 0,
                'ppd': round(len(graded) / n_days, 1) if n_days > 0 else 0,
                'roi': round(roi, 1),
            })
        
        if progress_callback:
            progress_callback(1.0, "Sweep complete!")
        
        return pd.DataFrame(results)
    
    @staticmethod
    def _team_name_to_abbr(name):
        """Convert full team name to abbreviation."""
        mapping = {
            'Atlanta Hawks': 'ATL', 'Boston Celtics': 'BOS',
            'Brooklyn Nets': 'BKN', 'Charlotte Hornets': 'CHA',
            'Chicago Bulls': 'CHI', 'Cleveland Cavaliers': 'CLE',
            'Dallas Mavericks': 'DAL', 'Denver Nuggets': 'DEN',
            'Detroit Pistons': 'DET', 'Golden State Warriors': 'GSW',
            'Houston Rockets': 'HOU', 'Indiana Pacers': 'IND',
            'LA Clippers': 'LAC', 'Los Angeles Lakers': 'LAL',
            'Memphis Grizzlies': 'MEM', 'Miami Heat': 'MIA',
            'Milwaukee Bucks': 'MIL', 'Minnesota Timberwolves': 'MIN',
            'New Orleans Pelicans': 'NOP', 'New York Knicks': 'NYK',
            'Oklahoma City Thunder': 'OKC', 'Orlando Magic': 'ORL',
            'Philadelphia 76ers': 'PHI', 'Phoenix Suns': 'PHX',
            'Portland Trail Blazers': 'POR', 'Sacramento Kings': 'SAC',
            'San Antonio Spurs': 'SAS', 'Toronto Raptors': 'TOR',
            'Utah Jazz': 'UTA', 'Washington Wizards': 'WAS',
        }
        return mapping.get(name)


# ============================================================
# CLI TEST
# ============================================================
if __name__ == '__main__':
    engine = BacktestEngine()
    
    dates = engine.get_available_dates()
    print(f"Available dates: {len(dates)} days ({dates[0]} to {dates[-1]})")
    
    # Quick test: simulate last available date
    test_date = dates[-2] if len(dates) > 1 else dates[0]
    print(f"\nSimulating {test_date}...")
    
    picks = engine.simulate_day(test_date)
    print(f"Picks generated: {len(picks)}")
    
    if picks:
        wins = sum(1 for p in picks if p['result'] == 'win')
        losses = sum(1 for p in picks if p['result'] == 'loss')
        print(f"W-L: {wins}-{losses}")
        
        for p in picks[:5]:
            print(f"  {p['player']} {p['stat']} {p['direction']} {p['line']} "
                  f"| proj={p['projection']} edge={p['edge']}% "
                  f"| actual={p['actual']} -> {p['result'].upper()}")
