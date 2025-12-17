#!/usr/bin/env python3
"""
publish_discord.py - Smart Discord Publisher for SB-ALGO
==========================================================
- 9 AM ET: Full daily report (2 games + 2 props + reasoning)
- Hourly (10 AM - 9 PM): Only HIGH VALUE alerts (edge >= 5)
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
DISCORD_WEBHOOK = os.environ.get('DISCORD_WEBHOOK_TOP_EDGES')

MIN_EDGE_FOR_ALERT = 5.0  # Only alert during day if edge >= this

def get_eastern_date():
    return datetime.now(pytz.timezone('US/Eastern')).strftime('%Y-%m-%d')

def get_eastern_time():
    return datetime.now(pytz.timezone('US/Eastern')).strftime('%I:%M %p ET')

def get_eastern_hour():
    return datetime.now(pytz.timezone('US/Eastern')).hour

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

def fetch_todays_games(engine):
    today = get_eastern_date()
    query = text("""
        SELECT g.home_team, g.visitor_team, g.start_time, g.home_days_rest, g.visitor_days_rest,
               g.home_is_b2b, g.visitor_is_b2b, b.home_spread, b.total, b.sportsbook
        FROM games g
        LEFT JOIN betting_odds b ON g.date = b.game_date AND g.home_team = b.home_team
        WHERE g.date = :today AND (g.home_pts IS NULL OR g.home_pts = 0)
        ORDER BY g.start_time
    """)
    with engine.connect() as conn:
        return conn.execute(query, {"today": today}).fetchall()

def fetch_todays_props(engine):
    today = get_eastern_date()
    query = text("""
        SELECT player_name, market, line, over_odds, under_odds, sportsbook
        FROM player_props
        WHERE game_date = :today
        LIMIT 100
    """)
    try:
        with engine.connect() as conn:
            return conn.execute(query, {"today": today}).fetchall()
    except:
        return []

def calculate_game_edge(row):
    home, away, time_str, h_rest, a_rest, h_b2b, a_b2b, spread, total, book = row
    
    if spread is None:
        return None
    
    spread = float(spread)
    rest_diff = (h_rest or 0) - (a_rest or 0)
    b2b_adj = (-2 if h_b2b else 0) + (2 if a_b2b else 0)
    
    predicted_margin = 3 + rest_diff * 0.5 + b2b_adj
    edge = predicted_margin - (-spread)
    
    if abs(edge) < 1.5:
        return None
    
    if edge > 0:
        pick = f"{home} {spread}"
        side = "HOME"
    else:
        pick = f"{away} +{-spread}"
        side = "AWAY"
    
    edge_abs = abs(edge)
    
    # Unit sizing based on edge
    if edge_abs >= 7:
        units = "2.0u"
        unit_emoji = "🔥🔥"
    elif edge_abs >= 5:
        units = "1.5u"
        unit_emoji = "🔥"
    elif edge_abs >= 3:
        units = "1.0u"
        unit_emoji = "✅"
    else:
        units = "0.5u"
        unit_emoji = "📊"
    
    # Build reasoning
    reasons = []
    if rest_diff > 0:
        reasons.append(f"{home} has rest advantage (+{rest_diff} days)")
    elif rest_diff < 0:
        reasons.append(f"{away} has rest advantage (+{abs(rest_diff)} days)")
    
    if h_b2b:
        reasons.append(f"{home} on back-to-back (fatigue factor)")
    if a_b2b:
        reasons.append(f"{away} on back-to-back (fatigue factor)")
    
    reasons.append(f"Home court advantage factored (+3 pts)")
    reasons.append(f"Model projects {home} by {predicted_margin:+.1f}")
    reasons.append(f"Line value: {edge_abs:.1f} pts edge vs market")
    
    return {
        'matchup': f"{away} @ {home}",
        'pick': pick,
        'edge': edge_abs,
        'confidence': min(92, 60 + edge_abs * 4),
        'spread': spread,
        'total': total,
        'book': book or 'Consensus',
        'time': time_str or 'TBD',
        'home': home,
        'away': away,
        'h_b2b': h_b2b,
        'a_b2b': a_b2b,
        'units': units,
        'unit_emoji': unit_emoji,
        'side': side,
        'reasoning': reasons,
        'predicted_margin': predicted_margin
    }

def calculate_prop_edge(row, engine):
    player, market, line, over_odds, under_odds, book = row
    
    if line is None:
        return None
    
    line = float(line)
    
    # Get player's last 10 games average
    query = text("""
        SELECT AVG(pts) as avg_pts, AVG(reb) as avg_reb, AVG(ast) as avg_ast,
               AVG(fg3m) as avg_3pm, AVG(stl) as avg_stl, AVG(blk) as avg_blk
        FROM player_boxscores
        WHERE player_name = :player
        ORDER BY game_date DESC
        LIMIT 10
    """)
    
    try:
        with engine.connect() as conn:
            stats = conn.execute(query, {"player": player}).fetchone()
    except:
        return None
    
    if not stats or stats[0] is None:
        return None
    
    # Map market to stat
    market_map = {
        'player_points': stats[0],
        'player_rebounds': stats[1],
        'player_assists': stats[2],
        'player_threes': stats[3],
        'player_steals': stats[4],
        'player_blocks': stats[5],
    }
    
    avg = market_map.get(market)
    if avg is None:
        return None
    
    avg = float(avg)
    
    # Calculate edge
    diff = avg - line
    edge_pct = (diff / line) * 100 if line > 0 else 0
    
    if abs(edge_pct) < 10:
        return None
    
    if diff > 0:
        pick = f"OVER {line}"
        direction = "OVER"
    else:
        pick = f"UNDER {line}"
        direction = "UNDER"
    
    edge_abs = abs(edge_pct)
    
    # Unit sizing
    if edge_abs >= 25:
        units = "1.5u"
        unit_emoji = "🔥"
    elif edge_abs >= 15:
        units = "1.0u"
        unit_emoji = "✅"
    else:
        units = "0.5u"
        unit_emoji = "📊"
    
    market_clean = market.replace('player_', '').title()
    
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
        'unit_emoji': unit_emoji,
        'reasoning': [
            f"L10 average: {avg:.1f} {market_clean.lower()}",
            f"Line: {line}",
            f"Edge: {edge_abs:.0f}% {'above' if diff > 0 else 'below'} projection"
        ]
    }

# ============================================================
# EMBED BUILDERS
# ============================================================

def build_game_card(pick):
    """Single game card with full details"""
    if pick['edge'] >= 6:
        color = 0xFF0000  # Red = max value
    elif pick['edge'] >= 4:
        color = 0x00FF00  # Green = high value
    else:
        color = 0xFFFF00  # Yellow = solid
    
    return {
        "title": f"🏀 {pick['matchup']}",
        "description": f"**{pick['pick']}** — {pick['units']} {pick['unit_emoji']}",
        "color": color,
        "fields": [
            {"name": "Expected Value", "value": f"+{pick['edge']:.1f} pts", "inline": True},
            {"name": "Win Probability", "value": f"{pick['confidence']:.0f}%", "inline": True},
            {"name": "Market Line", "value": f"{pick['spread']} @ {pick['book']}", "inline": True},
            {"name": "AI Stake", "value": pick['units'], "inline": True},
            {"name": "Risk Class", "value": "High" if pick['edge'] >= 5 else "Medium", "inline": True},
            {"name": "Game Time", "value": pick['time'], "inline": True},
        ],
        "footer": {"text": "SB-ALGO Terminal • Automated"}
    }

def build_game_reasoning(pick):
    """Reasoning block for a game pick"""
    reasoning_text = "\n".join([f"• {r}" for r in pick['reasoning']])
    
    return {
        "title": f"🧠 Algo Reasoning — {pick['pick']}",
        "description": reasoning_text,
        "color": 0x667eea,
        "footer": {"text": f"Model confidence: {pick['confidence']:.0f}%"}
    }

def build_prop_card(prop):
    """Single prop card"""
    color = 0xFFAA00  # Orange for props
    
    return {
        "title": f"🎯 {prop['player']} — {prop['market']}",
        "description": f"**{prop['pick']}** — {prop['units']} {prop['unit_emoji']}",
        "color": color,
        "fields": [
            {"name": "Edge", "value": f"+{prop['edge']:.0f}%", "inline": True},
            {"name": "L10 Avg", "value": f"{prop['avg']:.1f}", "inline": True},
            {"name": "Line", "value": f"{prop['line']}", "inline": True},
        ],
        "footer": {"text": f"SB-ALGO Props Engine • {prop['book']}"}
    }

def build_prop_reasoning(prop):
    """Reasoning for prop"""
    reasoning_text = "\n".join([f"• {r}" for r in prop['reasoning']])
    
    return {
        "title": f"📊 Prop Analysis — {prop['player']}",
        "description": reasoning_text,
        "color": 0x667eea,
    }

# ============================================================
# MAIN FUNCTIONS
# ============================================================

def publish_morning_report(engine):
    """Full morning report: 2 games + 2 props + reasoning"""
    log.info("Publishing MORNING REPORT...")
    
    games = fetch_todays_games(engine)
    props = fetch_todays_props(engine)
    
    if not games:
        send_discord({
            "username": "SB-ALGO Terminal",
            "content": f"📅 **{get_eastern_date()}** | No NBA games scheduled today."
        })
        return
    
    # Calculate all edges
    game_edges = [calculate_game_edge(g) for g in games]
    game_edges = [g for g in game_edges if g is not None]
    game_edges.sort(key=lambda x: x['edge'], reverse=True)
    
    prop_edges = [calculate_prop_edge(p, engine) for p in props]
    prop_edges = [p for p in prop_edges if p is not None]
    prop_edges.sort(key=lambda x: x['edge'], reverse=True)
    
    # Build embeds
    embeds = []
    
    # Header
    embeds.append({
        "title": "☀️ SB-ALGO Morning Report",
        "description": f"**{get_eastern_date()}** | {len(games)} Games Today\nTop picks with full algo reasoning below.",
        "color": 0x667eea,
        "footer": {"text": f"Published {get_eastern_time()}"}
    })
    
    # Top 2 game picks with reasoning
    for pick in game_edges[:2]:
        embeds.append(build_game_card(pick))
        embeds.append(build_game_reasoning(pick))
    
    # Top 2 prop picks with reasoning
    for prop in prop_edges[:2]:
        embeds.append(build_prop_card(prop))
        embeds.append(build_prop_reasoning(prop))
    
    # Limit to 10 embeds (Discord max)
    embeds = embeds[:10]
    
    success = send_discord({"username": "SB-ALGO Terminal", "embeds": embeds})
    
    if success:
        log.info(f"Morning report posted: {len(game_edges)} games, {len(prop_edges)} props analyzed")
    else:
        log.error("Failed to post morning report")

def publish_hourly_alert(engine):
    """Hourly check: only post if HIGH VALUE edge found"""
    log.info("Checking for HIGH VALUE edges...")
    
    games = fetch_todays_games(engine)
    
    if not games:
        log.info("No games. Skipping.")
        return
    
    game_edges = [calculate_game_edge(g) for g in games]
    game_edges = [g for g in game_edges if g is not None]
    
    # Filter to HIGH VALUE only
    high_value = [g for g in game_edges if g['edge'] >= MIN_EDGE_FOR_ALERT]
    
    if not high_value:
        log.info(f"No edges >= {MIN_EDGE_FOR_ALERT} pts. Staying silent.")
        return
    
    high_value.sort(key=lambda x: x['edge'], reverse=True)
    
    embeds = [{
        "title": "🚨 HIGH VALUE ALERT",
        "description": f"Edge detected at {get_eastern_time()}",
        "color": 0xFF0000
    }]
    
    for pick in high_value[:3]:
        embeds.append(build_game_card(pick))
    
    send_discord({"username": "SB-ALGO Terminal", "embeds": embeds})
    log.info(f"Posted {len(high_value)} high value alerts")

def main():
    log.info("=" * 50)
    log.info(f"SB-ALGO Discord | {get_eastern_date()} {get_eastern_time()}")
    log.info("=" * 50)
    
    hour = get_eastern_hour()
    
    # Check operating hours (7 AM - 9 PM ET)
    if hour < 7 or hour > 21:
        log.info(f"Outside hours ({hour}:00 ET). Exiting.")
        return
    
    if not DATABASE_URL:
        log.error("Missing DATABASE_URL")
        sys.exit(1)
    if not DISCORD_WEBHOOK:
        log.error("Missing DISCORD_WEBHOOK_TOP_EDGES")
        sys.exit(1)
    
    engine = create_engine(DATABASE_URL)
    
    # 9 AM = Full morning report
    if hour == 9:
        publish_morning_report(engine)
    else:
        # Other hours = alert only if high value
        publish_hourly_alert(engine)
    
    log.info("Done.")

if __name__ == "__main__":
    main()
