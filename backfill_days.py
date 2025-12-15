"""Backfill missing days from Dec 6 to Dec 14"""
import os
from datetime import datetime, timedelta
from daily_update import update_games_with_scores, update_player_stats
from sqlalchemy import create_engine

DATABASE_URL = os.environ.get('DATABASE_URL')
engine = create_engine(DATABASE_URL)

# Dec 6 to Dec 14 (9 days)
start = datetime(2025, 12, 6)
end = datetime(2025, 12, 14)

current = start
while current <= end:
    date_str = current.strftime("%Y%m%d")
    date_obj = current.date()
    print(f"\n{'='*50}")
    print(f"📅 Processing {current.strftime('%Y-%m-%d')}")
    print(f"{'='*50}")
    
    try:
        # Update game scores
        updated = update_games_with_scores(engine, date_str, date_obj)
        print(f"✅ Updated {updated} games")
        
        # Update player stats
        players = update_player_stats(engine, date_str, date_obj)
        print(f"✅ Updated {players} player stats")
    except Exception as e:
        print(f"❌ Error: {e}")
    
    current += timedelta(days=1)

print("\n🎉 Backfill complete!")
