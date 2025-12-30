#!/usr/bin/env python3
from sqlalchemy import create_engine, text

DATABASE_URL = "postgresql://sb_algo_db_user:0HDtYp4EY2Lo5At8iyf44PD1zDioSPK7@dpg-d495uhchg0os738l1a50-a.virginia-postgres.render.com/sb_algo_db"
engine = create_engine(DATABASE_URL)

with engine.connect() as conn:
    print("COLUMNS IN nba_team_advanced_stats:")
    cols = conn.execute(text("""
        SELECT column_name FROM information_schema.columns 
        WHERE table_name = 'nba_team_advanced_stats' ORDER BY ordinal_position
    """)).fetchall()
    for c in cols:
        print(f"  {c[0]}")
    
    print("\nSAMPLE ROW:")
    row = conn.execute(text("SELECT * FROM nba_team_advanced_stats LIMIT 1")).fetchone()
    if row:
        print(dict(row._mapping))
