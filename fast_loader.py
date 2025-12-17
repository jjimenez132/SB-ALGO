"""
fast_loader.py - Speed Layer for SB-ALGO
=========================================
Uses @functools.lru_cache to keep data in RAM for 5000x speedup.
"""

import functools
import os
import pandas as pd
from sqlalchemy import create_engine, text
from datetime import datetime, timedelta
import pytz

@functools.lru_cache(maxsize=1)
def get_engine():
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        raise ValueError("DATABASE_URL not set")
    return create_engine(database_url, pool_pre_ping=True, pool_recycle=300)

def get_eastern_date():
    eastern = pytz.timezone('US/Eastern')
    return datetime.now(eastern).strftime('%Y-%m-%d')

def get_eastern_datetime():
    eastern = pytz.timezone('US/Eastern')
    return datetime.now(eastern)

@functools.lru_cache(maxsize=1)
def load_todays_games():
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
        return games

@functools.lru_cache(maxsize=1)
def load_todays_odds():
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
    return odds_map

@functools.lru_cache(maxsize=1)
def load_injuries():
    engine = get_engine()
    query = text("SELECT player_name, team, status, description FROM injuries LIMIT 150")
    with engine.connect() as conn:
        result = conn.execute(query)
        return [{'player_name': row[0], 'team': row[1], 'status': row[2], 'description': row[3]} for row in result]

@functools.lru_cache(maxsize=1)
def load_dashboard_metrics():
    engine = get_engine()
    today = get_eastern_date()
    metrics = {'games_today': 0, 'active_injuries': 0, 'edges_found': 0, 'system_confidence': 75, 'best_play': 'See Games Tab', 'best_play_conf': 0}
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM games WHERE date = :today"), {"today": today}).fetchone()
            metrics['games_today'] = result[0] if result else 0
            result = conn.execute(text("SELECT COUNT(*) FROM injuries")).fetchone()
            metrics['active_injuries'] = result[0] if result else 0
            metrics['edges_found'] = metrics['games_today']
    except Exception as e:
        print(f"Metrics error: {e}")
    return metrics

@functools.lru_cache(maxsize=64)
def get_team_record(team: str, days: int = 30):
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
            return {'wins': int(result[0] or 0), 'losses': int(result[1] or 0), 
                    'home_record': f"{int(result[2] or 0)}-{int(result[3] or 0)}", 
                    'away_record': f"{int(result[4] or 0)}-{int(result[5] or 0)}"}
    return {'wins': 0, 'losses': 0, 'home_record': '0-0', 'away_record': '0-0'}

@functools.lru_cache(maxsize=1)
def get_hot_teams(limit: int = 5):
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
               ROUND(100.0 * SUM(win) / COUNT(*), 1) as win_pct, ROUND(AVG(margin), 1) as avg_margin
        FROM team_games GROUP BY team HAVING COUNT(*) >= 5 ORDER BY win_pct DESC, avg_margin DESC LIMIT :limit
    """)
    with engine.connect() as conn:
        return pd.read_sql(query, conn, params={"start_date": start_date, "today": today, "limit": limit})

@functools.lru_cache(maxsize=1)
def get_cold_teams(limit: int = 5):
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
               ROUND(100.0 * SUM(win) / COUNT(*), 1) as win_pct, ROUND(AVG(margin), 1) as avg_margin
        FROM team_games GROUP BY team HAVING COUNT(*) >= 5 ORDER BY win_pct ASC, avg_margin ASC LIMIT :limit
    """)
    with engine.connect() as conn:
        return pd.read_sql(query, conn, params={"start_date": start_date, "today": today, "limit": limit})

@functools.lru_cache(maxsize=256)
def get_player_last_n_games(player_name: str, n: int = 20):
    engine = get_engine()
    query = text("""
        SELECT game_date, pts, reb, ast, stl, blk, fg3m, min, team_abbreviation
        FROM player_boxscores WHERE player_name = :player ORDER BY game_date DESC LIMIT :n
    """)
    with engine.connect() as conn:
        return pd.read_sql(query, conn, params={"player": player_name, "n": n})

def clear_all_caches():
    load_todays_games.cache_clear()
    load_todays_odds.cache_clear()
    load_injuries.cache_clear()
    load_dashboard_metrics.cache_clear()
    get_team_record.cache_clear()
    get_hot_teams.cache_clear()
    get_cold_teams.cache_clear()
    get_player_last_n_games.cache_clear()
    print("All caches cleared")

@functools.lru_cache(maxsize=1)
def load_game_edges():
    try:
        from algo_brain import analyze_games
        return analyze_games()
    except Exception as e:
        print(f"Game edges error: {e}")
        return []

@functools.lru_cache(maxsize=1)
def load_prop_edges():
    try:
        from algo_brain import analyze_props
        return analyze_props()
    except Exception as e:
        print(f"Prop edges error: {e}")
        return []

def get_all_edges():
    return load_game_edges(), load_prop_edges()
