#!/usr/bin/env python3
"""
Grade Discord Picks - Grade picks sent to Discord and post results
==================================================================
This script:
1. Gets pending picks from algo_picks_tracking
2. Grades them against actual game scores / player stats
3. Posts individual results to #results
4. Posts daily summary to #daily-recap
"""

import os
import requests
import re
from datetime import datetime, timedelta
from sqlalchemy import create_engine, text
import pytz

DATABASE_URL = os.environ.get('DATABASE_URL',
    "postgresql://sb_algo_db_user:0HDtYp4EY2Lo5At8iyf44PD1zDioSPK7@dpg-d495uhchg0os738l1a50-a.virginia-postgres.render.com/sb_algo_db")

RESULTS_WEBHOOK = os.environ.get('DISCORD_WEBHOOK_RESULTS',
    'https://discord.com/api/webhooks/1453117355327750185/SIakCtSyVdXBzyhguN_2NWsYjAw6Xg6sTOMcdudnp9L9WDO5Mj7k0pk1o51qFyfX7EJb')

# Daily recap webhook - using same for now, change if different
RECAP_WEBHOOK = os.environ.get('DISCORD_WEBHOOK_RECAP', RESULTS_WEBHOOK)

def get_engine():
    return create_engine(DATABASE_URL)

def get_eastern_now():
    return datetime.now(pytz.timezone('US/Eastern'))

def get_eastern_date():
    return get_eastern_now().strftime('%Y-%m-%d')

# ============================================================
# GET GAME SCORES
# ============================================================

def get_game_scores(game_date):
    """Get actual game scores for a date"""
    engine = get_engine()
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT home_team, visitor_team, home_pts, visitor_pts, total_points
            FROM games
            WHERE date = :game_date
        """), {"game_date": game_date}).fetchall()
        
        scores = {}
        for r in result:
            home = r[0]
            away = r[1]
            total = r[4] or 0
            
            # Create multiple keys for matching
            key1 = f"{away} @ {home}".upper()
            key2 = f"{home} vs {away}".upper()
            
            scores[key1] = {
                'home': home, 'away': away,
                'home_pts': r[2], 'away_pts': r[3],
                'total': total
            }
            scores[key2] = scores[key1]
            
            # Also add abbreviated versions
            scores[home.upper()] = scores[key1]
            scores[away.upper()] = scores[key1]
        
        return scores

# ============================================================
# GET PLAYER STATS
# ============================================================

def get_player_stats(game_date):
    """Get actual player stats for a date"""
    engine = get_engine()
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT player_name, pts, reb, ast, stl, blk, "TO", 
                   pts + reb + ast as pra
            FROM player_boxscores
            WHERE game_date = :game_date
        """), {"game_date": game_date}).fetchall()
        
        stats = {}
        for r in result:
            name = r[0].upper() if r[0] else ''
            stats[name] = {
                'pts': r[1] or 0,
                'reb': r[2] or 0,
                'ast': r[3] or 0,
                'stl': r[4] or 0,
                'blk': r[5] or 0,
                'tov': r[6] or 0,
                'pra': r[7] or 0
            }
        return stats

# ============================================================
# GRADE A SINGLE PICK
# ============================================================

def grade_pick(pick, game_scores, player_stats):
    """
    Grade a single pick against actual results.
    Returns: 'win', 'loss', 'push', or None if can't grade
    """
    pick_name = pick['pick_name'].upper()
    pick_type = pick['pick_type']
    
    if pick_type == 'game':
        # Parse game pick: "LAL @ NO UNDER 244.0" or "MIA @ MIN UNDER 238.5"
        # Look for OVER/UNDER pattern
        match = re.search(r'(.+?)\s+(UNDER|OVER)\s+([\d.]+)', pick_name)
        if match:
            matchup = match.group(1).strip()
            direction = match.group(2)
            line = float(match.group(3))
            
            # Find the game
            for key, score in game_scores.items():
                if matchup in key or key in matchup:
                    actual_total = score['total']
                    
                    if actual_total == 0:
                        return None  # Game not finished
                    
                    if direction == 'UNDER':
                        if actual_total < line:
                            return 'win'
                        elif actual_total > line:
                            return 'loss'
                        else:
                            return 'push'
                    else:  # OVER
                        if actual_total > line:
                            return 'win'
                        elif actual_total < line:
                            return 'loss'
                        else:
                            return 'push'
            
            print(f"   ⚠️ Could not find game for: {matchup}")
            return None
    
    elif pick_type == 'prop':
        # Parse prop pick: "EVAN MOBLEY PTS UNDER 20.5" or "NAJI MARSHALL REB UNDER 5.5"
        match = re.search(r'(.+?)\s+(PTS|REB|AST|STL|BLK|PRA)\s+(UNDER|OVER)\s+([\d.]+)', pick_name)
        if match:
            player_name = match.group(1).strip()
            stat_type = match.group(2).lower()
            direction = match.group(3)
            line = float(match.group(4))
            
            # Find player stats
            for name, stats in player_stats.items():
                if player_name in name or name in player_name:
                    actual_value = stats.get(stat_type, 0)
                    
                    if direction == 'UNDER':
                        if actual_value < line:
                            return 'win'
                        elif actual_value > line:
                            return 'loss'
                        else:
                            return 'push'
                    else:  # OVER
                        if actual_value > line:
                            return 'win'
                        elif actual_value < line:
                            return 'loss'
                        else:
                            return 'push'
            
            print(f"   ⚠️ Could not find player stats for: {player_name}")
            return None
    
    return None

