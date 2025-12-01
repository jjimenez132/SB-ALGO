#!/usr/bin/env python3
"""
Daily NBA Data Update Script
Runs at 5:00 AM ET to pull:
1. Yesterday's final game scores
2. Yesterday's player box scores  
3. Today's schedule (games without scores)
"""

import requests
from sqlalchemy import create_engine, text
from datetime import datetime, timedelta
import hashlib
import os

# Configuration
API_KEY = "ada93da8e5msh75c5342a07b643cp1b45fajsn72f3bfcd3653"
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
    "PHO": "PHX", "PHX": "PHX", "POR": "POR", "SA": "SAS", "SAS": "SAS",
    "SAC": "SAC", "TOR": "TOR", "UTA": "UTA", "WAS": "WAS"
}

def game_string_to_bigint(s):
    """Convert game string like '20251129_BKN@MIL' to bigint"""
    return int(hashlib.md5(s.encode()).hexdigest()[:15], 16)

def safe_float(val):
    try:
        return float(val) if val else 0.0
    except:
        return 0.0

def fetch_games_for_date(date_str):
    """Fetch games for a specific date (format: YYYYMMDD)"""
    url = "https://tank01-fantasy-stats.p.rapidapi.com/getNBAGamesForDate"
    response = requests.get(url, headers=HEADERS, params={"gameDate": date_str})
    
    if response.status_code != 200:
        print(f"  ❌ Error fetching games for {date_str}: {response.status_code}")
        return []
    
    return response.json().get('body', [])

def fetch_boxscore(game_id):
    """Fetch box score for a specific game"""
    url = "https://tank01-fantasy-stats.p.rapidapi.com/getNBABoxScore"
    response = requests.get(url, headers=HEADERS, params={"gameID": game_id})
    
    if response.status_code != 200:
        print(f"  ❌ Error fetching boxscore for {game_id}: {response.status_code}")
        return None
    
    return response.json().get('body', {})

def update_games_with_scores(engine, date_str, date_obj):
    """Update games table with final scores"""
    print(f"\n📥 Fetching games for {date_str}...")
    games = fetch_games_for_date(date_str)
    
    if not games:
        print("   No games found")
        return 0
    
    updated = 0
    for game in games:
        game_id = game.get('gameID') or game.get('gameId')
        home = TEAM_MAP.get(game.get('home'), game.get('home'))
        away = TEAM_MAP.get(game.get('away'), game.get('away'))
        
        # Get boxscore for final scores
        box_data = fetch_boxscore(game_id)
        if not box_data:
            continue
        
        home_pts = int(box_data.get('homePts', 0) or 0)
        away_pts = int(box_data.get('awayPts', 0) or 0)
        
        if home_pts == 0 and away_pts == 0:
            print(f"   ⏳ {away} @ {home}: Game not finished")
            continue
        
        total_points = home_pts + away_pts
        margin_home = home_pts - away_pts
        home_win = 1 if home_pts > away_pts else 0
        
        with engine.connect() as conn:
            # Try update first
            result = conn.execute(text("""
                UPDATE games SET 
                    home_pts = :home_pts, visitor_pts = :away_pts,
                    total_points = :total, margin_home = :margin, home_win = :home_win
                WHERE date = :date AND home_team = :home AND visitor_team = :away
            """), {"home_pts": home_pts, "away_pts": away_pts, "total": total_points,
                   "margin": margin_home, "home_win": home_win,
                   "date": date_obj, "home": home, "away": away})
            
            if result.rowcount == 0:
                # Insert if doesn't exist
                conn.execute(text("""
                    INSERT INTO games (date, home_team, visitor_team, home_pts, visitor_pts, 
                                      total_points, margin_home, home_win)
                    VALUES (:date, :home, :away, :home_pts, :away_pts, :total, :margin, :home_win)
                """), {"date": date_obj, "home": home, "away": away, "home_pts": home_pts,
                       "away_pts": away_pts, "total": total_points, "margin": margin_home,
                       "home_win": home_win})
            
            conn.commit()
            updated += 1
            print(f"   ✅ {away} @ {home}: {away_pts}-{home_pts}")
    
    return updated

