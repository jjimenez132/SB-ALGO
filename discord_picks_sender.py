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

# Import explanation engine
try:
    from explanation_engine import generate_game_explanation, generate_prop_explanation
    EXPLANATION_ENABLED = True
except ImportError:
    EXPLANATION_ENABLED = False
    print("⚠️ Explanation engine not available")
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


def get_recent_players(days=1):
    """Get players picked in the last N days to avoid repeats"""
    try:
        from sqlalchemy import create_engine, text
        engine = create_engine(DATABASE_URL)
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT DISTINCT 
                    SPLIT_PART(pick_name, ' ', 1) || ' ' || SPLIT_PART(pick_name, ' ', 2) as player_name
                FROM algo_picks_tracking 
                WHERE pick_type = 'prop' 
                AND pick_date >= CURRENT_DATE - :days
                AND pick_date < CURRENT_DATE
            """), {'days': days}).fetchall()
            return [r[0].lower() for r in result]
    except Exception as e:
        print(f"   ⚠️ Could not check recent players: {e}")
        return []


def filter_cooldown_picks(picks, cooldown_days=1):
    """Remove picks for players that were picked in the last N days"""
    recent_players = get_recent_players(cooldown_days)
    if not recent_players:
        return picks
    
    filtered = []
    for pick in picks:
        player = pick.get('player', '').lower()
        if player and not any(recent in player or player in recent for recent in recent_players):
            filtered.append(pick)
        else:
            print(f"   ⏸️ Cooldown: Skipping {pick.get('player')} (picked yesterday)")
    
    return filtered


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


def save_pick_for_grading(pick_id, pick_name, pick_type, units, odds=-110, line=None, details=None):
    """Save pick to algo_picks_tracking for later grading"""
    today = get_eastern_date()
    
    try:
        from sqlalchemy import create_engine, text
        import os
        db_url = os.environ.get('DATABASE_URL', DATABASE_URL)
        engine = create_engine(db_url)
        with engine.connect() as conn:
            # First try insert
            result = conn.execute(text("""
                INSERT INTO algo_picks_tracking (pick_date, pick_id, pick_name, pick_type, units, odds, line, status, pick_details, created_at)
                VALUES (:date, :pick_id, :name, :type, :units, :odds, :line, 'pending', :details, NOW())
                ON CONFLICT (pick_date, pick_type, pick_name) DO UPDATE SET
                    pick_id = EXCLUDED.pick_id,
                    units = EXCLUDED.units,
                    odds = EXCLUDED.odds,
                    line = EXCLUDED.line
                RETURNING id
            """), {
                'date': today,
                'pick_id': pick_id,
                'name': pick_name,
                'type': pick_type,
                'units': float(units),
                'odds': int(odds) if odds else -110,
                'line': float(line) if line else None,
                'details': details
            })
            row = result.fetchone()
            conn.commit()
            if row:
                print(f"   📝 Saved {pick_id} for grading (DB id: {row[0]})")
            else:
                print(f"   📝 Saved {pick_id} for grading")
    except Exception as e:
        import traceback
        print(f"   ⚠️ Could not save for grading: {e}")
        traceback.print_exc()

def create_pick_key(pick, pick_type):
    """Create unique key for a pick - ignores line numbers to avoid duplicates"""
    import re
    if pick_type == 'game':
        matchup = pick.get('matchup', '')
        pick_str = pick.get('pick', '')
        # Extract just OVER/UNDER direction, ignore the number
        direction = 'OVER' if 'OVER' in pick_str.upper() else 'UNDER' if 'UNDER' in pick_str.upper() else pick_str
        return f"GAME_{matchup}_{direction}"
    else:
        player = pick.get('player', '')
        prop = pick.get('prop', '')
        # Extract stat type and direction, ignore the number
        # e.g., "PTS OVER 25.5" -> "PTS_OVER"
        parts = prop.upper().split()
        if len(parts) >= 2:
            stat = parts[0]  # PTS, REB, AST, etc.
            direction = 'OVER' if 'OVER' in prop.upper() else 'UNDER' if 'UNDER' in prop.upper() else ''
            return f"PROP_{player}_{stat}_{direction}"
        return f"PROP_{player}_{prop}"

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
            time.sleep(1.5)  # Rate limit prevention
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
    
    # Determine units - CONSERVATIVE (start small, only go big on locks)
    # 2.0u = LOCK (edge 40%+, confidence 95%+)
    # 1.0u = Strong edge (edge 30%+, confidence 90%+)
    # 0.5u = Standard (everything else)
    confidence = float(str(pick.get('confidence', '80')).replace('%', ''))
    if edge_val >= 40 and confidence >= 95:
        units = "2.0u"
    elif edge_val >= 30 and confidence >= 90:
        units = "1.0u"
    else:
        units = "0.5u"
    
    # Generate explanation if available
    explanation = ""
    if EXPLANATION_ENABLED:
        try:
            # Build pick data for explanation engine - use numeric values
            pick_data = {
                'game_id': pick.get('game_id', matchup),
                'pick': pick_str,
                'type': pick.get('type', 'TOTAL'),
                'edge': pick.get('edge_numeric', edge_val),
                'ev_pct': pick.get('ev_pct', float(str(pick.get('ev', '0')).replace('%', ''))),
                'confidence': pick.get('confidence_numeric', confidence),
                'grade': pick.get('grade', 'A+'),
                # Model data for explanation engine
                'model_total': pick.get('model_total'),
                'model_home_pts': pick.get('model_home_pts'),
                'model_away_pts': pick.get('model_away_pts'),
                'model_pace': pick.get('model_pace'),
                'model_margin': pick.get('model_margin'),
                'regime_status': pick.get('regime_status', 'NORMAL'),
                'regime_confidence': pick.get('regime_confidence', 0),
                'injury_adjustment': pick.get('injury_adjustment', 0),
                'injury_edge': pick.get('injury_edge', 'NEUTRAL'),
            }
            explanation = generate_game_explanation(pick_data)
        except Exception as e:
            print(f"   ⚠️ Explanation failed: {e}")
            explanation = ""
    
    fields = [
        {"name": "Expected Value", "value": f"+{edge_val:.1f} pts", "inline": True},
        {"name": "EV %", "value": pick.get('ev', 'N/A'), "inline": True},
        {"name": "Grade", "value": pick.get('grade', 'A+'), "inline": True},
        {"name": "AI Stake", "value": units, "inline": True},
        {"name": "Risk Class", "value": "High" if edge_val >= 25 else "Medium", "inline": True},
        {"name": "Confidence", "value": f"{pick.get('confidence', '80')}%", "inline": True},
    ]
    
    # Add explanation as a field if available (truncate if needed)
    if explanation:
        # Discord field value limit is 1024 chars
        explanation_truncated = explanation[:1000] + "..." if len(explanation) > 1000 else explanation
        fields.append({"name": "🔒 Why This Bet Has Edge", "value": explanation_truncated, "inline": False})
    
    embed = {
        "title": title,
        "description": f"**{pick_str}** — {units} 🔥🔥",
        "color": color,
        "fields": fields,
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
    
    # Conservative prop sizing
    # 1.5u = LOCK (edge 50%+, hit rate 80%+)
    # 1.0u = Strong (edge 35%+, hit rate 70%+)
    # 0.5u = Standard (everything else)
    hit_rate_val = float(str(hit_rate).replace('%', '')) if hit_rate else 0
    if edge_val >= 50 and hit_rate_val >= 80:
        units = "1.5u"
    elif edge_val >= 35 and hit_rate_val >= 70:
        units = "1.0u"
    else:
        units = "0.5u"
    
    # Generate explanation if available
    explanation = ""
    if EXPLANATION_ENABLED:
        try:
            explanation = generate_prop_explanation(pick)
        except Exception as e:
            print(f"   ⚠️ Explanation failed: {e}")
            explanation = ""
    
    fields = [
        {"name": "Hit Rate", "value": hit_rate, "inline": True},
        {"name": "Edge", "value": f"+{edge_val:.1f}%", "inline": True},
        {"name": "EV", "value": pick.get('ev', 'N/A'), "inline": True},
        {"name": "Model Proj", "value": f"{pick.get('model', 'N/A')}", "inline": True},
        {"name": "Line", "value": f"{pick.get('line', 'N/A')}", "inline": True},
        {"name": "Grade", "value": pick.get('grade', 'A+'), "inline": True},
    ]
    
    # Add explanation as a field if available
    if explanation:
        explanation_truncated = explanation[:1000] + "..." if len(explanation) > 1000 else explanation
        fields.append({"name": "🔒 Why This Bet Has Edge", "value": explanation_truncated, "inline": False})
    
    embed = {
        "title": title,
        "description": f"**{prop}** — {units} 🔥",
        "color": color,
        "fields": fields,
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
    
    # CHECK: If morning picks already sent today, don't resend
    sent_today = get_sent_picks_today()
    if sent_today:
        print(f"   ⚠️ MORNING PICKS ALREADY SENT TODAY ({len(sent_today)} picks)")
        print(f"   ⚠️ Skipping to prevent duplicate/different picks")
        print(f"   ℹ️ To force resend, manually clear discord_sent_picks table")
        return False
    
    # Clear old sent picks (from previous days)
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
    for pick in game_picks[:2]:  # MAX 2 GAME PICKS PER DAY
        embed = create_game_pick_embed(pick)
        if send_discord_message(GAME_PICKS_CHANNEL, embed=embed):
            sent_games += 1
            pick_key = create_pick_key(pick, 'game')
            mark_pick_sent(pick_key, 'game')
            # Save for grading
            pick_id = pick.get('id', f'G{sent_games:02d}')
            pick_name = f"{pick.get('matchup', 'Unknown')} {pick.get('pick', '')}"
            real_odds = pick.get('odds', -110)
            # Extract line from pick string (e.g., "UNDER 230.5" -> 230.5)
            import re
            line_match = re.search(r'[\d.]+', str(pick.get('pick', '')))
            line_val = float(line_match.group()) if line_match else None
            save_pick_for_grading(pick_id, pick_name, 'game', 2.0, odds=real_odds, line=line_val)
    
    print(f"   ✅ Sent {sent_games} game picks")
    
    # Summary
    send_discord_message(GAME_PICKS_CHANNEL, embed=create_summary_embed(picks_data))
    
    # === SEND PROP PICKS ===
    print(f"\n   📤 Sending to #top-props...")
    
    # Header
    send_discord_message(PROP_PICKS_CHANNEL, embed=create_header_embed())
    
    # Each prop pick
    sent_props = 0
    for pick in prop_picks[:3]:  # MAX 3 PROP PICKS PER DAY
        embed = create_prop_pick_embed(pick)
        if send_discord_message(PROP_PICKS_CHANNEL, embed=embed):
            sent_props += 1
            pick_key = create_pick_key(pick, 'prop')
            mark_pick_sent(pick_key, 'prop')
            # Save for grading
            pick_id = pick.get('id', f'P{sent_props:02d}')
            pick_name = f"{pick.get('player', 'Unknown')} {pick.get('prop', '')}"
            real_odds = pick.get('odds', -110)
            line_val = pick.get('book_line', pick.get('line'))
            save_pick_for_grading(pick_id, pick_name, 'prop', 1.5, odds=real_odds, line=line_val)
    
    print(f"   ✅ Sent {sent_props} prop picks")
    
    print(f"\n{'='*60}")
    print(f"✅ MORNING REPORT COMPLETE")
    print(f"{'='*60}")
    
    return True



def check_line_movement():
    """Check if morning picks have significant line movement - compare morning odds vs current odds"""
    
    print(f"\n{'='*60}")
    print(f"📉 CHECKING LINE MOVEMENT - {get_eastern_time().strftime('%I:%M %p ET')}")
    print(f"{'='*60}")
    
    from sqlalchemy import create_engine, text
    engine = create_engine(DATABASE_URL)
    
    # Get today's picks with their morning odds
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT pick_id, pick_name, pick_type, odds, units, line
                FROM algo_picks_tracking 
                WHERE pick_date = CURRENT_DATE AND status = 'pending'
            """)).fetchall()
            
            morning_picks = []
            for r in result:
                morning_picks.append({
                    'pick_id': r[0],
                    'pick_name': r[1],
                    'pick_type': r[2],
                    'morning_odds': r[3] or -110,
                    'units': r[4],
                    'line': r[5]
                })
    except Exception as e:
        print(f"   ⚠️ Could not load morning picks: {e}")
        return []
    
    if not morning_picks:
        print("   ℹ️ No pending picks to check for today")
        return []
    
    print(f"   📋 Checking {len(morning_picks)} picks for line movement...")
    
    alerts_to_send = []
    
    for mp in morning_picks:
        pick_name = mp['pick_name']
        pick_type = mp['pick_type']
        morning_odds = mp['morning_odds']
        
        # Parse pick details
        # Format: "Player Name STAT SIDE LINE" e.g., "Marcus Smart PTS UNDER 12.5"
        parts = pick_name.split()
        
        current_odds = None
        current_line = None
        
        if pick_type == 'prop' and len(parts) >= 4:
            # Extract player name (first two words), stat, side, line
            player_name = ' '.join(parts[:-3])  # Everything except last 3
            stat = parts[-3].lower()  # PTS, REB, AST
            side = parts[-2].upper()  # OVER, UNDER
            line = float(parts[-1])  # 12.5
            
            # Map stat to market name
            stat_map = {'pts': 'player_points', 'reb': 'player_rebounds', 'ast': 'player_assists'}
            market = stat_map.get(stat, f'player_{stat}')
            
            # Get current odds from player_props table
            try:
                with engine.connect() as conn:
                    result = conn.execute(text("""
                        SELECT line, over_odds, under_odds 
                        FROM player_props 
                        WHERE game_date = CURRENT_DATE 
                          AND LOWER(player_name) LIKE :player
                          AND market = :market
                        ORDER BY updated_at DESC 
                        LIMIT 1
                    """), {
                        'player': f'%{player_name.lower()}%',
                        'market': market
                    }).fetchone()
                    
                    if result:
                        current_line = float(result[0])
                        current_odds = result[1] if side == 'OVER' else result[2]
            except Exception as e:
                print(f"   ⚠️ Error checking {player_name}: {e}")
                continue
        
        elif pick_type == 'game':
            # Game pick - check betting_odds table
            # Format: "TEAM @ TEAM OVER/UNDER LINE"
            try:
                with engine.connect() as conn:
                    # Extract teams and direction from pick name
                    if 'UNDER' in pick_name.upper():
                        side = 'UNDER'
                    elif 'OVER' in pick_name.upper():
                        side = 'OVER'
                    else:
                        continue
                    
                    result = conn.execute(text("""
                        SELECT total, over_odds, under_odds
                        FROM betting_odds 
                        WHERE game_date = CURRENT_DATE
                        ORDER BY updated_at DESC 
                        LIMIT 1
                    """)).fetchone()
                    
                    if result:
                        current_line = float(result[0]) if result[0] else None
                        current_odds = result[1] if side == 'OVER' else result[2]
            except Exception as e:
                print(f"   ⚠️ Error checking game: {e}")
                continue
        
        # Calculate line movement
        if current_odds is not None and morning_odds:
            odds_change = current_odds - morning_odds
            
            # Significant movement thresholds
            # If odds moved against us by 15+ cents, alert
            if odds_change <= -15:  # Line moved against us (worse odds)
                movement_desc = f"Odds moved from {morning_odds} to {current_odds} ({odds_change:+d})"
                alerts_to_send.append({
                    'pick_id': mp['pick_id'],
                    'pick_name': pick_name,
                    'reason': 'ODDS_MOVED_AGAINST',
                    'morning_odds': morning_odds,
                    'current_odds': current_odds,
                    'change': odds_change,
                    'message': f"⚠️ **LINE MOVED** - {pick_name}\n\n{movement_desc}\n\n💡 **Consider:** Cash out early if available, or hold with reduced confidence."
                })
                print(f"   ⚠️ {pick_name} - ODDS MOVED AGAINST ({morning_odds} → {current_odds})")
            
            elif odds_change >= 15:  # Line moved in our favor (better value now)
                print(f"   🟢 {pick_name} - Line moved IN OUR FAVOR ({morning_odds} → {current_odds})")
            
            else:
                print(f"   ✅ {pick_name} - Minimal movement ({morning_odds} → {current_odds})")
        
        elif current_line is not None and mp.get('line'):
            # Check line movement (not just odds)
            line_change = current_line - float(mp['line'])
            if abs(line_change) >= 1.5:
                print(f"   ⚠️ {pick_name} - LINE CHANGED by {line_change:+.1f} points")
        
        else:
            print(f"   ❓ {pick_name} - Could not find current odds (may need odds refresh)")
    
    # Send alerts
    if alerts_to_send:
        print(f"\n   📤 Sending {len(alerts_to_send)} line movement alerts...")
        
        for alert in alerts_to_send:
            embed = {
                'title': "📉 LINE MOVEMENT ALERT",
                'description': alert['message'],
                'color': 0xFFA500,  # Orange
                'footer': {'text': f"SB-ALGO Risk Management • {get_eastern_time().strftime('%I:%M %p ET')}"}
            }
            
            # Send to appropriate channel
            if 'PTS' in alert['pick_name'] or 'REB' in alert['pick_name'] or 'AST' in alert['pick_name']:
                send_discord_message(PROP_PICKS_CHANNEL, embed=embed)
            else:
                send_discord_message(GAME_PICKS_CHANNEL, embed=embed)
            
            print(f"   📤 Sent alert for {alert['pick_name']}")
    else:
        print("\n   ✅ No significant line movement detected")
    
    return alerts_to_send


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
    
    # DAILY LIMITS: MAX 2 GAMES, MAX 3 PROPS
    MAX_DAILY_GAMES = 2
    MAX_DAILY_PROPS = 3
    
    # ABSOLUTE LOCK thresholds (only exception to exceed limits)
    LOCK_EDGE_THRESHOLD = 50  # 50%+ edge
    LOCK_CONFIDENCE_THRESHOLD = 95  # 95%+ confidence
    LOCK_HIT_RATE_THRESHOLD = 80  # 80%+ hit rate for props
    
    def is_absolute_lock(pick, pick_type):
        """Check if pick is an ABSOLUTE LOCK worth exceeding daily limit"""
        edge = float(str(pick.get('edge', '0')).replace('+', '').replace('%', ''))
        conf = float(str(pick.get('confidence', '0')).replace('%', ''))
        if pick_type == 'prop':
            hit_rate = float(str(pick.get('hit_rate', '0')).replace('%', ''))
            return edge >= LOCK_EDGE_THRESHOLD and hit_rate >= LOCK_HIT_RATE_THRESHOLD
        return edge >= LOCK_EDGE_THRESHOLD and conf >= LOCK_CONFIDENCE_THRESHOLD
    
    games_sent_today = len([k for k in sent_picks if k.startswith('GAME_')])
    props_sent_today = len([k for k in sent_picks if k.startswith('PROP_')])
    
    games_remaining = MAX_DAILY_GAMES - games_sent_today
    props_remaining = MAX_DAILY_PROPS - props_sent_today
    
    print(f"   📊 Daily limits: {games_sent_today}/{MAX_DAILY_GAMES} games, {props_sent_today}/{MAX_DAILY_PROPS} props")
    
    new_game_picks = []
    new_prop_picks = []
    
    # Check game picks
    for pick in picks_data.get('game_picks', []):
        pick_key = create_pick_key(pick, 'game')
        if pick_key not in sent_picks:
            # Under limit OR absolute lock
            if games_remaining > len(new_game_picks) or is_absolute_lock(pick, 'game'):
                new_game_picks.append(pick)
                if is_absolute_lock(pick, 'game') and games_remaining <= 0:
                    print(f"   🔒 ABSOLUTE LOCK detected: {pick.get('matchup')} (exceeds daily limit)")
    
    # Check prop picks
    for pick in picks_data.get('prop_picks', []):
        pick_key = create_pick_key(pick, 'prop')
        if pick_key not in sent_picks:
            # Under limit OR absolute lock
            if props_remaining > len(new_prop_picks) or is_absolute_lock(pick, 'prop'):
                new_prop_picks.append(pick)
                if is_absolute_lock(pick, 'prop') and props_remaining <= 0:
                    print(f"   🔒 ABSOLUTE LOCK detected: {pick.get('player')} (exceeds daily limit)")
    
    # Limit non-locks to remaining quota
    regular_games = [p for p in new_game_picks if not is_absolute_lock(p, 'game')][:max(0, games_remaining)]
    lock_games = [p for p in new_game_picks if is_absolute_lock(p, 'game')]
    new_game_picks = regular_games + lock_games
    
    regular_props = [p for p in new_prop_picks if not is_absolute_lock(p, 'prop')][:max(0, props_remaining)]
    lock_props = [p for p in new_prop_picks if is_absolute_lock(p, 'prop')]
    new_prop_picks = regular_props + lock_props
    
    print(f"   🆕 {len(new_game_picks)} new game picks, {len(new_prop_picks)} new prop picks")
    
    alerts_sent = 0
    
    # Send new game picks
    for pick in new_game_picks:
        is_lock = is_absolute_lock(pick, 'game')
        lock_tag = " 🔒 LOCK" if is_lock else ""
        print(f"   🚨 NEW GAME{lock_tag}: {pick.get('matchup')} - {pick.get('pick')}")
        embed = create_game_pick_embed(pick, is_alert=True)
        if send_discord_message(GAME_PICKS_CHANNEL, embed=embed):
            pick_key = create_pick_key(pick, 'game')
            mark_pick_sent(pick_key, 'game')
            # Save for grading
            pick_id = pick.get('id', f'G{games_sent_today + alerts_sent + 1:02d}')
            pick_name = f"{pick.get('matchup', 'Unknown')} {pick.get('pick', '')}"
            units = 2.0 if is_lock else 0.5
            save_pick_for_grading(pick_id, pick_name, 'game', units)
            alerts_sent += 1
    
    # Send new prop picks
    props_sent_this_run = 0
    for pick in new_prop_picks:
        is_lock = is_absolute_lock(pick, 'prop')
        lock_tag = " 🔒 LOCK" if is_lock else ""
        print(f"   🚨 NEW PROP{lock_tag}: {pick.get('player')} - {pick.get('prop')}")
        embed = create_prop_pick_embed(pick, is_alert=True)
        if send_discord_message(PROP_PICKS_CHANNEL, embed=embed):
            pick_key = create_pick_key(pick, 'prop')
            mark_pick_sent(pick_key, 'prop')
            # Save for grading
            pick_id = pick.get('id', f'P{props_sent_today + props_sent_this_run + 1:02d}')
            pick_name = f"{pick.get('player', 'Unknown')} {pick.get('prop', '')}"
            units = 1.5 if is_lock else 0.5
            save_pick_for_grading(pick_id, pick_name, 'prop', units)
            alerts_sent += 1
            props_sent_this_run += 1
    
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
    elif mode == 'linecheck':
        check_line_movement()
    elif mode == 'test':
        test_picks()
    else:
        print(f"Unknown mode: {mode}")
        print("Usage: python3 discord_picks_sender.py [morning|alert|linecheck|test]")
