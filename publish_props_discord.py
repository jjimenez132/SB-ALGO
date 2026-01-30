#!/usr/bin/env python3
"""
publish_props_discord.py - Props Publisher for Discord
=======================================================
Sends top prop picks to Discord channel using sb_algo_api (FULL TIERED ENGINE)

FEATURES:
- Uses sb_algo_api.get_todays_picks() which applies FINAL_CONFIG filters
- Only sends NEW picks not already sent today (supports mid-day runs)
- Shows "🆕 NEW VALUE FOUND" header for mid-day updates
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

DISCORD_WEBHOOK = os.environ.get('DISCORD_WEBHOOK_TOP_PROPS')
DATABASE_URL = os.environ.get('DATABASE_URL',
    "postgresql://sb_algo_db_user:0HDtYp4EY2Lo5At8iyf44PD1zDioSPK7@dpg-d495uhchg0os738l1a50-a.virginia-postgres.render.com/sb_algo_db")

def get_eastern_date():
    return datetime.now(pytz.timezone('US/Eastern')).date()

def get_eastern_time():
    return datetime.now(pytz.timezone('US/Eastern')).strftime('%I:%M %p ET')

def get_already_sent_today():
    """Get list of pick_keys already sent today"""
    engine = create_engine(DATABASE_URL)
    today = get_eastern_date()
    
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT pick_key FROM discord_sent_picks 
            WHERE sent_date = :today
        """), {'today': today})
        return set(row[0] for row in result)

def make_pick_key(player, stat, side):
    """Create unique key for a prop pick"""
    stat_abbrev = stat.replace('player_', '').upper()[:3]
    return f"PROP_{player}_{stat_abbrev}_{side.upper()}"

def record_sent_pick(pick_key):
    """Record pick as sent in database"""
    engine = create_engine(DATABASE_URL)
    today = get_eastern_date()
    with engine.connect() as conn:
        conn.execute(text("""
            INSERT INTO discord_sent_picks (pick_key, sent_date, sent_at)
            VALUES (:key, :date, NOW())
            ON CONFLICT (pick_key, sent_date) DO NOTHING
        """), {'key': pick_key, 'date': today})
        conn.commit()

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

def build_prop_embed(prop, is_midday=False):
    """Build Discord embed for a prop pick"""
    edge = prop.get('edge', 0)
    
    # Parse edge if it's a string like "+25%"
    if isinstance(edge, str):
        edge = float(edge.replace('+', '').replace('%', ''))
    
    grade = prop.get('grade', 'B')
    
    if grade in ['A+', 'A'] or edge >= 30:
        color = 0xFF0000  # Red = fire
        unit_emoji = "🔥🔥"
        units = "1.5u"
    elif grade == 'B+' or edge >= 20:
        color = 0x00FF00  # Green = solid
        unit_emoji = "🔥"
        units = "1.0u"
    else:
        color = 0xFFAA00  # Orange = decent
        unit_emoji = "✅"
        units = "0.5u"
    
    # Get stat type
    subtype = prop.get('subtype', 'points')
    if subtype:
        market = subtype.replace('player_', '').replace('_', ' ').title()
    else:
        market = 'Points'
    
    # Add NEW tag for mid-day picks
    title_prefix = "🆕 " if is_midday else "🎯 "
    
    player = prop.get('player', 'Unknown')
    pick_str = prop.get('pick', '')
    
    # Extract line from pick string if not provided
    line = prop.get('line', 0)
    projection = prop.get('projection', prop.get('model', 0))
    hit_rate = prop.get('hit_rate', '')
    
    fields = [
        {"name": "Edge", "value": f"+{edge:.0f}%", "inline": True},
        {"name": "Grade", "value": grade, "inline": True},
        {"name": "Stake", "value": units, "inline": True},
    ]
    
    if projection:
        fields.append({"name": "Model Projection", "value": f"{float(projection):.1f}", "inline": True})
    if line:
        fields.append({"name": "Line", "value": f"{line}", "inline": True})
    if hit_rate:
        fields.append({"name": "Hit Rate", "value": str(hit_rate), "inline": True})
    
    return {
        "title": f"{title_prefix}{player} — {market}",
        "description": f"**{pick_str}** — {units} {unit_emoji}",
        "color": color,
        "fields": fields[:6],  # Discord max fields
        "footer": {"text": f"SB-ALGO Props • {get_eastern_time()}"}
    }

