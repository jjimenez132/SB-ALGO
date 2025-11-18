import requests
import psycopg2
from datetime import datetime, timedelta
import os

DATABASE_URL = os.environ.get('DATABASE_URL', 'postgresql://sb_algo_db_user:0HDtYp4EY2Lo5At8iyf44PD1zDioSPK7@dpg-d495uhchg0os738l1a50-a.virginia-postgres.render.com/sb_algo_db?sslmode=require')

def fetch_yesterday_games():
    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y%m%d')
    url = f'https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates={yesterday}'
    
    response = requests.get(url)
    data = response.json()
    
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    
    games = data.get('events', [])
    print(f"📥 {len(games)} games found")
    
    for game in games:
        game_id = game['id']
        game_date_str = game['date'][:10]
        
        competitions = game.get('competitions', [])
        if not competitions:
            continue
            
        comp = competitions[0]
        home_team = next((t for t in comp['competitors'] if t['homeAway'] == 'home'), None)
        away_team = next((t for t in comp['competitors'] if t['homeAway'] == 'away'), None)
        
        if not home_team or not away_team:
            continue
        
        visitor_name = away_team['team']['displayName']
        home_name = home_team['team']['displayName']
        visitor_score = float(away_team.get('score', 0))
        home_score = float(home_team.get('score', 0))
        
        game_dt = datetime.strptime(game_date_str, '%Y-%m-%d')
        if game_dt.month >= 10:
            season = game_dt.year
        else:
            season = game_dt.year - 1
        
        season_str = f"{season}-{str(season+1)[-2:]}"
        
        cur.execute("""
            INSERT INTO games (date, visitor_team, visitor_pts, home_team, home_pts, season)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (date, visitor_team, home_team) DO NOTHING
        """, (game_date_str, visitor_name, visitor_score, home_name, home_score, season))
        
        boxscore_url = f'https://site.web.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event={game_id}'
        box_response = requests.get(boxscore_url)
        box_data = box_response.json()
        
        players_count = 0
        
        if 'boxscore' in box_data and 'players' in box_data['boxscore']:
            for team in box_data['boxscore']['players']:
                team_name = team['team']['displayName']
                team_abbr = team['team']['abbreviation']
                
                for player in team.get('statistics', [{}])[0].get('athletes', []):
                    player_name = player['athlete']['displayName']
                    player_id = player['athlete']['id']
                    stats = player.get('stats', [])
                    
                    if not stats or len(stats) < 15:
                        continue
                    
                    minutes = stats[0] if stats[0] != '--' else '0'
                    pts = float(stats[14]) if stats[14] != '--' else 0
                    reb = float(stats[12]) if stats[12] != '--' else 0
                    ast = float(stats[13]) if stats[13] != '--' else 0
                    stl = float(stats[6]) if stats[6] != '--' else 0
                    blk = float(stats[7]) if stats[7] != '--' else 0
                    to = float(stats[8]) if stats[8] != '--' else 0
                    
                    fg = stats[1].split('-') if '-' in stats[1] else ['0', '0']
                    fgm = float(fg[0]) if fg[0] != '--' else 0
                    fga = float(fg[1]) if len(fg) > 1 and fg[1] != '--' else 0
                    
                    fg3 = stats[2].split('-') if '-' in stats[2] else ['0', '0']
                    fg3m = float(fg3[0]) if fg3[0] != '--' else 0
                    fg3a = float(fg3[1]) if len(fg3) > 1 and fg3[1] != '--' else 0
                    
                    ft = stats[3].split('-') if '-' in stats[3] else ['0', '0']
                    ftm = float(ft[0]) if ft[0] != '--' else 0
                    fta = float(ft[1]) if len(ft) > 1 and ft[1] != '--' else 0
                    
                    plus_minus = 0
                    
                    cur.execute("""
                        INSERT INTO player_boxscores 
                        (game_id, player_id, team_id, team_abbreviation, player_name, min,
                         pts, reb, ast, stl, blk, "TO", fgm, fga, fg3m, fg3a, ftm, fta,
                         plus_minus, season, game_date)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (game_id, player_id) DO NOTHING
                    """, (game_id, player_id, team_name, team_abbr, player_name, minutes,
                          pts, reb, ast, stl, blk, to, fgm, fga, fg3m, fg3a, ftm, fta,
                          plus_minus, season_str, game_date_str))
                    
                    players_count += 1
        
        conn.commit()
        print(f"✅ {away_team['team']['abbreviation']}@{home_team['team']['abbreviation']}: {players_count} players")
    
    cur.close()
    conn.close()
    print("🎉 DONE!")

if __name__ == '__main__':
    fetch_yesterday_games()
