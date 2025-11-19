#!/usr/bin/env python3
"""
SUPER SIMPLE NBA DAILY UPDATE
Just paste data from Basketball Reference!
"""

import sys
import os
from datetime import datetime, timedelta
from sqlalchemy import create_engine, text
import hashlib

DATABASE_URL = 'postgresql://sb_algo_db_user:0HDtYp4EY2Lo5At8iyf44PD1zDioSPK7@dpg-d495uhchg0os738l1a50-a.virginia-postgres.render.com/sb_algo_db?sslmode=require'

def get_date():
    date_str = input("Enter date YYYY-MM-DD (or press Enter for yesterday): ").strip()
    if date_str:
        return datetime.strptime(date_str, '%Y-%m-%d').date()
    return (datetime.now() - timedelta(days=1)).date()

def parse_games(text, date):
    """Parse Basketball Reference games - handles their weird format"""
    games = []
    for line in text.strip().split('\n'):
        if 'Visitor' in line or not line.strip():
            continue
        
        # Split by tabs or multiple spaces
        parts = line.replace('\t', '    ').split('    ')
        parts = [p.strip() for p in parts if p.strip()]
        
        # Find pattern: TeamName Score TeamName Score
        visitor, v_pts, home, h_pts = None, None, None, None
        
        for i, p in enumerate(parts):
            if not visitor and len(p) > 3 and not p.isdigit() and ':' not in p:
                visitor = p
            elif visitor and not v_pts and p.isdigit():
                v_pts = int(p)
            elif v_pts and not home and len(p) > 3 and not p.isdigit():
                home = p
            elif home and not h_pts and p.isdigit():
                h_pts = int(p)
                games.append({
                    'date': date,
                    'visitor_team': visitor,
                    'visitor_pts': v_pts, 
                    'home_team': home,
                    'home_pts': h_pts
                })
                break
    return games

def parse_boxscores(text, date):
    """Parse Basketball Reference boxscores"""
    players = []
    for line in text.strip().split('\n'):
        if 'Player' in line or 'Rk' in line or not line.strip():
            continue
            
        parts = line.split('\t')
        if len(parts) < 25:
            continue
            
        try:
            def safe_num(idx, default=0):
                try:
                    val = parts[idx].strip() if idx < len(parts) else ""
                    return float(val) if val and val != '-' else default
                except:
                    return default
            
            player = {
                'game_date': date,
                'player_name': parts[1].strip(),
                'team_abbreviation': parts[2].strip(),
                'min': parts[6].strip() if len(parts) > 6 else "0:00",
                'pts': safe_num(24),
                'reb': safe_num(18),
                'ast': safe_num(19),
                'stl': safe_num(20),
                'blk': safe_num(21),
                'fgm': safe_num(7),
                'fga': safe_num(8),
                'fg_pct': safe_num(9),
                'fg3m': safe_num(10),
                'fg3a': safe_num(11),
                'ftm': safe_num(13),
                'fta': safe_num(14),
                'oreb': safe_num(16),
                'dreb': safe_num(17),
                'TO': safe_num(22),
                'pf': safe_num(23),
                'plus_minus': safe_num(25)
            }
            players.append(player)
        except:
            continue
    
    return players

def main():
    print("\n🏀 NBA DAILY UPDATE")
    print("="*50)
    
    date = get_date()
    print(f"📅 Updating for: {date}\n")
    
    engine = create_engine(DATABASE_URL)
    
    # Get games
    print("STEP 1: Copy and paste the games table from Basketball Reference")
    print("(paste all, then press Enter twice)\n")
    
    lines = []
    empty = 0
    while empty < 2:
        line = input()
        if not line:
            empty += 1
        else:
            empty = 0
            lines.append(line)
    
    games = parse_games('\n'.join(lines), date)
    print(f"\n✅ Found {len(games)} games")
    
    # Insert games
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM games WHERE date = :date"), {"date": date})
        for game in games:
            conn.execute(text("""
                INSERT INTO games (date, visitor_team, visitor_pts, home_team, home_pts)
                VALUES (:date, :visitor_team, :visitor_pts, :home_team, :home_pts)
            """), game)
    
    for g in games:
        print(f"  {g['visitor_team']} {g['visitor_pts']} @ {g['home_team']} {g['home_pts']}")
    
    # Get boxscores
    print("\nSTEP 2: Copy and paste the boxscores table")
    print("(paste all, then press Enter twice)\n")
    
    lines = []
    empty = 0
    while empty < 2:
        line = input()
        if not line:
            empty += 1
        else:
            empty = 0
            lines.append(line)
    
    players = parse_boxscores('\n'.join(lines), date)
    print(f"\n✅ Found {len(players)} player stats")
    
    # Generate season
    season = f"{date.year}-{str((date.year + 1) % 100).zfill(2)}"
    if date.month < 7:
        season = f"{date.year - 1}-{str(date.year % 100).zfill(2)}"
    
    # Insert boxscores
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM player_boxscores WHERE game_date = :date"), {"date": date})
        
        for p in players:
            # Generate IDs
            game_id = int(hashlib.md5(f"{date}_{p['team_abbreviation']}".encode()).hexdigest()[:15], 16)
            team_id = int(hashlib.md5(p['team_abbreviation'].encode()).hexdigest()[:15], 16)
            player_id = int(hashlib.md5(f"{p['player_name']}_{date}".encode()).hexdigest()[:15], 16)
            
            conn.execute(text("""
                INSERT INTO player_boxscores (
                    game_id, team_id, team_abbreviation, player_id, player_name,
                    min, pts, reb, ast, stl, blk, fgm, fga, fg_pct, fg3m, fg3a,
                    ftm, fta, oreb, dreb, "TO", pf, plus_minus,
                    season, game_date
                ) VALUES (
                    :game_id, :team_id, :team_abbreviation, :player_id, :player_name,
                    :min, :pts, :reb, :ast, :stl, :blk, :fgm, :fga, :fg_pct, :fg3m, :fg3a,
                    :ftm, :fta, :oreb, :dreb, :TO, :pf, :plus_minus,
                    :season, :game_date
                )
            """), {**p, 'game_id': game_id, 'team_id': team_id, 'player_id': player_id, 'season': season})
    
    # Verify
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT team_abbreviation, COUNT(*) as players, SUM(pts)::int as pts
            FROM player_boxscores
            WHERE game_date = :date
            GROUP BY team_abbreviation
            ORDER BY team_abbreviation
        """), {"date": date})
        
        print("\n📊 Team totals:")
        for team, players, pts in result:
            print(f"  {team}: {pts} points ({players} players)")
    
    print(f"\n✅ DONE! Updated {date} with {len(games)} games and {len(players)} players")

if __name__ == "__main__":
    main()
