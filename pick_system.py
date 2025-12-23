#!/usr/bin/env python3
"""
pick_system.py - Unified Pick ID System
========================================
Generates pick IDs, tracks followers, auto-grades.
"""

import os
import logging
from datetime import datetime, date
from sqlalchemy import create_engine, text
import pytz
import requests

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(message)s')
log = logging.getLogger(__name__)

DATABASE_URL = os.environ.get('DATABASE_URL',
    "postgresql://sb_algo_db_user:0HDtYp4EY2Lo5At8iyf44PD1zDioSPK7@dpg-d495uhchg0os738l1a50-a.virginia-postgres.render.com/sb_algo_db")

def get_engine():
    return create_engine(DATABASE_URL)

def get_eastern_date():
    return datetime.now(pytz.timezone('US/Eastern')).strftime('%Y-%m-%d')

# ============================================================
# PICK ID GENERATION
# ============================================================

def generate_pick_id(pick_type: str = 'prop'):
    """Generate unique pick ID like P47 or G12"""
    engine = get_engine()
    prefix = 'P' if pick_type == 'prop' else 'G'
    today = get_eastern_date()
    
    with engine.connect() as conn:
        # Count today's picks of this type
        result = conn.execute(text("""
            SELECT COUNT(*) FROM algo_picks_tracking 
            WHERE pick_date = :date AND pick_type = :type
        """), {"date": today, "type": pick_type}).fetchone()
        
        count = (result[0] or 0) + 1
        pick_id = f"{prefix}{count:02d}"
        
        return pick_id

def create_pick(pick_type: str, pick_name: str, units: float, odds: int = None, 
                details: str = None, line: float = None):
    """Create a new pick with generated ID"""
    engine = get_engine()
    today = get_eastern_date()
    pick_id = generate_pick_id(pick_type)
    
    with engine.connect() as conn:
        result = conn.execute(text("""
            INSERT INTO algo_picks_tracking 
            (pick_id, pick_date, pick_type, pick_name, pick_details, units, odds, line, status)
            VALUES (:pid, :date, :type, :name, :details, :units, :odds, :line, 'pending')
            RETURNING id, pick_id
        """), {
            "pid": pick_id, "date": today, "type": pick_type, "name": pick_name,
            "details": details, "units": units, "odds": odds, "line": line
        })
        row = result.fetchone()
        conn.commit()
        
        log.info(f"✅ Created pick {pick_id}: {pick_name} ({units}u)")
        return {"db_id": row[0], "pick_id": row[1]}

def get_pick_by_id(pick_id: str):
    """Get pick details by ID (e.g., P47)"""
    engine = get_engine()
    
    # Handle both formats: P47 or just 47
    if pick_id[0].isalpha():
        search_id = pick_id.upper()
    else:
        search_id = pick_id
    
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT id, pick_id, pick_date, pick_type, pick_name, pick_details, 
                   units, odds, line, status, result_units
            FROM algo_picks_tracking 
            WHERE pick_id = :pid OR pick_id LIKE :pid_pattern
            ORDER BY pick_date DESC
            LIMIT 1
        """), {"pid": search_id, "pid_pattern": f"%{search_id}"}).fetchone()
        
        if result:
            return {
                "db_id": result[0],
                "pick_id": result[1],
                "date": result[2],
                "type": result[3],
                "name": result[4],
                "details": result[5],
                "units": float(result[6]),
                "odds": result[7],
                "line": float(result[8]) if result[8] else None,
                "status": result[9],
                "result_units": float(result[10]) if result[10] else 0
            }
        return None

# ============================================================
# USER FOLLOW SYSTEM
# ============================================================

def init_followers_table():
    """Create followers table"""
    engine = get_engine()
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS pick_followers (
                id SERIAL PRIMARY KEY,
                pick_id VARCHAR(10) NOT NULL,
                discord_id VARCHAR(50) NOT NULL,
                units_multiplier DECIMAL(4,2) DEFAULT 1.0,
                stake_usd DECIMAL(12,2),
                followed_at TIMESTAMP DEFAULT NOW(),
                graded BOOLEAN DEFAULT FALSE,
                pnl_usd DECIMAL(12,2),
                UNIQUE(pick_id, discord_id)
            )
        """))
        conn.commit()
    log.info("✅ Followers table ready")