def update_player_stats(engine, date_str, date_obj):
    """Update player_boxscores table"""
    print(f"\n📥 Fetching player stats for {date_str}...")
    games = fetch_games_for_date(date_str)
    
    if not games:
        return 0
    
    inserted = 0
    for game in games:
        game_id_str = game.get('gameID') or game.get('gameId')
        game_id_int = game_string_to_bigint(game_id_str)
        
        box_data = fetch_boxscore(game_id_str)
        if not box_data:
            continue
        
        player_stats = box_data.get('playerStats', {})
        if not player_stats:
            continue
        
        for player_id_str, stats in player_stats.items():
            team = TEAM_MAP.get(stats.get('team'), stats.get('team'))
            
            fgm = safe_float(stats.get('fgm', 0))
            fga = safe_float(stats.get('fga', 0))
            fg3m = safe_float(stats.get('tptfgm', 0) or stats.get('threePtMade', 0))
            fg3a = safe_float(stats.get('tptfga', 0) or stats.get('threePtAtt', 0))
            ftm = safe_float(stats.get('ftm', 0))
            fta = safe_float(stats.get('fta', 0))
            
            player_data = {
                'game_id': game_id_int,
                'player_id': int(player_id_str),
                'player_name': stats.get('longName', stats.get('name', 'Unknown')),
                'team_abbreviation': team,
                'game_date': date_obj,
                'pts': safe_float(stats.get('pts', 0)),
                'reb': safe_float(stats.get('reb', 0)),
                'ast': safe_float(stats.get('ast', 0)),
                'stl': safe_float(stats.get('stl', 0)),
                'blk': safe_float(stats.get('blk', 0)),
                'fgm': fgm,
                'fga': fga,
                'fg_pct': round(fgm / fga, 3) if fga > 0 else None,
                'fg3m': fg3m,
                'fg3a': fg3a,
                'fg3_pct': round(fg3m / fg3a, 3) if fg3a > 0 else None,
                'ftm': ftm,
                'fta': fta,
                'ft_pct': round(ftm / fta, 3) if fta > 0 else None,
                'oreb': safe_float(stats.get('offReb', 0) or stats.get('oreb', 0)),
                'dreb': safe_float(stats.get('defReb', 0) or stats.get('dreb', 0)),
                'pf': safe_float(stats.get('pf', 0)),
                'tov': safe_float(stats.get('TOV', 0)),
                'plus_minus': safe_float(stats.get('plusMinus', 0)),
                'min': str(stats.get('mins', stats.get('min', '0'))),
            }
            
            try:
                with engine.connect() as conn:
                    conn.execute(text("""
                        INSERT INTO player_boxscores 
                        (game_id, player_id, player_name, team_abbreviation, game_date, 
                         pts, reb, ast, stl, blk, fgm, fga, fg_pct, fg3m, fg3a, fg3_pct,
                         ftm, fta, ft_pct, oreb, dreb, pf, "TO", plus_minus, min, season)
                        VALUES 
                        (:game_id, :player_id, :player_name, :team_abbreviation, :game_date,
                         :pts, :reb, :ast, :stl, :blk, :fgm, :fga, :fg_pct, :fg3m, :fg3a, :fg3_pct,
                         :ftm, :fta, :ft_pct, :oreb, :dreb, :pf, :tov, :plus_minus, :min, '2025-26')
                    """), player_data)
                    conn.commit()
                    inserted += 1
            except Exception as e:
                if 'duplicate' not in str(e).lower():
                    print(f"   ⚠️ Error inserting {player_data['player_name']}: {str(e)[:50]}")
    
    print(f"   ✅ Inserted {inserted} player stats")
    return inserted

def add_todays_schedule(engine, date_str, date_obj):
    """Add today's games to schedule (without scores)"""
    print(f"\n📅 Adding today's schedule ({date_str})...")
    games = fetch_games_for_date(date_str)
    
    if not games:
        print("   No games scheduled")
        return 0
    
    added = 0
    for game in games:
        home = TEAM_MAP.get(game.get('home'), game.get('home'))
        away = TEAM_MAP.get(game.get('away'), game.get('away'))
        
        with engine.connect() as conn:
            # Check if exists
            result = conn.execute(text("""
                SELECT 1 FROM games WHERE date = :date AND home_team = :home AND visitor_team = :away
            """), {"date": date_obj, "home": home, "away": away})
            
            if not result.fetchone():
                conn.execute(text("""
                    INSERT INTO games (date, home_team, visitor_team, home_pts, visitor_pts, 
                                      total_points, margin_home, home_win)
                    VALUES (:date, :home, :away, 0, 0, 0, 0, 0)
                """), {"date": date_obj, "home": home, "away": away})
                conn.commit()
                added += 1
                print(f"   📅 {away} @ {home}")
    
    print(f"   ✅ Added {added} games to schedule")
    return added

def main():
    print("=" * 50)
    print("🏀 NBA Daily Data Update")
    print(f"⏰ Run time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)
    
    engine = create_engine(DATABASE_URL)
    
    # Calculate dates
    today = datetime.now()
    yesterday = today - timedelta(days=1)
    
    today_str = today.strftime("%Y%m%d")
    yesterday_str = yesterday.strftime("%Y%m%d")
    
    today_date = today.date()
    yesterday_date = yesterday.date()
    
    # 1. Update yesterday's games with final scores
    games_updated = update_games_with_scores(engine, yesterday_str, yesterday_date)
    print(f"\n📊 Games updated: {games_updated}")
    
    # 2. Update yesterday's player stats
    players_inserted = update_player_stats(engine, yesterday_str, yesterday_date)
    print(f"📊 Player stats inserted: {players_inserted}")
    
    # 3. Add today's schedule
    schedule_added = add_todays_schedule(engine, today_str, today_date)
    print(f"📊 Today's games added: {schedule_added}")
    
    print("\n" + "=" * 50)
    print("✅ Daily update complete!")
    print("=" * 50)

if __name__ == "__main__":
    main()
