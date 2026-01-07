#!/usr/bin/env python3
"""
================================================================================
SB-ALGO DISCORD PICKS SENDER v2.1
================================================================================
Uses requests API instead of discord.py to avoid SSL issues.
Tracks sent picks to avoid duplicates during intraday alerts.

CHANNELS:
- 🔥-top-edges (1450976507127140544) → Game picks
- 🎯-top-props (1451003425021100103) → Player props

USAGE:
  python3 discord_picks_sender.py morning   # Send full daily report (9:30am ET)
  python3 discord_picks_sender.py alert     # Check for NEW picks (hourly)
  python3 discord_picks_sender.py test      # Test picks retrieval

================================================================================
"""

import os
import requests
import json
from datetime import datetime
import pytz
import warnings
warnings.filterwarnings('ignore')

# Channel IDs
GAME_PICKS_CHANNEL = 1450976507127140544  # 🔥-top-edges
PROP_PICKS_CHANNEL = 1451003425021100103  # 🎯-top-props

# Discord Bot Token
DISCORD_TOKEN = os.environ.get('DISCORD_BOT_TOKEN')

# Database for tracking sent picks
DATABASE_URL = os.environ.get('DATABASE_URL', 'postgresql://sb_algo_db_user:0HDtYp4EY2Lo5At8iyf44PD1zDioSPK7@dpg-d495uhchg0os738l1a50-a.virginia-postgres.render.com/sb_algo_db')

# API Base URL
DISCORD_API = "https://discord.com/api/v10"

# File to track sent picks (backup if DB fails)
SENT_PICKS_FILE = "/tmp/sb_algo_sent_picks.json"

def get_eastern_time():
    """Get current Eastern time"""
    eastern = pytz.timezone('US/Eastern')
    return datetime.now(eastern)

def get_eastern_date():
    """Get current Eastern date string"""
    return get_eastern_time().strftime('%Y-%m-%d')

def get_picks_from_engine():
    """Get picks from the NEW sb_algo engine"""
    try:
        from sb_algo_api import get_todays_picks
        return get_todays_picks()
    except Exception as e:
        print(f"❌ Error getting picks: {e}")
        return None

