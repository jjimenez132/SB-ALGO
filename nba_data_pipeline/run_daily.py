#!/usr/bin/env python3
"""
NBA Data Pipeline - Daily Runner
Run this script once daily (recommended: 4 AM ET) to pull all data.

Usage:
    python run_daily.py              # Full daily pull
    python run_daily.py --quick      # Quick pull (skip slow endpoints)
    python run_daily.py --test       # Test mode (only a few endpoints)
"""

import argparse
import sys
import os
from datetime import datetime
import time

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import CURRENT_SEASON, DATA_DIR
from database import init_database, store_dataframe, log_pull, get_connection
from pullers.nba_stats import NBAStatsPuller
from pullers.bbref import BBRefScraper
from calculators.derived_stats import DerivedStatsCalculator
from calculators.schedule_context import ScheduleContextCalculator


def run_nba_pull(quick: bool = False) -> dict:
    """Run the NBA.com data pull"""
    puller = NBAStatsPuller()
    results = {}
    
    if quick:
        # Quick mode - only essential endpoints
        essential = ['team_advanced', 'player_base', 'player_advanced', 'schedule']
        print("\n🚀 QUICK MODE - Essential endpoints only")
        
        for endpoint in essential:
            df = puller.pull_endpoint(endpoint)
            if df is not None:
                results[endpoint] = df
    else:
        # Full pull
        results = puller.pull_all()
    
    return results


def run_bbref_pull() -> dict:
    """Run the Basketball Reference pull"""
    scraper = BBRefScraper()
    return scraper.pull_all()


def store_all_data(nba_results: dict, bbref_results: dict, pull_date: str) -> dict:
    """Store all pulled data to database"""
    print("\n💾 STORING DATA TO DATABASE")
    print("=" * 50)
    
    stored_counts = {}
    
    # Map endpoint keys to table names
    table_mapping = {
        # Team tables
        'team_base': 'team_base_stats',
        'team_advanced': 'team_advanced_stats',
        'team_four_factors': 'team_four_factors',
        'team_scoring': 'team_scoring',
        'team_opponent': 'team_opponent_stats',
        'team_hustle': 'team_hustle',
        'team_clutch': 'team_clutch',
        # Player tables
        'player_base': 'player_base_stats',
        'player_advanced': 'player_advanced_stats',
        'player_scoring': 'player_scoring',
        'player_usage': 'player_usage',
        'player_tracking_touches': 'player_tracking_possessions',
        'player_tracking_passes': 'player_tracking_passes',
        'player_tracking_rebounding': 'player_tracking_rebounding',
        'player_hustle': 'player_hustle',
        'player_clutch': 'player_clutch',
        'player_on_off': 'player_on_off',
        'player_shots_general': 'player_shot_zones',
        # Other tables
        'lineups': 'lineups',
        'defense_dashboard': 'defense_dashboard',
        'schedule': 'schedule',
        # BBRef
        'bbref_advanced': 'player_bpm_vorp',
    }
    
    # Store NBA.com data
    for key, df in nba_results.items():
        table_name = table_mapping.get(key)
        if table_name and df is not None and not df.empty:
            try:
                count = store_dataframe(df, table_name, pull_date)
                stored_counts[key] = count
                print(f"  ✅ {key} → {table_name}: {count} rows")
            except Exception as e:
                print(f"  ❌ {key} → {table_name}: Error - {str(e)[:50]}")
                stored_counts[key] = 0
    
    # Store BBRef data
    for key, df in bbref_results.items():
        table_name = table_mapping.get(key)
        if table_name and df is not None and not df.empty:
            try:
                count = store_dataframe(df, table_name, pull_date)
                stored_counts[key] = count
                print(f"  ✅ {key} → {table_name}: {count} rows")
            except Exception as e:
                print(f"  ❌ {key} → {table_name}: Error - {str(e)[:50]}")
                stored_counts[key] = 0
    
    return stored_counts


