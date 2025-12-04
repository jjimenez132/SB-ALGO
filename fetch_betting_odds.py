#!/usr/bin/env python3
"""
Fetch NBA Betting Odds from Tank01 API
Runs 3x daily: 5 AM, 12 PM, 6 PM ET
"""

import requests
from sqlalchemy import create_engine, text
from datetime import datetime
import pytz
import os

API_KEY = "ada93da8e5msh75c5342a07b643cp1b45fajsn72f3bfcd3653"
DATABASE_URL = os.environ.get('DATABASE_URL',
    "postgresql://sb_algo_db_user:0HDtYp4EY2Lo5At8iyf44PD1zDioSPK7@dpg-d495uhchg0os738l1a50-a.virginia-postgres.render.com/sb_algo_db?sslmode=require")

HEADERS = {
    "x-rapidapi-host": "tank01-fantasy-stats.p.rapidapi.com",
    "x-rapidapi-key": API_KEY
}

SPORTSBOOKS = ['fanduel', 'draftkings', 'betmgm', 'caesars', 'bet365', 'fanatics', 'hardrock']

def parse_val(s):
    if not s or s == 'N/A':
        return None
    try:
        return float(str(s).replace('+', ''))
    except:
        return None

def fetch_and_store_odds():
    eastern = pytz.timezone('US/Eastern')
    now = datetime.now(eastern)
    today_str = now.strftime("%Y%m%d")
    today_date = now.date()
    
    print(f"{'='*60}")
    print(f"🏀 BETTING ODDS FETCHER")
    print(f"⏰ {now.strftime('%Y-%m-%d %H:%M:%S')} ET")
    print(f"{'='*60}")
    
    # Fetch odds from API
    print(f"\n📥 Fetching odds for {today_str}...")
    
    url = "https://tank01-fantasy-stats.p.rapidapi.com/getNBABettingOdds"
    response = requests.get(url, headers=HEADERS, params={"gameDate": today_str})
    
    if response.status_code != 200:
        print(f"❌ API Error: {response.status_code}")
        return
    
    odds_data = response.json().get('body', {})
    
    if not odds_data:
        print("⚠️ No odds data returned")
        return
    
    print(f"✅ Got odds for {len(odds_data)} games")
    
    # Store in database
    engine = create_engine(DATABASE_URL)
    inserted = 0
    
    with engine.connect() as conn:
        for game_id, data in odds_data.items():
            home = data.get('homeTeam')
            away = data.get('awayTeam')
            print(f"   {away} @ {home}")
            
            for book in SPORTSBOOKS:
                if book not in data:
                    continue
                
                b = data[book]
                try:
                    conn.execute(text("""
                        INSERT INTO betting_odds 
                        (game_id, game_date, home_team, away_team, sportsbook,
                         home_spread, home_spread_odds, away_spread, away_spread_odds,
                         total, over_odds, under_odds, home_ml, away_ml, updated_at)
                        VALUES (:gid, :gd, :h, :a, :book, :hs, :hso, :as, :aso, :t, :oo, :uo, :hm, :am, NOW())
                        ON CONFLICT (game_id, sportsbook) DO UPDATE SET
                        home_spread=:hs, home_spread_odds=:hso, away_spread=:as, away_spread_odds=:aso,
                        total=:t, over_odds=:oo, under_odds=:uo, home_ml=:hm, away_ml=:am, updated_at=NOW()
                    """), {
                        'gid': game_id,
                        'gd': today_date,
                        'h': home,
                        'a': away,
                        'book': book,
                        'hs': parse_val(b.get('homeTeamSpread')),
                        'hso': parse_val(b.get('homeTeamSpreadOdds')),
                        'as': parse_val(b.get('awayTeamSpread')),
                        'aso': parse_val(b.get('awayTeamSpreadOdds')),
                        't': parse_val(b.get('totalOver')),
                        'oo': parse_val(b.get('totalOverOdds')),
                        'uo': parse_val(b.get('totalUnderOdds')),
                        'hm': parse_val(b.get('homeTeamMLOdds')),
                        'am': parse_val(b.get('awayTeamMLOdds'))
                    })
                    inserted += 1
                except Exception as e:
                    print(f"      ⚠️ Error {book}: {e}")
        
        conn.commit()
    
    # Verify
    with engine.connect() as conn:
        result = conn.execute(text(
            "SELECT COUNT(*) FROM betting_odds WHERE game_date = :d"
        ), {"d": today_date}).fetchone()
        total = result[0]
    
    print(f"\n{'='*60}")
    print(f"✅ COMPLETE: {inserted} records inserted/updated")
    print(f"📊 Total odds for today: {total}")
    print(f"{'='*60}")

if __name__ == "__main__":
    fetch_and_store_odds()

# Trigger algo brain after data update
try:
    from algo_brain import analyze_and_alert
    analyze_and_alert()
except Exception as e:
    print(f"Brain error: {e}")
