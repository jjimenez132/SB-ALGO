#!/usr/bin/env python3
"""
discord_results.py - Results Tracking & Daily Recap System
===========================================================
Tracks every pick, updates results, and posts daily summaries.
"""

import os
import logging
from datetime import datetime, date
from decimal import Decimal
import pytz
import requests
from sqlalchemy import create_engine, text

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(message)s')
log = logging.getLogger(__name__)

DATABASE_URL = os.environ.get('DATABASE_URL',
    "postgresql://sb_algo_db_user:0HDtYp4EY2Lo5At8iyf44PD1zDioSPK7@dpg-d495uhchg0os738l1a50-a.virginia-postgres.render.com/sb_algo_db")

# Discord webhooks
RESULTS_WEBHOOK = os.environ.get('DISCORD_WEBHOOK_RESULTS')
RECAP_WEBHOOK = os.environ.get('DISCORD_WEBHOOK_RECAP')
HEALTH_WEBHOOK = os.environ.get('DISCORD_WEBHOOK_HEALTH')

def get_engine():
    return create_engine(DATABASE_URL)

def get_eastern_now():
    return datetime.now(pytz.timezone('US/Eastern'))

def get_eastern_date():
    return get_eastern_now().strftime('%Y-%m-%d')

# ============================================================
# PICK TRACKING DATABASE
# ============================================================

def init_picks_table():
    """Create picks tracking table if not exists"""
    engine = get_engine()
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS algo_picks_tracking (
                id SERIAL PRIMARY KEY,
                pick_date DATE NOT NULL,
                pick_type VARCHAR(20) NOT NULL,
                pick_name VARCHAR(200) NOT NULL,
                pick_details TEXT,
                units DECIMAL(4,2) NOT NULL,
                odds INTEGER,
                status VARCHAR(20) DEFAULT 'pending',
                result_units DECIMAL(6,2) DEFAULT 0,
                discord_message_id VARCHAR(50),
                discord_channel_id VARCHAR(50),
                created_at TIMESTAMP DEFAULT NOW(),
                graded_at TIMESTAMP,
                UNIQUE(pick_date, pick_type, pick_name)
            )
        """))
        conn.commit()
    log.info("✅ Picks tracking table ready")

# ============================================================
# RESULTS CHANNEL FUNCTIONS
# ============================================================

def create_pick_message(pick_type: str, pick_name: str, units: float, odds: int = None, details: str = None):
    """Create a new pick in #results channel and database"""
    engine = get_engine()
    today = get_eastern_date()
    
    # Save to database first
    with engine.connect() as conn:
        result = conn.execute(text("""
            INSERT INTO algo_picks_tracking (pick_date, pick_type, pick_name, pick_details, units, odds, status)
            VALUES (:date, :type, :name, :details, :units, :odds, 'pending')
            ON CONFLICT (pick_date, pick_type, pick_name) DO UPDATE SET
                units = :units, odds = :odds, pick_details = :details
            RETURNING id
        """), {
            "date": today, "type": pick_type, "name": pick_name,
            "details": details, "units": units, "odds": odds
        })
        pick_id = result.fetchone()[0]
        conn.commit()
    
    # Post to Discord #results
    if RESULTS_WEBHOOK:
        embed = build_pick_embed(pick_id, pick_name, units, odds, 'pending')
        message_id = send_to_results(embed)
        
        # Save message ID for later editing
        if message_id:
            with engine.connect() as conn:
                conn.execute(text("""
                    UPDATE algo_picks_tracking 
                    SET discord_message_id = :mid
                    WHERE id = :pid
                """), {"mid": message_id, "pid": pick_id})
                conn.commit()
        
        return pick_id, message_id
    
    return pick_id, None

