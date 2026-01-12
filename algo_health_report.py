#!/usr/bin/env python3
"""
SB-ALGO Health Report
=====================
Private stats for owner only - advanced algo performance metrics.
Runs after daily grading to provide detailed analytics.
"""

import os
import requests
from datetime import datetime, timedelta
from sqlalchemy import create_engine, text

DATABASE_URL = os.environ.get('DATABASE_URL', 
    'postgresql://sb_algo_db_user:0HDtYp4EY2Lo5At8iyf44PD1zDioSPK7@dpg-d495uhchg0os738l1a50-a.virginia-postgres.render.com/sb_algo_db')

HEALTH_WEBHOOK = os.environ.get('ALGO_HEALTH_WEBHOOK',
    'https://discord.com/api/webhooks/1453117705984151724/22JltUkGycD-TyNUlzymZEN6D9UoJsmF_GH2v0Ctv8f77DvPFOqHQi0dxR4nZP7kK0WX')

engine = create_engine(DATABASE_URL)


def get_period_stats(days_back=None, start_date=None, end_date=None):
    """Get stats for a specific period"""
    stats = {
        'wins': 0, 'losses': 0, 'pushes': 0,
        'units': 0, 'units_risked': 0,
        'game_wins': 0, 'game_losses': 0, 'game_units': 0,
        'prop_wins': 0, 'prop_losses': 0, 'prop_units': 0,
        'picks': []
    }
    
    try:
        with engine.connect() as conn:
            if days_back:
                start = datetime.now() - timedelta(days=days_back)
                query = text("""
                    SELECT pick_type, status, units, result_units, pick_name, pick_date
                    FROM algo_picks_tracking
                    WHERE pick_date >= :start_date AND status IN ('win', 'loss', 'push')
                    ORDER BY pick_date DESC
                """)
                results = conn.execute(query, {"start_date": start}).fetchall()
            elif start_date:
                query = text("""
                    SELECT pick_type, status, units, result_units, pick_name, pick_date
                    FROM algo_picks_tracking
                    WHERE pick_date >= :start_date AND pick_date < :end_date AND status IN ('win', 'loss', 'push')
                    ORDER BY pick_date DESC
                """)
                results = conn.execute(query, {"start_date": start_date, "end_date": end_date or datetime.now()}).fetchall()
            else:
                return stats
            
            for row in results:
                pick_type, status, units_risked, result_units, pick_name, pick_date = row
                
                # Track units risked (always positive)
                stats['units_risked'] += float(units_risked or 0)
                
                if status == 'win':
                    stats['wins'] += 1
                    stats['units'] += float(result_units or 0)  # Net P/L (positive)
                    if pick_type == 'game':
                        stats['game_wins'] += 1
                        stats['game_units'] += float(result_units or 0)
                    else:
                        stats['prop_wins'] += 1
                        stats['prop_units'] += float(result_units or 0)
                elif status == 'loss':
                    stats['losses'] += 1
                    stats['units'] += float(result_units or 0)  # Net P/L (negative)
                    if pick_type == 'game':
                        stats['game_losses'] += 1
                        stats['game_units'] += float(result_units or 0)
                    else:
                        stats['prop_losses'] += 1
                        stats['prop_units'] += float(result_units or 0)
                elif status == 'push':
                    stats['pushes'] += 1
                
                stats['picks'].append({
                    'type': pick_type,
                    'status': status,
                    'units': float(result_units or 0),
                    'name': pick_name
                })
                
    except Exception as e:
        print(f"   ⚠️ Error getting period stats: {e}")
    
    return stats


def calculate_roi(stats):
    """Calculate ROI percentage"""
    if stats['units'] > 0:
        return (stats['units'] / stats['units_risked']) * 100 if stats['units_risked'] > 0 else 0
    return 0


def calculate_win_rate(wins, losses):
    """Calculate win rate"""
    total = wins + losses
    if total > 0:
        return (wins / total) * 100
    return 0


