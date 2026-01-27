"""
REAL Explanation Engine v2 - Comprehensive Analysis
Uses ALL available data to generate expert-level explanations
"""
import psycopg2
from datetime import datetime
from collections import defaultdict

DATABASE_URL = 'postgresql://sb_algo_db_user:0HDtYp4EY2Lo5At8iyf44PD1zDioSPK7@dpg-d495uhchg0os738l1a50-a.virginia-postgres.render.com/sb_algo_db'

ABBR_TO_FULL = {
    'ATL': 'Atlanta Hawks', 'BOS': 'Boston Celtics', 'BKN': 'Brooklyn Nets', 'CHA': 'Charlotte Hornets',
    'CHI': 'Chicago Bulls', 'CLE': 'Cleveland Cavaliers', 'DAL': 'Dallas Mavericks', 'DEN': 'Denver Nuggets',
    'DET': 'Detroit Pistons', 'GSW': 'Golden State Warriors', 'HOU': 'Houston Rockets', 'IND': 'Indiana Pacers',
    'LAC': 'LA Clippers', 'LAL': 'Los Angeles Lakers', 'MEM': 'Memphis Grizzlies', 'MIA': 'Miami Heat',
    'MIL': 'Milwaukee Bucks', 'MIN': 'Minnesota Timberwolves', 'NOP': 'New Orleans Pelicans', 'NYK': 'New York Knicks',
    'OKC': 'Oklahoma City Thunder', 'ORL': 'Orlando Magic', 'PHI': 'Philadelphia 76ers', 'PHX': 'Phoenix Suns',
    'POR': 'Portland Trail Blazers', 'SAC': 'Sacramento Kings', 'SAS': 'San Antonio Spurs', 'TOR': 'Toronto Raptors',
    'UTA': 'Utah Jazz', 'WAS': 'Washington Wizards'
}

def parse_min(m):
    if not m: return 0
    if ':' in str(m): return float(str(m).split(':')[0])
    try: return float(m)
    except: return 0

