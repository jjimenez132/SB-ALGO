#!/usr/bin/env python3
"""
publish_props_discord.py - Props Publisher for Discord
Sends top prop picks to Discord channel
"""
import os
import sys
import logging
from datetime import datetime
import pytz
import requests
from sqlalchemy import create_engine, text

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(message)s')
log = logging.getLogger(__name__)

DATABASE_URL = os.environ.get('DATABASE_URL')
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

def fetch_todays_props(engine):
    today = get_eastern_date()
    query = text("""
        SELECT player_name, market, line, over_odds, under_odds, sportsbook
        FROM player_props
        WHERE game_date = :today
        AND market IN ('player_points', 'player_rebounds', 'player_assists', 'player_threes')
        LIMIT 500
    """)
    try:
        with engine.connect() as conn:
            return conn.execute(query, {"today": today}).fetchall()
    except:
        return []

def get_player_avg(engine, player, market):
    """Get player's last 10 games average for specific stat"""
    stat_col = {
        'player_points': 'pts',
        'player_rebounds': 'reb',
        'player_assists': 'ast',
        'player_threes': 'fg3m',
        'player_steals': 'stl',
        'player_blocks': 'blk'
    }.get(market, 'pts')
    
    query = text(f"""
        SELECT AVG({stat_col}) as avg_stat
        FROM (
            SELECT {stat_col}
            FROM player_boxscores
            WHERE player_name = :player
            ORDER BY game_date DESC
            LIMIT 10
        ) last_10
    """)
    
    try:
        with engine.connect() as conn:
            result = conn.execute(query, {"player": player}).fetchone()
            return float(result[0]) if result and result[0] else None
    except:
        return None

def calculate_prop_edge(row, engine):
    player, market, line, over_odds, under_odds, book = row
    
    if line is None:
        return None
    
    line = float(line)
    avg = get_player_avg(engine, player, market)
    
    if avg is None:
        return None
    
    # Calculate edge
    diff = avg - line
    edge_pct = (diff / line) * 100 if line > 0 else 0
    
    # Only return if significant edge (>12%)
    if abs(edge_pct) < 12:
        return None
    
    if diff > 0:
        pick = f"OVER {line}"
        direction = "OVER"
    else:
        pick = f"UNDER {line}"
        direction = "UNDER"
    
    # Unit sizing based on edge
    edge_abs = abs(edge_pct)
    if edge_abs >= 25:
        units = "1.5u"
        unit_emoji = "🔥🔥"
    elif edge_abs >= 18:
        units = "1.0u"
        unit_emoji = "🔥"
    else:
        units = "0.5u"
        unit_emoji = "✅"
    
    market_clean = market.replace('player_', '').replace('_', ' ').title()
    
    return {
        'player': player,
        'market': market_clean,
        'line': line,
        'pick': pick,
        'edge': edge_abs,
        'avg': avg,
        'direction': direction,
        'book': book or 'Consensus',
        'units': units,
        'unit_emoji': unit_emoji
    }

def build_prop_embed(prop):
    """Build Discord embed for a prop pick"""
    if prop['edge'] >= 25:
        color = 0xFF0000  # Red = fire
    elif prop['edge'] >= 18:
        color = 0x00FF00  # Green = solid
    else:
        color = 0xFFAA00  # Orange = decent
    
    return {
        "title": f"🎯 {prop['player']} — {prop['market']}",
        "description": f"**{prop['pick']}** — {prop['units']} {prop['unit_emoji']}",
        "color": color,
        "fields": [
            {"name": "Edge", "value": f"+{prop['edge']:.0f}%", "inline": True},
            {"name": "L10 Avg", "value": f"{prop['avg']:.1f}", "inline": True},
            {"name": "Line", "value": f"{prop['line']}", "inline": True},
            {"name": "Book", "value": prop['book'], "inline": True},
        ],
        "footer": {"text": f"SB-ALGO Props • {get_eastern_time()}"}
    }

def main():
    log.info("=" * 50)
    log.info(f"SB-ALGO Props Publisher | {get_eastern_date()}")
    log.info("=" * 50)
    
    if not DATABASE_URL:
        log.error("Missing DATABASE_URL")
        sys.exit(1)
    if not DISCORD_WEBHOOK:
        log.error("Missing DISCORD_WEBHOOK_TOP_PROPS")
        sys.exit(1)
    
    engine = create_engine(DATABASE_URL)
    
    # Fetch props
    props = fetch_todays_props(engine)
    log.info(f"Found {len(props)} props today")
    
    if not props:
        send_discord({
            "username": "SB-ALGO Props",
            "content": f"📅 **{get_eastern_date()}** | No props available today."
        })
        return
    
    # Calculate edges
    prop_edges = []
    for p in props:
        edge = calculate_prop_edge(p, engine)
        if edge:
            prop_edges.append(edge)
    
    log.info(f"Found {len(prop_edges)} props with edge")
    
    if not prop_edges:
        send_discord({
            "username": "SB-ALGO Props",
            "content": f"📅 **{get_eastern_date()}** | No high-value props found today."
        })
        return
    
    # Sort by edge
    prop_edges.sort(key=lambda x: x['edge'], reverse=True)
    
    # Build embeds (top 5 props)
    embeds = [{
        "title": "🎯 SB-ALGO Top Props",
        "description": f"**{get_eastern_date()}** | {len(prop_edges)} Props with Edge",
        "color": 0x667eea,
        "footer": {"text": f"Published {get_eastern_time()}"}
    }]
    
    for prop in prop_edges[:5]:
        embeds.append(build_prop_embed(prop))
    
    # Send
    success = send_discord({"username": "SB-ALGO Props", "embeds": embeds})
    
    if success:
        log.info(f"Posted {len(prop_edges[:5])} props to Discord")
    else:
        log.error("Failed to post")
        sys.exit(1)

if __name__ == "__main__":
    main()