def get_streak():
    """Get current win/loss streak"""
    try:
        with engine.connect() as conn:
            results = conn.execute(text("""
                SELECT status FROM algo_picks_tracking
                WHERE status IN ('win', 'loss')
                ORDER BY pick_date DESC
                LIMIT 20
            """)).fetchall()
            
            if not results:
                return 0, 'none'
            
            streak = 0
            streak_type = results[0][0]
            
            for row in results:
                if row[0] == streak_type:
                    streak += 1
                else:
                    break
            
            return streak, streak_type
    except:
        return 0, 'none'


def get_best_worst_day():
    """Get best and worst performing days"""
    try:
        with engine.connect() as conn:
            results = conn.execute(text("""
                SELECT pick_date as day, SUM(result_units) as units
                FROM algo_picks_tracking
                WHERE status IN ('win', 'loss') AND pick_date >= CURRENT_DATE - INTERVAL '30 days'
                GROUP BY pick_date
                ORDER BY units DESC
            """)).fetchall()
            
            if results:
                best = results[0]
                worst = results[-1]
                return {
                    'best_day': str(best[0]),
                    'best_units': float(best[1]),
                    'worst_day': str(worst[0]),
                    'worst_units': float(worst[1])
                }
    except:
        pass
    return None


def send_health_report():
    """Send comprehensive health report to private channel"""
    print("📊 Generating Algo Health Report...")
    
    now = datetime.now()
    
    # Today stats
    yesterday = now - timedelta(days=1)
    yesterday_start = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday_end = now.replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday_stats = get_period_stats(start_date=yesterday_start, end_date=yesterday_end)
    
    # Week stats (Monday start)
    week_start = now - timedelta(days=now.weekday())
    week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
    week_stats = get_period_stats(start_date=week_start, end_date=now)
    
    # Month stats
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    month_stats = get_period_stats(start_date=month_start, end_date=now)
    
    # All time (last 90 days)
    alltime_stats = get_period_stats(days_back=90)
    
    # Streak
    streak_count, streak_type = get_streak()
    streak_emoji = "🔥" if streak_type == 'win' else "❄️" if streak_type == 'loss' else "➖"
    
    # Best/worst day
    extremes = get_best_worst_day()
    
    # Calculate rates
    yesterday_wr = calculate_win_rate(yesterday_stats['wins'], yesterday_stats['losses'])
    week_wr = calculate_win_rate(week_stats['wins'], week_stats['losses'])
    month_wr = calculate_win_rate(month_stats['wins'], month_stats['losses'])
    alltime_wr = calculate_win_rate(alltime_stats['wins'], alltime_stats['losses'])
    
    week_roi = calculate_roi(week_stats)
    month_roi = calculate_roi(month_stats)
    
    # Game vs Prop breakdown
    game_wr = calculate_win_rate(week_stats['game_wins'], week_stats['game_losses'])
    prop_wr = calculate_win_rate(week_stats['prop_wins'], week_stats['prop_losses'])
    
    # Build the report
    report = f"""**📅 {now.strftime('%A, %B %d, %Y')}**

━━━━━━━━━━━━━━━━━━━━━━━━━━━
**💰 UNITS PERFORMANCE**
━━━━━━━━━━━━━━━━━━━━━━━━━━━
- Yesterday: **{yesterday_stats['units']:+.1f}u** ({yesterday_stats['wins']}-{yesterday_stats['losses']})
- Week: **{week_stats['units']:+.1f}u** ({week_stats['wins']}-{week_stats['losses']})
- Month: **{month_stats['units']:+.1f}u** ({month_stats['wins']}-{month_stats['losses']})
- 90-Day: **{alltime_stats['units']:+.1f}u** ({alltime_stats['wins']}-{alltime_stats['losses']})

━━━━━━━━━━━━━━━━━━━━━━━━━━━
**📈 SUCCESS RATES**
━━━━━━━━━━━━━━━━━━━━━━━━━━━
- Yesterday: **{yesterday_wr:.1f}%**
- Week: **{week_wr:.1f}%**
- Month: **{month_wr:.1f}%**
- 90-Day: **{alltime_wr:.1f}%**

━━━━━━━━━━━━━━━━━━━━━━━━━━━
**🎯 CATEGORY BREAKDOWN (Week)**
━━━━━━━━━━━━━━━━━━━━━━━━━━━
- Games: {week_stats['game_wins']}-{week_stats['game_losses']} ({game_wr:.0f}%) | {week_stats['game_units']:+.1f}u
- Props: {week_stats['prop_wins']}-{week_stats['prop_losses']} ({prop_wr:.0f}%) | {week_stats['prop_units']:+.1f}u

━━━━━━━━━━━━━━━━━━━━━━━━━━━
**⚡ ADVANCED METRICS**
━━━━━━━━━━━━━━━━━━━━━━━━━━━
- Week ROI: **{week_roi:+.1f}%**
- Month ROI: **{month_roi:+.1f}%**
- Current Streak: {streak_emoji} **{streak_count} {streak_type}s**
- Avg Units/Pick: **{week_stats['units']/max(week_stats['wins']+week_stats['losses'],1):.2f}u**"""

    if extremes:
        report += f"""

━━━━━━━━━━━━━━━━━━━━━━━━━━━
**📊 30-DAY EXTREMES**
━━━━━━━━━━━━━━━━━━━━━━━━━━━
- Best Day: {extremes['best_day']} ({extremes['best_units']:+.1f}u)
- Worst Day: {extremes['worst_day']} ({extremes['worst_units']:+.1f}u)"""

    report += """

━━━━━━━━━━━━━━━━━━━━━━━━━━━
*SB-ALGO Health Monitor • Private*"""

    # Color based on week performance
    if week_stats['units'] > 0:
        color = 0x00FF00  # Green
    elif week_stats['units'] < 0:
        color = 0xFF0000  # Red
    else:
        color = 0x888888  # Gray

    embed = {
        "title": "🏥 SB-ALGO HEALTH REPORT",
        "description": report,
        "color": color,
    }
    
    try:
        response = requests.post(HEALTH_WEBHOOK, json={"embeds": [embed]}, timeout=10)
        if response.status_code in [200, 204]:
            print("   ✅ Health report sent to private channel")
            return True
        else:
            print(f"   ❌ Failed to send: {response.status_code}")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    return False


