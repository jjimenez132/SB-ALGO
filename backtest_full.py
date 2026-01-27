#!/usr/bin/env python3
"""
================================================================================
FULL ENGINE BACKTEST - COMPREHENSIVE
================================================================================
Tests the ACTUAL algorithm (engine + filters) against real results.
Shows full breakdown by:
- Stat type (PTS, REB, AST)
- Over/Under
- Date
- Win/Loss per pick
================================================================================
"""

import psycopg2
import statistics
from collections import defaultdict
from datetime import datetime, date, timedelta
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'engines'))

DATABASE_URL = 'postgresql://sb_algo_db_user:0HDtYp4EY2Lo5At8iyf44PD1zDioSPK7@dpg-d495uhchg0os738l1a50-a.virginia-postgres.render.com/sb_algo_db'

# Import filters from the actual algo
from sb_algo_api import PROP_FILTERS, get_proj

# =============================================================================
# FILTER THRESHOLDS (from sb_algo_api.py)
# =============================================================================
print("\n📋 FILTERS BEING TESTED:")
for fkey, f in PROP_FILTERS.items():
    print(f"   {fkey}: edge>={f.get('edge_min',0)*100:.0f}%, cv<={f.get('cv_max',0)}, proj>={f.get('proj_min',0)}")

def run_full_backtest():
    print("\n" + "=" * 70)
    print("🔥 FULL ENGINE BACKTEST - Dec 1, 2025 to Jan 25, 2026")
    print("=" * 70)
    
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    
    # =========================================================================
    # LOAD ALL DATA
    # =========================================================================
    print("\n📊 Loading data...")
    
    # Load all boxscores
    cur.execute("""
        SELECT player_name, game_date, pts, reb, ast, min
        FROM player_boxscores
        WHERE game_date >= '2025-10-01'
        ORDER BY player_name, game_date
    """)
    
    player_games = defaultdict(list)
    for row in cur.fetchall():
        player, gdate, pts, reb, ast, mins = row
        min_val = 0
        if mins:
            if ':' in str(mins):
                min_val = float(str(mins).split(':')[0])
            else:
                try: min_val = float(mins)
                except: min_val = 0
        if min_val >= 20:  # Same filter as algo
            player_games[player].append({
                'date': gdate, 
                'pts': float(pts or 0), 
                'reb': float(reb or 0), 
                'ast': float(ast or 0),
                'min': min_val
            })
    
    print(f"   ✅ {len(player_games)} players loaded")
    
    # Load props
    cur.execute("""
        SELECT player_name, market, line, over_odds, under_odds, game_date
        FROM player_props
        WHERE game_date >= '2025-12-01' AND game_date <= '2026-01-25'
        AND sportsbook = 'DraftKings'
        AND market IN ('player_points', 'player_rebounds', 'player_assists')
        ORDER BY game_date
    """)
    props = cur.fetchall()
    print(f"   ✅ {len(props)} props loaded")
    
    conn.close()
    
    # Market to stat mapping
    MARKET_TO_STAT = {
        'player_points': 'pts',
        'player_rebounds': 'reb',
        'player_assists': 'ast'
    }
    
    # =========================================================================
    # RUN BACKTEST
    # =========================================================================
    print(f"\n⚡ Running backtest with FULL FILTERS...")
    
    results = {
        'pts_over': {'wins': 0, 'losses': 0, 'pushes': 0, 'picks': []},
        'pts_under': {'wins': 0, 'losses': 0, 'pushes': 0, 'picks': []},
        'reb_over': {'wins': 0, 'losses': 0, 'pushes': 0, 'picks': []},
        'reb_under': {'wins': 0, 'losses': 0, 'pushes': 0, 'picks': []},
        'ast_over': {'wins': 0, 'losses': 0, 'pushes': 0, 'picks': []},
        'ast_under': {'wins': 0, 'losses': 0, 'pushes': 0, 'picks': []},
    }
    
    by_date = defaultdict(lambda: {'wins': 0, 'losses': 0})
    
    tested = 0
    skipped_no_data = 0
    skipped_no_result = 0
    
    for player, market, line, over_odds, under_odds, game_date in props:
        stat = MARKET_TO_STAT.get(market)
        if not stat:
            continue
            
        line = float(line)
        if line == 0:
            continue
        
        # Get projection using same method as algo
        proj, cv = get_proj(player_games, player, stat, game_date)
        if proj is None:
            skipped_no_data += 1
            continue
        
        # Get actual result
        actual_games = [g for g in player_games[player] if g['date'] == game_date]
        if not actual_games:
            skipped_no_result += 1
            continue
        actual = actual_games[0][stat]
        
        tested += 1
        
        # =======================================================================
        # CHECK OVER
        # =======================================================================
        edge = (proj - line) / line
        fkey = f"{stat}_over"
        if fkey in PROP_FILTERS:
            f = PROP_FILTERS[fkey]
            e_pass = edge >= f.get('edge_min', 0.15)
            c_pass = cv <= f.get('cv_max', 0.45)
            p_pass = proj >= f.get('proj_min', 10)
            
            if e_pass and c_pass and p_pass:
                # This pick would have been made!
                if actual > line:
                    results[fkey]['wins'] += 1
                    by_date[str(game_date)]['wins'] += 1
                    results[fkey]['picks'].append({'player': player, 'line': line, 'actual': actual, 'proj': proj, 'result': 'W', 'date': str(game_date)})
                elif actual < line:
                    results[fkey]['losses'] += 1
                    by_date[str(game_date)]['losses'] += 1
                    results[fkey]['picks'].append({'player': player, 'line': line, 'actual': actual, 'proj': proj, 'result': 'L', 'date': str(game_date)})
                else:
                    results[fkey]['pushes'] += 1
        
        # =======================================================================
        # CHECK UNDER
        # =======================================================================
        edge_u = (line - proj) / line
        fkey_u = f"{stat}_under"
        if fkey_u in PROP_FILTERS:
            f = PROP_FILTERS[fkey_u]
            e_pass = edge_u >= f.get('edge_min', 0.15)
            c_pass = cv <= f.get('cv_max', 0.45)
            p_pass = proj >= f.get('proj_min', 10)
            
            if e_pass and c_pass and p_pass:
                # This pick would have been made!
                if actual < line:
                    results[fkey_u]['wins'] += 1
                    by_date[str(game_date)]['wins'] += 1
                    results[fkey_u]['picks'].append({'player': player, 'line': line, 'actual': actual, 'proj': proj, 'result': 'W', 'date': str(game_date)})
                elif actual > line:
                    results[fkey_u]['losses'] += 1
                    by_date[str(game_date)]['losses'] += 1
                    results[fkey_u]['picks'].append({'player': player, 'line': line, 'actual': actual, 'proj': proj, 'result': 'L', 'date': str(game_date)})
                else:
                    results[fkey_u]['pushes'] += 1
    
    # =========================================================================
    # PRINT RESULTS
    # =========================================================================
    print(f"\n{'='*70}")
    print("📊 FULL BACKTEST RESULTS")
    print(f"{'='*70}")
    print(f"Props analyzed: {tested}")
    print(f"Skipped (no data): {skipped_no_data}")
    print(f"Skipped (no result): {skipped_no_result}")
    
    print(f"\n{'='*70}")
    print("📈 RESULTS BY STAT TYPE")
    print(f"{'='*70}")
    
    total_wins = 0
    total_losses = 0
    total_pushes = 0
    
    for fkey in ['pts_over', 'pts_under', 'reb_over', 'reb_under', 'ast_over', 'ast_under']:
        r = results[fkey]
        total = r['wins'] + r['losses']
        total_wins += r['wins']
        total_losses += r['losses']
        total_pushes += r['pushes']
        
        if total > 0:
            pct = r['wins'] / total * 100
            emoji = "🔥" if pct >= 70 else "✅" if pct >= 55 else "⚠️"
            print(f"   {emoji} {fkey.upper():12} {r['wins']:3}-{r['losses']:3} ({pct:5.1f}%) | {total} picks")
        else:
            print(f"   ⬜ {fkey.upper():12} No picks")
    
    print(f"\n{'='*70}")
    print("🎯 OVERALL RESULTS")
    print(f"{'='*70}")
    
    total = total_wins + total_losses
    if total > 0:
        overall_pct = total_wins / total * 100
        roi = (total_wins * 0.909 - total_losses) / total * 100  # Using -110 odds
        print(f"   TOTAL: {total_wins}-{total_losses} ({overall_pct:.1f}%)")
        print(f"   ROI: {roi:+.1f}%")
        print(f"   Total filtered picks: {total}")
        print(f"   Pushes: {total_pushes}")
    
    # Show last 20 picks
    print(f"\n{'='*70}")
    print("📋 LAST 20 PICKS (Sample)")
    print(f"{'='*70}")
    
    all_picks = []
    for fkey, r in results.items():
        for p in r['picks']:
            p['type'] = fkey
            all_picks.append(p)
    
    all_picks.sort(key=lambda x: x['date'], reverse=True)
    
    for p in all_picks[:20]:
        emoji = "✅" if p['result'] == 'W' else "❌"
        print(f"   {emoji} {p['date']} | {p['player'][:20]:20} | {p['type']:12} | Line: {p['line']:5.1f} | Actual: {p['actual']:5.1f} | Proj: {p['proj']:5.1f}")
    
    # Daily breakdown
    print(f"\n{'='*70}")
    print("📅 DAILY BREAKDOWN")
    print(f"{'='*70}")
    
    sorted_dates = sorted(by_date.keys(), reverse=True)
    for d in sorted_dates[:14]:
        r = by_date[d]
        total = r['wins'] + r['losses']
        if total > 0:
            pct = r['wins'] / total * 100
            emoji = "🔥" if pct >= 70 else "✅" if pct >= 55 else "⚠️"
            print(f"   {emoji} {d}: {r['wins']}-{r['losses']} ({pct:.0f}%)")
    
    print(f"\n{'='*70}")
    print("✅ BACKTEST COMPLETE")
    print(f"{'='*70}")

if __name__ == "__main__":
    run_full_backtest()