def build_pick_embed(pick_id: int, pick_name: str, units: float, odds: int, status: str, result_units: float = 0):
    """Build embed for pick based on status"""
    
    if status == 'pending':
        emoji = "⏳"
        color = 0x667eea  # Purple
        status_text = "Pending"
        result_text = ""
    elif status == 'win':
        emoji = "✅"
        color = 0x00FF00  # Green
        status_text = "WIN"
        result_text = f"\n**+{result_units:.1f}u**"
    elif status == 'loss':
        emoji = "❌"
        color = 0xFF0000  # Red
        status_text = "LOSS"
        result_text = f"\n**{result_units:.1f}u**"
    elif status == 'void':
        emoji = "🟨"
        color = 0xFFFF00  # Yellow
        status_text = "VOID"
        result_text = "\n**0.0u**"
    else:
        emoji = "⏳"
        color = 0x667eea
        status_text = status.upper()
        result_text = ""
    
    odds_text = f" @ {odds:+d}" if odds else ""
    
    embed = {
        "title": f"{emoji} {pick_name}",
        "description": f"**{units}u**{odds_text}\nStatus: {status_text}{result_text}",
        "color": color,
        "footer": {"text": f"Pick #{pick_id} | {get_eastern_now().strftime('%I:%M %p ET')}"}
    }
    
    return embed

def send_to_results(embed: dict):
    """Send embed to #results channel, return message ID"""
    if not RESULTS_WEBHOOK:
        log.warning("No RESULTS_WEBHOOK configured")
        return None
    
    try:
        # Add ?wait=true to get message ID back
        url = RESULTS_WEBHOOK + "?wait=true"
        payload = {"embeds": [embed]}
        r = requests.post(url, json=payload, timeout=10)
        
        if r.status_code == 200:
            data = r.json()
            return data.get('id')
        else:
            log.error(f"Results webhook error: {r.status_code}")
            return None
    except Exception as e:
        log.error(f"Results webhook failed: {e}")
        return None

def update_pick_result(pick_id: int = None, pick_name: str = None, pick_date: str = None, 
                       result: str = 'win', void_reason: str = None):
    """Update pick result - edits the Discord message"""
    engine = get_engine()
    
    # Find the pick
    with engine.connect() as conn:
        if pick_id:
            pick = conn.execute(text("""
                SELECT id, pick_name, units, odds, discord_message_id 
                FROM algo_picks_tracking WHERE id = :pid
            """), {"pid": pick_id}).fetchone()
        elif pick_name and pick_date:
            pick = conn.execute(text("""
                SELECT id, pick_name, units, odds, discord_message_id 
                FROM algo_picks_tracking 
                WHERE pick_name = :name AND pick_date = :date
            """), {"name": pick_name, "date": pick_date}).fetchone()
        else:
            log.error("Must provide pick_id or (pick_name + pick_date)")
            return False
        
        if not pick:
            log.error(f"Pick not found: {pick_id or pick_name}")
            return False
        
        pick_id, pick_name, units, odds, message_id = pick
        units = float(units)
        
        # Calculate result units
        if result == 'win':
            if odds and odds > 0:
                result_units = units * (odds / 100)
            elif odds and odds < 0:
                result_units = units * (100 / abs(odds))
            else:
                result_units = units  # Default even money
        elif result == 'loss':
            result_units = -units
        else:  # void
            result_units = 0
        
        # Update database
        conn.execute(text("""
            UPDATE algo_picks_tracking SET
                status = :status,
                result_units = :ru,
                graded_at = NOW()
            WHERE id = :pid
        """), {"status": result, "ru": result_units, "pid": pick_id})
        conn.commit()
    
    # Edit Discord message
    if message_id and RESULTS_WEBHOOK:
        embed = build_pick_embed(pick_id, pick_name, units, odds, result, result_units)
        edit_results_message(message_id, embed)
    
    log.info(f"✅ Pick #{pick_id} graded: {result} ({result_units:+.1f}u)")
    return True

def edit_results_message(message_id: str, embed: dict):
    """Edit existing message in #results"""
    if not RESULTS_WEBHOOK:
        return False
    
    try:
        # Extract webhook ID and token from URL
        parts = RESULTS_WEBHOOK.split('/')
        webhook_id = parts[-2]
        webhook_token = parts[-1]
        
        url = f"https://discord.com/api/webhooks/{webhook_id}/{webhook_token}/messages/{message_id}"
        payload = {"embeds": [embed]}
        r = requests.patch(url, json=payload, timeout=10)
        
        if r.status_code == 200:
            log.info(f"✅ Edited message {message_id}")
            return True
        else:
            log.error(f"Edit failed: {r.status_code} - {r.text}")
            return False
    except Exception as e:
        log.error(f"Edit failed: {e}")
        return False

