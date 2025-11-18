"""
DAILY PICKS GENERATOR
"""

from nba_math_engine import NBAMathEngine
from datetime import datetime, timedelta
import psycopg2
import random

DATABASE_URL = 'postgresql://sb_algo_db_user:0HDtYp4EY2Lo5At8iyf44PD1zDioSPK7@dpg-d495uhchg0os738l1a50-a.virginia-postgres.render.com/sb_algo_db?sslmode=require'


class DailyPicksGenerator:
    def __init__(self):
        self.engine = NBAMathEngine()
        self.conn = psycopg2.connect(DATABASE_URL)
        self.cur = self.conn.cursor()
        self.key_players = [
            'LeBron James', 'Stephen Curry', 'Kevin Durant', 'Giannis Antetokounmpo',
            'Luka Doncic', 'Jayson Tatum', 'Joel Embiid', 'Nikola Jokic',
            'Damian Lillard', 'Anthony Davis', 'Kawhi Leonard', 'Paul George',
            'Devin Booker', 'Donovan Mitchell', 'Trae Young', 'Ja Morant',
            'Jimmy Butler', 'Bam Adebayo', 'Jaylen Brown', 'Anthony Edwards',
            'Shai Gilgeous-Alexander', 'Tyrese Haliburton', 'De\'Aaron Fox',
            'Lauri Markkanen', 'Paolo Banchero', 'Franz Wagner', 'Scottie Barnes',
            'LaMelo Ball', 'Cade Cunningham', 'Alperen Sengun', 'Victor Wembanyama'
        ]
    
    def get_todays_games(self):
        today = datetime.now().strftime('%Y-%m-%d')
        self.cur.execute("SELECT date, visitor_team, home_team FROM games WHERE date = %s ORDER BY date", (today,))
        return self.cur.fetchall()
    
    def get_active_players_in_game(self, team1, team2):
        self.cur.execute("SELECT DISTINCT player_name FROM player_boxscores WHERE (team_id LIKE %s OR team_id LIKE %s) AND game_date >= %s AND pts > 5 ORDER BY game_date DESC", (f'%{team1}%', f'%{team2}%', (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')))
        players = self.cur.fetchall()
        active_players = []
        for p in players:
            if p[0] in self.key_players:
                active_players.append(p[0])
        return active_players[:10]
    
    def generate_simulated_lines(self, projection):
        variance = random.uniform(-2, 2)
        line = projection + variance
        line = round(line * 2) / 2
        return {'pts': line}
    
    def analyze_all_games(self):
        games = self.get_todays_games()
        if not games:
            return []
        all_picks = []
        print(f"\n{'='*70}")
        print(f"🏀 ANALYZING {len(games)} GAMES FOR TODAY")
        print(f"{'='*70}\n")
        for game in games:
            date, visitor, home = game
            print(f"Analyzing: {visitor} @ {home}")
            players = self.get_active_players_in_game(visitor, home)
            for player in players[:5]:
                self.cur.execute("SELECT team_id FROM player_boxscores WHERE player_name = %s ORDER BY game_date DESC LIMIT 1", (player,))
                result = self.cur.fetchone()
                if not result:
                    continue
                player_team = result[0]
                is_home = home in player_team
                opponent = visitor if is_home else home
                proj = self.engine.generate_projection(player, opponent, 'pts', is_home=is_home)
                if not proj:
                    continue
                lines = self.generate_simulated_lines(proj['projection'])
                pick = self.engine.evaluate_line(proj, lines['pts'], odds=-110)
                if pick and pick['ev_percent'] >= 8:
                    pick['player'] = player
                    pick['game'] = f"{visitor} @ {home}"
                    pick['is_home'] = is_home
                    pick['stat'] = 'PTS'
                    pick['projection_data'] = proj
                    all_picks.append(pick)
        return all_picks
    
    def rank_picks(self, picks):
        for pick in picks:
            score = pick['ev_percent'] * 0.5 + pick['confidence'] * 0.3 + pick['edge'] * 5 * 0.2
            pick['score'] = score
        return sorted(picks, key=lambda x: x['score'], reverse=True)
    
    def format_pick_for_discord(self, pick, rank):
        proj_data = pick['projection_data']
        output = f"""
{'='*70}
🔥 PICK #{rank}: {pick['player']} {pick['pick']} {pick['line']} {pick['stat']} (-110)
{'='*70}

📊 EDGE: +{pick['edge']} | CONFIDENCE: {pick['confidence']}% | EV: +{pick['ev_percent']}%

🎯 WHY THIS WORKS:

✅ PROJECTION: {pick['projection']} points
   • L5: {proj_data['l5_avg']} pts
   • L10: {proj_data['l10_avg']} pts
   • L20: {proj_data['l20_avg']} pts

✅ CONSISTENCY: {100 - proj_data['variance_pct']:.0f}% reliable
   • StdDev: {proj_data['stdev']}

✅ MATCHUP: {proj_data['matchup_avg']} pts avg ({proj_data['matchup_games']} games)

✅ LOCATION: {'HOME' if pick['is_home'] else 'AWAY'}

✅ TREND: {proj_data['trend'].upper()}

📈 STATS:
   • Win Prob: {pick['win_probability']}%
   • EV: ${pick['ev_dollars']} per $100
   • Kelly: {pick['kelly_size']}%

🎮 RECENT: {', '.join([str(int(x)) for x in proj_data['recent_games']])} pts

💡 REASONS:
"""
        for i, reason in enumerate(pick['reasoning'], 1):
            output += f"   {i}. {reason}\n"
        output += f"\n{'='*70}\n"
        return output
    
    def generate_daily_report(self):
        print("\n🚀 GENERATING DAILY PICKS...\n")
        all_picks = self.analyze_all_games()
        if not all_picks:
            return "❌ No picks generated."
        ranked_picks = self.rank_picks(all_picks)
        top_5 = ranked_picks[:5]
        report = f"""
{'#'*70}
🏀 NBA BETTING ALGORITHM - DAILY PICKS
📅 {datetime.now().strftime('%A, %B %d, %Y')}
🎯 TOP 5 PLAYS
{'#'*70}

📊 ANALYZED: {len(all_picks)} opportunities
🔥 SELECTED: Top 5 highest EV
⏰ {datetime.now().strftime('%I:%M %p EST')}

"""
        for i, pick in enumerate(top_5, 1):
            report += self.format_pick_for_discord(pick, i)
        report += f"\n{'#'*70}\n"
        return report
    
    def close(self):
        self.cur.close()
        self.conn.close()
        self.engine.close()


if __name__ == '__main__':
    generator = DailyPicksGenerator()
    report = generator.generate_daily_report()
    print(report)
    filename = f"picks_{datetime.now().strftime('%Y%m%d')}.txt"
    with open(filename, 'w') as f:
        f.write(report)
    print(f"\n✅ Saved: {filename}")
    generator.close()
