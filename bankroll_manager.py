"""
bankroll_manager.py - Hedge Fund Style Bankroll Management for Discord
========================================================================
Handles user onboarding, bankroll tracking, bet sizing, and analytics.
"""

import os
from datetime import datetime, date
from decimal import Decimal
from sqlalchemy import create_engine, text
import pytz

DATABASE_URL = os.environ.get('DATABASE_URL', 
    "postgresql://sb_algo_db_user:0HDtYp4EY2Lo5At8iyf44PD1zDioSPK7@dpg-d495uhchg0os738l1a50-a.virginia-postgres.render.com/sb_algo_db")

def get_engine():
    return create_engine(DATABASE_URL)

# ============================================================
# USER MANAGEMENT
# ============================================================

def get_user(discord_id: str):
    """Get user by Discord ID"""
    engine = get_engine()
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT discord_id, username, onboarding_complete 
            FROM discord_users WHERE discord_id = :did
        """), {"did": discord_id}).fetchone()
        return result

def create_user(discord_id: str, username: str):
    """Create new user"""
    engine = get_engine()
    with engine.connect() as conn:
        conn.execute(text("""
            INSERT INTO discord_users (discord_id, username, onboarding_complete)
            VALUES (:did, :uname, FALSE)
            ON CONFLICT (discord_id) DO UPDATE SET username = :uname, last_active = NOW()
        """), {"did": discord_id, "uname": username})
        conn.commit()

def complete_onboarding(discord_id: str):
    """Mark onboarding as complete"""
    engine = get_engine()
    with engine.connect() as conn:
        conn.execute(text("""
            UPDATE discord_users SET onboarding_complete = TRUE WHERE discord_id = :did
        """), {"did": discord_id})
        conn.commit()

def is_onboarded(discord_id: str) -> bool:
    """Check if user completed onboarding"""
    user = get_user(discord_id)
    return user and user[2] == True

# ============================================================
# BANKROLL SETTINGS
# ============================================================

def get_bankroll_settings(discord_id: str):
    """Get user's bankroll settings"""
    engine = get_engine()
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT * FROM bankroll_settings WHERE discord_id = :did
        """), {"did": discord_id}).fetchone()
        if result:
            return dict(result._mapping)
        return None

def create_bankroll_settings(discord_id: str, starting_bankroll: float, 
                            risk_method: str = 'percentage', max_risk_pct: float = 2.0,
                            strategy_profile: str = 'balanced'):
    """Create or update bankroll settings"""
    engine = get_engine()
    
    # Calculate unit size
    unit_size = starting_bankroll * (max_risk_pct / 100)
    
    with engine.connect() as conn:
        conn.execute(text("""
            INSERT INTO bankroll_settings 
            (discord_id, starting_bankroll, current_bankroll, risk_method, 
             max_risk_pct, strategy_profile, unit_size, peak_bankroll)
            VALUES (:did, :sb, :sb, :rm, :mrp, :sp, :us, :sb)
            ON CONFLICT (discord_id) DO UPDATE SET
                starting_bankroll = :sb,
                current_bankroll = :sb,
                risk_method = :rm,
                max_risk_pct = :mrp,
                strategy_profile = :sp,
                unit_size = :us,
                peak_bankroll = :sb,
                updated_at = NOW()
        """), {
            "did": discord_id, "sb": starting_bankroll, "rm": risk_method,
            "mrp": max_risk_pct, "sp": strategy_profile, "us": unit_size
        })
        conn.commit()

def update_bankroll(discord_id: str, new_bankroll: float):
    """Update current bankroll"""
    engine = get_engine()
    settings = get_bankroll_settings(discord_id)
    if not settings:
        return False
    
    # Recalculate unit size
    unit_size = new_bankroll * (float(settings['max_risk_pct']) / 100)
    
    # Calculate ROI
    starting = float(settings['starting_bankroll'])
    profit = new_bankroll - starting
    roi = (profit / starting * 100) if starting > 0 else 0
    
    # Update peak if new high
    peak = max(new_bankroll, float(settings['peak_bankroll']))
    
    # Calculate drawdown
    drawdown = peak - new_bankroll
    max_drawdown = max(drawdown, float(settings['max_drawdown']))
    
    # Determine risk rating
    if roi < -10:
        risk_rating = 'critical'
    elif roi < 0:
        risk_rating = 'high'
    elif roi < 10:
        risk_rating = 'medium'
    else:
        risk_rating = 'low'
    
    with engine.connect() as conn:
        conn.execute(text("""
            UPDATE bankroll_settings SET
                current_bankroll = :cb,
                unit_size = :us,
                total_profit = :tp,
                roi_pct = :roi,
                peak_bankroll = :peak,
                max_drawdown = :md,
                risk_rating = :rr,
                updated_at = NOW()
            WHERE discord_id = :did
        """), {
            "did": discord_id, "cb": new_bankroll, "us": unit_size,
            "tp": profit, "roi": roi, "peak": peak, "md": max_drawdown, "rr": risk_rating
        })
        conn.commit()
    return True

def set_exposure_limits(discord_id: str, max_daily_pct: float, max_single_pct: float):
    """Set exposure limits"""
    engine = get_engine()
    with engine.connect() as conn:
        conn.execute(text("""
            UPDATE bankroll_settings SET
                max_daily_exposure_pct = :mdp,
                max_single_game_pct = :msp,
                updated_at = NOW()
            WHERE discord_id = :did
        """), {"did": discord_id, "mdp": max_daily_pct, "msp": max_single_pct})
        conn.commit()

def set_session_targets(discord_id: str, profit_goal: float, stop_loss: float):
    """Set daily profit goal and stop loss"""
    engine = get_engine()
    with engine.connect() as conn:
        conn.execute(text("""
            UPDATE bankroll_settings SET
                daily_profit_goal = :pg,
                stop_loss_limit = :sl,
                updated_at = NOW()
            WHERE discord_id = :did
        """), {"did": discord_id, "pg": profit_goal, "sl": stop_loss})
        conn.commit()

# ============================================================
# BET SIZE CALCULATOR
# ============================================================

def calculate_stake(discord_id: str, units: float = 1.0):
    """Calculate stake in dollars for given units"""
    settings = get_bankroll_settings(discord_id)
    if not settings:
        return None
    
    unit_size = float(settings['unit_size'])
    return round(unit_size * units, 2)

def get_bet_sizes(discord_id: str):
    """Get all bet size tiers"""
    settings = get_bankroll_settings(discord_id)
    if not settings:
        return None
    
    unit_size = float(settings['unit_size'])
    current = float(settings['current_bankroll'])
    
    return {
        'unit_size': round(unit_size, 2),
        'low_confidence': {'units': 0.5, 'stake': round(unit_size * 0.5, 2), 'label': '60-70% confidence'},
        'standard': {'units': 1.0, 'stake': round(unit_size * 1.0, 2), 'label': '70-80% confidence'},
        'high_confidence': {'units': 2.0, 'stake': round(unit_size * 2.0, 2), 'label': '80%+ confidence'},
        'max_bet': round(current * float(settings['max_single_game_pct']) / 100, 2),
        'max_daily': round(current * float(settings['max_daily_exposure_pct']) / 100, 2)
    }

def check_exposure(discord_id: str, stake: float):
    """Check if bet is within exposure limits"""
    settings = get_bankroll_settings(discord_id)
    if not settings:
        return {'allowed': False, 'reason': 'No bankroll settings found'}
    
    current = float(settings['current_bankroll'])
    max_single = current * float(settings['max_single_game_pct']) / 100
    max_daily = current * float(settings['max_daily_exposure_pct']) / 100
    daily_used = float(settings['daily_exposure_used'])
    
    if stake > max_single:
        return {'allowed': False, 'reason': f'Exceeds max single bet (${max_single:.2f})'}
    
    if daily_used + stake > max_daily:
        return {'allowed': False, 'reason': f'Exceeds daily exposure limit (${max_daily:.2f})'}
    
    # Check stop loss
    stop_loss = float(settings['stop_loss_limit'])
    daily_pnl = float(settings['daily_profit_today'])
    if stop_loss > 0 and daily_pnl <= -stop_loss:
        return {'allowed': False, 'reason': f'Stop loss hit (-${stop_loss:.2f})'}
    
    return {'allowed': True, 'reason': 'Within limits'}

# ============================================================
# BET TRACKING
# ============================================================

def log_bet(discord_id: str, bet_type: str, description: str, pick: str,
            units: float, odds: int, confidence: str = 'standard', line: float = None):
    """Log a new bet"""
    settings = get_bankroll_settings(discord_id)
    if not settings:
        return None
    
    stake = calculate_stake(discord_id, units)
    bankroll_before = float(settings['current_bankroll'])
    
    engine = get_engine()
    with engine.connect() as conn:
        result = conn.execute(text("""
            INSERT INTO user_bets 
            (discord_id, bet_type, description, pick, units, stake_usd, 
             confidence, odds, line, bankroll_before)
            VALUES (:did, :bt, :desc, :pick, :units, :stake, :conf, :odds, :line, :bb)
            RETURNING id
        """), {
            "did": discord_id, "bt": bet_type, "desc": description, "pick": pick,
            "units": units, "stake": stake, "conf": confidence, "odds": odds,
            "line": line, "bb": bankroll_before
        })
        bet_id = result.fetchone()[0]
        
        # Update daily exposure
        conn.execute(text("""
            UPDATE bankroll_settings SET
                daily_exposure_used = daily_exposure_used + :stake,
                total_bets = total_bets + 1
            WHERE discord_id = :did
        """), {"did": discord_id, "stake": stake})
        
        conn.commit()
        return bet_id

def grade_bet(discord_id: str, bet_id: int, result: str):
    """Grade a bet (win/loss/push)"""
    engine = get_engine()
    
    with engine.connect() as conn:
        # Get bet details
        bet = conn.execute(text("""
            SELECT stake_usd, odds, bankroll_before FROM user_bets 
            WHERE id = :bid AND discord_id = :did
        """), {"bid": bet_id, "did": discord_id}).fetchone()
        
        if not bet:
            return None
        
        stake = float(bet[0])
        odds = bet[1]
        
        # Calculate P/L
        if result == 'win':
            if odds > 0:
                pnl = stake * (odds / 100)
            else:
                pnl = stake * (100 / abs(odds))
        elif result == 'loss':
            pnl = -stake
        else:  # push
            pnl = 0
        
        # Get current bankroll
        settings = get_bankroll_settings(discord_id)
        current = float(settings['current_bankroll'])
        new_bankroll = current + pnl
        
        # Update bet record
        conn.execute(text("""
            UPDATE user_bets SET
                result = :result,
                pnl_usd = :pnl,
                bankroll_after = :ba,
                graded_at = NOW()
            WHERE id = :bid
        """), {"result": result, "pnl": pnl, "ba": new_bankroll, "bid": bet_id})
        
        # Update bankroll settings
        win_add = 1 if result == 'win' else 0
        loss_add = 1 if result == 'loss' else 0
        push_add = 1 if result == 'push' else 0
        
        conn.execute(text("""
            UPDATE bankroll_settings SET
                current_bankroll = :cb,
                total_profit = total_profit + :pnl,
                wins = wins + :w,
                losses = losses + :l,
                pushes = pushes + :p,
                daily_profit_today = daily_profit_today + :pnl
            WHERE discord_id = :did
        """), {"did": discord_id, "cb": new_bankroll, "pnl": pnl, 
               "w": win_add, "l": loss_add, "p": push_add})
        
        conn.commit()
        
        # Update full bankroll stats
        update_bankroll(discord_id, new_bankroll)
        
        return {'pnl': pnl, 'new_bankroll': new_bankroll}

def get_pending_bets(discord_id: str):
    """Get all pending bets for user"""
    engine = get_engine()
    with engine.connect() as conn:
        results = conn.execute(text("""
            SELECT id, bet_type, description, pick, units, stake_usd, odds, placed_at
            FROM user_bets 
            WHERE discord_id = :did AND result = 'pending'
            ORDER BY placed_at DESC
        """), {"did": discord_id}).fetchall()
        return [dict(r._mapping) for r in results]

def get_bet_history(discord_id: str, limit: int = 20):
    """Get recent bet history"""
    engine = get_engine()
    with engine.connect() as conn:
        results = conn.execute(text("""
            SELECT id, bet_type, description, pick, units, stake_usd, odds, 
                   result, pnl_usd, placed_at, graded_at
            FROM user_bets 
            WHERE discord_id = :did AND result != 'pending'
            ORDER BY graded_at DESC
            LIMIT :lim
        """), {"did": discord_id, "lim": limit}).fetchall()
        return [dict(r._mapping) for r in results]

# ============================================================
# ANALYTICS & PERFORMANCE
# ============================================================

def get_performance_metrics(discord_id: str):
    """Get full performance metrics"""
    settings = get_bankroll_settings(discord_id)
    if not settings:
        return None
    
    starting = float(settings['starting_bankroll'])
    current = float(settings['current_bankroll'])
    profit = float(settings['total_profit'])
    roi = float(settings['roi_pct'])
    wins = settings['wins']
    losses = settings['losses']
    pushes = settings['pushes']
    total = wins + losses + pushes
    
    win_rate = (wins / total * 100) if total > 0 else 0
    
    return {
        'starting_bankroll': starting,
        'current_bankroll': current,
        'total_profit': profit,
        'roi_pct': round(roi, 2),
        'total_bets': total,
        'wins': wins,
        'losses': losses,
        'pushes': pushes,
        'win_rate': round(win_rate, 1),
        'risk_rating': settings['risk_rating'],
        'max_drawdown': float(settings['max_drawdown']),
        'peak_bankroll': float(settings['peak_bankroll']),
        'current_streak': settings['current_streak'],
        'best_streak': settings['best_streak'],
        'worst_streak': settings['worst_streak'],
        'unit_size': float(settings['unit_size']),
        'strategy': settings['strategy_profile']
    }

def get_bankroll_health(discord_id: str):
    """Get bankroll health indicator"""
    settings = get_bankroll_settings(discord_id)
    if not settings:
        return None
    
    starting = float(settings['starting_bankroll'])
    current = float(settings['current_bankroll'])
    peak = float(settings['peak_bankroll'])
    
    # Health score (0-100)
    roi = (current - starting) / starting * 100 if starting > 0 else 0
    drawdown_pct = (peak - current) / peak * 100 if peak > 0 else 0
    
    if roi >= 20 and drawdown_pct < 5:
        health = 'excellent'
        score = 95
    elif roi >= 10 and drawdown_pct < 10:
        health = 'good'
        score = 80
    elif roi >= 0 and drawdown_pct < 15:
        health = 'stable'
        score = 65
    elif roi >= -10 and drawdown_pct < 25:
        health = 'caution'
        score = 45
    else:
        health = 'critical'
        score = 25
    
    return {
        'health': health,
        'score': score,
        'roi': round(roi, 2),
        'drawdown_pct': round(drawdown_pct, 2),
        'current': current,
        'peak': peak
    }

def reset_daily_stats(discord_id: str):
    """Reset daily stats (call at midnight or on demand)"""
    engine = get_engine()
    with engine.connect() as conn:
        # Save to history first
        settings = get_bankroll_settings(discord_id)
        if settings:
            conn.execute(text("""
                INSERT INTO bankroll_history (discord_id, date, bankroll_value, daily_pnl)
                VALUES (:did, :date, :bv, :pnl)
                ON CONFLICT (discord_id, date) DO UPDATE SET
                    bankroll_value = :bv, daily_pnl = :pnl
            """), {
                "did": discord_id, 
                "date": date.today(),
                "bv": settings['current_bankroll'],
                "pnl": settings['daily_profit_today']
            })
        
        # Reset daily counters
        conn.execute(text("""
            UPDATE bankroll_settings SET
                daily_exposure_used = 0,
                daily_profit_today = 0,
                last_reset_date = CURRENT_DATE
            WHERE discord_id = :did
        """), {"did": discord_id})
        conn.commit()

# ============================================================
# DISCORD EMBED BUILDERS
# ============================================================

def build_bankroll_embed(discord_id: str):
    """Build Discord embed for bankroll overview"""
    settings = get_bankroll_settings(discord_id)
    if not settings:
        return None
    
    metrics = get_performance_metrics(discord_id)
    health = get_bankroll_health(discord_id)
    sizes = get_bet_sizes(discord_id)
    
    # Color based on health
    colors = {'excellent': 0x00FF00, 'good': 0x00CC00, 'stable': 0xFFFF00, 
              'caution': 0xFFA500, 'critical': 0xFF0000}
    color = colors.get(health['health'], 0x667eea)
    
    # ROI emoji
    roi = metrics['roi_pct']
    roi_emoji = "📈" if roi > 0 else "📉" if roi < 0 else "➡️"
    
    embed = {
        "title": "💰 Bankroll Manager — Financial Control Suite",
        "description": f"**{settings['strategy_profile'].title()} Strategy** | {health['health'].title()} Health",
        "color": color,
        "fields": [
            {"name": "💵 Current Bankroll", "value": f"${metrics['current_bankroll']:,.2f}", "inline": True},
            {"name": f"{roi_emoji} ROI", "value": f"{roi:+.1f}%", "inline": True},
            {"name": "📊 Total P/L", "value": f"${metrics['total_profit']:+,.2f}", "inline": True},
            
            {"name": "🎯 Unit Size", "value": f"${sizes['unit_size']:,.2f}", "inline": True},
            {"name": "📈 Win Rate", "value": f"{metrics['win_rate']:.1f}%", "inline": True},
            {"name": "🎲 Record", "value": f"{metrics['wins']}W-{metrics['losses']}L-{metrics['pushes']}P", "inline": True},
            
            {"name": "🟢 Low (0.5u)", "value": f"${sizes['low_confidence']['stake']:,.2f}", "inline": True},
            {"name": "🟡 Standard (1u)", "value": f"${sizes['standard']['stake']:,.2f}", "inline": True},
            {"name": "🔴 High (2u)", "value": f"${sizes['high_confidence']['stake']:,.2f}", "inline": True},
        ],
        "footer": {"text": f"Risk Rating: {metrics['risk_rating'].title()} | Max Bet: ${sizes['max_bet']:,.2f}"}
    }
    
    return embed

def build_health_embed(discord_id: str):
    """Build Discord embed for bankroll health"""
    health = get_bankroll_health(discord_id)
    if not health:
        return None
    
    # Health bar visualization
    filled = int(health['score'] / 10)
    empty = 10 - filled
    bar = "🟩" * filled + "⬜" * empty
    
    colors = {'excellent': 0x00FF00, 'good': 0x00CC00, 'stable': 0xFFFF00, 
              'caution': 0xFFA500, 'critical': 0xFF0000}
    
    embed = {
        "title": "🏥 Bankroll Health",
        "description": f"{bar}\n**{health['health'].upper()}** — {health['score']}%",
        "color": colors.get(health['health'], 0x667eea),
        "fields": [
            {"name": "📈 ROI", "value": f"{health['roi']:+.1f}%", "inline": True},
            {"name": "📉 Drawdown", "value": f"{health['drawdown_pct']:.1f}%", "inline": True},
            {"name": "🏔️ Peak", "value": f"${health['peak']:,.2f}", "inline": True},
        ]
    }
    
    return embed

print("✅ bankroll_manager.py loaded successfully")

# ============================================================
# STAKE PREVIEW
# ============================================================

def preview_bet(discord_id: str, units: float, odds: int, description: str = ""):
    """Preview a bet before placing it - shows full impact analysis"""
    settings = get_bankroll_settings(discord_id)
    if not settings:
        return None
    
    current = float(settings['current_bankroll'])
    unit_size = float(settings['unit_size'])
    stake = unit_size * units
    
    # Calculate potential outcomes
    if odds > 0:
        potential_win = stake * (odds / 100)
    else:
        potential_win = stake * (100 / abs(odds))
    
    potential_loss = stake
    
    bankroll_if_win = current + potential_win
    bankroll_if_loss = current - potential_loss
    
    # Exposure analysis
    daily_used = float(settings['daily_exposure_used'])
    max_daily = current * float(settings['max_daily_exposure_pct']) / 100
    max_single = current * float(settings['max_single_game_pct']) / 100
    
    new_daily_exposure = daily_used + stake
    daily_remaining = max_daily - new_daily_exposure
    
    # Risk checks
    warnings = []
    
    # Check single bet limit
    if stake > max_single:
        warnings.append(f"⚠️ Exceeds max single bet (${max_single:,.2f})")
    
    # Check daily exposure
    if new_daily_exposure > max_daily:
        warnings.append(f"⚠️ Exceeds daily exposure limit (${max_daily:,.2f})")
    
    # Check stop loss
    stop_loss = float(settings['stop_loss_limit'])
    daily_pnl = float(settings['daily_profit_today'])
    if stop_loss > 0 and daily_pnl <= -stop_loss:
        warnings.append(f"🛑 Stop loss already hit (-${stop_loss:,.2f})")
    
    # Check if loss would hit stop loss
    if stop_loss > 0 and (daily_pnl - stake) <= -stop_loss:
        warnings.append(f"⚠️ Loss would trigger stop loss")
    
    # Discipline warnings
    if daily_pnl < 0 and units > 1.0:
        warnings.append("💡 Consider smaller size after losses")
    
    return {
        'stake': stake,
        'units': units,
        'odds': odds,
        'pct_of_bankroll': (stake / current) * 100,
        'potential_win': potential_win,
        'potential_loss': potential_loss,
        'bankroll_if_win': bankroll_if_win,
        'bankroll_if_loss': bankroll_if_loss,
        'roi_if_win': ((bankroll_if_win - float(settings['starting_bankroll'])) / float(settings['starting_bankroll'])) * 100,
        'roi_if_loss': ((bankroll_if_loss - float(settings['starting_bankroll'])) / float(settings['starting_bankroll'])) * 100,
        'daily_exposure_after': new_daily_exposure,
        'daily_remaining': max(0, daily_remaining),
        'max_daily': max_daily,
        'warnings': warnings,
        'allowed': len([w for w in warnings if w.startswith('⚠️') or w.startswith('🛑')]) == 0
    }

def build_preview_embed(discord_id: str, units: float, odds: int, description: str = ""):
    """Build Discord embed for bet preview"""
    preview = preview_bet(discord_id, units, odds, description)
    if not preview:
        return None
    
    # Color based on risk
    if not preview['allowed']:
        color = 0xFF0000  # Red - blocked
    elif preview['warnings']:
        color = 0xFFA500  # Orange - caution
    else:
        color = 0x00FF00  # Green - good
    
    title = f"🔍 Bet Preview: {units}u @ {odds:+d}"
    if description:
        title = f"🔍 Preview: {description[:30]}"
    
    embed = {
        "title": title,
        "color": color,
        "fields": [
            {"name": "💵 Stake", "value": f"**${preview['stake']:,.2f}**\n({preview['pct_of_bankroll']:.1f}% of bankroll)", "inline": True},
            {"name": "📈 If Win", "value": f"+${preview['potential_win']:,.2f}\n→ ${preview['bankroll_if_win']:,.2f}", "inline": True},
            {"name": "📉 If Loss", "value": f"-${preview['potential_loss']:,.2f}\n→ ${preview['bankroll_if_loss']:,.2f}", "inline": True},
            {"name": "📊 Daily Exposure", "value": f"${preview['daily_exposure_after']:,.2f} / ${preview['max_daily']:,.2f}\nRemaining: ${preview['daily_remaining']:,.2f}", "inline": False},
        ]
    }
    
    if preview['warnings']:
        embed['fields'].append({
            "name": "⚠️ Warnings",
            "value": "\n".join(preview['warnings']),
            "inline": False
        })
    
    status = "✅ Within limits" if preview['allowed'] else "❌ Exceeds limits"
    embed['footer'] = {"text": f"{status} | To place: !bet {units} {odds} <pick>"}
    
    return embed

# ============================================================
# DAILY SNAPSHOTS
# ============================================================

def save_daily_snapshot(discord_id: str):
    """Save daily bankroll snapshot for equity curve"""
    settings = get_bankroll_settings(discord_id)
    if not settings:
        return False
    
    engine = get_engine()
    with engine.connect() as conn:
        # Count today's bets
        bet_stats = conn.execute(text("""
            SELECT COUNT(*), 
                   SUM(CASE WHEN result = 'win' THEN 1 ELSE 0 END),
                   SUM(CASE WHEN result = 'loss' THEN 1 ELSE 0 END)
            FROM user_bets 
            WHERE discord_id = :did 
            AND DATE(placed_at) = CURRENT_DATE
        """), {"did": discord_id}).fetchone()
        
        conn.execute(text("""
            INSERT INTO bankroll_history 
            (discord_id, date, bankroll_value, daily_pnl, bets_placed, wins, losses)
            VALUES (:did, CURRENT_DATE, :bv, :pnl, :bets, :wins, :losses)
            ON CONFLICT (discord_id, date) DO UPDATE SET
                bankroll_value = :bv,
                daily_pnl = :pnl,
                bets_placed = :bets,
                wins = :wins,
                losses = :losses
        """), {
            "did": discord_id,
            "bv": settings['current_bankroll'],
            "pnl": settings['daily_profit_today'],
            "bets": bet_stats[0] or 0,
            "wins": bet_stats[1] or 0,
            "losses": bet_stats[2] or 0
        })
        conn.commit()
    return True

def get_equity_curve(discord_id: str, days: int = 30):
    """Get bankroll history for equity curve"""
    engine = get_engine()
    with engine.connect() as conn:
        results = conn.execute(text("""
            SELECT date, bankroll_value, daily_pnl
            FROM bankroll_history
            WHERE discord_id = :did
            ORDER BY date DESC
            LIMIT :days
        """), {"did": discord_id, "days": days}).fetchall()
        return [{"date": r[0], "value": float(r[1]), "pnl": float(r[2])} for r in results]

# ============================================================
# DISCIPLINE WARNINGS
# ============================================================

def check_discipline(discord_id: str, proposed_units: float):
    """Check for discipline issues and return warnings"""
    settings = get_bankroll_settings(discord_id)
    if not settings:
        return []
    
    warnings = []
    
    daily_pnl = float(settings['daily_profit_today'])
    current_streak = settings['current_streak']
    
    # Warning: Increasing size after loss
    if daily_pnl < 0 and proposed_units > 1.0:
        warnings.append({
            "type": "tilt_risk",
            "message": "💡 You're increasing size after a losing day. Consider standard sizing.",
            "severity": "medium"
        })
    
    # Warning: On a losing streak
    if current_streak < -2:
        warnings.append({
            "type": "streak",
            "message": f"📉 You're on a {abs(current_streak)}-bet losing streak. Maybe take a break?",
            "severity": "medium"
        })
    
    # Warning: Near stop loss
    stop_loss = float(settings['stop_loss_limit'])
    if stop_loss > 0 and daily_pnl < 0:
        pct_to_stop = abs(daily_pnl) / stop_loss * 100
        if pct_to_stop >= 75:
            warnings.append({
                "type": "stop_loss",
                "message": f"⚠️ You're {pct_to_stop:.0f}% to your stop loss. Proceed carefully.",
                "severity": "high"
            })
    
    # Warning: High exposure already
    daily_used = float(settings['daily_exposure_used'])
    current = float(settings['current_bankroll'])
    max_daily = current * float(settings['max_daily_exposure_pct']) / 100
    if daily_used > max_daily * 0.75:
        warnings.append({
            "type": "exposure",
            "message": f"📊 You've used {daily_used/max_daily*100:.0f}% of daily exposure.",
            "severity": "low"
        })
    
    return warnings

def send_discipline_dm_content(warnings: list):
    """Generate DM content for discipline warnings"""
    if not warnings:
        return None
    
    high = [w for w in warnings if w['severity'] == 'high']
    medium = [w for w in warnings if w['severity'] == 'medium']
    
    if high:
        title = "🛑 Risk Alert"
        color = 0xFF0000
    elif medium:
        title = "💡 Discipline Check"
        color = 0xFFA500
    else:
        title = "📊 Quick Note"
        color = 0x667eea
    
    messages = [w['message'] for w in warnings]
    
    return {
        "title": title,
        "description": "\n\n".join(messages),
        "color": color,
        "footer": {"text": "This is coaching, not control. You decide."}
    }
