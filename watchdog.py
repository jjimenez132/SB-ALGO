#!/usr/bin/env python3
"""
================================================================================
SB-ALGO EXTERNAL WATCHDOG
================================================================================
Runs on GitHub Actions (NOT Render) to detect if the system has gone down.
Checks the database for recent pick activity and alerts via Discord webhook
if no picks have been sent in 24+ hours.

This solves the "who watches the watchmen" problem - when Render goes down,
the health monitors on Render also go down. This runs OUTSIDE Render.
================================================================================
"""

import os
import sys
from datetime import datetime, timedelta

DATABASE_URL = os.environ.get('DATABASE_URL',
    'postgresql://sb_algo_db_user:0HDtYp4EY2Lo5At8iyf44PD1zDioSPK7@dpg-d495uhchg0os738l1a50-a.virginia-postgres.render.com/sb_algo_db')

HEALTH_WEBHOOK = os.environ.get('ALGO_HEALTH_WEBHOOK',
    'https://discord.com/api/webhooks/1453117705984151724/22JltUkGycD-TyNUlzymZEN6D9UoJsmF_GH2v0Ctv8f77DvPFOqHQi0dxR4nZP7kK0WX')


def check_system_health():
    """Check if the system has been sending picks and alert if not."""
    import psycopg2
    import requests

    issues = []
    
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()

        # 1. Check: Were picks sent to Discord today or yesterday?
        cur.execute("""
            SELECT MAX(sent_date) FROM discord_sent_picks
        """)
        last_sent = cur.fetchone()[0]
        
        today = datetime.now().date()
        if last_sent is None:
            issues.append("🔴 **No picks have EVER been sent to Discord**")
        else:
            days_since = (today - last_sent).days
            if days_since >= 2:
                issues.append(f"🔴 **No picks sent in {days_since} days** (last: {last_sent})")
            elif days_since == 1:
                # Check if there were games yesterday — it's okay to skip if no games
                cur.execute("""
                    SELECT COUNT(*) FROM games WHERE date = %s
                """, (last_sent + timedelta(days=1),))
                games_yesterday = cur.fetchone()[0]
                if games_yesterday > 0:
                    issues.append(f"⚠️ **No picks sent yesterday** despite {games_yesterday} games")

        # 2. Check: Are boxscores being updated?
        cur.execute("SELECT MAX(game_date) FROM player_boxscores")
        last_boxscore = cur.fetchone()[0]
        if last_boxscore:
            days_behind = (today - last_boxscore).days
            if days_behind >= 3:
                issues.append(f"🔴 **Boxscores {days_behind} days behind** (last: {last_boxscore})")

        # 3. Check: Are injuries being updated?
        cur.execute("SELECT MAX(updated_at) FROM injuries")
        last_injury = cur.fetchone()[0]
        if last_injury:
            hours_since = (datetime.now() - last_injury).total_seconds() / 3600
            if hours_since >= 24:
                issues.append(f"⚠️ **Injuries not updated in {int(hours_since)}h**")

        # 4. Check: Are picks being tracked/graded?
        cur.execute("SELECT MAX(pick_date) FROM algo_picks_tracking")
        last_pick = cur.fetchone()[0]
        if last_pick:
            days_since_pick = (today - last_pick).days
            if days_since_pick >= 2:
                issues.append(f"⚠️ **No picks tracked in {days_since_pick} days** (last: {last_pick})")

        # 5. Check: Are there pending picks that should have been graded?
        cur.execute("""
            SELECT COUNT(*) FROM algo_picks_tracking 
            WHERE status = 'pending' AND pick_date < CURRENT_DATE - INTERVAL '2 days'
        """)
        stale_pending = cur.fetchone()[0]
        if stale_pending > 0:
            issues.append(f"⚠️ **{stale_pending} picks pending grading** (2+ days old)")

        conn.close()

    except Exception as e:
        issues.append(f"🔴 **DATABASE UNREACHABLE**: {str(e)[:100]}")

    # Send alert if there are issues
    if issues:
        description = "\\n".join(issues)
        description += f"\\n\\n*Watchdog check: {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}*"
        description += "\\n*This alert runs outside Render — if you see this, the watchdog is working.*"

        embed = {
            "title": "🚨 SB-ALGO SYSTEM DOWN ALERT",
            "description": description,
            "color": 0xFF0000,
            "footer": {"text": "External Watchdog • GitHub Actions"}
        }

        try:
            r = requests.post(HEALTH_WEBHOOK, json={"embeds": [embed]}, timeout=10)
            if r.status_code in [200, 204]:
                print(f"🚨 ALERT SENT — {len(issues)} issue(s) detected")
            else:
                print(f"❌ Failed to send alert: {r.status_code}")
        except Exception as e:
            print(f"❌ Webhook error: {e}")

        # Print issues for GitHub Actions logs
        for issue in issues:
            print(f"  {issue}")
        
        return False
    else:
        print("✅ All systems healthy — picks flowing, data fresh")
        return True


if __name__ == "__main__":
    healthy = check_system_health()
    sys.exit(0 if healthy else 1)
