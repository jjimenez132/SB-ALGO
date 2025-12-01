#!/usr/bin/env python3
"""
Player Props Fetcher - The Odds API
Pulls all player props from all sportsbooks for today's games
"""

import requests
from sqlalchemy import create_engine, text
from datetime import datetime
import os

ODDS_API_KEY = "f5c273adfb5cfcc8890985b55585fb66"
DATABASE_URL = os.environ.get('DATABASE_URL', 
    "postgresql://sb_algo_db_user:0HDtYp4EY2Lo5At8iyf44PD1zDioSPK7@dpg-d495uhchg0os738l1a50-a.virginia-postgres.render.com/sb_algo_db?sslmode=require")

PROP_MARKETS = [
    "player_points", "player_rebounds", "player_assists", "player_threes",
    "player_points_rebounds_assists", "player_points_rebounds",
    "player_points_assists", "player_rebounds_assists",
    "player_blocks", "player_steals", "player_turnovers"
]

def create_props_table(engine):
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS player_props (
                id SERIAL PRIMARY KEY,
                event_id VARCHAR(100),
                game_date DATE,
                home_team VARCHAR(100),
                away_team VARCHAR(100),
                sportsbook VARCHAR(50),
                market VARCHAR(50),
                player_name VARCHAR(100),
                line DECIMAL(5,2),
                over_odds INTEGER,
                under_odds INTEGER,
                updated_at TIMESTAMP DEFAULT NOW(),
                UNIQUE(event_id, sportsbook, market, player_name)
            )
        """))
        conn.commit()
    print("✅ player_props table ready")

def fetch_todays_events():
    url = "https://api.the-odds-api.com/v4/sports/basketball_nba/events"
    response = requests.get(url, params={"apiKey": ODDS_API_KEY})
    if response.status_code != 200:
        print(f"❌ Error: {response.status_code}")
        return []
    events = response.json()
    print(f"📅 Found {len(events)} NBA games")
    print(f"   Credits remaining: {response.headers.get('x-requests-remaining')}")
    return events

def fetch_props_for_event(event_id, home_team, away_team):
    url = f"https://api.the-odds-api.com/v4/sports/basketball_nba/events/{event_id}/odds"
    params = {
        "apiKey": ODDS_API_KEY,
        "regions": "us,us2",
        "markets": ",".join(PROP_MARKETS),
        "oddsFormat": "american"
    }
    response = requests.get(url, params=params)
    remaining = response.headers.get('x-requests-remaining', '?')
    
    if response.status_code != 200:
        return [], remaining
    
    data = response.json()
    props = []
    
    for book in data.get('bookmakers', []):
        book_name = book.get('title')
        for market in book.get('markets', []):
            market_key = market.get('key')
            player_lines = {}
            
            for outcome in market.get('outcomes', []):
                player = outcome.get('description', '')
                if not player:
                    continue
                if player not in player_lines:
                    player_lines[player] = {'line': None, 'over': None, 'under': None}
                
                if outcome.get('name') == 'Over':
                    player_lines[player]['over'] = outcome.get('price')
                    player_lines[player]['line'] = outcome.get('point')
                elif outcome.get('name') == 'Under':
                    player_lines[player]['under'] = outcome.get('price')
            
            for player, d in player_lines.items():
                props.append({
                    'event_id': event_id, 'home_team': home_team, 'away_team': away_team,
                    'sportsbook': book_name, 'market': market_key, 'player_name': player,
                    'line': d['line'], 'over_odds': d['over'], 'under_odds': d['under']
                })
    
    return props, remaining

def save_props_to_db(engine, props, game_date):
    if not props:
        return 0
    inserted = 0
    with engine.connect() as conn:
        for p in props:
            try:
                conn.execute(text("""
                    INSERT INTO player_props 
                    (event_id, game_date, home_team, away_team, sportsbook, market, player_name, line, over_odds, under_odds)
                    VALUES (:event_id, :game_date, :home_team, :away_team, :sportsbook, :market, :player_name, :line, :over_odds, :under_odds)
                    ON CONFLICT (event_id, sportsbook, market, player_name) 
                    DO UPDATE SET line = :line, over_odds = :over_odds, under_odds = :under_odds, updated_at = NOW()
                """), {'event_id': p['event_id'], 'game_date': game_date, 'home_team': p['home_team'],
                       'away_team': p['away_team'], 'sportsbook': p['sportsbook'], 'market': p['market'],
                       'player_name': p['player_name'], 'line': p['line'], 'over_odds': p['over_odds'],
                       'under_odds': p['under_odds']})
                inserted += 1
            except:
                pass
        conn.commit()
    return inserted

def main():
    print("=" * 60)
    print("🏀 PLAYER PROPS FETCHER")
    print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    engine = create_engine(DATABASE_URL)
    create_props_table(engine)
    
    events = fetch_todays_events()
    if not events:
        return
    
    today = datetime.now().date()
    total_props = 0
    
    for i, event in enumerate(events, 1):
        event_id = event['id']
        home = event['home_team']
        away = event['away_team']
        
        print(f"\n🏀 [{i}/{len(events)}] {away} @ {home}")
        props, remaining = fetch_props_for_event(event_id, home, away)
        
        if props:
            saved = save_props_to_db(engine, props, today)
            total_props += saved
            players = len(set(p['player_name'] for p in props))
            books = len(set(p['sportsbook'] for p in props))
            print(f"   ✅ {saved} props | {players} players | {books} books")
        else:
            print(f"   ⚠️ No props available")
        print(f"   📊 Credits remaining: {remaining}")
    
    print(f"\n{'='*60}")
    print(f"✅ TOTAL: {total_props} props saved to database")
    print("=" * 60)

if __name__ == "__main__":
    main()
