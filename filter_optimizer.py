#!/usr/bin/env python3
"""
================================================================================
FILTER OPTIMIZER V3 - Three Tiers for 4+ picks/day
================================================================================
Goal: 
- Tier 1: 80%+ win rate (elite picks)
- Tier 2: 70-80% win rate (strong picks)  
- Tier 3: 65-70% win rate (good value picks)
- Combined: ~4+ picks per day
================================================================================
"""

import psycopg2
import statistics
from collections import defaultdict
import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'engines'))

DATABASE_URL = 'postgresql://sb_algo_db_user:0HDtYp4EY2Lo5At8iyf44PD1zDioSPK7@dpg-d495uhchg0os738l1a50-a.virginia-postgres.render.com/sb_algo_db'

def load_data():
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    
    cur.execute("""
        SELECT player_name, game_date, pts, reb, ast, min
        FROM player_boxscores WHERE game_date >= '2025-10-01'
        ORDER BY player_name, game_date
    """)
    
    player_games = defaultdict(list)
    for row in cur.fetchall():
        player, gdate, pts, reb, ast, mins = row
        min_val = 0
        if mins:
            if ':' in str(mins): min_val = float(str(mins).split(':')[0])
            else:
                try: min_val = float(mins)
                except: min_val = 0
        if min_val >= 20:
            player_games[player].append({
                'date': gdate, 'pts': float(pts or 0), 
                'reb': float(reb or 0), 'ast': float(ast or 0), 'min': min_val
            })
    
    cur.execute("""
        SELECT player_name, market, line, over_odds, under_odds, game_date
        FROM player_props
        WHERE game_date >= '2025-12-01' AND game_date <= '2026-01-25'
        AND sportsbook = 'DraftKings'
        AND market IN ('player_points', 'player_rebounds', 'player_assists')
        ORDER BY game_date
    """)
    props = cur.fetchall()
    conn.close()
    return player_games, props

def get_proj(player_games, player, stat, game_date):
    if player not in player_games:
        return None, None
    games_list = sorted([g for g in player_games[player] if g['date'] < game_date], key=lambda x: x['date'], reverse=True)
    if len(games_list) < 5:
        return None, None
    values = [g[stat] for g in games_list[:15]]
    if len(values) < 5:
        return None, None
    l5 = sum(values[:5]) / 5
    l10 = sum(values[:min(10, len(values))]) / min(10, len(values))
    l15 = sum(values[:min(15, len(values))]) / min(15, len(values))
    season = sum(values) / len(values)
    proj = 0.40*l5 + 0.30*l10 + 0.20*l15 + 0.10*season
    std = statistics.stdev(values[:10]) if len(values) >= 10 else statistics.stdev(values[:5])
    cv = std / proj if proj > 0 else 1
    return proj, cv

def test_single_filter(player_games, props, fkey, edge_min, cv_max, proj_min):
    MARKET_TO_STAT = {'player_points': 'pts', 'player_rebounds': 'reb', 'player_assists': 'ast'}
    stat, direction = fkey.rsplit('_', 1)
    
    wins, losses = 0, 0
    for player, market, line, over_odds, under_odds, game_date in props:
        s = MARKET_TO_STAT.get(market)
        if s != stat:
            continue
        line = float(line)
        if line == 0:
            continue
        
        proj, cv = get_proj(player_games, player, stat, game_date)
        if proj is None:
            continue
        
        actual_games = [g for g in player_games[player] if g['date'] == game_date]
        if not actual_games:
            continue
        actual = actual_games[0][stat]
        
        if direction == 'over':
            edge = (proj - line) / line
            if edge >= edge_min and cv <= cv_max and proj >= proj_min:
                if actual > line: wins += 1
                elif actual < line: losses += 1
        else:
            edge = (line - proj) / line
            if edge >= edge_min and cv <= cv_max and proj >= proj_min:
                if actual < line: wins += 1
                elif actual > line: losses += 1
    
    total = wins + losses
    win_rate = wins / total * 100 if total > 0 else 0
    return wins, losses, total, win_rate

