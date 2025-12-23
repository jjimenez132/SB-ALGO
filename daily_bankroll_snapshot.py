#!/usr/bin/env python3
"""
daily_bankroll_snapshot.py - Saves daily bankroll snapshots for all users
Run as cron job at midnight ET
"""

import os
import sys
import logging
from sqlalchemy import create_engine, text

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(message)s')
log = logging.getLogger(__name__)

DATABASE_URL = os.environ.get('DATABASE_URL',
    "postgresql://sb_algo_db_user:0HDtYp4EY2Lo5At8iyf44PD1zDioSPK7@dpg-d495uhchg0os738l1a50-a.virginia-postgres.render.com/sb_algo_db")

def main():
    log.info("=" * 50)
    log.info("SB-ALGO Daily Bankroll Snapshot")
    log.info("=" * 50)
    
    engine = create_engine(DATABASE_URL)
    
    with engine.connect() as conn:
        # Get all users with bankroll settings
        users = conn.execute(text("""
            SELECT discord_id, current_bankroll, daily_profit_today
            FROM bankroll_settings
        """)).fetchall()
        
        log.info(f"Found {len(users)} users")
        
        saved = 0
        for user in users:
            discord_id, bankroll, daily_pnl = user
            
            # Save snapshot
            conn.execute(text("""
                INSERT INTO bankroll_history 
                (discord_id, date, bankroll_value, daily_pnl)
                VALUES (:did, CURRENT_DATE, :bv, :pnl)
                ON CONFLICT (discord_id, date) DO UPDATE SET
                    bankroll_value = :bv, daily_pnl = :pnl
            """), {"did": discord_id, "bv": bankroll, "pnl": daily_pnl})
            saved += 1
        
        # Reset daily stats for all users
        conn.execute(text("""
            UPDATE bankroll_settings SET
                daily_exposure_used = 0,
                daily_profit_today = 0,
                last_reset_date = CURRENT_DATE
        """))
        
        conn.commit()
        
    log.info(f"✅ Saved {saved} snapshots and reset daily stats")

if __name__ == "__main__":
    main()
