#!/usr/bin/env python3
from datetime import datetime
from sqlalchemy import create_engine, text
import hashlib

DATABASE_URL = 'postgresql://sb_algo_db_user:0HDtYp4EY2Lo5At8iyf44PD1zDioSPK7@dpg-d495uhchg0os738l1a50-a.virginia-postgres.render.com/sb_algo_db?sslmode=require'
engine = create_engine(DATABASE_URL)

date_str = input("Date (YYYY-MM-DD): ")
date = datetime.strptime(date_str, '%Y-%m-%d').date()

print("\nPaste BOX SCORES, then type ENDBOX:\n")
box_lines = []
while True:
    line = input()
    if line.strip() == "ENDBOX":
        break
    box_lines.append(line)

print("\nPaste GAMES (team score F format), then type END:\n")
game_lines = []
while True:
    line = input()
    if line.strip() == "END":
        break
    game_lines.append(line)

# Parse games (simplified - just get team names and scores)
games = []
i = 0
while i < len(game_lines):
    line = game_lines[i].strip()
    # Look for pattern like "Charlotte 110 F" or "Charlotte 110"
    parts = line.split()
    if len(parts) >= 2 and parts[-1].isdigit():
        # This is a visitor line
        visitor_team = ' '.join(parts[:-1]) if parts[-1].isdigit() else ' '.join(parts[:-2])
        visitor_pts = int(parts[-1]) if parts[-1].isdigit() else int(parts[-2])
        
        # Next line should be home team
        if i + 1 < len(game_lines):
            next_line = game_lines[i + 1].strip()
            next_parts = next_line.split()
            if len(next_parts) >= 2:
                home_team = ' '.join(next_parts[:-1]) if next_parts[-1].isdigit() else next_parts[0]
                home_pts = int(next_parts[-1]) if next_parts[-1].isdigit() else int(next_parts[1])
                
                games.append({
                    "date": date,
                    "visitor_team": visitor_team,
                    "visitor_pts": visitor_pts,
                    "home_team": home_team,
                    "home_pts": home_pts
                })
                i += 2
                continue
    i += 1

# Parse boxscores
players = []
season = f"{date.year}-{str((date.year+1)%100).zfill(2)}" if date.month >= 7 else f"{date.year-1}-{str(date.year%100).zfill(2)}"

for line in box_lines:
    parts = line.split('\t')
    if not parts or not parts[0].isdigit():
        continue
    
    try:
        player_name = parts[1].strip()
        team = parts[2].strip()
        
        # Get stats with safe defaults
        def safe_float(idx, default=0):
            try:
                val = parts[idx].strip() if idx < len(parts) else ""
                return float(val) if val and val != '-' else default
            except:
                return default
        
        pts = safe_float(23)
        reb = safe_float(17)
        ast = safe_float(18)
        
        # Generate IDs
        game_id = int(hashlib.md5(f"{date}_{team}".encode()).hexdigest()[:15], 16)
        team_id = int(hashlib.md5(team.encode()).hexdigest()[:15], 16)
        player_id = int(hashlib.md5(f"{player_name}_{date}".encode()).hexdigest()[:15], 16)
        
        players.append({
            "game_id": game_id,
            "team_id": team_id,
            "player_id": player_id,
            "player_name": player_name,
            "team_abbreviation": team,
            "season": season,
            "game_date": date,
            "min": parts[5].strip() if len(parts) > 5 else "0:00",
            "pts": pts,
            "reb": reb,
            "ast": ast,
            "fgm": safe_float(6),
            "fga": safe_float(7),
            "fg3m": safe_float(9),
            "fg3a": safe_float(10),
            "ftm": safe_float(12),
            "fta": safe_float(13),
            "oreb": safe_float(15),
            "dreb": safe_float(16),
            "stl": safe_float(19),
            "blk": safe_float(20),
            "TO": safe_float(21),
            "pf": safe_float(22),
            "plus_minus": safe_float(24)
        })
    except:
        continue

# INSERT INTO DATABASE
with engine.begin() as conn:
    # Clear existing data
    conn.execute(text("DELETE FROM games WHERE date = :d"), {"d": date})
    conn.execute(text("DELETE FROM player_boxscores WHERE game_date = :d"), {"d": date})
    
    # Insert games (WITHOUT game_id since it doesn't exist)
    for g in games:
        conn.execute(text("""
            INSERT INTO games (date, visitor_team, visitor_pts, home_team, home_pts)
            VALUES (:date, :visitor_team, :visitor_pts, :home_team, :home_pts)
        """), g)
    
    # Insert player boxscores
    for p in players:
        conn.execute(text("""
            INSERT INTO player_boxscores (
                game_id, team_id, player_id, player_name, team_abbreviation,
                season, game_date, min, pts, reb, ast,
                fgm, fga, fg3m, fg3a, ftm, fta,
                oreb, dreb, stl, blk, "TO", pf, plus_minus
            ) VALUES (
                :game_id, :team_id, :player_id, :player_name, :team_abbreviation,
                :season, :game_date, :min, :pts, :reb, :ast,
                :fgm, :fga, :fg3m, :fg3a, :ftm, :fta,
                :oreb, :dreb, :stl, :blk, :TO, :pf, :plus_minus
            )
        """), p)

print(f"\n✅ DONE!")
print(f"Inserted {len(games)} games")
print(f"Inserted {len(players)} player boxscores")

# Verify
with engine.connect() as conn:
    game_count = conn.execute(text("SELECT COUNT(*) FROM games WHERE date = :d"), {"d": date}).scalar()
    player_count = conn.execute(text("SELECT COUNT(*) FROM player_boxscores WHERE game_date = :d"), {"d": date}).scalar()
    
    print(f"\n✅ VERIFIED IN DATABASE:")
    print(f"  Games: {game_count}")
    print(f"  Players: {player_count}")