def optimize():
    print("=" * 70)
    print("🔧 FILTER OPTIMIZER V3 - Three Tier System for 4+ PPD")
    print("=" * 70)
    
    print("\n📊 Loading data...")
    player_games, props = load_data()
    
    dates = set(p[5] for p in props)
    num_days = len(dates)
    print(f"   ✅ {len(player_games)} players, {len(props)} props, {num_days} days")
    
    combos = ['pts_over', 'pts_under', 'reb_over', 'reb_under', 'ast_over', 'ast_under']
    
    # Aggressive search for more picks
    edge_range = [0.08, 0.10, 0.12, 0.15, 0.18, 0.20, 0.22, 0.25, 0.28, 0.30]
    cv_range = [0.30, 0.35, 0.40, 0.45, 0.50, 0.55]
    
    all_results = []
    
    for fkey in combos:
        stat = fkey.rsplit('_', 1)[0]
        if stat == 'pts':
            proj_mins = [12, 15, 18, 20]
        elif stat == 'reb':
            proj_mins = [4, 6, 8, 10]
        else:
            proj_mins = [3, 4, 5, 6]
        
        print(f"\n🔍 Testing {fkey}...")
        
        for edge in edge_range:
            for cv in cv_range:
                for proj_min in proj_mins:
                    wins, losses, total, win_rate = test_single_filter(
                        player_games, props, fkey, edge, cv, proj_min
                    )
                    if total >= 3:
                        all_results.append({
                            'fkey': fkey, 'edge_min': edge, 'cv_max': cv,
                            'proj_min': proj_min, 'wins': wins, 'losses': losses,
                            'total': total, 'win_rate': win_rate, 'ppd': total / num_days
                        })
    
    # ==========================================================================
    # TIERED FILTER SELECTION
    # ==========================================================================
    print("\n" + "=" * 70)
    print("🏆 TIER 1: 80%+ WIN RATE")
    print("=" * 70)
    
    tier1 = {}
    for fkey in combos:
        candidates = [r for r in all_results if r['fkey'] == fkey and r['win_rate'] >= 80 and r['total'] >= 5]
        if candidates:
            best = max(candidates, key=lambda x: (x['total'], x['win_rate']))
            tier1[fkey] = best
            print(f"   🔥 {fkey:12} | {best['wins']:2}-{best['losses']:2} ({best['win_rate']:.1f}%) | e>={best['edge_min']*100:.0f}% cv<={best['cv_max']} p>={best['proj_min']} | {best['ppd']:.2f} ppd")
    
    print("\n" + "=" * 70)
    print("✅ TIER 2: 70-80% WIN RATE (incremental from T1)")
    print("=" * 70)
    
    tier2 = {}
    for fkey in combos:
        # Find filters that give MORE picks than T1 while staying 70%+
        t1_filter = tier1.get(fkey)
        candidates = [r for r in all_results if r['fkey'] == fkey and 70 <= r['win_rate'] < 80 and r['total'] >= 10]
        
        # Exclude picks that would overlap with T1
        if candidates:
            best = max(candidates, key=lambda x: x['total'])
            # Only add if it's different from T1
            if not t1_filter or best['edge_min'] != t1_filter['edge_min'] or best['cv_max'] != t1_filter['cv_max']:
                tier2[fkey] = best
                print(f"   ✅ {fkey:12} | {best['wins']:2}-{best['losses']:2} ({best['win_rate']:.1f}%) | e>={best['edge_min']*100:.0f}% cv<={best['cv_max']} p>={best['proj_min']} | {best['ppd']:.2f} ppd")
    
    print("\n" + "=" * 70)
    print("📊 TIER 3: 65-70% WIN RATE (for volume)")
    print("=" * 70)
    
    tier3 = {}
    for fkey in combos:
        candidates = [r for r in all_results if r['fkey'] == fkey and 65 <= r['win_rate'] < 70 and r['total'] >= 15]
        if candidates:
            best = max(candidates, key=lambda x: x['total'])
            tier3[fkey] = best
            print(f"   📊 {fkey:12} | {best['wins']:2}-{best['losses']:2} ({best['win_rate']:.1f}%) | e>={best['edge_min']*100:.0f}% cv<={best['cv_max']} p>={best['proj_min']} | {best['ppd']:.2f} ppd")
    
    # ==========================================================================
    # SUMMARY
    # ==========================================================================
    print("\n" + "=" * 70)
    print("📊 FINAL CONFIGURATION")
    print("=" * 70)
    
    def tier_stats(t, name):
        if not t:
            return 0, 0, 0
        wins = sum(v['wins'] for v in t.values())
        losses = sum(v['losses'] for v in t.values())
        total = sum(v['total'] for v in t.values())
        rate = wins / total * 100 if total > 0 else 0
        ppd = total / num_days
        print(f"   {name}: {wins}-{losses} ({rate:.1f}%) | {total} picks | {ppd:.2f} ppd")
        return wins, losses, total
    
    t1w, t1l, t1t = tier_stats(tier1, "🏆 TIER 1")
    t2w, t2l, t2t = tier_stats(tier2, "✅ TIER 2")
    t3w, t3l, t3t = tier_stats(tier3, "📊 TIER 3")
    
    all_w = t1w + t2w + t3w
    all_l = t1l + t2l + t3l
    all_t = t1t + t2t + t3t
    all_rate = all_w / all_t * 100 if all_t > 0 else 0
    all_ppd = all_t / num_days
    roi = (all_w * 0.909 - all_l) / all_t * 100 if all_t > 0 else 0
    
    print(f"\n   📊 COMBINED: {all_w}-{all_l} ({all_rate:.1f}%) | {all_t} picks | {all_ppd:.2f} ppd")
    print(f"   💰 ROI: {roi:+.1f}%")
    
    # Output code
    print("\n" + "=" * 70)
    print("📝 CODE FOR sb_algo_api.py")
    print("=" * 70)
    
    for name, t in [("TIER1", tier1), ("TIER2", tier2), ("TIER3", tier3)]:
        if t:
            print(f"\n{name}_FILTERS = {{")
            for fkey, v in t.items():
                print(f"    '{fkey}': {{'edge_min': {v['edge_min']}, 'cv_max': {v['cv_max']}, 'proj_min': {v['proj_min']}}},  # {v['win_rate']:.1f}%")
            print("}")

if __name__ == "__main__":
    optimize()
