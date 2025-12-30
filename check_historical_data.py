#!/usr/bin/env python3
"""Check historical data available in database"""

from sqlalchemy import create_engine, text
import os

DATABASE_URL = "postgresql://sb_algo_db_user:0HDtYp4EY2Lo5At8iyf44PD1zDioSPK7@dpg-d495uhchg0os738l1a50-a.virginia-postgres.render.com/sb_algo_db"

engine = create_engine(DATABASE_URL)

with engine.connect() as conn:
    print("=" * 70)
    print("HISTORICAL DATA ANALYSIS")
    print("=" * 70)
    
    # Check all tables
    tables = conn.execute(text("""
        SELECT table_name FROM information_schema.tables 
        WHERE table_schema = 'public' ORDER BY table_name
    """)).fetchall()
    
    print(f"\n📊 ALL TABLES ({len(tables)} total):")
    for t in tables:
        count = conn.execute(text(f"SELECT COUNT(*) FROM {t[0]}")).fetchone()[0]
        print(f"  {t[0]}: {count:,} rows")
    
    # Check games table structure
    print("\n" + "=" * 70)
    print("GAMES TABLE STRUCTURE")
    print("=" * 70)
    
    cols = conn.execute(text("""
        SELECT column_name FROM information_schema.columns 
        WHERE table_name = 'games'
    """)).fetchall()
    print("Columns:", [c[0] for c in cols])
    
    # Check date range
    date_range = conn.execute(text("""
        SELECT MIN(date), MAX(date), COUNT(*) FROM games
    """)).fetchone()
    print(f"\nDate Range: {date_range[0]} to {date_range[1]}")
    print(f"Total Games: {date_range[2]:,}")
    
    # Check player_boxscores
    print("\n" + "=" * 70)
    print("PLAYER BOXSCORES TABLE")
    print("=" * 70)
    
    cols = conn.execute(text("""
        SELECT column_name FROM information_schema.columns 
        WHERE table_name = 'player_boxscores'
    """)).fetchall()
    print("Columns:", [c[0] for c in cols])
    
    boxscore_count = conn.execute(text("SELECT COUNT(*) FROM player_boxscores")).fetchone()[0]
    print(f"Total Boxscores: {boxscore_count:,}")
    
    # Sample boxscore
    print("\nSample Boxscore:")
    sample = conn.execute(text("""
        SELECT * FROM player_boxscores LIMIT 1
    """)).fetchone()
    if sample:
        print(dict(sample._mapping))
    
    # Check player_props (historical props data)
    print("\n" + "=" * 70)
    print("PLAYER PROPS TABLE")
    print("=" * 70)
    
    cols = conn.execute(text("""
        SELECT column_name FROM information_schema.columns 
        WHERE table_name = 'player_props'
    """)).fetchall()
    print("Columns:", [c[0] for c in cols])
    
    props_count = conn.execute(text("SELECT COUNT(*) FROM player_props")).fetchone()[0]
    print(f"Total Props: {props_count:,}")
    
    # Check betting_odds (historical odds)
    print("\n" + "=" * 70)
    print("BETTING ODDS TABLE")
    print("=" * 70)
    
    cols = conn.execute(text("""
        SELECT column_name FROM information_schema.columns 
        WHERE table_name = 'betting_odds'
    """)).fetchall()
    print("Columns:", [c[0] for c in cols])
    
    odds_count = conn.execute(text("SELECT COUNT(*) FROM betting_odds")).fetchone()[0]
    print(f"Total Odds Records: {odds_count:,}")
    
    # Sample game with result
    print("\n" + "=" * 70)
    print("SAMPLE COMPLETED GAME")
    print("=" * 70)
    
    sample_game = conn.execute(text("""
        SELECT * FROM games 
        WHERE home_score IS NOT NULL 
        ORDER BY date DESC LIMIT 1
    """)).fetchone()
    if sample_game:
        print(dict(sample_game._mapping))