# ============================================================
# POST RESULT TO DISCORD
# ============================================================

def post_result_to_discord(pick, result, actual_value=None):
    """Post individual result to #results channel"""
    import time
    
    if result == 'win':
        emoji = "✅"
        color = 0x00FF00  # Green
        pnl = f"+{pick['units']:.1f}u"
    elif result == 'loss':
        emoji = "❌"
        color = 0xFF0000  # Red
        pnl = f"-{pick['units']:.1f}u"
    else:  # push
        emoji = "➖"
        color = 0xFFFF00  # Yellow
        pnl = "0u"
    
    embed = {
        "title": f"{emoji} [{pick['pick_id']}] {pick['pick_name']}",
        "description": f"**Result: {result.upper()}** | P/L: **{pnl}**",
        "color": color,
        "footer": {"text": f"SB-ALGO • {pick['pick_date']}"}
    }
    
    if actual_value:
        embed["description"] += f"\nActual: {actual_value}"
    
    for attempt in range(3):
        try:
            response = requests.post(RESULTS_WEBHOOK, json={"embeds": [embed]}, timeout=10)
            if response.status_code in [200, 204]:
                print(f"   {emoji} Posted [{pick['pick_id']}] {result.upper()}")
                return True
            elif response.status_code == 429:
                retry_after = response.json().get('retry_after', 2)
                time.sleep(retry_after + 1)
            else:
                print(f"   ⚠️ Discord error: {response.status_code}")
                return False
        except Exception as e:
            print(f"   ⚠️ Error: {e}")
            time.sleep(2)
    
    return False

# ============================================================
# POST DAILY RECAP
# ============================================================

def post_daily_recap(pick_date, results):
    """Post daily summary to #daily-recap"""
    import time
    
    wins = sum(1 for r in results if r['result'] == 'win')
    losses = sum(1 for r in results if r['result'] == 'loss')
    pushes = sum(1 for r in results if r['result'] == 'push')
    total = len(results)
    
    if total == 0:
        return
    
    # Calculate P/L
    total_pnl = 0
    for r in results:
        if r['result'] == 'win':
            total_pnl += r['units']
        elif r['result'] == 'loss':
            total_pnl -= r['units']
    
    win_rate = (wins / (wins + losses) * 100) if (wins + losses) > 0 else 0
    
    # Color based on P/L
    if total_pnl > 0:
        color = 0x00FF00
        emoji = "🟢"
    elif total_pnl < 0:
        color = 0xFF0000
        emoji = "🔴"
    else:
        color = 0xFFFF00
        emoji = "🟡"
    
    embed = {
        "title": f"📊 DAILY RECAP — {pick_date}",
        "description": f"{emoji} **Record: {wins}-{losses}** ({win_rate:.0f}%)",
        "color": color,
        "fields": [
            {"name": "✅ Wins", "value": str(wins), "inline": True},
            {"name": "❌ Losses", "value": str(losses), "inline": True},
            {"name": "➖ Pushes", "value": str(pushes), "inline": True},
            {"name": "💰 P/L", "value": f"**{total_pnl:+.1f}u**", "inline": True},
            {"name": "📈 Win Rate", "value": f"{win_rate:.0f}%", "inline": True},
            {"name": "🎯 Total Picks", "value": str(total), "inline": True},
        ],
        "footer": {"text": "SB-ALGO • Automated Grading System"}
    }
    
    # Add individual results
    results_text = ""
    for r in results:
        em = "✅" if r['result'] == 'win' else "❌" if r['result'] == 'loss' else "➖"
        results_text += f"{em} [{r['pick_id']}] {r['pick_name'][:30]}...\n"
    
    if results_text:
        embed["fields"].append({
            "name": "📋 Results",
            "value": results_text[:1000],
            "inline": False
        })
    
    for attempt in range(3):
        try:
            response = requests.post(RECAP_WEBHOOK, json={"embeds": [embed]}, timeout=10)
            if response.status_code in [200, 204]:
                print(f"   ✅ Posted daily recap: {wins}-{losses} ({total_pnl:+.1f}u)")
                return True
            elif response.status_code == 429:
                retry_after = response.json().get('retry_after', 2)
                time.sleep(retry_after + 1)
        except Exception as e:
            print(f"   ⚠️ Recap error: {e}")
            time.sleep(2)
    
    return False

