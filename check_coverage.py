import os
from sqlalchemy import create_engine, text

DATABASE_URL = 'postgresql://sb_algo_db_user:0HDtYp4EY2Lo5At8iyf44PD1zDioSPK7@dpg-d495uhchg0os738l1a50-a.virginia-postgres.render.com/sb_algo_db?sslmode=require'
engine = create_engine(DATABASE_URL)

with engine.connect() as conn:
    print("\n📊 DATABASE STATUS")
    print("="*50)
    
    # Games coverage
    result = conn.execute(text("""
        SELECT MIN(date) as min_date, MAX(date) as max_date, 
               COUNT(*) as total, COUNT(DISTINCT date) as days
        FROM games
    """)).fetchone()
    print(f"GAMES: {result[0]} to {result[1]} ({result[2]} games, {result[3]} days)")
    
    # Boxscores coverage  
    result = conn.execute(text("""
        SELECT MIN(game_date) as min_date, MAX(game_date) as max_date,
               COUNT(*) as total, COUNT(DISTINCT game_date) as days
        FROM player_boxscores WHERE game_date IS NOT NULL
    """)).fetchone()
    print(f"BOXSCORES: {result[0]} to {result[1]} ({result[2]} rows, {result[3]} days)")
    
    # Show gaps
    print("\nLAST 20 DATES (✅=has boxscores, ❌=missing):")
    result = conn.execute(text("""
        SELECT g.date, COUNT(DISTINCT g.home_team) as games,
               COUNT(DISTINCT pb.player_name) as players
        FROM games g
        LEFT JOIN player_boxscores pb ON g.date = pb.game_date
        GROUP BY g.date
        ORDER BY g.date DESC
        LIMIT 20
    """)).fetchall()
    
    for date, games, players in result:
        status = "✅" if players > 0 else "❌"
        print(f"  {date}: {games} games, {players} players {status}")