def get_sent_picks_today():
    """Get list of picks already sent today"""
    today = get_eastern_date()
    
    # Try database first
    try:
        from sqlalchemy import create_engine, text
        engine = create_engine(DATABASE_URL)
        with engine.connect() as conn:
            # Create table if not exists
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS discord_sent_picks (
                    id SERIAL PRIMARY KEY,
                    pick_key VARCHAR(255) NOT NULL,
                    pick_type VARCHAR(50),
                    sent_date DATE NOT NULL,
                    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(pick_key, sent_date)
                )
            """))
            conn.commit()
            
            # Get today's sent picks
            result = conn.execute(text("""
                SELECT pick_key FROM discord_sent_picks WHERE sent_date = :today
            """), {"today": today}).fetchall()
            
            return set(row[0] for row in result)
    except Exception as e:
        print(f"   ⚠️ DB error, using file: {e}")
    
    # Fallback to file
    try:
        with open(SENT_PICKS_FILE, 'r') as f:
            data = json.load(f)
            if data.get('date') == today:
                return set(data.get('picks', []))
    except:
        pass
    
    return set()

def mark_pick_sent(pick_key, pick_type='unknown'):
    """Mark a pick as sent"""
    today = get_eastern_date()
    
    # Try database first
    try:
        from sqlalchemy import create_engine, text
        engine = create_engine(DATABASE_URL)
        with engine.connect() as conn:
            conn.execute(text("""
                INSERT INTO discord_sent_picks (pick_key, pick_type, sent_date)
                VALUES (:key, :type, :date)
                ON CONFLICT (pick_key, sent_date) DO NOTHING
            """), {"key": pick_key, "type": pick_type, "date": today})
            conn.commit()
            return
    except Exception as e:
        print(f"   ⚠️ DB mark error: {e}")
    
    # Fallback to file
    try:
        sent = get_sent_picks_today()
        sent.add(pick_key)
        with open(SENT_PICKS_FILE, 'w') as f:
            json.dump({'date': today, 'picks': list(sent)}, f)
    except:
        pass

def clear_sent_picks():
    """Clear sent picks (for new day)"""
    try:
        from sqlalchemy import create_engine, text
        engine = create_engine(DATABASE_URL)
        with engine.connect() as conn:
            # Keep last 7 days only
            conn.execute(text("""
                DELETE FROM discord_sent_picks 
                WHERE sent_date < CURRENT_DATE - INTERVAL '7 days'
            """))
            conn.commit()
    except:
        pass


def save_pick_for_grading(pick_id, pick_name, pick_type, units, odds=-110, details=None):
    """Save pick to algo_picks_tracking for later grading"""
    today = get_eastern_date()
    
    try:
        from sqlalchemy import create_engine, text
        engine = create_engine(DATABASE_URL)
        with engine.connect() as conn:
            conn.execute(text("""
                INSERT INTO algo_picks_tracking (pick_date, pick_id, pick_name, pick_type, units, odds, status, pick_details)
                VALUES (:date, :pick_id, :name, :type, :units, :odds, 'pending', :details)
                ON CONFLICT (pick_date, pick_type, pick_name) DO UPDATE SET
                    pick_id = EXCLUDED.pick_id,
                    units = EXCLUDED.units
            """), {
                'date': today,
                'pick_id': pick_id,
                'name': pick_name,
                'type': pick_type,
                'units': units,
                'odds': odds,
                'details': details
            })
            conn.commit()
            print(f"   📝 Saved {pick_id} for grading")
    except Exception as e:
        print(f"   ⚠️ Could not save for grading: {e}")

def create_pick_key(pick, pick_type):
    """Create unique key for a pick"""
    if pick_type == 'game':
        return f"GAME_{pick.get('matchup', '')}_{pick.get('pick', '')}"
    else:
        return f"PROP_{pick.get('player', '')}_{pick.get('prop', '')}"

def send_discord_message(channel_id, content=None, embed=None):
    """Send a message to Discord channel"""
    headers = {
        'Authorization': f'Bot {DISCORD_TOKEN}',
        'Content-Type': 'application/json'
    }
    
    data = {}
    if content:
        data['content'] = content
    if embed:
        data['embeds'] = [embed]
    
    url = f"{DISCORD_API}/channels/{channel_id}/messages"
    
    import time
    for attempt in range(3):
        try:
            time.sleep(0.5)  # Rate limit prevention
            response = requests.post(url, headers=headers, json=data, timeout=30)
            
            if response.status_code == 200:
                return True
            elif response.status_code == 429:
                try:
                    retry_after = response.json().get('retry_after', 2)
                except:
                    retry_after = 2
                print(f"   ⏳ Rate limited, waiting {retry_after}s...")
                time.sleep(retry_after + 1)
                continue
            else:
                print(f"   ⚠️ Discord error {response.status_code}: {response.text[:100] if response.text else 'empty'}")
                return False
        except requests.exceptions.Timeout:
            print(f"   ⏳ Timeout, retrying ({attempt+1}/3)...")
            time.sleep(2)
        except Exception as e:
            print(f"   ❌ Request error ({attempt+1}/3): {e}")
            time.sleep(2)
    
    return False

def create_game_pick_embed(pick, is_alert=False):
    """Create embed dict for game pick"""
    
    edge_val = float(str(pick.get('edge', '0')).replace('+', '').replace('%', ''))
    
    # Color based on edge
    if edge_val >= 30:
        color = 0xFF4444  # Red - fire
    elif edge_val >= 20:
        color = 0xFFAA00  # Orange
    else:
        color = 0x00AA00  # Green
    
    matchup = pick.get('matchup', 'Unknown')
    pick_str = pick.get('pick', '')
    
    title = f"🏀 {matchup}"
    if is_alert:
        title = f"🚨 NEW EDGE: {matchup}"
    
    # Determine units based on edge
    units = "2.0u" if edge_val >= 20 else "1.5u" if edge_val >= 15 else "1.0u"
    
    embed = {
        "title": title,
        "description": f"**{pick_str}** — {units} 🔥🔥",
        "color": color,
        "fields": [
            {"name": "Expected Value", "value": f"+{edge_val:.1f} pts", "inline": True},
            {"name": "EV %", "value": pick.get('ev', 'N/A'), "inline": True},
            {"name": "Grade", "value": pick.get('grade', 'A+'), "inline": True},
            {"name": "AI Stake", "value": units, "inline": True},
            {"name": "Risk Class", "value": "High" if edge_val >= 25 else "Medium", "inline": True},
            {"name": "Confidence", "value": f"{pick.get('confidence', '80')}%", "inline": True},
        ],
        "footer": {"text": f"SB-ALGO Terminal • {get_eastern_time().strftime('%I:%M %p ET')}"}
    }
    
    return embed

def create_prop_pick_embed(pick, is_alert=False):
    """Create embed dict for prop pick"""
    
    edge_val = float(str(pick.get('edge', '0')).replace('+', '').replace('%', ''))
    hit_rate = pick.get('hit_rate', '0%')
    
    # Color based on edge
    if edge_val >= 40:
        color = 0xFF4444  # Red - fire
    elif edge_val >= 25:
        color = 0xFFAA00  # Orange
    else:
        color = 0x00AA00  # Green
    
    player = pick.get('player', 'Unknown')
    prop = pick.get('prop', '')
    
    title = f"🎯 {player}"
    if is_alert:
        title = f"🚨 NEW EDGE: {player}"
    
    units = "1.5u" if edge_val >= 25 else "1.0u"
    
    embed = {
        "title": title,
        "description": f"**{prop}** — {units} 🔥",
        "color": color,
        "fields": [
            {"name": "Hit Rate", "value": hit_rate, "inline": True},
            {"name": "Edge", "value": f"+{edge_val:.1f}%", "inline": True},
            {"name": "EV", "value": pick.get('ev', 'N/A'), "inline": True},
            {"name": "Model Proj", "value": f"{pick.get('model', 'N/A')}", "inline": True},
            {"name": "Line", "value": f"{pick.get('line', 'N/A')}", "inline": True},
            {"name": "Grade", "value": pick.get('grade', 'A+'), "inline": True},
        ],
        "footer": {"text": f"SB-ALGO Terminal • {get_eastern_time().strftime('%I:%M %p ET')}"}
    }
    
    return embed

def create_header_embed():
    """Create header embed for daily report"""
    now = get_eastern_time()
    
    return {
        "title": "🏀 SB-ALGO DAILY PICKS",
        "description": f"**{now.strftime('%A, %B %d, %Y')}**\n\n15-Engine Analysis • Meta-Merge v4.0",
        "color": 0x667eea,
        "footer": {"text": "Algorithmically generated with edge analysis"}
    }

def create_summary_embed(picks_data):
    """Create summary embed"""
    game_picks = picks_data.get('game_picks', [])
    prop_picks = picks_data.get('prop_picks', [])
    
    return {
        "title": "📊 TODAY'S SUMMARY",
        "color": 0x667eea,
        "fields": [
            {"name": "🏀 Game Picks", "value": str(len(game_picks)), "inline": True},
            {"name": "🎯 Prop Picks", "value": str(len(prop_picks)), "inline": True},
            {"name": "💰 Total Stake", "value": picks_data.get('total_stake', '$0'), "inline": True},
            {"name": "📈 Avg EV", "value": f"{picks_data.get('avg_ev', '0')}%", "inline": True},
            {"name": "🎯 Total Picks", "value": str(picks_data.get('total_picks', 0)), "inline": True},
            {"name": "⏰ Generated", "value": get_eastern_time().strftime('%I:%M %p ET'), "inline": True},
        ],
        "footer": {"text": "SB-ALGO v4.0 • Meta-Merge Engine • 15 Sub-Engines"}
    }

def send_morning_report():
    """Send full morning report to both channels"""
    
    print(f"\n{'='*60}")
    print(f"📤 SENDING MORNING REPORT - {get_eastern_time().strftime('%I:%M %p ET')}")
    print(f"{'='*60}")
    
    # Clear old sent picks
    clear_sent_picks()
    
    # Get picks
    picks_data = get_picks_from_engine()
    
    if not picks_data:
        print("❌ No picks data available")
        return False
    
    game_picks = picks_data.get('game_picks', [])
    prop_picks = picks_data.get('prop_picks', [])
    
    print(f"   📊 {len(game_picks)} game picks, {len(prop_picks)} prop picks")
    
    # === SEND GAME PICKS ===
    print(f"\n   📤 Sending to #top-edges...")
    
    # Header
    send_discord_message(GAME_PICKS_CHANNEL, embed=create_header_embed())
    
    # Each game pick
    sent_games = 0
    for pick in game_picks[:10]:
        embed = create_game_pick_embed(pick)
        if send_discord_message(GAME_PICKS_CHANNEL, embed=embed):
            sent_games += 1
            pick_key = create_pick_key(pick, 'game')
            mark_pick_sent(pick_key, 'game')
            # Save for grading
            pick_id = pick.get('id', f'G{sent_games:02d}')
            pick_name = f"{pick.get('matchup', 'Unknown')} {pick.get('pick', '')}"
            save_pick_for_grading(pick_id, pick_name, 'game', 2.0)
    
    print(f"   ✅ Sent {sent_games} game picks")
    
    # Summary
    send_discord_message(GAME_PICKS_CHANNEL, embed=create_summary_embed(picks_data))
    
    # === SEND PROP PICKS ===
    print(f"\n   📤 Sending to #top-props...")
    
    # Header
    send_discord_message(PROP_PICKS_CHANNEL, embed=create_header_embed())
    
    # Each prop pick
    sent_props = 0
    for pick in prop_picks[:10]:
        embed = create_prop_pick_embed(pick)
        if send_discord_message(PROP_PICKS_CHANNEL, embed=embed):
            sent_props += 1
            pick_key = create_pick_key(pick, 'prop')
            mark_pick_sent(pick_key, 'prop')
            # Save for grading
            pick_id = pick.get('id', f'P{sent_props:02d}')
            pick_name = f"{pick.get('player', 'Unknown')} {pick.get('prop', '')}"
            save_pick_for_grading(pick_id, pick_name, 'prop', 1.5)
    
    print(f"   ✅ Sent {sent_props} prop picks")
    
    print(f"\n{'='*60}")
    print(f"✅ MORNING REPORT COMPLETE")
    print(f"{'='*60}")
    
    return True

def check_new_picks():
    """Check for NEW picks that weren't in morning report"""
    
    print(f"\n{'='*60}")
    print(f"🔍 CHECKING FOR NEW PICKS - {get_eastern_time().strftime('%I:%M %p ET')}")
    print(f"{'='*60}")
    
    # Get already sent picks
    sent_picks = get_sent_picks_today()
    print(f"   📋 {len(sent_picks)} picks already sent today")
    
    # Get current picks
    picks_data = get_picks_from_engine()
    if not picks_data:
        print("❌ No picks data")
        return
    
    new_game_picks = []
    new_prop_picks = []
    
    # Check game picks
    for pick in picks_data.get('game_picks', []):
        pick_key = create_pick_key(pick, 'game')
        if pick_key not in sent_picks:
            new_game_picks.append(pick)
    
    # Check prop picks
    for pick in picks_data.get('prop_picks', []):
        pick_key = create_pick_key(pick, 'prop')
        if pick_key not in sent_picks:
            new_prop_picks.append(pick)
    
    print(f"   🆕 {len(new_game_picks)} new game picks, {len(new_prop_picks)} new prop picks")
    
    alerts_sent = 0
    
    # Send new game picks
    for pick in new_game_picks:
        print(f"   🚨 NEW GAME: {pick.get('matchup')} - {pick.get('pick')}")
        send_discord_message(GAME_PICKS_CHANNEL, content="🚨 **NEW EDGE DETECTED** 🚨")
        if send_discord_message(GAME_PICKS_CHANNEL, embed=create_game_pick_embed(pick, is_alert=True)):
            pick_key = create_pick_key(pick, 'game')
            mark_pick_sent(pick_key, 'game')
            # Save for grading
            pick_id = pick.get('id', f'G{alerts_sent+1:02d}')
            pick_name = f"{pick.get('matchup', 'Unknown')} {pick.get('pick', '')}"
            save_pick_for_grading(pick_id, pick_name, 'game', 2.0)
            alerts_sent += 1
    
    # Send new prop picks
    for pick in new_prop_picks:
        print(f"   🚨 NEW PROP: {pick.get('player')} - {pick.get('prop')}")
        send_discord_message(PROP_PICKS_CHANNEL, content="🚨 **NEW EDGE DETECTED** 🚨")
        if send_discord_message(PROP_PICKS_CHANNEL, embed=create_prop_pick_embed(pick, is_alert=True)):
            pick_key = create_pick_key(pick, 'prop')
            mark_pick_sent(pick_key, 'prop')
            # Save for grading
            pick_id = pick.get('id', f'P{alerts_sent+1:02d}')
            pick_name = f"{pick.get('player', 'Unknown')} {pick.get('prop', '')}"
            save_pick_for_grading(pick_id, pick_name, 'prop', 1.5)
            alerts_sent += 1
    
    if alerts_sent == 0:
        print("   ✅ No new picks found")
    else:
        print(f"   ✅ Sent {alerts_sent} new pick alerts")
    
    print(f"{'='*60}")