def follow_pick(discord_id: str, pick_id: str, units_multiplier: float = 1.0):
    """User follows a pick"""
    from bankroll_manager import get_bankroll_settings, calculate_stake, check_exposure
    
    # Get pick details
    pick = get_pick_by_id(pick_id)
    if not pick:
        return {"success": False, "error": "Pick not found"}
    
    if pick['status'] != 'pending':
        return {"success": False, "error": f"Pick already {pick['status']}"}
    
    # Get user's stake
    settings = get_bankroll_settings(discord_id)
    if not settings:
        return {"success": False, "error": "No bankroll setup. Use !setup first"}
    
    units = pick['units'] * units_multiplier
    stake = calculate_stake(discord_id, units)
    
    # Note: We skip strict exposure checks here because unit size is already personalized
    # The user's unit size is calculated from their bankroll and risk tolerance
    # If they want to follow a 2u pick, that's 2x their personal unit size
    
    # Save follow
    engine = get_engine()
    with engine.connect() as conn:
        conn.execute(text("""
            INSERT INTO pick_followers (pick_id, discord_id, units_multiplier, stake_usd)
            VALUES (:pid, :did, :mult, :stake)
            ON CONFLICT (pick_id, discord_id) DO UPDATE SET
                units_multiplier = :mult, stake_usd = :stake, followed_at = NOW()
        """), {"pid": pick['pick_id'], "did": discord_id, "mult": units_multiplier, "stake": stake})
        
        # Update daily exposure
        conn.execute(text("""
            UPDATE bankroll_settings SET
                daily_exposure_used = daily_exposure_used + :stake
            WHERE discord_id = :did
        """), {"did": discord_id, "stake": stake})
        
        conn.commit()
    
    return {
        "success": True,
        "pick": pick,
        "units": units,
        "stake": stake,
        "message": f"Following {pick['pick_id']}: {pick['name']}"
    }

def get_pick_followers(pick_id: str):
    """Get all followers of a pick"""
    engine = get_engine()
    with engine.connect() as conn:
        results = conn.execute(text("""
            SELECT discord_id, units_multiplier, stake_usd, graded
            FROM pick_followers
            WHERE pick_id = :pid
        """), {"pid": pick_id}).fetchall()
        
        return [{"discord_id": r[0], "multiplier": float(r[1]), 
                 "stake": float(r[2]), "graded": r[3]} for r in results]

# ============================================================
# AUTO-GRADING
# ============================================================