# ============================================================
# DAILY RECAP
# ============================================================

def get_daily_stats(date_str: str = None):
    """Get stats for a specific day"""
    engine = get_engine()
    if not date_str:
        date_str = get_eastern_date()
    
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN status = 'win' THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN status = 'loss' THEN 1 ELSE 0 END) as losses,
                SUM(CASE WHEN status = 'void' THEN 1 ELSE 0 END) as voids,
                SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending,
                COALESCE(SUM(result_units), 0) as net_units
            FROM algo_picks_tracking
            WHERE pick_date = :date
        """), {"date": date_str}).fetchone()
        
        return {
            "date": date_str,
            "total": result[0] or 0,
            "wins": result[1] or 0,
            "losses": result[2] or 0,
            "voids": result[3] or 0,
            "pending": result[4] or 0,
            "net_units": float(result[5] or 0)
        }

def post_daily_recap(date_str: str = None):
    """Post daily recap to #daily-recap channel"""
    if not RECAP_WEBHOOK:
        log.warning("No RECAP_WEBHOOK configured")
        return False
    
    stats = get_daily_stats(date_str)
    
    # Skip if nothing happened
    if stats['total'] == 0:
        log.info("No picks today, skipping recap")
        return False
    
    # Skip if picks still pending
    if stats['pending'] > 0:
        log.info(f"{stats['pending']} picks still pending, skipping recap")
        return False
    
    # Build recap embed
    net = stats['net_units']
    if net > 0:
        emoji = "✅"
        color = 0x00FF00
        note = "Solid day! The edge delivered."
    elif net < 0:
        emoji = "❌"
        color = 0xFF0000
        note = "Variance happens. Trust the process."
    else:
        emoji = "➡️"
        color = 0xFFFF00
        note = "Break even. Live to fight another day."
    
    # Format date nicely
    date_obj = datetime.strptime(stats['date'], '%Y-%m-%d')
    date_formatted = date_obj.strftime('%B %d, %Y').upper()
    
    embed = {
        "title": f"📊 DAILY SUMMARY — {date_formatted}",
        "color": color,
        "fields": [
            {"name": "✅ Wins", "value": str(stats['wins']), "inline": True},
            {"name": "❌ Losses", "value": str(stats['losses']), "inline": True},
            {"name": "🟨 Voids", "value": str(stats['voids']), "inline": True},
            {"name": f"{emoji} Net Result", "value": f"**{net:+.1f} units**", "inline": False},
        ],
        "footer": {"text": f"{note} | See #results for full breakdown"}
    }
    
    try:
        r = requests.post(RECAP_WEBHOOK, json={"embeds": [embed]}, timeout=10)
        if r.status_code == 204:
            log.info(f"✅ Posted daily recap: {net:+.1f}u")
            return True
        else:
            log.error(f"Recap webhook error: {r.status_code}")
            return False
    except Exception as e:
        log.error(f"Recap failed: {e}")
        return False

# ============================================================
# HEALTH ALERTS
# ============================================================

def send_health_alert(alert_type: str, message: str, severity: str = "warning"):
    """Send alert to #algo-health channel"""
    if not HEALTH_WEBHOOK:
        log.warning("No HEALTH_WEBHOOK configured")
        return False
    
    colors = {"info": 0x667eea, "warning": 0xFFA500, "error": 0xFF0000, "critical": 0xFF0000}
    emojis = {"info": "ℹ️", "warning": "⚠️", "error": "❌", "critical": "🚨"}
    
    embed = {
        "title": f"{emojis.get(severity, '⚠️')} {alert_type.upper()}",
        "description": message,
        "color": colors.get(severity, 0xFFA500),
        "footer": {"text": f"{get_eastern_now().strftime('%Y-%m-%d %I:%M %p ET')}"}
    }
    
    try:
        r = requests.post(HEALTH_WEBHOOK, json={"embeds": [embed]}, timeout=10)
        return r.status_code == 204
    except:
        return False

# ============================================================
# USER TODAY STATS
# ============================================================

