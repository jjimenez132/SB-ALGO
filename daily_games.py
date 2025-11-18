import requests
import psycopg2
import os
from datetime import datetime, timedelta

DATABASE_URL = os.environ.get('DATABASE_URL', 'postgresql://sb_algo_db_user:0HDtYp4EY2Lo5At8iyf44PD1zDioSPK7@dpg-d495uhchg0os738l1a50-a.virginia-postgres.render.com/sb_algo_db?sslmode=require')

yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y%m%d')

url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates={yesterday}"
games = requests.get(url).json()['events']

print(f"📥 {len(games)} games found")

conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()

for game in games:
    game_id = game['id']
    comps = game['competitions'][0]
    competitors = comps['competitors']
    
    home = next(c for c in competitors if c['homeAway'] == 'home')
    away = next(c for c in competitors if c['homeAway'] == 'away')
    
    cur.execute("""
        INSERT INTO games (date, visitor_team, visitor_pts, home_team, home_pts, season)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT DO NOTHING
    """, (
        yesterday[:4]+'-'+yesterday[4:6]+'-'+yesterday[6:],
        away['team']['displayName'],
        float(away.get('score', 0)),
        home['team']['displayName'],
        float(home.get('score', 0)),
        2025
    ))
    
    # Get boxscore
    box = requests.get(f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event={game_id}").json()
    
    count = 0
    for team_data in box.get('boxscore', {}).get('players', []):
        team = team_data['team']
        
        for stat_group in team_data.get('statistics', []):
            # Get stat names/keys mapping
            names = stat_group.get('names', [])
            keys = stat_group.get('keys', [])
            
            for player in stat_group.get('athletes', []):
                athlete = player['athlete']
                stats_array = player.get('stats', [])
                
                # Create dict from names and values
                stats_dict = {}
                for i, name in enumerate(names):
                    if i < len(stats_array):
                        stats_dict[name] = stats_array[i]
                
                # Parse stats
                pts = float(stats_dict.get('PTS', 0))
                reb = float(stats_dict.get('REB', 0))
                ast = float(stats_dict.get('AST', 0))
                stl = float(stats_dict.get('STL', 0))
                blk = float(stats_dict.get('BLK', 0))
                to = float(stats_dict.get('TO', 0))
                minutes = stats_dict.get('MIN', '0')
                plus_minus = stats_dict.get('+/-', '0')
                
                # Parse FG (3-7 format)
                fg = stats_dict.get('FG', '0-0').split('-')
                fgm = float(fg[0]) if len(fg) > 0 else 0
                fga = float(fg[1]) if len(fg) > 1 else 0
                
                # Parse 3PT
                three_pt = stats_dict.get('3PT', '0-0').split('-')
                fg3m = float(three_pt[0]) if len(three_pt) > 0 else 0
                fg3a = float(three_pt[1]) if len(three_pt) > 1 else 0
                
                # Parse FT
                ft = stats_dict.get('FT', '0-0').split('-')
                ftm = float(ft[0]) if len(ft) > 0 else 0
                fta = float(ft[1]) if len(ft) > 1 else 0
                
                cur.execute("""
                    INSERT INTO player_boxscores 
                    (game_id, player_id, team_id, team_abbreviation, player_name, min, pts, reb, ast, stl, blk, "TO", fgm, fga, fg3m, fg3a, ftm, fta, plus_minus, season)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (game_id, player_id) DO UPDATE SET
                    pts = EXCLUDED.pts, reb = EXCLUDED.reb, ast = EXCLUDED.ast
                """, (
                    int(game_id), int(athlete['id']), str(team['id']), team['abbreviation'],
                    athlete['displayName'], minutes, pts, reb, ast, stl, blk, to,
                    fgm, fga, fg3m, fg3a, ftm, fta, 
                    float(plus_minus) if plus_minus and plus_minus != '--' else 0, 
                    '2025-26'
                ))
                count += 1
    
    print(f"✅ {away['team']['abbreviation']}@{home['team']['abbreviation']}: {count} players")
    conn.commit()

cur.close()
conn.close()
print("🎉 DONE!")
