#!/usr/bin/env python3
"""
Find T3 filters that hit 70%+ win rate for maximum volume
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

def find_70_plus_t3():
    print("=" * 70)
    print("🔍 FINDING T3 FILTERS AT 70%+ WIN RATE")
    print("=" * 70)
    
    print("\n📊 Loading data...")
    player_games, props = load_data()
    
    dates = set(p[5] for p in props)
    num_days = len(dates)
    print(f"   ✅ {len(player_games)} players, {len(props)} props, {num_days} days")
    
    combos = ['pts_over', 'pts_under', 'reb_over', 'reb_under', 'ast_over', 'ast_under']
    
    # Search for 70%+ filters with maximum volume
    edge_range = [0.10, 0.12, 0.15, 0.18, 0.20, 0.22, 0.25]
    cv_range = [0.35, 0.40, 0.45, 0.50]
    
    t3_filters = {}
    
    for fkey in combos:
        stat = fkey.rsplit('_', 1)[0]
        if stat == 'pts':
            proj_mins = [15, 18, 20]
        elif stat == 'reb':
            proj_mins = [5, 6, 8]
        else:
            proj_mins = [4, 5, 6]
        
        print(f"\n🔍 Testing {fkey}...")
        best = None
        
        for edge in edge_range:
            for cv in cv_range:
                for proj_min in proj_mins:
                    wins, losses, total, win_rate = test_single_filter(
                        player_games, props, fkey, edge, cv, proj_min
                    )
                    # Want 70%+ with at least 15 picks for volume
                    if total >= 15 and win_rate >= 70:
                        if best is None or total > best['total']:
                            best = {
                                'fkey': fkey, 'edge_min': edge, 'cv_max': cv,
                                'proj_min': proj_min, 'wins': wins, 'losses': losses,
                                'total': total, 'win_rate': win_rate, 'ppd': total / num_days
                            }
        
        if best:
            t3_filters[fkey] = best
            print(f"   🔥 {fkey:12} | {best['wins']:3}-{best['losses']:3} ({best['win_rate']:.1f}%) | e>={best['edge_min']*100:.0f}% cv<={best['cv_max']} p>={best['proj_min']} | {best['ppd']:.2f} ppd")
        else:
            # Find best even if under 70%
            for edge in edge_range:
                for cv in cv_range:
                    for proj_min in proj_mins:
                        wins, losses, total, win_rate = test_single_filter(
                            player_games, props, fkey, edge, cv, proj_min
                        )
                        if total >= 20:
                            if best is None or win_rate > best['win_rate']:
                                best = {
                                    'fkey': fkey, 'edge_min': edge, 'cv_max': cv,
                                    'proj_min': proj_min, 'wins': wins, 'losses': losses,
                                    'total': total, 'win_rate': win_rate, 'ppd': total / num_days
                                }
            if best:
                print(f"   ⚠️ {fkey:12} | {best['wins']:3}-{best['losses']:3} ({best['win_rate']:.1f}%) | BEST FOUND (under 70%)")
    
    # Summary
    print("\n" + "=" * 70)
    print("📊 T3 FILTERS AT 70%+")
    print("=" * 70)
    
    total_wins = sum(v['wins'] for v in t3_filters.values())
    total_losses = sum(v['losses'] for v in t3_filters.values())
    total_picks = sum(v['total'] for v in t3_filters.values())
    total_rate = total_wins / total_picks * 100 if total_picks > 0 else 0
    
    print(f"\n   📊 T3 (70%+): {total_wins}-{total_losses} ({total_rate:.1f}%) | {total_picks} picks | {total_picks/num_days:.2f} ppd")
    
    # Output code
    print("\n" + "=" * 70)
    print("📝 T3 FILTER CODE (70%+ only)")
    print("=" * 70)
    
    print("\nTIER3_FILTERS = {")
    for fkey, v in t3_filters.items():
        print(f"    '{fkey}': {{'edge_min': {v['edge_min']}, 'cv_max': {v['cv_max']}, 'proj_min': {v['proj_min']}}},  # {v['win_rate']:.1f}%")
    print("}")
    
    return t3_filters, num_days

if __name__ == "__main__":
    find_70_plus_t3()
