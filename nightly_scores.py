#!/usr/bin/env python3
"""
Nightly Scores & Box Scores Fetcher
====================================
Runs hourly 9pm-3am ET to pull TONIGHT's games
- Game scores (for spread/total grading)
- Player box scores (for props grading)
"""

import os
import requests
from datetime import datetime
from sqlalchemy import create_engine, text
import pytz

API_KEY = os.environ.get('TANK01_API_KEY', 'ada93da8e5msh75c5342a07b643cp1b45fajsn72f3bfcd3653')
DATABASE_URL = os.environ.get('DATABASE_URL',
    "postgresql://sb_algo_db_user:0HDtYp4EY2Lo5At8iyf44PD1zDioSPK7@dpg-d495uhchg0os738l1a50-a.virginia-postgres.render.com/sb_algo_db?sslmode=require")

HEADERS = {
    "x-rapidapi-host": "tank01-fantasy-stats.p.rapidapi.com",
    "x-rapidapi-key": API_KEY
}

TEAM_MAP = {
    "ATL": "ATL", "BOS": "BOS", "BKN": "BKN", "CHA": "CHA", "CHI": "CHI",
    "CLE": "CLE", "DAL": "DAL", "DEN": "DEN", "DET": "DET", "GS": "GSW", "GSW": "GSW",
    "HOU": "HOU", "IND": "IND", "LAC": "LAC", "LAL": "LAL", "MEM": "MEM",
    "MIA": "MIA", "MIL": "MIL", "MIN": "MIN", "NO": "NOP", "NOP": "NOP",
    "NY": "NYK", "NYK": "NYK", "OKC": "OKC", "ORL": "ORL", "PHI": "PHI",
    "PHX": "PHX", "PHO": "PHX", "POR": "POR", "SAC": "SAC", "SA": "SAS", "SAS": "SAS",
    "TOR": "TOR", "UTA": "UTA", "UTAH": "UTA", "WAS": "WAS", "WSH": "WAS"
}

def get_eastern_date():
    """Get current date in Eastern time - this is the game date"""
    et = pytz.timezone('US/Eastern')
    return datetime.now(et)

def fetch_games_for_date(date_str):
    url = "https://tank01-fantasy-stats.p.rapidapi.com/getNBAGamesForDate"
    response = requests.get(url, headers=HEADERS, params={"gameDate": date_str})
    if response.status_code == 200:
        data = response.json()
        return data.get('body', [])
    return []

def fetch_boxscore(game_id):
    url = "https://tank01-fantasy-stats.p.rapidapi.com/getNBABoxScore"
    response = requests.get(url, headers=HEADERS, params={"gameID": game_id})
    if response.status_code == 200:
        data = response.json()
        return data.get('body', {})
    return {}

def update_game_scores(engine, date_str, date_obj):
    """Update game scores for today's games"""
    print(f"\n📥 Fetching game scores for {date_str}...")
    games = fetch_games_for_date(date_str)
    if not games:
        print("   No games found")
        return 0
    
    updated = 0
    for game in games:
        home = TEAM_MAP.get(game.get('home'), game.get('home'))
        away = TEAM_MAP.get(game.get('away'), game.get('away'))
        home_pts = int(game.get('homePts') or 0)
        away_pts = int(game.get('awayPts') or 0)
        total = home_pts + away_pts
        margin = home_pts - away_pts
        home_win = 1 if home_pts > away_pts else 0
        game_status = game.get('gameStatus', '')
        
        # Only update if game has started (has points or is final)
        if home_pts > 0 or away_pts > 0 or 'Final' in game_status:
            with engine.connect() as conn:
                conn.execute(text("""
                    UPDATE games SET 
                        home_pts = :hp, visitor_pts = :ap, 
                        total_points = :tp, margin_home = :mh, home_win = :hw
                    WHERE date = :d AND home_team = :h AND visitor_team = :a
                """), {
                    "hp": home_pts, "ap": away_pts, "tp": total, 
                    "mh": margin, "hw": home_win,
                    "d": date_obj, "h": home, "a": away
                })
                conn.commit()
                updated += 1
                status = "🏁 FINAL" if 'Final' in game_status else "🔴 LIVE"
                print(f"   {status} {away} {away_pts} @ {home} {home_pts}")
    
    print(f"   ✅ Updated {updated} games")
    return updated

