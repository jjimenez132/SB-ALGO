#!/usr/bin/env python3
"""
publish_daily_recap.py - Posts daily summary to #daily-recap
Run as cron job at end of day (11 PM ET)
"""

import os
import sys
import logging
from datetime import datetime
import pytz

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(message)s')
log = logging.getLogger(__name__)

def main():
    log.info("=" * 50)
    log.info("SB-ALGO Daily Recap")
    log.info("=" * 50)
    
    # Initialize tables if needed
    from discord_results import init_picks_table, post_daily_recap, get_daily_stats
    init_picks_table()
    
    # Get today's stats first
    stats = get_daily_stats()
    log.info(f"Today's stats: {stats['wins']}W-{stats['losses']}L, {stats['net_units']:+.1f}u")
    
    if stats['pending'] > 0:
        log.info(f"⏳ {stats['pending']} picks still pending - skipping recap")
        return
    
    if stats['total'] == 0:
        log.info("No picks today - skipping recap")
        return
    
    # Post recap
    success = post_daily_recap()
    
    if success:
        log.info("✅ Daily recap posted!")
    else:
        log.error("❌ Failed to post recap")
        sys.exit(1)

if __name__ == "__main__":
    main()