# ============================================================
# UPDATE DATABASE
# ============================================================

def update_pick_result(pick_id, result, units_result):
    """Update pick status in database"""
    engine = get_engine()
    with engine.connect() as conn:
        conn.execute(text("""
            UPDATE algo_picks_tracking
            SET status = :result,
                result_units = :units_result,
                graded_at = CURRENT_TIMESTAMP
            WHERE id = :id
        """), {
            "result": result,
            "units_result": units_result,
            "id": pick_id
        })
        conn.commit()

# ============================================================
# MAIN
# ============================================================

def main():
    eastern = pytz.timezone('US/Eastern')
    now = datetime.now(eastern)
    yesterday = (now - timedelta(days=1)).strftime('%Y-%m-%d')
    
    print(f"{'='*60}")
    print(f"📊 GRADING DISCORD PICKS")
    print(f"⏰ {now.strftime('%Y-%m-%d %H:%M:%S')} ET")
    print(f"📅 Grading: {yesterday}")
    print(f"{'='*60}")
    
    engine = get_engine()
    
    # Get pending picks from yesterday
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT id, pick_id, pick_name, pick_type, units, pick_date
            FROM algo_picks_tracking
            WHERE pick_date = :yesterday AND status = 'pending'
            ORDER BY created_at
        """), {"yesterday": yesterday}).fetchall()
        
        picks = []
        for r in result:
            picks.append({
                'id': r[0],
                'pick_id': r[1],
                'pick_name': r[2],
                'pick_type': r[3],
                'units': float(r[4]) if r[4] else 1.0,
                'pick_date': str(r[5])
            })
    
    if not picks:
        print(f"   ℹ️ No pending picks to grade for {yesterday}")
        return
    
    print(f"   📋 Found {len(picks)} pending picks")
    
    # Get actual results
    game_scores = get_game_scores(yesterday)
    player_stats = get_player_stats(yesterday)
    
    print(f"   🏀 Found {len(game_scores)//2} games with scores")
    print(f"   🎯 Found {len(player_stats)} player stat lines")
    
    # Grade each pick
    graded_results = []
    
    print(f"\n{'='*60}")
    print(f"📝 GRADING PICKS")
    print(f"{'='*60}")
    
    for pick in picks:
        result = grade_pick(pick, game_scores, player_stats)
        
        if result:
            # Calculate units result based on actual odds
            if result == 'win':
                odds = pick.get('odds') or -110  # Default to -110 if no odds
                if odds < 0:
                    multiplier = 100 / abs(odds)
                else:
                    multiplier = odds / 100
                units_result = round(pick['units'] * multiplier, 2)
            elif result == 'loss':
                units_result = -pick['units']
            else:
                units_result = 0
            
            # Update database
            update_pick_result(pick['id'], result, units_result)
            
            # Post to Discord
            post_result_to_discord(pick, result)
            
            graded_results.append({
                'pick_id': pick['pick_id'],
                'pick_name': pick['pick_name'],
                'result': result,
                'units': pick['units']
            })
            
            import time
            time.sleep(1)  # Rate limit
        else:
            print(f"   ⚠️ Could not grade: {pick['pick_name']}")
    
    # Post daily recap
    if graded_results:
        print(f"\n{'='*60}")
        print(f"📊 POSTING DAILY RECAP")
        print(f"{'='*60}")
        post_daily_recap(yesterday, graded_results)
    
    print(f"\n{'='*60}")
    print(f"✅ GRADING COMPLETE - {len(graded_results)}/{len(picks)} graded")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()
