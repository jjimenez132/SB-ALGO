#!/usr/bin/env python3
"""
Manual NBA Data Input Script - FIXED VERSION
Properly parses Basketball Reference format and handles games table correctly
"""
import hashlib
from datetime import datetime
from sqlalchemy import create_engine, text

DATABASE_URL = 'postgresql://sb_algo_db_user:0HDtYp4EY2Lo5At8iyf44PD1zDioSPK7@dpg-d495uhchg0os738l1a50-a.virginia-postgres.render.com/sb_algo_db?sslmode=require'
engine = create_engine(DATABASE_URL)

def safe_float(val, default=0):
    """Convert value to float, return default if fails"""
    try:
        return float(val)
    except (ValueError, TypeError):
        return default

# Get date
date_str = input("Enter date (YYYY-MM-DD): ").strip()
date = datetime.strptime(date_str, "%Y-%m-%d").date()

# Calculate season
if date.month >= 7:
    season = f"{date.year}-{str(date.year + 1)[2:]}"
else:
    season = f"{date.year - 1}-{str(date.year)[2:]}"

print(f"Date: {date}, Season: {season}")

# ==========================
# COLLECT PLAYER BOXSCORES
# ==========================
print("\n📊 PASTE PLAYER BOXSCORES (tab-separated from Basketball Reference)")
print("End with 'ENDBOX' on its own line:")

boxscore_lines = []
while True:
    line = input()
    if line.strip() == "ENDBOX":
        break
    boxscore_lines.append(line)

# Parse player boxscores
players = []
for line in boxscore_lines:
    if not line.strip():
        continue
    
    parts = line.split('\t')
    if len(parts) < 25:  # Need at least 25 columns
        continue
    
    # Skip header rows
    if parts[0] in ["Rk", "Rank", ""]:
        continue
    
    try:
        player_name = parts[1]
        team_abbreviation = parts[2] if len(parts[2]) == 3 else parts[2][:3]
        opponent = parts[3] if len(parts[3]) == 3 else parts[3][:3]
        
        # Generate IDs
        game_id_seed = f"{date}_{team_abbreviation}"
        game_id = int(hashlib.md5(game_id_seed.encode()).hexdigest()[:15], 16)
        team_id = int(hashlib.md5(team_abbreviation.encode()).hexdigest()[:15], 16)
        player_id = int(hashlib.md5(f"{player_name}_{date}".encode()).hexdigest()[:15], 16)
        
        players.append({
            'game_id': game_id,
            'team_id': team_id,
            'player_id': player_id,
            'player_name': player_name,
            'team_abbreviation': team_abbreviation,
            'season': season,
            'game_date': date,
            'min': safe_float(parts[4]),
            'pts': safe_float(parts[23]),
            'reb': safe_float(parts[17]),
            'ast': safe_float(parts[18]),
            'fgm': safe_float(parts[5]),
            'fga': safe_float(parts[6]),
            'fg_pct': safe_float(parts[7]),
            'fg3m': safe_float(parts[8]),
            'fg3a': safe_float(parts[9]),
            'fg3_pct': safe_float(parts[10]),
            'ftm': safe_float(parts[11]),
            'fta': safe_float(parts[12]),
            'ft_pct': safe_float(parts[13]),
            'oreb': safe_float(parts[14]),
            'dreb': safe_float(parts[15]),
            'stl': safe_float(parts[19]),
            'blk': safe_float(parts[20]),
            'TO': safe_float(parts[21]),
            'pf': safe_float(parts[22]),
            'plus_minus': safe_float(parts[24]) if len(parts) > 24 else 0
        })
    except Exception as e:
        continue

print(f"✅ Parsed {len(players)} player boxscores")

# ==========================
# COLLECT GAMES
# ==========================
print("\n🏀 PASTE GAME RESULTS from Basketball Reference")
print("End with 'END' on its own line:")

game_lines = []
while True:
    line = input()
    if line.strip() == "END":
        break
    game_lines.append(line)

# ==========================
# PARSE GAMES - FIXED VERSION
# ==========================
print("\n🔄 Parsing games...")