def test_picks():
    """Test picks retrieval"""
    print("🧪 Testing picks retrieval...")
    picks = get_picks_from_engine()
    if picks:
        print(f"\n✅ Got {picks.get('total_picks', 0)} picks")
        print(f"   Game picks: {len(picks.get('game_picks', []))}")
        print(f"   Prop picks: {len(picks.get('prop_picks', []))}")
        print(f"   Avg EV: {picks.get('avg_ev', '0')}%")
        
        print("\n📋 Game Picks:")
        for p in picks.get('game_picks', [])[:5]:
            print(f"   • {p.get('matchup')}: {p.get('pick')} ({p.get('edge')})")
        
        print("\n📋 Prop Picks:")
        for p in picks.get('prop_picks', []):
            print(f"   • {p.get('player')}: {p.get('prop')} ({p.get('edge')})")
    else:
        print("❌ No picks")

# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    import sys
    
    print("""
================================================================================
🏀 SB-ALGO DISCORD PICKS SENDER v2.1
================================================================================
    """)
    
    if not DISCORD_TOKEN:
        print("❌ DISCORD_BOT_TOKEN not set!")
        print("   Run: export DISCORD_BOT_TOKEN='your_token_here'")
        sys.exit(1)
    
    mode = sys.argv[1] if len(sys.argv) > 1 else 'morning'
    
    if mode == 'morning':
        send_morning_report()
    elif mode == 'alert':
        check_new_picks()
    elif mode == 'test':
        test_picks()
    else:
        print(f"Unknown mode: {mode}")
        print("Usage: python3 discord_picks_sender.py [morning|alert|test]")
