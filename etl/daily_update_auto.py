import os
import requests
from sqlalchemy import create_engine, text
import hashlib
from datetime import datetime, timedelta
import time

DATABASE_URL = os.environ['DATABASE_URL']
engine = create_engine(DATABASE_URL)

print("🏀 Daily Update - Fetching yesterday's games...")

yesterday = datetime.now() - timedelta(days=1)
date_str = yesterday.strftime('%Y%m%d')

print(f"📅 Date: {yesterday.strftime('%Y-%m-%d')}")

# Fetch games from ESPN
url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates={date_str}"
response = requests.get(url, timeout=15)

if response.status_code != 200:
    print("❌ Failed to fetch games")
    exit(1)

data = response.json()
games = data.get('events', [])

print(f"✅ Found {len(games)} games")

games_inserted = 0
players_inserted = 0

# Insert games
for game in games:
    try:
        game_id = game['id']
        game_date = yesterday.date()
        
        competitions = game.get('competitions', [{}])[0]
        competitors = competitions.get('competitors', [])
        
        if len(competitors) < 2:
            continue
        
        home_team = next((c for c in competitors if c.get('homeAway') == 'home'), None)
        away_team = next((c for c in competitors if c.get('homeAway') == 'away'), None)
        
        if not home_team or not away_team:
            continue
        
        home_pts = float(home_team.get('score', 0))
        away_pts = float(away_team.get('score', 0))
        home_name = home_team['team']['displayName']
        away_name = away_team['team']['displayName']
        
        with engine.connect() as conn:
            conn.execute(text("""
                INSERT INTO games (date, visitor_team, visitor_pts, home_team, home_pts, season)
                VALUES (:date, :visitor_team, :visitor_pts, :home_team, :home_pts, :season)
                ON CONFLICT (date, visitor_team, home_team) DO UPDATE SET
                    visitor_pts = EXCLUDED.visitor_pts,
                    home_pts = EXCLUDED.home_pts
            """), {
                'date': game_date,
                'visitor_team': away_name,
                'visitor_pts': away_pts,
                'home_team': home_name,
                'home_pts': home_pts,
                'season': 2026
            })
            conn.commit()
            games_inserted += 1
    
    except Exception as e:
        print(f"Error: {e}")
        continue

print(f"✅ Inserted {games_inserted} games")

# Fetch boxscores
for game in games:
    game_id = game['id']
    
    try:
        box_url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event={game_id}"
        box_response = requests.get(box_url, timeout=15)
        
        if box_response.status_code != 200:
            continue
        
        box_data = box_response.json()
        
        if 'boxscore' not in box_data or 'players' not in box_data['boxscore']:
            continue
        
        for team_data in box_data['boxscore']['players']:
            team_abbr = team_data['team']['abbreviation']
            team_id = team_data['team']['id']
            
            stat_category = team_data['statistics'][0]
            athletes = stat_category.get('athletes', [])
            
            for player_data in athletes:
                try:
                    athlete = player_data['athlete']
                    player_name = athlete['displayName']
                    player_id_espn = athlete['id']
                    
                    stats = player_data.get('stats', [])
                    
                    if not stats or len(stats) < 14:
                        continue
                    
                    pts = float(stats[0])
                    fg, fg3, ft = stats[1], stats[2], stats[3]
                    reb, ast, to = float(stats[4]), float(stats[5]), float(stats[6])
                    stl, blk = float(stats[7]), float(stats[8])
                    minutes = stats[12]
                    plus_minus = float(stats[13]) if stats[13] else 0
                    
                    fgm, fga = 0, 0
                    if '-' in str(fg):
                        parts = str(fg).split('-')
                        fgm, fga = float(parts[0]), float(parts[1])
                    
                    fg3m, fg3a = 0, 0
                    if '-' in str(fg3):
                        parts = str(fg3).split('-')
                        fg3m, fg3a = float(parts[0]), float(parts[1])
                    
                    ftm, fta = 0, 0
                    if '-' in str(ft):
                        parts = str(ft).split('-')
                        ftm, fta = float(parts[0]), float(parts[1])
                    
                    game_hash_hex = hashlib.md5(f"{yesterday.date()}_{game_id}".encode()).hexdigest()[:16]
                    player_hash_hex = hashlib.md5(f"{player_id_espn}_{game_id}".encode()).hexdigest()[:16]
                    
                    game_id_int = int(game_hash_hex, 16)
                    player_id_int = int(player_hash_hex, 16)
                    
                    with engine.connect() as conn:
                        conn.execute(text("""
                            INSERT INTO player_boxscores (
                                game_id, player_id, team_id, team_abbreviation,
                                player_name, min, pts, reb, ast, stl, blk, 
                                "TO", fgm, fga, fg3m, fg3a, ftm, fta, 
                                plus_minus, season
                            ) VALUES (
                                :game_id, :player_id, :team_id, :team_abbreviation,
                                :player_name, :min, :pts, :reb, :ast, :stl, :blk,
                                :to, :fgm, :fga, :fg3m, :fg3a, :ftm, :fta,
                                :plus_minus, :season
                            ) ON CONFLICT (game_id, player_id) DO NOTHING
                        """), {
                            'game_id': game_id_int,
                            'player_id': player_id_int,
                            'team_id': str(team_id),
                            'team_abbreviation': team_abbr,
                            'player_name': player_name,
                            'min': str(minutes),
                            'pts': pts, 'reb': reb, 'ast': ast,
                            'stl': stl, 'blk': blk, 'to': to,
                            'fgm': fgm, 'fga': fga,
                            'fg3m': fg3m, 'fg3a': fg3a,
                            'ftm': ftm, 'fta': fta,
                            'plus_minus': plus_minus,
                            'season': '2026'
                        })
                        conn.commit()
                        players_inserted += 1
                
                except Exception as e:
                    continue
        
        time.sleep(0.5)
        
    except Exception as e:
        continue

print(f"✅ Inserted {players_inserted} player performances")
print(f"🎉 Daily update complete!")
