#!/usr/bin/env python3
"""Check injuries and news table structure"""

from sqlalchemy import create_engine, text

DATABASE_URL = "postgresql://sb_algo_db_user:0HDtYp4EY2Lo5At8iyf44PD1zDioSPK7@dpg-d495uhchg0os738l1a50-a.virginia-postgres.render.com/sb_algo_db"

engine = create_engine(DATABASE_URL)

with engine.connect() as conn:
    print("=" * 70)
    print("INJURIES TABLE")
    print("=" * 70)
    
    # Columns
    cols = conn.execute(text("""
        SELECT column_name, data_type FROM information_schema.columns 
        WHERE table_name = 'injuries' ORDER BY ordinal_position
    """)).fetchall()
    print("\nColumns:")
    for c in cols:
        print(f"  {c[0]}: {c[1]}")
    
    # Sample data
    print("\nSample Data (5 rows):")
    sample = conn.execute(text("SELECT * FROM injuries LIMIT 5")).fetchall()
    for row in sample:
        print(f"  {dict(row._mapping)}")
    
    # Count
    count = conn.execute(text("SELECT COUNT(*) FROM injuries")).fetchone()[0]
    print(f"\nTotal rows: {count}")
    
    # Unique statuses
    print("\nUnique Statuses:")
    statuses = conn.execute(text("""
        SELECT DISTINCT status, COUNT(*) as cnt FROM injuries 
        GROUP BY status ORDER BY cnt DESC
    """)).fetchall()
    for s in statuses:
        print(f"  {s[0]}: {s[1]}")
    
    print("\n" + "=" * 70)
    print("NEWS TABLE")
    print("=" * 70)
    
    # Columns
    cols = conn.execute(text("""
        SELECT column_name, data_type FROM information_schema.columns 
        WHERE table_name = 'nba_news' ORDER BY ordinal_position
    """)).fetchall()
    print("\nColumns:")
    for c in cols:
        print(f"  {c[0]}: {c[1]}")
    
    # Sample
    print("\nSample News (3 rows):")
    sample = conn.execute(text("SELECT * FROM nba_news ORDER BY published_at DESC LIMIT 3")).fetchall()
    for row in sample:
        print(f"  {dict(row._mapping)}")
    
    count = conn.execute(text("SELECT COUNT(*) FROM nba_news")).fetchone()[0]
    print(f"\nTotal news: {count}")
