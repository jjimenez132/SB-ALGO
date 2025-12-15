"""Backfill missing player stats with proper error handling"""
import os
import requests
from datetime import datetime
from sqlalchemy import create_engine, text

DATABASE_URL = os.environ.get('DATABASE_URL')
engine = create_engine(DATABASE_URL)

HEADERS = {
    "x-rapidapi-host": "tank01-fantasy-stats.p.rapidapi.com",
    "x-rapidapi-key": "ada93da8e5msh75c5342a07b643cp1b45fajsn72f3bfcd3653"
}

TEAM_MAP = {
    'SA': 'SAS', 'GS': 'GSW', 'NY': 'NYK', 'NO': 'NOP', 'PHO': 'PHX', 'UTAH': 'UTA'
}

def safe_float(val):
    try: return float(val) if val else 0.0
    except: return 0.0

def game_string_to_bigint(s):
    return int(''.join(filter(str.isdigit, s[:8])))

def fetch_and_insert_stats(date_str):
    date_obj = datetime.strptime(date_str, "%Y%m%d").date()
    print(f"\n📅 Processing {date_obj}...")
    
    # Get games
    url = "https://tank01-fantasy-stats.p.rapidapi.com/getNBAGamesForDate"
    response = requests.get(url, headers=HEADERS, params={"gameDate": date_str})
    games = response.json().get('body', [])
    
    if not games:
        print("   No games found")
        return 0
    
    inserted = 0
    skipped = 0
    
    for game in games:
        game_id_str = game.get('gameID')
        game_id_int = game_string_to_bigint(game_id_str)
        
        # Get boxscore
        box_url = "https://tank01-fantasy-stats.p.rapidapi.com/getNBABoxScore"
        box_response = requests.get(box_url, headers=HEADERS, params={"gameID": game_id_str})
        box_data = box_response.json().get('body', {})
        
        player_stats = box_data.get('playerStats', {})
        
        for player_id_str, stats in player_stats.items():
            team = TEAM_MAP.get(stats.get('team'), stats.get('team'))
            fgm, fga = safe_float(stats.get('fgm')), safe_float(stats.get('fga'))
            fg3m = safe_float(stats.get('tptfgm') or stats.get('threePtMade'))
            fg3a = safe_float(stats.get('tptfga') or stats.get('threePtAtt'))
            ftm, fta = safe_float(stats.get('ftm')), safe_float(stats.get('fta'))
            
            p = {
                'game_id': game_id_int, 'player_id': int(player_id_str),
                'player_name': stats.get('longName', 'Unknown'), 'team_abbreviation': team,
                'game_date': date_obj, 'pts': safe_float(stats.get('pts')),
                'reb': safe_float(stats.get('reb')), 'ast': safe_float(stats.get('ast')),
                'stl': safe_float(stats.get('stl')), 'blk': safe_float(stats.get('blk')),
                'fgm': fgm, 'fga': fga, 'fg_pct': round(fgm/fga,3) if fga>0 else None,
                'fg3m': fg3m, 'fg3a': fg3a, 'fg3_pct': round(fg3m/fg3a,3) if fg3a>0 else None,
                'ftm': ftm, 'fta': fta, 'ft_pct': round(ftm/fta,3) if fta>0 else None,
                'oreb': safe_float(stats.get('offReb')), 'dreb': safe_float(stats.get('defReb')),
                'pf': safe_float(stats.get('pf')), 'tov': safe_float(stats.get('TOV')),
                'plus_minus': safe_float(stats.get('plusMinus')),
                'min': str(stats.get('mins', '0'))
            }
            
            try:
                with engine.connect() as conn:
                    # Check if exists
                    exists = conn.execute(text(
                        "SELECT 1 FROM player_boxscores WHERE game_id=:gid AND player_id=:pid"
                    ), {'gid': game_id_int, 'pid': int(player_id_str)}).fetchone()
                    
                    if exists:
                        skipped += 1
                        continue
                    
                    conn.execute(text("""
                        INSERT INTO player_boxscores 
                        (game_id, player_id, player_name, team_abbreviation, game_date, 
                         pts, reb, ast, stl, blk, fgm, fga, fg_pct, fg3m, fg3a, fg3_pct,
                         ftm, fta, ft_pct, oreb, dreb, pf, "TO", plus_minus, min, season)
                        VALUES (:game_id, :player_id, :player_name, :team_abbreviation, :game_date,
                         :pts, :reb, :ast, :stl, :blk, :fgm, :fga, :fg_pct, :fg3m, :fg3a, :fg3_pct,
                         :ftm, :fta, :ft_pct, :oreb, :dreb, :pf, :tov, :plus_minus, :min, '2025-26')
                    """), p)
                    conn.commit()
                    inserted += 1
            except Exception as e:
                print(f"   ❌ Error for {stats.get('longName')}: {e}")
    
    print(f"   ✅ Inserted: {inserted}, Skipped (exists): {skipped}")
    return inserted

# Run for missing days
for date_str in ["20251206", "20251207", "20251208", "20251209", "20251214"]:
    fetch_and_insert_stats(date_str)

print("\n🎉 Done!")
