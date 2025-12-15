"""Backfill missing player stats"""
import os
from datetime import datetime
from daily_update import update_player_stats
from sqlalchemy import create_engine

DATABASE_URL = os.environ.get('DATABASE_URL')
engine = create_engine(DATABASE_URL)

# Days that had 0 player stats
missing_days = ["20251206", "20251207", "20251208", "20251209", "20251214"]

for date_str in missing_days:
    date_obj = datetime.strptime(date_str, "%Y%m%d").date()
    print(f"\n{'='*50}")
    print(f"📅 Retrying {date_obj}")
    print(f"{'='*50}")
    
    try:
        players = update_player_stats(engine, date_str, date_obj)
        print(f"✅ Updated {players} player stats")
    except Exception as e:
        print(f"❌ Error: {e}")

print("\n🎉 Done!")