def is_valid_game_line(line):
    """
    Check if a line looks like a valid game score line.
    Valid formats:
    - "Charlotte 118 F" (visitor with F)
    - "Charlotte 118" (home without F)
    """
    line = line.strip()
    if not line:
        return False
    
    # Skip lines that are obviously not games
    if line.startswith("1 2 3 4"):
        return False
    if line.startswith("PTS ") or line.startswith("TRB ") or line.startswith("AST "):
        return False
    if "Box Score" in line or "Play-By-Play" in line:
        return False
    if line[0].isdigit() and len(line.split()) == 4:  # Quarter scores like "28 34 36 24"
        return False
    
    parts = line.split()
    if len(parts) < 2:
        return False
    
    # Check if last part (or second to last if F) is a number
    if parts[-1] == 'F' and len(parts) >= 3:
        # Visitor line: "TeamName Score F"
        try:
            int(parts[-2])
            return True
        except:
            return False
    else:
        # Home line: "TeamName Score"
        try:
            int(parts[-1])
            # Make sure it's not a quarter score line
            if all(p.isdigit() for p in parts):
                return False
            return True
        except:
            return False

def parse_game_line(line):
    """Parse a valid game line and return team name and score"""
    parts = line.strip().split()
    
    if parts[-1] == 'F':
        # Visitor: "Charlotte 118 F"
        score = int(parts[-2])
        team = ' '.join(parts[:-2])
        return team, score, True  # True = visitor
    else:
        # Home: "Indiana 127"
        score = int(parts[-1])
        team = ' '.join(parts[:-1])
        return team, score, False  # False = home

# Process games - look for visitor/home pairs
games = []
i = 0
clean_lines = [line for line in game_lines if is_valid_game_line(line)]

print(f"Found {len(clean_lines)} valid game lines")

while i < len(clean_lines):
    line = clean_lines[i]
    
    try:
        team1, score1, is_visitor1 = parse_game_line(line)
        
        # If this is a visitor, look for the home team next
        if is_visitor1 and i + 1 < len(clean_lines):
            next_line = clean_lines[i + 1]
            team2, score2, is_visitor2 = parse_game_line(next_line)
            
            if not is_visitor2:  # Confirmed home team
                games.append({
                    'date': date,
                    'visitor_team': team1,
                    'visitor_pts': score1,
                    'home_team': team2,
                    'home_pts': score2
                })
                print(f"  ✓ {team1} {score1} @ {team2} {score2}")
                i += 2
                continue
        
        # Skip if we couldn't pair it properly
        i += 1
        
    except Exception as e:
        print(f"  ⚠️ Skipping line: {line}")
        i += 1

print(f"\n📊 Parsed {len(games)} games")

# ==========================
# INSERT INTO DATABASE
# ==========================
print("\n💾 Inserting into database...")

with engine.begin() as conn:
    # Clear existing data for this date
    conn.execute(text("DELETE FROM games WHERE date = :d"), {"d": date})
    conn.execute(text("DELETE FROM player_boxscores WHERE game_date = :d"), {"d": date})
    
    # Insert games (WITHOUT game_id - games table doesn't have this column!)
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
                fgm, fga, fg_pct, fg3m, fg3a, fg3_pct,
                ftm, fta, ft_pct, oreb, dreb, stl, blk, "TO", pf, plus_minus
            ) VALUES (
                :game_id, :team_id, :player_id, :player_name, :team_abbreviation,
                :season, :game_date, :min, :pts, :reb, :ast,
                :fgm, :fga, :fg_pct, :fg3m, :fg3a, :fg3_pct,
                :ftm, :fta, :ft_pct, :oreb, :dreb, :stl, :blk, :TO, :pf, :plus_minus
            )
        """), p)

print(f"\n✅ DONE!")
print(f"Inserted {len(games)} games")
print(f"Inserted {len(players)} player boxscores")

# Verify
with engine.connect() as conn:
    game_count = conn.execute(text("""
        SELECT COUNT(*) FROM games WHERE date = :d
    """), {"d": date}).scalar()
    
    player_count = conn.execute(text("""
        SELECT COUNT(*) FROM player_boxscores WHERE game_date = :d
    """), {"d": date}).scalar()
    
    total_pts = conn.execute(text("""
        SELECT SUM(visitor_pts + home_pts) FROM games WHERE date = :d
    """), {"d": date}).scalar()
    
    print(f"\n✅ VERIFIED IN DATABASE:")
    print(f"  Games: {game_count}")
    print(f"  Players: {player_count}")
    print(f"  Total Points: {int(total_pts) if total_pts else 0}")
