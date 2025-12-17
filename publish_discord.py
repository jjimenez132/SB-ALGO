#!/usr/bin/env python3
"""
publish_discord.py - Production Discord Publisher for SB-ALGO
Runs as Render Cron Job - NO local execution required.
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

def fetch_todays_games(engine):
    today = get_eastern_date()
    query = text("""
        SELECT g.home_team, g.visitor_team, g.start_time, g.home_days_rest, g.visitor_days_rest,
               g.home_is_b2b, g.visitor_is_b2b, b.home_spread, b.total, b.sportsbook
        FROM games g
        LEFT JOIN betting_odds b ON g.date = b.game_date AND g.home_team = b.home_team
        WHERE g.date = :today AND g.home_pts IS NULL
        ORDER BY g.start_time
    """)
    with engine.connect() as conn:
        return conn.execute(query, {"today": today}).fetchall()

def build_embed(row):
    home, away, time_str, h_rest, a_rest, h_b2b, a_b2b, spread, total, book = row
    spread = spread or 0
    rest_diff = (h_rest or 0) - (a_rest or 0)
    b2b_adj = (-2 if h_b2b else 0) + (2 if a_b2b else 0)
    pred = 3 + rest_diff * 0.5 + b2b_adj
    edge = pred - (-spread)
    
    if edge > 2:
        pick, conf = f"{home} {spread}", min(85, 65 + edge * 3)
        color = 0x00FF00
    elif edge < -2:
        pick, conf = f"{away} +{-spread}", min(85, 65 + abs(edge) * 3)
        color = 0x00FF00
    else:
        pick, conf, color = "NO EDGE", 50, 0x666666
    
    notes = []
    if h_b2b: notes.append(f"{home} B2B")
    if a_b2b: notes.append(f"{away} B2B")
    
    return {
        "title": f"🏀 {away} @ {home}",
        "description": f"**{pick}**",
        "color": color,
        "fields": [
            {"name": "Edge", "value": f"{abs(edge):.1f} pts", "inline": True},
            {"name": "Confidence", "value": f"{conf:.0f}%", "inline": True},
            {"name": "Line", "value": f"{spread} @ {book or 'N/A'}", "inline": True},
            {"name": "Total", "value": str(total) if total else "N/A", "inline": True},
            {"name": "Time", "value": time_str or "TBD", "inline": True},
            {"name": "Notes", "value": " | ".join(notes) if notes else "Clean", "inline": True},
        ],
        "footer": {"text": f"SB-ALGO Terminal • {get_eastern_time()}"}
    }, pick != "NO EDGE" and conf >= 60

def main():
    log.info(f"SB-ALGO Discord Publisher | {get_eastern_date()}")
    
    if not DATABASE_URL:
        log.error("Missing DATABASE_URL")
        sys.exit(1)
    if not DISCORD_WEBHOOK:
        log.error("Missing DISCORD_WEBHOOK_TOP_EDGES")
        sys.exit(1)
    
    engine = create_engine(DATABASE_URL)
    games = fetch_todays_games(engine)
    log.info(f"Found {len(games)} games")
    
    if not games:
        send_discord({"username": "SB-ALGO Terminal", "content": f"📅 {get_eastern_date()} | No NBA games today."})
        return
    
    embeds = [{"title": "📊 SB-ALGO Daily Edges", "description": f"**{get_eastern_date()}** | {len(games)} Games", "color": 0x667eea}]
    
    for row in games:
        embed, actionable = build_embed(row)
        if actionable and len(embeds) < 10:
            embeds.append(embed)
    
    send_discord({"username": "SB-ALGO Terminal", "embeds": embeds})
    log.info("Publish complete")

if __name__ == "__main__":
    main()