def calculate_derived_stats(nba_results: dict, pull_date: str) -> dict:
    """Calculate all derived/meta statistics"""
    print("\n🧮 CALCULATING DERIVED STATS")
    print("=" * 50)
    
    derived_results = {}
    
    # Player derived stats
    if 'player_base' in nba_results and 'player_advanced' in nba_results:
        calc = DerivedStatsCalculator()
        
        player_tracking = nba_results.get('player_tracking_touches')
        
        derived_player = calc.process_all_players(
            player_base=nba_results['player_base'],
            player_tracking=player_tracking
        )
        
        if derived_player is not None and not derived_player.empty:
            derived_results['derived_player'] = derived_player
            store_dataframe(derived_player, 'derived_player_stats', pull_date)
            print(f"  ✅ Stored {len(derived_player)} derived player stats")
    
    # Team derived stats
    if 'team_advanced' in nba_results:
        calc = DerivedStatsCalculator()
        
        derived_team = calc.process_all_teams(
            team_advanced=nba_results['team_advanced']
        )
        
        if derived_team is not None and not derived_team.empty:
            derived_results['derived_team'] = derived_team
            store_dataframe(derived_team, 'derived_team_stats', pull_date)
            print(f"  ✅ Stored {len(derived_team)} derived team stats")
    
    # Schedule context
    if 'schedule' in nba_results:
        sched_calc = ScheduleContextCalculator()
        
        schedule_context = sched_calc.process_all_teams(nba_results['schedule'])
        
        if schedule_context is not None and not schedule_context.empty:
            derived_results['schedule_context'] = schedule_context
            print(f"  ✅ Calculated {len(schedule_context)} schedule contexts")
    
    return derived_results


def print_summary(stored_counts: dict, start_time: datetime, pull_date: str):
    """Print final summary"""
    elapsed = datetime.now() - start_time
    total_rows = sum(stored_counts.values())
    
    print("\n" + "=" * 60)
    print("✅ DAILY PULL COMPLETE")
    print("=" * 60)
    print(f"  📅 Pull Date: {pull_date}")
    print(f"  ⏱️  Duration: {elapsed.seconds // 60}m {elapsed.seconds % 60}s")
    print(f"  📊 Total Rows Stored: {total_rows:,}")
    print(f"  📁 Tables Updated: {len(stored_counts)}")
    print(f"  💾 Database: {DATA_DIR / 'nba_stats.db'}")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description='NBA Data Pipeline - Daily Runner')
    parser.add_argument('--quick', action='store_true', help='Quick mode (essential endpoints only)')
    parser.add_argument('--test', action='store_true', help='Test mode (minimal pull)')
    parser.add_argument('--skip-bbref', action='store_true', help='Skip Basketball Reference pull')
    parser.add_argument('--skip-derived', action='store_true', help='Skip derived stat calculations')
    args = parser.parse_args()
    
    start_time = datetime.now()
    pull_date = start_time.strftime('%Y-%m-%d')
    
    print("\n" + "=" * 60)
    print("🏀 NBA DATA PIPELINE - DAILY PULL")
    print("=" * 60)
    print(f"  📅 Date: {pull_date}")
    print(f"  🏀 Season: {CURRENT_SEASON}")
    print(f"  ⏰ Started: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    if args.test:
        print("  🧪 MODE: TEST (minimal pull)")
    elif args.quick:
        print("  🚀 MODE: QUICK (essential only)")
    else:
        print("  📊 MODE: FULL (all endpoints)")
    print("=" * 60)
    
    # Initialize database
    print("\n📁 Initializing database...")
    init_database()
    
    # NBA.com Pull
    if args.test:
        # Test mode - just pull one endpoint to verify it works
        print("\n🧪 TEST MODE - Pulling team_advanced only")
        puller = NBAStatsPuller()
        team_adv = puller.pull_endpoint('team_advanced')
        nba_results = {'team_advanced': team_adv} if team_adv is not None else {}
    else:
        nba_results = run_nba_pull(quick=args.quick)
    
    # BBRef Pull
    if args.skip_bbref or args.test:
        print("\n⏭️  Skipping Basketball Reference pull")
        bbref_results = {}
    else:
        print("\n⏳ Waiting 5 seconds before BBRef pull...")
        time.sleep(5)
        bbref_results = run_bbref_pull()
    
    # Store all data
    stored_counts = store_all_data(nba_results, bbref_results, pull_date)
    
    # Calculate derived stats
    if not args.skip_derived and not args.test:
        derived = calculate_derived_stats(nba_results, pull_date)
    
    # Log the pull
    total_rows = sum(stored_counts.values())
    log_pull('daily_full', total_rows, 'success')
    
    # Print summary
    print_summary(stored_counts, start_time, pull_date)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