def grade_pick(pick_id: str, result: str):
    """Grade a pick and auto-grade all followers"""
    from bankroll_manager import update_bankroll, get_bankroll_settings
    
    pick = get_pick_by_id(pick_id)
    if not pick:
        return {"success": False, "error": "Pick not found"}
    
    # Calculate result units for the pick
    units = pick['units']
    odds = pick['odds']
    
    if result == 'win':
        if odds and odds > 0:
            result_units = units * (odds / 100)
        elif odds and odds < 0:
            result_units = units * (100 / abs(odds))
        else:
            result_units = units
    elif result == 'loss':
        result_units = -units
    else:  # void/push
        result_units = 0
    
    # Update pick status
    engine = get_engine()
    with engine.connect() as conn:
        conn.execute(text("""
            UPDATE algo_picks_tracking SET
                status = :status,
                result_units = :ru,
                graded_at = NOW()
            WHERE pick_id = :pid
        """), {"status": result, "ru": result_units, "pid": pick_id})
        conn.commit()
    
    # Grade all followers
    followers = get_pick_followers(pick_id)
    graded_users = []
    
    for follower in followers:
        if follower['graded']:
            continue
        
        discord_id = follower['discord_id']
        stake = follower['stake']
        multiplier = follower['multiplier']
        
        # Calculate user's P/L
        if result == 'win':
            if odds and odds > 0:
                user_pnl = stake * (odds / 100)
            elif odds and odds < 0:
                user_pnl = stake * (100 / abs(odds))
            else:
                user_pnl = stake
        elif result == 'loss':
            user_pnl = -stake
        else:
            user_pnl = 0
        
        # Update user's bankroll
        settings = get_bankroll_settings(discord_id)
        if settings:
            new_bankroll = float(settings['current_bankroll']) + user_pnl
            update_bankroll(discord_id, new_bankroll)
        
        # Mark as graded
        with engine.connect() as conn:
            conn.execute(text("""
                UPDATE pick_followers SET graded = TRUE, pnl_usd = :pnl
                WHERE pick_id = :pid AND discord_id = :did
            """), {"pnl": user_pnl, "pid": pick_id, "did": discord_id})
            
            # Update user stats
            win_add = 1 if result == 'win' else 0
            loss_add = 1 if result == 'loss' else 0
            conn.execute(text("""
                UPDATE bankroll_settings SET
                    wins = wins + :w,
                    losses = losses + :l,
                    daily_profit_today = daily_profit_today + :pnl
                WHERE discord_id = :did
            """), {"w": win_add, "l": loss_add, "pnl": user_pnl, "did": discord_id})
            
            conn.commit()
        
        graded_users.append({
            "discord_id": discord_id,
            "pnl": user_pnl,
            "new_bankroll": new_bankroll if settings else None
        })
    
    log.info(f"✅ Graded {pick_id} as {result}: {len(graded_users)} followers updated")
    
    return {
        "success": True,
        "pick_id": pick_id,
        "result": result,
        "result_units": result_units,
        "followers_graded": graded_users
    }

def get_user_active_picks(discord_id: str):
    """Get user's pending followed picks"""
    engine = get_engine()
    with engine.connect() as conn:
        results = conn.execute(text("""
            SELECT pf.pick_id, apt.pick_name, pf.stake_usd, apt.units, apt.status
            FROM pick_followers pf
            JOIN algo_picks_tracking apt ON pf.pick_id = apt.pick_id
            WHERE pf.discord_id = :did AND apt.status = 'pending'
            ORDER BY pf.followed_at DESC
        """), {"did": discord_id}).fetchall()
        
        return [{"pick_id": r[0], "name": r[1], "stake": float(r[2]), 
                 "units": float(r[3]), "status": r[4]} for r in results]

# ============================================================
# INITIALIZATION
# ============================================================

def init_tables():
    """Initialize all required tables"""
    engine = get_engine()
    
    # Add pick_id column to algo_picks_tracking if not exists
    with engine.connect() as conn:
        # Check if pick_id column exists
        result = conn.execute(text("""
            SELECT column_name FROM information_schema.columns 
            WHERE table_name = 'algo_picks_tracking' AND column_name = 'pick_id'
        """)).fetchone()
        
        if not result:
            conn.execute(text("""
                ALTER TABLE algo_picks_tracking 
                ADD COLUMN pick_id VARCHAR(10),
                ADD COLUMN line DECIMAL(6,2)
            """))
            conn.commit()
            log.info("✅ Added pick_id column")
    
    init_followers_table()
    log.info("✅ Pick system tables ready")

if __name__ == "__main__":
    init_tables()
    print("✅ pick_system.py initialized")

# ============================================================
# RESULTS CHANNEL INTEGRATION
# ============================================================

