#!/usr/bin/env python3
"""
publish_props_discord.py - Props Publisher for Discord
Sends top prop picks to Discord channel using algo_brain.analyze_props()
"""
import os
import sys
import logging
from datetime import datetime
import pytz
import requests

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(message)s')
log = logging.getLogger(__name__)

DISCORD_WEBHOOK = os.environ.get('DISCORD_WEBHOOK_TOP_PROPS')

def get_eastern_date():
    return datetime.now(pytz.timezone('US/Eastern')).strftime('%Y-%m-%d')

def get_eastern_time():
    return datetime.now(pytz.timezone('US/Eastern')).strftime('%I:%M %p ET')

def send_discord(payload, retries=3):
    import time
    for attempt in range(retries):
        try:
            r = requests.post(DISCORD_WEBHOOK, json=payload, timeout=10)
            if r.status_code == 204:
                log.info("Discord post successful")
                return True
            elif r.status_code == 429:
                time.sleep(r.json().get('retry_after', 5))
            else:
                log.error(f"Discord error: {r.status_code}")
        except Exception as e:
            log.error(f"Request failed: {e}")
        time.sleep(2 * (attempt + 1))
    return False

def build_prop_embed(prop):
    edge = prop.get('edge', 0)
    
    if edge >= 50:
        color = 0xFF0000  # Red = fire
        unit_emoji = "🔥🔥"
        units = "1.5u"
    elif edge >= 30:
        color = 0x00FF00  # Green = solid
        unit_emoji = "🔥"
        units = "1.0u"
    else:
        color = 0xFFAA00  # Orange = decent
        unit_emoji = "✅"
        units = "0.5u"
    
    market = prop.get('subtype', 'points').replace('player_', '').replace('_', ' ').title()
    
    return {
        "title": f"🎯 {prop['player']} — {market}",
        "description": f"**{prop['pick']}** — {units} {unit_emoji}",
        "color": color,
        "fields": [
            {"name": "Edge", "value": f"+{edge:.0f}%", "inline": True},
            {"name": "Projected", "value": f"{prop.get('projected', 0):.1f}", "inline": True},
            {"name": "Line", "value": f"{prop.get('line', 0)}", "inline": True},
        ],
        "footer": {"text": f"SB-ALGO Props • {get_eastern_time()}"}
    }

def main():
    log.info("=" * 50)
    log.info(f"SB-ALGO Props Publisher | {get_eastern_date()}")
    log.info("=" * 50)
    
    if not DISCORD_WEBHOOK:
        log.error("Missing DISCORD_WEBHOOK_TOP_PROPS")
        sys.exit(1)
    
    # Use algo_brain to get props with edges
    log.info("Running analyze_props()...")
    try:
        from algo_brain import analyze_props
        prop_edges = analyze_props()
    except Exception as e:
        log.error(f"Error: {e}")
        sys.exit(1)
    
    log.info(f"Found {len(prop_edges)} props with edge")
    
    if not prop_edges:
        send_discord({
            "username": "SB-ALGO Props",
            "content": f"📅 **{get_eastern_date()}** | No props with edge found today."
        })
        return
    
    # Sort by edge and take top 5
    prop_edges.sort(key=lambda x: x.get('edge', 0), reverse=True)
    top_props = prop_edges[:5]
    
    # Build embeds
    embeds = [{
        "title": "🎯 SB-ALGO Top Props",
        "description": f"**{get_eastern_date()}** | {len(prop_edges)} total props with edge\nTop 5 plays below:",
        "color": 0x667eea
    }]
    
    for prop in top_props:
        embeds.append(build_prop_embed(prop))
    
    # Send
    success = send_discord({"username": "SB-ALGO Props", "embeds": embeds})
    
    if success:
        log.info(f"✅ Posted top {len(top_props)} props to Discord")
    else:
        log.error("Failed to post")
        sys.exit(1)

if __name__ == "__main__":
    main()