def send_weekly_report():
    """Send weekly breakdown every Sunday"""
    print("📊 Generating Weekly Report...")
    
    now = datetime.now()
    week_start = now - timedelta(days=now.weekday() + 7)  # Last Monday
    week_end = week_start + timedelta(days=7)
    
    week_stats = get_period_stats(start_date=week_start, end_date=week_end)
    
    if week_stats['wins'] + week_stats['losses'] == 0:
        print("   No picks to report for last week")
        return
    
    week_wr = calculate_win_rate(week_stats['wins'], week_stats['losses'])
    week_roi = calculate_roi(week_stats)
    game_wr = calculate_win_rate(week_stats['game_wins'], week_stats['game_losses'])
    prop_wr = calculate_win_rate(week_stats['prop_wins'], week_stats['prop_losses'])
    
    report = f"""**📅 WEEKLY REPORT**
**{week_start.strftime('%b %d')} - {week_end.strftime('%b %d, %Y')}**

━━━━━━━━━━━━━━━━━━━━━━━━━━━
**📊 WEEK SUMMARY**
━━━━━━━━━━━━━━━━━━━━━━━━━━━
- Record: **{week_stats['wins']}-{week_stats['losses']}** ({week_wr:.1f}%)
- Net P/L: **{week_stats['units']:+.2f}u**
- ROI: **{week_roi:+.1f}%**

━━━━━━━━━━━━━━━━━━━━━━━━━━━
**🎯 BY CATEGORY**
━━━━━━━━━━━━━━━━━━━━━━━━━━━
- Games: {week_stats['game_wins']}-{week_stats['game_losses']} ({game_wr:.0f}%) | {week_stats['game_units']:+.1f}u
- Props: {week_stats['prop_wins']}-{week_stats['prop_losses']} ({prop_wr:.0f}%) | {week_stats['prop_units']:+.1f}u

━━━━━━━━━━━━━━━━━━━━━━━━━━━
*Process over outcome. Consistency compounds.*"""

    color = 0x00FF00 if week_stats['units'] > 0 else 0xFF0000 if week_stats['units'] < 0 else 0x888888
    
    embed = {
        "title": "📈 SB-ALGO WEEKLY REPORT",
        "description": report,
        "color": color,
    }
    
    try:
        response = requests.post(HEALTH_WEBHOOK, json={"embeds": [embed]}, timeout=10)
        if response.status_code in [200, 204]:
            print("   ✅ Weekly report sent")
            return True
    except Exception as e:
        print(f"   ❌ Error: {e}")
    return False


