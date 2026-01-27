"""
REAL Explanation Engine - Uses ALL available data
"""
import psycopg2
from datetime import datetime

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

def get_player_explanation(player, stat, line, direction, projection, cv=None):
    """Generate COMPREHENSIVE explanation using ALL data"""
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        
        cur.execute("""
            SELECT game_date, pts, reb, ast, fg3m, min, team_abbreviation
            FROM player_boxscores 
            WHERE player_name = %s AND game_date >= '2025-10-01'
            ORDER BY game_date DESC
        """, (player,))
        games = cur.fetchall()
        
        if not games:
            conn.close()
            return f"• Projection: {projection:.1f} vs Line: {line}"
        
        team_abbr = games[0][6]
        
        today = datetime.now().strftime('%Y-%m-%d')
        cur.execute("""SELECT home_team, visitor_team, home_spread, closing_total FROM games_with_odds WHERE date = %s""", (today,))
        today_games = cur.fetchall()
        
        opp_abbr = None
        spread = None
        game_total = None
        is_home = False
        for home, away, sp, tot in today_games:
            if team_abbr == home:
                opp_abbr = away
                is_home = True
                spread = float(sp) if sp else None
            elif team_abbr == away:
                opp_abbr = home
                spread = -float(sp) if sp else None  # Flip for away team
            if opp_abbr:
                game_total = float(tot) if tot else None
                break
        
        opp_full = ABBR_TO_FULL.get(opp_abbr, opp_abbr) if opp_abbr else None
        
        opp_def_rating = None
        opp_def_rank = None
        if opp_full:
            cur.execute("""SELECT "TEAM_NAME", "DEF_RATING" FROM nba_team_advanced_stats ORDER BY pull_date DESC""")
            seen = {}
            for t, d in cur.fetchall():
                if t not in seen and d:
                    seen[t] = float(d)
            ranked = sorted(seen.items(), key=lambda x: x[1])
            for i, (t, d) in enumerate(ranked):
                if t == opp_full:
                    opp_def_rating = d
                    opp_def_rank = i + 1
                    break
        
        conn.close()
        
        stat_idx = {'pts': 1, 'reb': 2, 'ast': 3, '3pm': 4}.get(stat.lower(), 1)
        values = [float(g[stat_idx]) for g in games if g[stat_idx] is not None]
        
        avg = sum(values) / len(values)
        median = sorted(values)[len(values)//2]
        l5 = values[:5]
        l5_avg = sum(l5) / 5
        
        over_count = sum(1 for v in values if v > line)
        under_count = sum(1 for v in values if v < line)
        l5_under = sum(1 for v in l5 if v < line)
        l5_over = sum(1 for v in l5 if v > line)
        
        outliers = [v for v in values if v >= 35] if stat.lower() == 'pts' else []
        
        lines = []
        
        if direction == "UNDER":
            hit_pct = under_count / len(values) * 100
            
            lines.append(f"• Season: {under_count}/{len(values)} unders ({hit_pct:.0f}%) at {line}")
            lines.append(f"• Avg: {avg:.1f} | Median: {median:.1f} | L5: {l5_avg:.1f}")
            
            if l5_under >= 3:
                lines.append(f"• Trend: {l5_under}/5 recent unders")
            
            if outliers:
                lines.append(f"• {len(outliers)} blowup games (35+) inflate mean")
            
            # For UNDER - only mention defense if it's GOOD (helps under)
            if opp_abbr and opp_def_rank and opp_def_rank <= 10:
                lines.append(f"• vs {opp_abbr}: #{opp_def_rank} defense (tough matchup)")
            
            # Blowout = good for under (less minutes)
            if spread and spread < -6:
                lines.append(f"• Blowout risk ({team_abbr} -{abs(spread):.1f}) - early benching likely")
                
        else:  # OVER
            hit_pct = over_count / len(values) * 100
            
            lines.append(f"• Season: {over_count}/{len(values)} overs ({hit_pct:.0f}%) at {line}")
            lines.append(f"• Avg: {avg:.1f} | Median: {median:.1f} | L5: {l5_avg:.1f}")
            
            if l5_over >= 3:
                lines.append(f"• Trend: {l5_over}/5 recent overs")
            
            # For OVER - mention weak defense (helps over)
            if opp_abbr and opp_def_rank and opp_def_rank >= 20:
                lines.append(f"• vs {opp_abbr}: #{opp_def_rank} defense (weak)")
            
            if game_total and game_total > 228:
                lines.append(f"• High total (O/U {game_total:.1f}) = more possessions")
        
        return "\n".join(lines)
        
    except Exception as e:
        return f"• Projection: {projection:.1f} vs Line: {line}"

if __name__ == "__main__":
    exp = get_player_explanation("Jalen Brunson", "pts", 28.5, "UNDER", 23.3, 0.33)
    print(exp)