def update_player_boxscores(engine, date_str, date_obj):
    """Update player box scores for today's games"""
    print(f"\n📥 Fetching player box scores for {date_str}...")
    games = fetch_games_for_date(date_str)
    if not games:
        print("   No games found")
        return 0
    
    inserted = 0
    for game in games:
        game_id = game.get('gameID')
        game_status = game.get('gameStatus', '')
        
        # Only fetch boxscore if game has started
        if not game_id or ('Final' not in game_status and int(game.get('homePts') or 0) == 0):
            continue
            
        box_data = fetch_boxscore(game_id)
        if not box_data:
            continue
            
        player_stats = box_data.get('playerStats', {})
        for player_id_str, stats in player_stats.items():
            team = TEAM_MAP.get(stats.get('team'), stats.get('team'))
            data = {
                'game_id': int(game_id), 
                'player_id': int(player_id_str),
                'player_name': stats.get('longName', 'Unknown'), 
                'team_abbreviation': team,
                'game_date': date_obj,
                'minutes': stats.get('mins', '0'),
                'pts': int(stats.get('pts') or 0),
                'reb': int(stats.get('reb') or 0),
                'ast': int(stats.get('ast') or 0),
                'stl': int(stats.get('stl') or 0),
                'blk': int(stats.get('blk') or 0),
                'tov': int(stats.get('TOV') or 0),
                'fgm': int(stats.get('fgm') or 0),
                'fga': int(stats.get('fga') or 0),
                'tpm': int(stats.get('tptfgm') or 0),
                'tpa': int(stats.get('tptfga') or 0),
                'ftm': int(stats.get('ftm') or 0),
                'fta': int(stats.get('fta') or 0)
            }
            
            try:
                with engine.connect() as conn:
                    conn.execute(text("""
                        INSERT INTO player_boxscores
                        (game_id, player_id, player_name, team_abbreviation, game_date,
                         minutes, pts, reb, ast, stl, blk, tov, fgm, fga, tpm, tpa, ftm, fta)
                        VALUES (:game_id, :player_id, :player_name, :team_abbreviation, :game_date,
                                :minutes, :pts, :reb, :ast, :stl, :blk, :tov, :fgm, :fga, :tpm, :tpa, :ftm, :fta)
                        ON CONFLICT (game_id, player_id) DO UPDATE SET
                            pts = :pts, reb = :reb, ast = :ast, stl = :stl, blk = :blk,
                            tov = :tov, fgm = :fgm, fga = :fga, tpm = :tpm, tpa = :tpa,
                            ftm = :ftm, fta = :fta, minutes = :minutes
                    """), data)
                    conn.commit()
                    inserted += 1
            except Exception as e:
                pass
    
    print(f"   ✅ Upserted {inserted} player stats")
    return inserted

def main():
    et_now = get_eastern_date()
    
    print("=" * 60)
    print("🌙 NIGHTLY SCORES & BOX SCORES UPDATE")
    print(f"⏰ {et_now.strftime('%Y-%m-%d %I:%M %p')} ET")
    print("=" * 60)
    
    engine = create_engine(DATABASE_URL)
    
    # Use Eastern time date (tonight's games)
    date_str = et_now.strftime("%Y%m%d")
    date_obj = et_now.date()
    
    print(f"📅 Pulling data for: {date_obj}")
    
    # 1. Update game scores
    update_game_scores(engine, date_str, date_obj)
    
    # 2. Update player box scores
    update_player_boxscores(engine, date_str, date_obj)
    
    print("\n" + "=" * 60)
    print("✅ NIGHTLY UPDATE COMPLETE!")
    print("=" * 60)

if __name__ == "__main__":
    main()