def main():
    log.info("=" * 50)
    log.info(f"SB-ALGO Props Publisher | {get_eastern_date()}")
    log.info("=" * 50)
    
    if not DISCORD_WEBHOOK:
        log.error("Missing DISCORD_WEBHOOK_TOP_PROPS")
        sys.exit(1)
    
    # Get already sent picks
    already_sent = get_already_sent_today()
    log.info(f"Already sent today: {len(already_sent)} picks")
    
    # Use sb_algo_api to get filtered tier picks
    log.info("Running sb_algo_api.get_todays_picks() (FULL TIERED ENGINE)...")
    try:
        from sb_algo_api import get_todays_picks
        picks_data = get_todays_picks(force_refresh=True)
    except Exception as e:
        import traceback
        log.error(f"Error: {e}")
        traceback.print_exc()
        sys.exit(1)
    
    # Get prop picks (already filtered by FINAL_CONFIG!)
    prop_picks = picks_data.get('prop_picks', [])
    
    log.info(f"Found {len(prop_picks)} official prop picks (passed tier filters)")
    
    if not prop_picks:
        log.info("No official prop picks for today")
        return
    
    # Filter out already sent picks
    new_props = []
    for prop in prop_picks:
        player = prop.get('player', '')
        subtype = prop.get('subtype', 'player_points')
        pick_str = prop.get('pick', '')
        
        # Extract side from pick string
        side = 'OVER' if 'OVER' in pick_str.upper() else 'UNDER'
        
        pick_key = make_pick_key(player, subtype, side)
        
        if pick_key not in already_sent:
            prop['_pick_key'] = pick_key
            new_props.append(prop)
        else:
            log.info(f"⏭️ Skipping already sent: {pick_key}")
    
    if not new_props:
        log.info("✅ No NEW props to send (all official picks already sent today)")
        return
    
    log.info(f"🆕 Found {len(new_props)} NEW official props to send")
    
    # Check if this is a mid-day run
    is_midday = len(already_sent) > 0
    
    # Build embeds
    if is_midday:
        header = {
            "title": "🆕 NEW VALUE FOUND",
            "description": f"**{get_eastern_time()}** | Odds updated → {len(new_props)} new pick(s) passed filters!",
            "color": 0x00BFFF  # Light blue for updates
        }
    else:
        header = {
            "title": "🎯 SB-ALGO Official Props",
            "description": f"**{get_eastern_date()}** | {len(new_props)} props passed tier filters\nTop picks below:",
            "color": 0x667eea
        }
    
    embeds = [header]
    
    # Limit to 5 picks per message (Discord embed limit)
    for prop in new_props[:5]:
        embeds.append(build_prop_embed(prop, is_midday))
    
    # Send
    success = send_discord({"username": "SB-ALGO Props", "embeds": embeds})
    
    if success:
        log.info(f"✅ Posted {min(5, len(new_props))} official props to Discord")
        
        # Record sent picks
        for prop in new_props[:5]:
            pick_key = prop.get('_pick_key')
            if pick_key:
                record_sent_pick(pick_key)
                log.info(f"📝 Recorded: {pick_key}")
    else:
        log.error("Failed to post")
        sys.exit(1)

if __name__ == "__main__":
    main()

# ============================================================
# RESULTS INTEGRATION
# ============================================================

def post_prop_to_results(player: str, pick: str, units: float, odds: int = None):
    """Post prop to #results channel for tracking"""
    try:
        from discord_results import create_pick_message
        pick_name = f"{player} {pick}"
        pick_id, message_id = create_pick_message('prop', pick_name, units, odds)
        log.info(f"📊 Created results entry #{pick_id} for: {pick_name}")
        return pick_id
    except Exception as e:
        log.warning(f"Could not post to results: {e}")
        return None

def get_pick_footer():
    """Footer to add to prop embeds"""
    return "📊 Tracking in #results | Personal stake: !preview"