def send_monthly_report():
    """Send monthly breakdown on 1st of each month"""
    print("📊 Generating Monthly Report...")
    
    now = datetime.now()
    # Last month
    if now.month == 1:
        month_start = now.replace(year=now.year-1, month=12, day=1, hour=0, minute=0, second=0, microsecond=0)
    else:
        month_start = now.replace(month=now.month-1, day=1, hour=0, minute=0, second=0, microsecond=0)
    month_end = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    month_stats = get_period_stats(start_date=month_start, end_date=month_end)
    
    if month_stats['wins'] + month_stats['losses'] == 0:
        print("   No picks to report for last month")
        return
    
    month_wr = calculate_win_rate(month_stats['wins'], month_stats['losses'])
    month_roi = calculate_roi(month_stats)
    game_wr = calculate_win_rate(month_stats['game_wins'], month_stats['game_losses'])
    prop_wr = calculate_win_rate(month_stats['prop_wins'], month_stats['prop_losses'])
    
    report = f"""**📅 MONTHLY REPORT**
**{month_start.strftime('%B %Y')}**

━━━━━━━━━━━━━━━━━━━━━━━━━━━
**📊 MONTH SUMMARY**
━━━━━━━━━━━━━━━━━━━━━━━━━━━
- Record: **{month_stats['wins']}-{month_stats['losses']}** ({month_wr:.1f}%)
- Net P/L: **{month_stats['units']:+.2f}u**
- ROI: **{month_roi:+.1f}%**
- Total Picks: **{month_stats['wins'] + month_stats['losses'] + month_stats['pushes']}**

━━━━━━━━━━━━━━━━━━━━━━━━━━━
**🎯 BY CATEGORY**
━━━━━━━━━━━━━━━━━━━━━━━━━━━
- Games: {month_stats['game_wins']}-{month_stats['game_losses']} ({game_wr:.0f}%) | {month_stats['game_units']:+.1f}u
- Props: {month_stats['prop_wins']}-{month_stats['prop_losses']} ({prop_wr:.0f}%) | {month_stats['prop_units']:+.1f}u

━━━━━━━━━━━━━━━━━━━━━━━━━━━
*New month. Same process. Discipline remains.*"""

    color = 0x00FF00 if month_stats['units'] > 0 else 0xFF0000 if month_stats['units'] < 0 else 0x888888
    
    embed = {
        "title": "📊 SB-ALGO MONTHLY REPORT",
        "description": report,
        "color": color,
    }
    
    try:
        response = requests.post(HEALTH_WEBHOOK, json={"embeds": [embed]}, timeout=10)
        if response.status_code in [200, 204]:
            print("   ✅ Monthly report sent")
            return True
    except Exception as e:
        print(f"   ❌ Error: {e}")
    return False


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        if sys.argv[1] == 'weekly':
            send_weekly_report()
        elif sys.argv[1] == 'monthly':
            send_monthly_report()
        else:
            send_health_report()
    else:
        send_health_report()