def grade_pick_full(pick_id: str, result: str):
    """Grade pick, update followers, update #results channel, send DMs"""
    import requests
    
    RESULTS_WEBHOOK = os.environ.get('DISCORD_WEBHOOK_RESULTS')
    
    # First grade the pick and followers
    grade_result = grade_pick(pick_id, result)
    
    if not grade_result['success']:
        return grade_result
    
    # Update #results channel
    if RESULTS_WEBHOOK:
        pick = get_pick_by_id(pick_id)
        if pick:
            # Build updated embed
            if result == 'win':
                emoji = "✅"
                color = 0x00FF00
            elif result == 'loss':
                emoji = "❌"
                color = 0xFF0000
            else:
                emoji = "🟨"
                color = 0xFFFF00
            
            embed = {
                "title": f"{emoji} [{pick_id}] {pick['name']}",
                "description": f"**Result: {result.upper()}**\n{grade_result['result_units']:+.1f}u",
                "color": color,
                "fields": [
                    {"name": "Followers", "value": str(len(grade_result['followers_graded'])), "inline": True},
                ],
                "footer": {"text": f"Graded {datetime.now(pytz.timezone('US/Eastern')).strftime('%I:%M %p ET')}"}
            }
            
            try:
                requests.post(RESULTS_WEBHOOK, json={"embeds": [embed]}, timeout=10)
                log.info(f"✅ Posted result to #results: {pick_id} {result}")
            except Exception as e:
                log.error(f"Failed to post to results: {e}")
    
    return grade_result

def get_daily_summary():
    """Get summary for daily recap"""
    engine = get_engine()
    today = get_eastern_date()
    
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN status = 'win' THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN status = 'loss' THEN 1 ELSE 0 END) as losses,
                SUM(CASE WHEN status = 'void' THEN 1 ELSE 0 END) as voids,
                SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending,
                COALESCE(SUM(result_units), 0) as net_units,
                COALESCE(SUM(CASE WHEN status = 'win' THEN result_units ELSE 0 END), 0) as units_won,
                COALESCE(SUM(CASE WHEN status = 'loss' THEN ABS(result_units) ELSE 0 END), 0) as units_lost
            FROM algo_picks_tracking
            WHERE pick_date = :today
        """), {"today": today}).fetchone()
        
        return {
            "date": today,
            "total": result[0] or 0,
            "wins": result[1] or 0,
            "losses": result[2] or 0,
            "voids": result[3] or 0,
            "pending": result[4] or 0,
            "net_units": float(result[5] or 0),
            "units_won": float(result[6] or 0),
            "units_lost": float(result[7] or 0)
        }

def post_daily_recap():
    """Post daily recap to #daily-recap"""
    import requests
    
    RECAP_WEBHOOK = os.environ.get('DISCORD_WEBHOOK_RECAP')
    if not RECAP_WEBHOOK:
        log.warning("No DISCORD_WEBHOOK_RECAP configured")
        return False
    
    stats = get_daily_summary()
    
    if stats['total'] == 0:
        log.info("No picks today, skipping recap")
        return False
    
    if stats['pending'] > 0:
        log.info(f"{stats['pending']} picks still pending")
        return False
    
    # Build embed
    net = stats['net_units']
    if net > 0:
        emoji = "✅"
        color = 0x00FF00
        note = "Solid day. The edge delivered. 📈"
    elif net < 0:
        emoji = "❌"
        color = 0xFF0000
        note = "Variance happens. Trust the process. 📊"
    else:
        emoji = "➡️"
        color = 0xFFFF00
        note = "Break even. Live to fight another day."
    
    # Format date
    date_obj = datetime.strptime(stats['date'], '%Y-%m-%d')
    date_formatted = date_obj.strftime('%B %d, %Y').upper()
    
    embed = {
        "title": f"📊 DAILY RECAP — {date_formatted}",
        "color": color,
        "fields": [
            {"name": "✅ Wins", "value": str(stats['wins']), "inline": True},
            {"name": "❌ Losses", "value": str(stats['losses']), "inline": True},
            {"name": "🟨 Voids", "value": str(stats['voids']), "inline": True},
            {"name": "📈 Units Won", "value": f"+{stats['units_won']:.1f}u", "inline": True},
            {"name": "📉 Units Lost", "value": f"-{stats['units_lost']:.1f}u", "inline": True},
            {"name": f"{emoji} NET RESULT", "value": f"**{net:+.1f} units**", "inline": True},
        ],
        "footer": {"text": note}
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
