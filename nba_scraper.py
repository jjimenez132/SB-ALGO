#!/usr/bin/env python3
"""
NBA Scraper - Obtiene juegos y boxscores automáticamente
Sin API key, 100% gratis
"""

import requests
import psycopg2
from datetime import datetime, timedelta
import json
import re

DATABASE_URL = 'postgresql://sb_algo_db_user:0HDtYp4EY2Lo5At8iyf44PD1zDioSPK7@dpg-d495uhchg0os738l1a50-a.virginia-postgres.render.com/sb_algo_db?sslmode=require'

def scrape_nba_games(date_str):
    """Scrape games desde CBS Sports (más fácil de parsear)"""
    print(f"🕷️ Scraping juegos del {date_str}...")
    
    # CBS Sports API endpoint (público, no requiere key)
    formatted_date = date_str.replace('-', '')
    url = f"https://www.cbssports.com/nba/scoreboard/all/{formatted_date}/ajax"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        'Accept': 'application/json'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        
        # CBS devuelve HTML con JSON embebido
        # Buscar el JSON en el HTML
        json_pattern = r'window\.initialState\s*=\s*({.*?});'
        match = re.search(json_pattern, response.text)
        
        if match:
            data = json.loads(match.group(1))
            return parse_cbs_data(data, date_str)
    except:
        pass
    
    # Backup: ESPN endpoint alternativo
    return scrape_espn_backup(date_str)

def scrape_espn_backup(date_str):
    """Backup: ESPN web API"""
    print("  Intentando ESPN como backup...")
    
    formatted_date = date_str.replace('-', '')
    url = f"https://cdn.espn.com/core/nba/scoreboard?xhr=1&date={formatted_date}"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)',
        'Referer': 'https://www.espn.com/'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            
            games = []
            for game in data.get('content', {}).get('sbData', {}).get('events', []):
                competitions = game.get('competitions', [{}])[0]
                competitors = competitions.get('competitors', [])
                
                if len(competitors) == 2:
                    home = competitors[0]
                    away = competitors[1]
                    
                    games.append({
                        'date': date_str,
                        'home_team': home.get('team', {}).get('displayName', ''),
                        'home_score': int(home.get('score', 0)),
                        'away_team': away.get('team', {}).get('displayName', ''),
                        'away_score': int(away.get('score', 0))
                    })
            
            return games
    except Exception as e:
        print(f"  Error ESPN: {e}")
    
    return []

def scrape_boxscores(date_str):
    """Intenta obtener boxscores básicos"""
    print(f"📊 Scraping boxscores...")
    
    # NBA.com endpoint (a veces funciona sin auth)
    url = f"https://stats.nba.com/stats/leaguegamelog?Counter=0&DateFrom={date_str}&DateTo={date_str}&Direction=DESC&LeagueID=00&PlayerOrTeam=P&Season=2024-25&SeasonType=Regular+Season&Sorter=PTS"
    
    headers = {
        'User-Agent': 'Mozilla/5.0',
        'Accept': 'application/json',
        'Referer': 'https://www.nba.com/',
        'x-nba-stats-origin': 'stats',
        'x-nba-stats-token': 'true'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            
            players = []
            for row in data.get('resultSets', [{}])[0].get('rowSet', [])[:50]:  # Top 50 performances
                players.append({
                    'player_name': row[2],  # PLAYER_NAME
                    'team': row[4],  # TEAM_ABBREVIATION
                    'points': row[26],  # PTS
                    'rebounds': row[18],  # REB
                    'assists': row[19]  # AST
                })
            
            return players
    except:
        pass
    
    return []

def save_to_db(games, boxscores, date_str):
    """Guardar en la base de datos"""
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    
    # Guardar juegos
    games_saved = 0
    for game in games:
        try:
            cur.execute("""
                INSERT INTO games (date, visitor_team, visitor_pts, home_team, home_pts)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT DO NOTHING
            """, (
                game['date'],
                game['away_team'],
                game['away_score'],
                game['home_team'],
                game['home_score']
            ))
            games_saved += 1
        except:
            pass
    
    # Guardar boxscores
    stats_saved = 0
    for player in boxscores:
        try:
            cur.execute("""
                INSERT INTO player_boxscores 
                (game_date, player_name, team_abbreviation, pts, reb, ast)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT DO NOTHING
            """, (
                date_str,
                player['player_name'],
                player['team'],
                player['points'],
                player['rebounds'],
                player['assists']
            ))
            stats_saved += 1
        except:
            pass
    
    conn.commit()
    cur.close()
    conn.close()
    
    return games_saved, stats_saved

def main():
    """Función principal"""
    yesterday = (datetime.now() - timedelta(days=1))
    date_str = yesterday.strftime('%Y-%m-%d')
    
    print(f"🏀 NBA SCRAPER - {date_str}")
    print("=" * 40)
    
    # Scrape juegos
    games = scrape_nba_games(date_str)
    
    if games:
        print(f"✅ Encontrados {len(games)} juegos:")
        for g in games:
            print(f"  {g['away_team']} {g['away_score']} @ {g['home_team']} {g['home_score']}")
    else:
        print("❌ No se encontraron juegos")
    
    # Scrape boxscores
    boxscores = scrape_boxscores(date_str)
    
    if boxscores:
        print(f"\n📊 Top 5 performances:")
        for p in boxscores[:5]:
            print(f"  {p['player_name']} ({p['team']}): {p['points']} pts")
    
    # Guardar en DB
    if games or boxscores:
        games_saved, stats_saved = save_to_db(games, boxscores, date_str)
        print(f"\n💾 Guardados: {games_saved} juegos, {stats_saved} stats")
    
    print("\n✅ Scraper completado")

if __name__ == "__main__":
    main()
