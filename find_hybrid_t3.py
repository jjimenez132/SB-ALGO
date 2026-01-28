#!/usr/bin/env python3
"""Find hybrid T3 at 68-70% for OVER bets to hit 4+ ppd"""

import psycopg2
import statistics
from collections import defaultdict

DATABASE_URL = 'postgresql://sb_algo_db_user:0HDtYp4EY2Lo5At8iyf44PD1zDioSPK7@dpg-d495uhchg0os738l1a50-a.virginia-postgres.render.com/sb_algo_db'

conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()

cur.execute("SELECT player_name, game_date, pts, reb, ast, min FROM player_boxscores WHERE game_date >= '2025-10-01' ORDER BY player_name, game_date")
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
        player_games[player].append({'date': gdate, 'pts': float(pts or 0), 'reb': float(reb or 0), 'ast': float(ast or 0)})

cur.execute("SELECT player_name, market, line, game_date FROM player_props WHERE game_date >= '2025-12-01' AND game_date <= '2026-01-25' AND sportsbook = 'DraftKings' AND market IN ('player_points', 'player_rebounds', 'player_assists') ORDER BY game_date")
props = cur.fetchall()
conn.close()

num_days = len(set(p[3] for p in props))
print(f'Data: {len(player_games)} players, {len(props)} props, {num_days} days')

def get_proj(player, stat, game_date):
    if player not in player_games: return None, None
    games_list = sorted([g for g in player_games[player] if g['date'] < game_date], key=lambda x: x['date'], reverse=True)
    if len(games_list) < 5: return None, None
    values = [g[stat] for g in games_list[:15]]
    if len(values) < 5: return None, None
    l5 = sum(values[:5])/5
    l10 = sum(values[:min(10,len(values))])/min(10,len(values))
    l15 = sum(values[:min(15,len(values))])/min(15,len(values))
    proj = 0.40*l5 + 0.30*l10 + 0.20*l15 + 0.10*(sum(values)/len(values))
    cv = statistics.stdev(values[:min(10,len(values))]) / proj if proj > 0 else 1
    return proj, cv

def test(fkey, edge_min, cv_max, proj_min):
    MARKET = {'player_points': 'pts', 'player_rebounds': 'reb', 'player_assists': 'ast'}
    stat, direction = fkey.rsplit('_', 1)
    wins, losses = 0, 0
    for player, market, line, game_date in props:
        s = MARKET.get(market)
        if s != stat: continue
        line = float(line)
        if line == 0: continue
        proj, cv = get_proj(player, stat, game_date)
        if proj is None: continue
        actual_games = [g for g in player_games[player] if g['date'] == game_date]
        if not actual_games: continue
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
    return wins, losses, total, wins/total*100 if total > 0 else 0

# T1+T2 = 2.45 ppd, need ~1.5-2 more from T3 to hit 4+ ppd
print('\n' + '='*60)
print('FINDING HYBRID T3 (68-70%) FOR 4+ PPD TOTAL')
print('='*60)

# Current T1+T2 contribution
print(f'\nCurrent T1+T2: ~2.45 ppd')
print(f'Target T3: ~1.5-2.0 ppd at 68-70%')
print(f'Target Total: 4.0+ ppd\n')

hybrid_t3 = {}

for fkey in ['pts_over', 'pts_under', 'reb_over', 'reb_under', 'ast_over', 'ast_under']:
    stat = fkey.rsplit('_', 1)[0]
    if stat == 'pts': proj_mins = [12, 15, 18, 20]
    elif stat == 'reb': proj_mins = [5, 6, 8, 10]
    else: proj_mins = [3, 4, 5, 6]
    
    best = None
    # Search for 68%+ with maximum volume
    for edge in [0.10, 0.12, 0.15, 0.18, 0.20, 0.22, 0.25]:
        for cv in [0.35, 0.40, 0.45, 0.50]:
            for proj_min in proj_mins:
                w, l, t, r = test(fkey, edge, cv, proj_min)
                if t >= 10 and r >= 68:
                    if best is None or t > best['total']:
                        best = {'fkey': fkey, 'edge': edge, 'cv': cv, 'proj': proj_min, 'wins': w, 'losses': l, 'total': t, 'rate': r, 'ppd': t/num_days}
    
    if best:
        hybrid_t3[fkey] = best
        emoji = '🔥' if best['rate'] >= 70 else '✅'
        print(f"  {emoji} {fkey:12} | {best['wins']:2}-{best['losses']:2} ({best['rate']:.1f}%) | e>={best['edge']*100:.0f}% cv<={best['cv']} p>={best['proj']} | {best['ppd']:.2f} ppd")
    else:
        # Show best available even if under 68%
        for edge in [0.15, 0.18, 0.20, 0.25]:
            for cv in [0.40, 0.45, 0.50]:
                for proj_min in proj_mins:
                    w, l, t, r = test(fkey, edge, cv, proj_min)
                    if t >= 15:
                        if best is None or r > best.get('rate', 0):
                            best = {'fkey': fkey, 'edge': edge, 'cv': cv, 'proj': proj_min, 'wins': w, 'losses': l, 'total': t, 'rate': r, 'ppd': t/num_days}
        if best:
            print(f"  ⚠️ {fkey:12} | {best['wins']:2}-{best['losses']:2} ({best['rate']:.1f}%) | BEST (under 68%) | {best['ppd']:.2f} ppd")

# Summary
print('\n' + '='*60)
print('HYBRID T3 SUMMARY (68%+)')
print('='*60)

t3_wins = sum(v['wins'] for v in hybrid_t3.values())
t3_losses = sum(v['losses'] for v in hybrid_t3.values())
t3_total = sum(v['total'] for v in hybrid_t3.values())
t3_rate = t3_wins / t3_total * 100 if t3_total > 0 else 0
t3_ppd = t3_total / num_days

print(f'\n  T3 Hybrid: {t3_wins}-{t3_losses} ({t3_rate:.1f}%) | {t3_total} picks | {t3_ppd:.2f} ppd')
print(f'\n  T1+T2: 96-31 (75.6%) | 2.45 ppd')
print(f'  T3 Hybrid: {t3_wins}-{t3_losses} ({t3_rate:.1f}%) | {t3_ppd:.2f} ppd')
print(f'\n  TOTAL: {96+t3_wins}-{31+t3_losses} ({(96+t3_wins)/(127+t3_total)*100:.1f}%) | {2.45+t3_ppd:.2f} ppd')