def get_user_today_stats(discord_id: str):
    """Get user's stats for today"""
    engine = get_engine()
    today = get_eastern_date()
    
    with engine.connect() as conn:
        # Get user's bets today
        bets = conn.execute(text("""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN result = 'win' THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN result = 'loss' THEN 1 ELSE 0 END) as losses,
                SUM(CASE WHEN result = 'pending' THEN 1 ELSE 0 END) as pending,
                COALESCE(SUM(units), 0) as units_risked,
                COALESCE(SUM(pnl_usd), 0) as pnl
            FROM user_bets
            WHERE discord_id = :did AND DATE(placed_at) = :date
        """), {"did": discord_id, "date": today}).fetchone()
        
        # Get bankroll settings
        settings = conn.execute(text("""
            SELECT current_bankroll, daily_profit_goal, stop_loss_limit, 
                   daily_profit_today, daily_exposure_used
            FROM bankroll_settings
            WHERE discord_id = :did
        """), {"did": discord_id}).fetchone()
        
        if not settings:
            return None
        
        current = float(settings[0])
        profit_goal = float(settings[1])
        stop_loss = float(settings[2])
        daily_pnl = float(settings[3])
        daily_exposure = float(settings[4])
        
        return {
            "bets_today": bets[0] or 0,
            "wins": bets[1] or 0,
            "losses": bets[2] or 0,
            "pending": bets[3] or 0,
            "units_risked": float(bets[4] or 0),
            "session_pnl": daily_pnl,
            "profit_goal": profit_goal,
            "stop_loss": stop_loss,
            "distance_to_goal": profit_goal - daily_pnl if profit_goal > 0 else None,
            "distance_to_stop": stop_loss + daily_pnl if stop_loss > 0 else None,
            "exposure_used": daily_exposure,
            "current_bankroll": current
        }

def build_today_embed(discord_id: str):
    """Build embed for !today command"""
    stats = get_user_today_stats(discord_id)
    if not stats:
        return None
    
    # Color based on P/L
    pnl = stats['session_pnl']
    if pnl > 0:
        color = 0x00FF00
    elif pnl < 0:
        color = 0xFF0000
    else:
        color = 0x667eea
    
    embed = {
        "title": f"📅 Today's Session — {get_eastern_now().strftime('%B %d')}",
        "color": color,
        "fields": [
            {"name": "🎲 Bets Placed", "value": str(stats['bets_today']), "inline": True},
            {"name": "📊 Record", "value": f"{stats['wins']}W-{stats['losses']}L ({stats['pending']} pending)", "inline": True},
            {"name": "💰 Units Risked", "value": f"{stats['units_risked']:.1f}u", "inline": True},
            {"name": "📈 Session P/L", "value": f"**${pnl:+,.2f}**", "inline": False},
        ]
    }
    
    # Add distance to targets if set
    if stats['profit_goal'] and stats['profit_goal'] > 0:
        if stats['distance_to_goal'] > 0:
            embed['fields'].append({
                "name": "🎯 To Profit Goal",
                "value": f"${stats['distance_to_goal']:,.2f} away",
                "inline": True
            })
        else:
            embed['fields'].append({
                "name": "🎯 Profit Goal",
                "value": "✅ REACHED!",
                "inline": True
            })
    
    if stats['stop_loss'] and stats['stop_loss'] > 0:
        if stats['distance_to_stop'] > 0:
            pct = (1 - stats['distance_to_stop'] / stats['stop_loss']) * 100
            embed['fields'].append({
                "name": "🛑 To Stop Loss",
                "value": f"${stats['distance_to_stop']:,.2f} remaining ({pct:.0f}% used)",
                "inline": True
            })
        else:
            embed['fields'].append({
                "name": "🛑 Stop Loss",
                "value": "⚠️ HIT - Consider stopping",
                "inline": True
            })
    
    embed['footer'] = {"text": f"Exposure: ${stats['exposure_used']:,.2f} | Use !bankroll for full view"}
    
    return embed

# ============================================================
# PICK FOOTER FOR MAIN CHANNELS
# ============================================================

def get_pick_footer():
    """Standard footer to add to pick posts"""
    return "📊 Tracking live in #results | Personal stake: use `!preview`"

# ============================================================
# INITIALIZATION
# ============================================================

if __name__ == "__main__":
    init_picks_table()
    print("✅ discord_results.py ready")
