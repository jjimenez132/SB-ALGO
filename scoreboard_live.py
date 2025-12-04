#!/usr/bin/env python3
"""
Live Scoreboard Fetcher - Tank01 API
Runs every 5 minutes during game hours
Updates ONLY live fields, never overwrites final data
"""

import requests
from sqlalchemy import create_engine, text
from datetime import datetime
import pytz
import os

API_KEY = os.environ.get('TANK01_API_KEY', 'ada93da8e5msh75c5342a07b643cp1b45fajsn72f3bfcd3653')
DATABASE_URL = os.environ.get('DATABASE_URL',
    "postgresql://sb_algo_db_user:0HDtYp4EY2Lo5At8iyf44PD1zDioSPK7@dpg-d495uhchg0os738l1a50-a.virginia-postgres.render.com/sb_algo_db?sslmode=require")

HEADERS = {
    "x-rapidapi-host": "tank01-fantasy-stats.p.rapidapi.com",
    "x-rapidapi-key": API_KEY
}

def ensure_live_columns(engine):
    with engine.connect() as conn:
        conn.execute(text("""
            ALTER TABLE games 
            ADD COLUMN IF NOT EXISTS current_home_score INTEGER DEFAULT 0,
            ADD COLUMN IF NOT EXISTS current_away_score INTEGER DEFAULT 0,
            ADD COLUMN IF NOT EXISTS quarter VARCHAR(10),
            ADD COLUMN IF NOT EXISTS time_remaining VARCHAR(10),
            ADD COLUMN IF NOT EXISTS game_status VARCHAR(50),
            ADD COLUMN IF NOT EXISTS live_updated_at TIMESTAMP
        """))
        conn.commit()

def ensure_player_live_columns(engine):
    with engine.connect() as conn:
        conn.execute(text("""
            ALTER TABLE player_boxscores 
            ADD COLUMN IF NOT EXISTS live_pts INTEGER DEFAULT 0,
            ADD COLUMN IF NOT EXISTS live_reb INTEGER DEFAULT 0,
            ADD COLUMN IF NOT EXISTS live_ast INTEGER DEFAULT 0,
            ADD COLUMN IF NOT EXISTS live_stl INTEGER DEFAULT 0,
            ADD COLUMN IF NOT EXISTS live_blk INTEGER DEFAULT 0,
            ADD COLUMN IF NOT EXISTS live_updated_at TIMESTAMP
        """))
        conn.commit()

def fetch_live_scoreboard(game_date):
    url = "https://tank01-fantasy-stats.p.rapidapi.com/getNBAScoresOnly"
    params = {"gameDate": game_date, "topPerformers": "true", "lineups": "true"}
    response = requests.get(url, headers=HEADERS, params=params)
    if response.status_code != 200:
        print(f"   ❌ API Error: {response.status_code}")
        return None
    return response.json().get('body', {})

def update_game_live_data(engine, game_data, game_date_obj):
    home_team = game_data.get('home')
    away_team = game_data.get('away')
    home_score = game_data.get('homePts', 0) or 0
    away_score = game_data.get('awayPts', 0) or 0
    # gameClock can be a string or dict depending on game state
    game_clock = game_data.get('gameClock', '')
    if isinstance(game_clock, dict):
        quarter = game_clock.get('quarter', '') or game_data.get('currentPeriod', '')
        time_remaining = game_clock.get('timeRemaining', '') or game_data.get('gameTime', '')
    else:
        quarter = game_data.get('currentPeriod', '')
        time_remaining = game_data.get('gameTime', '')
    game_status = game_data.get('gameStatus') or game_data.get('gameStatusCode', '')
    
    if not home_team or not away_team:
        return False
    
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT home_pts FROM games 
            WHERE date = :game_date AND home_team = :home AND visitor_team = :away
        """), {"game_date": game_date_obj, "home": home_team, "away": away_team}).fetchone()
        
        if result:
            if result[0] and result[0] > 0 and str(game_status).lower() == 'final':
                print(f"   ⏭️ {away_team} @ {home_team}: Already final, skipping")
                return False
            
            conn.execute(text("""
                UPDATE games SET
                    current_home_score = :home_score, current_away_score = :away_score,
                    quarter = :quarter, time_remaining = :time_remaining,
                    game_status = :game_status, live_updated_at = NOW()
                WHERE date = :game_date AND home_team = :home AND visitor_team = :away
            """), {
                "home_score": int(home_score) if home_score else 0,
                "away_score": int(away_score) if away_score else 0,
                "quarter": str(quarter)[:10] if quarter else None,
                "time_remaining": str(time_remaining)[:10] if time_remaining else None,
                "game_status": str(game_status)[:50] if game_status else None,
                "game_date": game_date_obj, "home": home_team, "away": away_team
            })
            conn.commit()
            print(f"   ✅ {away_team} @ {home_team}: {away_score}-{home_score} ({quarter} {time_remaining})")
            return True
        else:
            conn.execute(text("""
                INSERT INTO games (date, home_team, visitor_team, home_pts, visitor_pts, 
                    current_home_score, current_away_score, quarter, time_remaining, game_status, live_updated_at)
                VALUES (:game_date, :home, :away, 0, 0, :home_score, :away_score, :quarter, :time_remaining, :game_status, NOW())
            """), {
                "game_date": game_date_obj, "home": home_team, "away": away_team,
                "home_score": int(home_score) if home_score else 0,
                "away_score": int(away_score) if away_score else 0,
                "quarter": str(quarter)[:10] if quarter else None,
                "time_remaining": str(time_remaining)[:10] if time_remaining else None,
                "game_status": str(game_status)[:50] if game_status else None
            })
            conn.commit()
            print(f"   🆕 {away_team} @ {home_team}: New game inserted")
            return True

def main():
    eastern = pytz.timezone('US/Eastern')
    now = datetime.now(eastern)
    today_str = now.strftime("%Y%m%d")
    today_date = now.date()
    
    print(f"{'='*60}")
    print(f"🏀 LIVE SCOREBOARD FETCHER")
    print(f"⏰ {now.strftime('%Y-%m-%d %H:%M:%S')} ET")
    print(f"{'='*60}")
    
    engine = create_engine(DATABASE_URL)
    
    try:
        ensure_live_columns(engine)
        ensure_player_live_columns(engine)
    except Exception as e:
        print(f"⚠️ Column setup warning: {e}")
    
    print(f"\n📥 Fetching live scoreboard for {today_str}...")
    scoreboard = fetch_live_scoreboard(today_str)
    
    if not scoreboard:
        print("⚠️ No scoreboard data returned")
        return
    
    if isinstance(scoreboard, dict):
        # scoreboard is {game_id: game_data}
        games = list(scoreboard.values())
    elif isinstance(scoreboard, list):
        games = scoreboard
    else:
        print(f"⚠️ Unexpected data format: {type(scoreboard)}")
        return
    
    print(f"✅ Got data for {len(games)} games")
    
    games_updated = 0
    for game in games:
        if not isinstance(game, dict):
            print(f"   ⚠️ Skipping non-dict game: {type(game)}")
            continue
        try:
            if update_game_live_data(engine, game, today_date):
                games_updated += 1
        except Exception as e:
            print(f"   ❌ Error processing {game.get('away', '?')} @ {game.get('home', '?')}: {e}")
    
    print(f"\n{'='*60}")
    print(f"✅ COMPLETE: {games_updated} games updated")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()