def get_player_explanation(player, stat, line, direction, projection, cv=None):
    """Generate COMPREHENSIVE explanation like a real analyst"""
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        
        # 1. Player game logs with minutes
        cur.execute("""
            SELECT game_date, pts, reb, ast, fg3m, min, team_abbreviation
            FROM player_boxscores 
            WHERE player_name = %s AND game_date >= '2025-10-01'
            ORDER BY game_date DESC
        """, (player,))
        raw_games = cur.fetchall()
        
        if not raw_games:
            conn.close()
            return f"• Projection: {projection:.1f} vs Line: {line}"
        
        # Filter 20+ min games
        games = [(g[0], float(g[1] or 0), float(g[2] or 0), float(g[3] or 0), float(g[4] or 0), parse_min(g[5]), g[6]) 
                 for g in raw_games if parse_min(g[5]) >= 20]
        
        if len(games) < 5:
            conn.close()
            return f"• Projection: {projection:.1f} vs Line: {line}"
        
        team_abbr = games[0][6]
        
        # 2. Today's game context
        today = datetime.now().strftime('%Y-%m-%d')
        cur.execute("""SELECT home_team, visitor_team, home_spread, closing_total 
                       FROM games_with_odds WHERE date = %s""", (today,))
        today_games = cur.fetchall()
        
        opp_abbr = None
        spread = None
        game_total = None
        is_home = False
        for home, away, sp, tot in today_games:
            if team_abbr == home:
                opp_abbr, is_home = away, True
                spread = float(sp) if sp else None
            elif team_abbr == away:
                opp_abbr = home
                spread = -float(sp) if sp else None
            if opp_abbr:
                game_total = float(tot) if tot else None
                break
        
        opp_full = ABBR_TO_FULL.get(opp_abbr) if opp_abbr else None
        
        # 3. Historical games with spreads (to analyze blowout patterns)
        cur.execute("""
            SELECT date, home_team, visitor_team, home_spread, closing_total, home_pts, visitor_pts
            FROM games_with_odds 
            WHERE (home_team = %s OR visitor_team = %s) AND date >= '2025-10-01'
            ORDER BY date DESC
        """, (team_abbr, team_abbr))
        team_games = cur.fetchall()
        
        # 4. Opponent defense ranking
        opp_def_rank = None
        opp_def_rating = None
        if opp_full:
            cur.execute("""SELECT "TEAM_NAME", "DEF_RATING" FROM nba_team_advanced_stats ORDER BY pull_date DESC""")
            seen = {}
            for t, d in cur.fetchall():
                if t not in seen and d: seen[t] = float(d)
            ranked = sorted(seen.items(), key=lambda x: x[1])
            for i, (t, d) in enumerate(ranked):
                if t == opp_full:
                    opp_def_rating, opp_def_rank = d, i + 1
                    break
        
        # 5. Opponent pace
        opp_pace = None
        if opp_full:
            cur.execute("""SELECT "TEAM_NAME", "PACE" FROM nba_team_advanced_stats ORDER BY pull_date DESC""")
            for t, p in cur.fetchall():
                if t == opp_full and p:
                    opp_pace = float(p)
                    break
        
        conn.close()
        
        # === ANALYSIS ===
        stat_idx = {'pts': 1, 'reb': 2, 'ast': 3, '3pm': 4}.get(stat.lower(), 1)
        values = [g[stat_idx] for g in games]
        
        avg = sum(values) / len(values)
        sorted_vals = sorted(values)
        median = sorted_vals[len(sorted_vals)//2]
        l5 = values[:5]
        l5_avg = sum(l5) / 5
        l10 = values[:10]
        l10_avg = sum(l10) / len(l10)
        
        # Hit rates
        over_count = sum(1 for v in values if v > line)
        under_count = sum(1 for v in values if v < line)
        push_count = len(values) - over_count - under_count
        total_games = len(values)
        
        l5_over = sum(1 for v in l5 if v > line)
        l5_under = sum(1 for v in l5 if v < line)
        l10_over = sum(1 for v in l10 if v > line)
        l10_under = sum(1 for v in l10 if v < line)
        
        # Outliers analysis
        if stat.lower() == 'pts':
            high_outliers = [v for v in values if v >= 35]
            low_outliers = [v for v in values if v <= 10]
        else:
            threshold_high = avg + 2 * (sum((v-avg)**2 for v in values)/len(values))**0.5
            high_outliers = [v for v in values if v >= threshold_high]
            low_outliers = []
        
        # Blowout analysis - games where team was favored by 7+
        blowout_games_stats = []
        for tg in team_games:
            gdate, home, away, sp, tot, h_pts, a_pts = tg
            if not sp: continue
            sp = float(sp)
            team_favored_by = -sp if team_abbr == home else sp
            if team_favored_by <= -7:  # Favored by 7+
                # Find matching player game
                for g in games:
                    if str(g[0]) == str(gdate):
                        blowout_games_stats.append(g[stat_idx])
                        break
        
        # === BUILD EXPLANATION ===
        lines = []
        
        if direction == "UNDER":
            hit_pct = under_count / total_games * 100
            
            # Distribution analysis
            lines.append(f"• Season avg: {avg:.1f} | Median: {median:.1f} (cleared {line} in {over_count}/{total_games} games, {100-hit_pct:.0f}%)")
            
            # Mean vs Median insight
            if high_outliers and avg > median + 1:
                lines.append(f"• {len(high_outliers)} blowup games ({', '.join(str(int(v)) for v in high_outliers[:3])}+) inflate mean - median tells the real story")
            
            # Recent trend
            if l5_under >= 3:
                streak = l5_under
                lines.append(f"• Recent trend: {streak}/5 unders in last 5 games (L5 avg: {l5_avg:.1f})")
            elif l10_under >= 6:
                lines.append(f"• Trend: {l10_under}/10 unders in last 10 (L10 avg: {l10_avg:.1f})")
            
            # Blowout context
            if blowout_games_stats and len(blowout_games_stats) >= 3:
                blowout_avg = sum(blowout_games_stats) / len(blowout_games_stats)
                blowout_unders = sum(1 for v in blowout_games_stats if v < line)
                if blowout_avg < avg:
                    lines.append(f"• In blowouts (favored 7+): avg {blowout_avg:.1f}, {blowout_unders}/{len(blowout_games_stats)} unders - usage compresses")
            
            # Today's spread context
            if spread and spread <= -7:
                lines.append(f"• Today: {team_abbr} favored by {abs(spread):.1f} - blowout risk caps late-game usage")
            
            # Opponent/pace context
            if opp_def_rank and opp_def_rank <= 10:
                lines.append(f"• vs {opp_abbr}: #{opp_def_rank} defense - tough matchup limits ceiling")
            
            if game_total and game_total < 225:
                lines.append(f"• Game total {game_total:.1f} (slow pace) - fewer possessions")
            elif opp_pace and opp_pace < 98:
                lines.append(f"• {opp_abbr} plays slow ({opp_pace:.1f} pace) - limits volume")
            
            # Bottom line
            if projection < line:
                fair_line = projection
                lines.append(f"• Model fair line: {fair_line:.1f} - current {line} offers {((line-fair_line)/line*100):.0f}% edge on under")
                
        else:  # OVER
            hit_pct = over_count / total_games * 100
            
            lines.append(f"• Season avg: {avg:.1f} | Median: {median:.1f} (cleared {line} in {over_count}/{total_games} games, {hit_pct:.0f}%)")
            
            if l5_over >= 3:
                lines.append(f"• Hot streak: {l5_over}/5 overs in last 5 (L5 avg: {l5_avg:.1f})")
            elif l10_over >= 6:
                lines.append(f"• Trend: {l10_over}/10 overs in last 10 (L10 avg: {l10_avg:.1f})")
            
            if opp_def_rank and opp_def_rank >= 20:
                lines.append(f"• vs {opp_abbr}: #{opp_def_rank} defense (bottom 10) - plus matchup")
            
            if game_total and game_total > 228:
                lines.append(f"• Game total {game_total:.1f} (shootout) - more possessions")
            elif opp_pace and opp_pace > 102:
                lines.append(f"• {opp_abbr} plays fast ({opp_pace:.1f} pace) - volume boost")
            
            if projection > line:
                fair_line = projection
                lines.append(f"• Model fair line: {fair_line:.1f} - current {line} offers {((fair_line-line)/line*100):.0f}% edge on over")
        
        return "\n".join(lines) if lines else f"• Projection: {projection:.1f} vs Line: {line}"
        
    except Exception as e:
        return f"• Projection: {projection:.1f} vs Line: {line} (Error: {str(e)[:50]})"

if __name__ == "__main__":
    print("=== BRUNSON PTS UNDER 28.5 ===")
    exp = get_player_explanation("Jalen Brunson", "pts", 28.5, "UNDER", 26.4, 0.33)
    print(exp)
    print()
    print("=== MARKKANEN PTS OVER 23.5 ===") 
    exp = get_player_explanation("Lauri Markkanen", "pts", 23.5, "OVER", 28.0, 0.16)
    print(exp)
