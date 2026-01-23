#!/usr/bin/env python3
"""
CLV DAILY REPORT - "WE BEAT THE BOOKS" NOTIFICATION
====================================================
Runs at 6-7 PM ET to flex market dominance.
Only posts if we actually beat the books. Silence = discipline.
"""

import os
import requests
from datetime import datetime
from sqlalchemy import create_engine, text
import pytz

DATABASE_URL = os.environ.get('DATABASE_URL',
    "postgresql://sb_algo_db_user:0HDtYp4EY2Lo5At8iyf44PD1zDioSPK7@dpg-d495uhchg0os738l1a50-a.virginia-postgres.render.com/sb_algo_db")

# Create a new webhook for #market-validation channel
CLV_WEBHOOK = os.environ.get('DISCORD_WEBHOOK_CLV',
    'https://discord.com/api/webhooks/1464404517402706046/hOveHjIOa_zG_hKgEiTXiVq0BzFlqUiRI2G_CwTZ1imQ9anw4qE7vEnNHiDqHpg-py7l')  # You'll need to create this

def get_eastern_time():
    return datetime.now(pytz.timezone('US/Eastern'))

def get_engine():
    return create_engine(DATABASE_URL)

def get_todays_clv_data():
    """Get CLV data for today's picks that have closing odds"""
    engine = get_engine()
    
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT 
                pick_name, 
                pick_type,
                odds as open_odds, 
                closing_odds, 
                clv_cents,
                status
            FROM algo_picks_tracking 
            WHERE pick_date = CURRENT_DATE
            AND closing_odds IS NOT NULL
            AND clv_cents IS NOT NULL
            ORDER BY clv_cents DESC
        """))
        
        picks = []
        for row in result:
            picks.append({
                'name': row[0],
                'type': row[1],
                'open_odds': row[2],
                'close_odds': row[3],
                'clv': float(row[4]) if row[4] else 0,
                'status': row[5]
            })
        
        return picks

def calculate_clv_stats(picks):
    """Calculate CLV statistics"""
    if not picks:
        return None
    
    clv_values = [p['clv'] for p in picks if p['clv'] is not None]
    
    if not clv_values:
        return None
    
    positive_clv = [c for c in clv_values if c > 0]
    
    return {
        'avg_clv': sum(clv_values) / len(clv_values),
        'total_picks': len(clv_values),
        'positive_picks': len(positive_clv),
        'pct_positive': (len(positive_clv) / len(clv_values)) * 100,
        'best_clv': max(clv_values),
        'worst_clv': min(clv_values)
    }

def format_odds(odds):
    """Format odds for display"""
    if odds >= 0:
        return f"+{odds}"
    return str(odds)

def build_picks_breakdown(picks):
    """Build the detailed picks breakdown"""
    lines = []
    
    for p in picks:
        if p['clv'] > 0:
            emoji = "🔥"
            verdict = "Beat the market"
        elif p['clv'] < 0:
            emoji = "📉"
            verdict = "Market moved against"
        else:
            emoji = "➖"
            verdict = "Line held"
        
        # Shorten pick name if needed
        name = p['name'][:35] + "..." if len(p['name']) > 35 else p['name']
        
        lines.append(
            f"{emoji} **{name}**\n"
            f"   Open: `{format_odds(p['open_odds'])}` → Close: `{format_odds(p['close_odds'])}` | "
            f"CLV: **{p['clv']:+.1f}¢** | {verdict}"
        )
    
    return "\n\n".join(lines)

def send_clv_report():
    """Main function - send CLV report if thresholds met"""
    
    print(f"\n{'='*60}")
    print(f"📊 CLV DAILY REPORT - {get_eastern_time().strftime('%I:%M %p ET')}")
    print(f"{'='*60}")
    
    # Get today's CLV data
    picks = get_todays_clv_data()
    
    if not picks:
        print("   ⚠️ No CLV data for today yet")
        return False
    
    stats = calculate_clv_stats(picks)
    
    if not stats:
        print("   ⚠️ Could not calculate CLV stats")
        return False
    
    print(f"   📊 Avg CLV: {stats['avg_clv']:+.1f}¢")
    print(f"   📊 Positive CLV: {stats['positive_picks']}/{stats['total_picks']} ({stats['pct_positive']:.0f}%)")
    
    # THRESHOLDS - Only post if we actually beat the books
    MIN_AVG_CLV = 3.0  # At least +3 cents average
    MIN_PCT_POSITIVE = 50  # At least 50% of picks beat closing
    
    # Check if we should post
    if stats['avg_clv'] < MIN_AVG_CLV or stats['pct_positive'] < MIN_PCT_POSITIVE:
        print(f"\n   ❄️ Thresholds not met. Staying silent.")
        print(f"      Required: Avg CLV ≥ {MIN_AVG_CLV}¢, {MIN_PCT_POSITIVE}%+ positive")
        print(f"      Actual: Avg CLV = {stats['avg_clv']:+.1f}¢, {stats['pct_positive']:.0f}% positive")
        return False
    
    # Determine notification level
    is_dominant = stats['avg_clv'] >= 10 and stats['pct_positive'] >= 75
    
    # Build the embed
    if is_dominant:
        # 🔥 DOMINANT DAY
        title = "🚨 MARKET DOMINATED"
        color = 0xFF4444  # Red/fire
        description = (
            f"**SB-ALGO beat the books HARD today.**\n\n"
            f"• Avg CLV: **{stats['avg_clv']:+.1f}¢**\n"
            f"• Markets beaten: **{stats['positive_picks']}/{stats['total_picks']}**\n"
            f"• {stats['pct_positive']:.0f}% of lines closed worse\n\n"
            f"*This is edge. This is why we play.*"
        )
        ping = "@everyone "
    else:
        # ✅ STANDARD DAY
        title = "📊 MARKET CHECK-IN"
        color = 0x00AA00  # Green
        description = (
            f"**SB-ALGO beat the closing line today.**\n\n"
            f"• Avg CLV: **{stats['avg_clv']:+.1f}¢**\n"
            f"• Markets beaten: **{stats['positive_picks']}/{stats['total_picks']}**\n"
            f"• Books adjusted after release\n\n"
            f"*Value confirmed. Results still loading.*"
        )
        ping = ""
    
    # Build picks breakdown
    breakdown = build_picks_breakdown(picks)
    
    embed = {
        "title": title,
        "description": description,
        "color": color,
        "fields": [
            {
                "name": "📋 Pick-by-Pick Breakdown",
                "value": breakdown[:1024],  # Discord limit
                "inline": False
            }
        ],
        "footer": {"text": f"SB-ALGO CLV Report • {get_eastern_time().strftime('%B %d, %Y %I:%M %p ET')}"}
    }
    
    # Send to Discord
    if CLV_WEBHOOK == 'https://discord.com/api/webhooks/1464404517402706046/hOveHjIOa_zG_hKgEiTXiVq0BzFlqUiRI2G_CwTZ1imQ9anw4qE7vEnNHiDqHpg-py7l':
        print("\n   ⚠️ CLV_WEBHOOK not configured!")
        print("   📋 Would have sent:")
        print(f"      Title: {title}")
        print(f"      Avg CLV: {stats['avg_clv']:+.1f}¢")
        print(f"      Breakdown:\n{breakdown}")
        return False
    
    try:
        payload = {"embeds": [embed]}
        if ping:
            payload["content"] = ping.strip()
        
        response = requests.post(CLV_WEBHOOK, json=payload, timeout=10)
        
        if response.status_code in [200, 204]:
            print(f"\n   ✅ CLV report sent to Discord!")
            return True
        else:
            print(f"\n   ❌ Discord error: {response.status_code}")
            print(f"      {response.text}")
            return False
            
    except Exception as e:
        print(f"\n   ❌ Error sending: {e}")
        return False

if __name__ == "__main__":
    send_clv_report()
