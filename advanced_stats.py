#!/usr/bin/env python3
"""
Advanced Stats Module for SB-ALGO
Provides easy access to NBA nerd stats from nba_data_pipeline
"""

from sqlalchemy import create_engine, text
import os

DATABASE_URL = os.environ.get('DATABASE_URL',
    "postgresql://sb_algo_db_user:0HDtYp4EY2Lo5At8iyf44PD1zDioSPK7@dpg-d495uhchg0os738l1a50-a.virginia-postgres.render.com/sb_algo_db?sslmode=require")

def get_engine():
    return create_engine(DATABASE_URL)

def get_team_advanced(team_name):
    """Get advanced stats for a team"""
    engine = get_engine()
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT * FROM nba_team_advanced_stats 
            WHERE "TEAM_NAME" ILIKE :team
            LIMIT 1
        """), {"team": f"%{team_name}%"}).fetchone()
        return dict(result._mapping) if result else None

def get_team_four_factors(team_name):
    """Get Four Factors for a team"""
    engine = get_engine()
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT * FROM nba_team_four_factors 
            WHERE "TEAM_NAME" ILIKE :team
            LIMIT 1
        """), {"team": f"%{team_name}%"}).fetchone()
        return dict(result._mapping) if result else None

def get_player_advanced(player_name):
    """Get advanced stats for a player"""
    engine = get_engine()
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT * FROM nba_player_advanced_stats 
            WHERE "PLAYER_NAME" ILIKE :player
            LIMIT 1
        """), {"player": f"%{player_name}%"}).fetchone()
        return dict(result._mapping) if result else None

def get_player_usage(player_name):
    """Get usage stats for a player"""
    engine = get_engine()
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT * FROM nba_player_usage 
            WHERE "PLAYER_NAME" ILIKE :player
            LIMIT 1
        """), {"player": f"%{player_name}%"}).fetchone()
        return dict(result._mapping) if result else None

def get_player_bpm_vorp(player_name):
    """Get BPM and VORP for a player"""
    engine = get_engine()
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT * FROM nba_player_bpm_vorp 
            WHERE "PLAYER_NAME" ILIKE :player
            LIMIT 1
        """), {"player": f"%{player_name}%"}).fetchone()
        return dict(result._mapping) if result else None

def get_matchup_edge(home_team, away_team):
    """Calculate edge based on advanced stats"""
    home = get_team_advanced(home_team)
    away = get_team_advanced(away_team)
    
    if not home or not away:
        return None
    
    # Net Rating differential (home team perspective)
    net_diff = (home.get('NET_RATING') or 0) - (away.get('NET_RATING') or 0)
    
    # Pace average (for totals projection)
    pace_avg = ((home.get('PACE') or 100) + (away.get('PACE') or 100)) / 2
    
    # Efficiency matchup
    home_off = home.get('OFF_RATING') or 110
    home_def = home.get('DEF_RATING') or 110
    away_off = away.get('OFF_RATING') or 110
    away_def = away.get('DEF_RATING') or 110
    
    # eFG% differential
    efg_diff = (home.get('EFG_PCT') or 0.5) - (away.get('EFG_PCT') or 0.5)
    
    # Projected spread (negative = home favored)
    # Rule of thumb: 1 point of net rating ≈ 1 point spread + 3 pts home court
    projected_spread = -(net_diff + 3)
    
    # Projected total
    home_pts = (pace_avg / 100) * home_off
    away_pts = (pace_avg / 100) * away_off
    projected_total = home_pts + away_pts
    
    return {
        'home_team': home_team,
        'away_team': away_team,
        'net_rating_diff': round(net_diff, 1),
        'projected_spread': round(projected_spread, 1),
        'projected_total': round(projected_total, 1),
        'pace_avg': round(pace_avg, 1),
        'home_off_rating': home_off,
        'home_def_rating': home_def,
        'away_off_rating': away_off,
        'away_def_rating': away_def,
        'efg_diff': round(efg_diff * 100, 1),
    }

def get_all_teams_ranked():
    """Get all teams ranked by Net Rating"""
    engine = get_engine()
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT "TEAM_NAME", "NET_RATING", "OFF_RATING", "DEF_RATING", "PACE", "EFG_PCT", "TS_PCT"
            FROM nba_team_advanced_stats
            ORDER BY "NET_RATING" DESC
        """)).fetchall()
        return [dict(r._mapping) for r in result]

# Quick test
if __name__ == "__main__":
    print("Testing Advanced Stats Module...\n")
    
    # Test team stats
    lakers = get_team_advanced("Lakers")
    if lakers:
        print(f"Lakers: NET_RATING={lakers.get('NET_RATING')}, PACE={lakers.get('PACE')}")
    
    celtics = get_team_advanced("Celtics")
    if celtics:
        print(f"Celtics: NET_RATING={celtics.get('NET_RATING')}, PACE={celtics.get('PACE')}")
    
    # Test matchup
    print("\nMatchup: Lakers vs Celtics")
    edge = get_matchup_edge("Lakers", "Celtics")
    if edge:
        print(f"  Net Rating Diff: {edge['net_rating_diff']}")
        print(f"  Projected Spread: {edge['projected_spread']}")
        print(f"  Projected Total: {edge['projected_total']}")
    
    # Test player
    print("\nPlayer: LeBron James")
    lebron = get_player_advanced("LeBron")
    if lebron:
        print(f"  TS%={lebron.get('TS_PCT')}, USG%={lebron.get('USG_PCT')}")
    
    # Top 5 teams
    print("\nTop 5 Teams by Net Rating:")
    teams = get_all_teams_ranked()
    for t in teams[:5]:
        print(f"  {t['TEAM_NAME']}: {t['NET_RATING']}")
    
    print("\n✅ Module working!")
