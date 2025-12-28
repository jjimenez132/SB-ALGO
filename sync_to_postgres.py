#!/usr/bin/env python3
"""
Sync NBA Data Pipeline (SQLite) to PostgreSQL (Render)
"""
import sqlite3
import pandas as pd
from sqlalchemy import create_engine, text
import os

# Database connections
SQLITE_PATH = os.path.expanduser("~/Desktop/SB-ALGO/nba_data_pipeline/data/nba_stats.db")
POSTGRES_URL = "postgresql://sb_algo_db_user:0HDtYp4EY2Lo5At8iyf44PD1zDioSPK7@dpg-d495uhchg0os738l1a50-a.virginia-postgres.render.com/sb_algo_db"

def get_sqlite_tables():
    """Get all tables from SQLite"""
    conn = sqlite3.connect(SQLITE_PATH)
    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cursor.fetchall() if not row[0].startswith('sqlite_')]
    conn.close()
    return tables

def sync_table(table_name, sqlite_conn, pg_engine):
    """Sync a single table from SQLite to PostgreSQL"""
    try:
        # Read from SQLite
        df = pd.read_sql(f"SELECT * FROM {table_name}", sqlite_conn)
        if df.empty:
            print(f"  ⚠️  {table_name}: empty, skipping")
            return 0
        
        # Add prefix to avoid conflicts with existing tables
        pg_table = f"nba_{table_name}" if not table_name.startswith('nba_') else table_name
        
        # Write to PostgreSQL (replace if exists)
        df.to_sql(pg_table, pg_engine, if_exists='replace', index=False)
        print(f"  ✅ {table_name} → {pg_table}: {len(df)} rows")
        return len(df)
    except Exception as e:
        print(f"  ❌ {table_name}: {str(e)[:50]}")
        return 0

def main():
    print("=" * 60)
    print("🔄 SYNCING NBA DATA PIPELINE TO POSTGRESQL")
    print("=" * 60)
    print(f"📁 Source: {SQLITE_PATH}")
    print(f"🐘 Target: Render PostgreSQL")
    print("=" * 60)
    
    # Connect to both databases
    sqlite_conn = sqlite3.connect(SQLITE_PATH)
    pg_engine = create_engine(POSTGRES_URL)
    
    # Get tables
    tables = get_sqlite_tables()
    print(f"\n📊 Found {len(tables)} tables to sync\n")
    
    total_rows = 0
    synced = 0
    
    for table in sorted(tables):
        rows = sync_table(table, sqlite_conn, pg_engine)
        if rows > 0:
            total_rows += rows
            synced += 1
    
    sqlite_conn.close()
    
    print("\n" + "=" * 60)
    print("✅ SYNC COMPLETE")
    print(f"📊 {synced} tables synced")
    print(f"📊 {total_rows:,} total rows")
    print("=" * 60)

if __name__ == "__main__":
    main()
