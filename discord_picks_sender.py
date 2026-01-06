#!/usr/bin/env python3
"""
================================================================================
SB-ALGO DISCORD PICKS SENDER v2.0
================================================================================
Uses requests API instead of discord.py to avoid SSL issues.

CHANNELS:
- 🔥-top-edges (1450976507127140544) → Game picks
- 🎯-top-props (1451003425021100103) → Player props

USAGE:
  python3 discord_picks_sender.py morning   # Send full daily report
  python3 discord_picks_sender.py alert     # Check for high value picks
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

# Thresholds
HIGH_VALUE_EDGE_THRESHOLD = 40  # Edge % to trigger breaking alert

# API Base URL
DISCORD_API = "https://discord.com/api/v10"

def get_eastern_time():
    """Get current Eastern time"""
    eastern = pytz.timezone('US/Eastern')
    return datetime.now(eastern)

def get_picks_from_engine():
    """Get picks from the NEW sb_algo engine"""
    try:
        from sb_algo_api import get_todays_picks
        return get_todays_picks()
    except Exception as e:
        print(f"❌ Error getting picks: {e}")
        return None

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
    
    try:
        response = requests.post(url, headers=headers, json=data, verify=False)
        if response.status_code == 200:
            return True
        else:
            print(f"   ⚠️ Discord error {response.status_code}: {response.text[:100]}")
            return False
    except Exception as e:
        print(f"   ❌ Request error: {e}")
        return False

def create_game_pick_embed(pick, is_breaking=False):
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
    if is_breaking:
        title = f"🚨 HIGH VALUE: {matchup}"
    
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

def create_prop_pick_embed(pick, is_breaking=False):
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
    if is_breaking:
        title = f"🚨 HIGH VALUE: {player}"
    
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
    
    print(f"   ✅ Sent {sent_props} prop picks")
    
    print(f"\n{'='*60}")
    print(f"✅ MORNING REPORT COMPLETE")
    print(f"{'='*60}")
    
    return True

def check_high_value_picks():
    """Check for high value picks and send alerts"""
    
    print(f"\n🔍 Checking for high value picks (edge >= {HIGH_VALUE_EDGE_THRESHOLD}%)...")
    
    picks_data = get_picks_from_engine()
    if not picks_data:
        print("❌ No picks data")
        return
    
    alerts_sent = 0
    
    # Check game picks
    for pick in picks_data.get('game_picks', []):
        edge_val = float(str(pick.get('edge', '0')).replace('+', '').replace('%', ''))
        if edge_val >= HIGH_VALUE_EDGE_THRESHOLD:
            print(f"   🚨 HIGH VALUE GAME: {pick.get('matchup')} - {pick.get('pick')} ({edge_val}%)")
            send_discord_message(GAME_PICKS_CHANNEL, content="🚨 **HIGH VALUE ALERT** 🚨")
            send_discord_message(GAME_PICKS_CHANNEL, embed=create_game_pick_embed(pick, is_breaking=True))
            alerts_sent += 1
    
    # Check prop picks
    for pick in picks_data.get('prop_picks', []):
        edge_val = float(str(pick.get('edge', '0')).replace('+', '').replace('%', ''))
        if edge_val >= HIGH_VALUE_EDGE_THRESHOLD:
            print(f"   🚨 HIGH VALUE PROP: {pick.get('player')} - {pick.get('prop')} ({edge_val}%)")
            send_discord_message(PROP_PICKS_CHANNEL, content="🚨 **HIGH VALUE ALERT** 🚨")
            send_discord_message(PROP_PICKS_CHANNEL, embed=create_prop_pick_embed(pick, is_breaking=True))
            alerts_sent += 1
    
    if alerts_sent == 0:
        print("   ✅ No high value picks found above threshold")
    else:
        print(f"   ✅ Sent {alerts_sent} high value alerts")

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
🏀 SB-ALGO DISCORD PICKS SENDER v2.0
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
        check_high_value_picks()
    elif mode == 'test':
        test_picks()
    else:
        print(f"Unknown mode: {mode}")
        print("Usage: python3 discord_picks_sender.py [morning|alert|test]")
