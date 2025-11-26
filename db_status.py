#!/usr/bin/env python3
"""
Database Status and Cleanup Script
Shows current state and provides cleanup options
"""
from datetime import datetime, timedelta
from sqlalchemy import create_engine, text

DATABASE_URL = 'postgresql://sb_algo_db_user:0HDtYp4EY2Lo5At8iyf44PD1zDioSPK7@dpg-d495uhchg0os738l1a50-a.virginia-postgres.render.com/sb_algo_db?sslmode=require'
engine = create_engine(DATABASE_URL)

print("\n" + "="*60)
print("NBA DATABASE STATUS CHECK")
print("="*60)

# Check last 10 days
today = datetime.now().date()
print(f"\nToday: {today}")
print("\nLast 10 days status:")
print("-" * 50)

with engine.connect() as conn:
    for i in range(10):
        check_date = today - timedelta(days=i)
        
        # Count games
        games = conn.execute(text("""
            SELECT COUNT(*) as count,
                   SUM(visitor_pts + home_pts)::int as total_pts
            FROM games 
            WHERE date = :d
        """), {"d": check_date}).fetchone()
        
        # Count boxscores
        boxscores = conn.execute(text("""
            SELECT COUNT(*) as count
            FROM player_boxscores 
            WHERE game_date = :d
        """), {"d": check_date}).fetchone()
        
        game_count = games[0] or 0
        total_pts = games[1] or 0
        box_count = boxscores[0] or 0
        
        # Determine status
        if game_count > 0 and box_count > 0:
            # Check ratio - should be ~12-15 players per game
            ratio = box_count / game_count if game_count > 0 else 0
            if ratio < 10:
                status = "⚠️  LOW BOXSCORES"
            elif ratio > 20:
                status = "⚠️  TOO MANY BOXSCORES"
            else:
                status = "✅ COMPLETE"
        elif game_count > 0 and box_count == 0:
            status = "❌ MISSING BOXSCORES"
        elif game_count == 0 and box_count > 0:
            status = "❌ MISSING GAMES"
        else:
            status = "📅 EMPTY"
        
        print(f"  {check_date}: {game_count:2} games, {box_count:3} boxscores, "
              f"{total_pts:4} pts {status}")

    print("\n" + "="*60)
    print("CLEANUP OPTIONS")
    print("="*60)
    
    print("\n1. Remove all data from Nov 18-24, 2025")
    print("2. Check specific date details")
    print("3. Exit")
    
    choice = input("\nEnter choice (1-3): ").strip()
    
    if choice == "1":
        confirm = input("\n⚠️  This will DELETE all data from Nov 18-24, 2025. Continue? (yes/no): ")
        if confirm.lower() == "yes":
            with engine.begin() as conn2:
                # Delete games
                result = conn2.execute(text("""
                    DELETE FROM games 
                    WHERE date BETWEEN '2025-11-18' AND '2025-11-24'
                """))
                games_deleted = result.rowcount
                
                # Delete boxscores
                result = conn2.execute(text("""
                    DELETE FROM player_boxscores 
                    WHERE game_date BETWEEN '2025-11-18' AND '2025-11-24'
                """))
                boxscores_deleted = result.rowcount
                
                print(f"\n✅ CLEANUP COMPLETE!")
                print(f"  Deleted {games_deleted} games")
                print(f"  Deleted {boxscores_deleted} player boxscores")
        else:
            print("Cancelled.")
    
    elif choice == "2":
        date_str = input("\nEnter date to check (YYYY-MM-DD): ").strip()
        check_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        
        # Show games
        games = conn.execute(text("""
            SELECT visitor_team, visitor_pts, home_team, home_pts
            FROM games
            WHERE date = :d
            ORDER BY home_team
        """), {"d": check_date}).fetchall()
        
        if games:
            print(f"\n🏀 GAMES on {check_date}:")
            for g in games:
                print(f"  {g[0]} {int(g[1])} @ {g[2]} {int(g[3])}")
        else:
            print(f"\n❌ No games found for {check_date}")
        
        # Show player summary
        player_stats = conn.execute(text("""
            SELECT COUNT(DISTINCT player_name) as players,
                   COUNT(*) as entries,
                   SUM(pts)::int as total_pts
            FROM player_boxscores
            WHERE game_date = :d
        """), {"d": check_date}).fetchone()
        
        if player_stats[0]:
            print(f"\n📊 PLAYER STATS:")
            print(f"  Unique players: {player_stats[0]}")
            print(f"  Total entries: {player_stats[1]}")
            print(f"  Total points: {player_stats[2]}")

print("\n" + "="*60)
print("Use manual_input.py to add missing data")
print("="*60)
