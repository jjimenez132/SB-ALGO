#!/usr/bin/env python3
"""
Add Today's Games to Database
Run this after inputting yesterday's results
"""
from datetime import datetime
from sqlalchemy import create_engine, text
import hashlib

DATABASE_URL = 'postgresql://sb_algo_db_user:0HDtYp4EY2Lo5At8iyf44PD1zDioSPK7@dpg-d495uhchg0os738l1a50-a.virginia-postgres.render.com/sb_algo_db?sslmode=require'
engine = create_engine(DATABASE_URL)

today = datetime.now().date()

# Calculate season
if today.month >= 7:
    season = f"{today.year}-{str(today.year + 1)[2:]}"
else:
    season = f"{today.year - 1}-{str(today.year)[2:]}"

print(f"\n📅 ADDING TODAY'S GAMES: {today}")
print("="*60)

# Check if games already exist for today
with engine.connect() as conn:
    existing = conn.execute(text("""
        SELECT COUNT(*) FROM games WHERE date = :d
    """), {"d": today}).scalar()
    
    if existing > 0:
        print(f"⚠️  Found {existing} games already for {today}")
        confirm = input("Delete and re-enter? (yes/no): ")
        if confirm.lower() != 'yes':
            print("Keeping existing games.")
            exit()
        else:
            with engine.begin() as conn2:
                conn2.execute(text("DELETE FROM games WHERE date = :d"), {"d": today})
                print("Deleted existing games.")

print("\n🏀 ENTER TODAY'S GAMES")
print("Format: VisitorTeam @ HomeTeam")
print("Example: Lakers @ Warriors")
print("Type 'DONE' when finished\n")

games = []
while True:
    game = input(f"Game {len(games) + 1}: ").strip()
    if game.upper() == "DONE":
        break
    
    if "@" in game:
        parts = game.split("@")
        if len(parts) == 2:
            visitor = parts[0].strip()
            home = parts[1].strip()
            
            # For now, set scores to 0 (will update tomorrow)
            games.append({
                'date': today,
                'visitor_team': visitor,
                'visitor_pts': 0,
                'home_team': home,
                'home_pts': 0
            })
            print(f"  ✓ Added: {visitor} @ {home}")
    else:
        print("  ❌ Invalid format. Use: Team @ Team")

if not games:
    print("No games entered!")
    exit()

print(f"\n💾 Saving {len(games)} games for {today}...")

with engine.begin() as conn:
    for g in games:
        conn.execute(text("""
            INSERT INTO games (date, visitor_team, visitor_pts, home_team, home_pts)
            VALUES (:date, :visitor_team, :visitor_pts, :home_team, :home_pts)
        """), g)

print(f"\n✅ SAVED TODAY'S SCHEDULE:")
for g in games:
    print(f"  {g['visitor_team']} @ {g['home_team']}")

# Verify
with engine.connect() as conn:
    saved = conn.execute(text("""
        SELECT COUNT(*) FROM games WHERE date = :d
    """), {"d": today}).scalar()
    
    print(f"\n✅ CONFIRMED: {saved} games saved for {today}")
    print("\n📝 Tomorrow you'll update these with final scores")

print("="*60)
