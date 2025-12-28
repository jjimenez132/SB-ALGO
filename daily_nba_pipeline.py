#!/usr/bin/env python3
"""
Daily NBA Pipeline - Runs the full data pull and sync
Schedule this to run at 4 AM ET daily
"""
import subprocess
import sys
import os
from datetime import datetime
import pytz

def run_command(cmd, description):
    """Run a command and return success status"""
    print(f"\n{'='*60}")
    print(f"🔄 {description}")
    print(f"{'='*60}")
    result = subprocess.run(cmd, shell=True, cwd=os.path.expanduser("~/Desktop/SB-ALGO"))
    return result.returncode == 0

def main():
    eastern = pytz.timezone('US/Eastern')
    now = datetime.now(eastern)
    
    print(f"\n{'='*60}")
    print(f"🏀 SB-ALGO DAILY DATA PIPELINE")
    print(f"⏰ {now.strftime('%Y-%m-%d %H:%M:%S')} ET")
    print(f"{'='*60}")
    
    steps = [
        ("cd nba_data_pipeline && python3 run_daily.py", "Pulling NBA.com + BBRef data"),
        ("python3 sync_to_postgres.py", "Syncing to PostgreSQL"),
    ]
    
    results = []
    for cmd, desc in steps:
        success = run_command(cmd, desc)
        results.append((desc, success))
    
    # Summary
    print(f"\n{'='*60}")
    print("📊 PIPELINE SUMMARY")
    print(f"{'='*60}")
    for desc, success in results:
        status = "✅" if success else "❌"
        print(f"  {status} {desc}")
    
    all_success = all(r[1] for r in results)
    print(f"\n{'✅ ALL COMPLETE' if all_success else '⚠️ SOME STEPS FAILED'}")
    print(f"{'='*60}")
    
    return 0 if all_success else 1

if __name__ == "__main__":
    sys.exit(main())
