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
        self.key_players = ['LeBron James', 'Stephen Curry', 'Kevin Durant', 'Giannis Antetokounmpo', 'Luka Doncic', 'Jayson Tatum', 'Joel Embiid', 'Nikola Jokic', 'Damian Lillard', 'Anthony Davis', 'Kawhi Leonard', 'Paul George', 'Devin Booker', 'Donovan Mitchell', 'Trae Young', 'Ja Morant', 'Jimmy Butler', 'Bam Adebayo', 'Jaylen Brown', 'Anthony Edwards', 'Shai Gilgeous-Alexander', 'Tyrese Haliburton', 'De\'Aaron Fox', 'Lauri Markkanen', 'Paolo Banchero', 'Franz Wagner', 'Scottie Barnes', 'LaMelo Ball', 'Cade Cunningham', 'Alperen Sengun', 'Victor Wembanyama']
    
    def get_todays_games(self):
        today = datetime.now().strftime('%Y-%m-%d')
        self.cur.execute("SELECT date, visitor_team, home_team FROM games WHERE date = %s", (today,))
        return self.cur.fetchall()
    
    def get_active_players_in_game(self, team1, team2):
        cutoff = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
        self.cur.execute("SELECT DISTINCT player_name FROM player_boxscores WHERE (team_id::text LIKE %s OR team_id::text LIKE %s) AND game_date >= %s AND pts > 5", (f'%{team1}%', f'%{team2}%', cutoff))
        players = [p[0] for p in self.cur.fetchall() if p[0] in self.key_players]
        return players[:10]
    
    def analyze_all_games(self):
        games = self.get_todays_games()
        if not games:
            return []
        all_picks = []
        print(f"\n{'='*70}\n🏀 ANALYZING {len(games)} GAMES\n{'='*70}\n")
        for date, visitor, home in games:
            print(f"Analyzing: {visitor} @ {home}")
            for player in self.get_active_players_in_game(visitor, home)[:5]:
                self.cur.execute("SELECT team_id FROM player_boxscores WHERE player_name = %s ORDER BY game_date DESC LIMIT 1", (player,))
                result = self.cur.fetchone()
                if not result:
                    continue
                is_home = home in result[0]
                opponent = visitor if is_home else home
                proj = self.engine.generate_projection(player, opponent, 'pts', is_home)
                if not proj:
                    continue
                line = round((proj['projection'] + random.uniform(-2, 2)) * 2) / 2
                pick = self.engine.evaluate_line(proj, line, -110)
                if pick and pick['ev_percent'] >= 8:
                    pick.update({'player': player, 'game': f"{visitor} @ {home}", 'is_home': is_home, 'stat': 'PTS', 'projection_data': proj})
                    all_picks.append(pick)
        return all_picks
    
    def generate_daily_report(self):
        print("\n🚀 GENERATING PICKS...\n")
        picks = self.analyze_all_games()
        if not picks:
            return "❌ No picks generated."
        for p in picks:
            p['score'] = p['ev_percent'] * 0.5 + p['confidence'] * 0.3 + p['edge'] * 2.5
        top5 = sorted(picks, key=lambda x: x['score'], reverse=True)[:5]
        report = f"\n{'#'*70}\n🏀 DAILY PICKS - {datetime.now().strftime('%A, %B %d, %Y')}\n{'#'*70}\n\n"
        for i, p in enumerate(top5, 1):
            pd = p['projection_data']
            report += f"{'='*70}\n🔥 PICK #{i}: {p['player']} {p['pick']} {p['line']} PTS\n{'='*70}\n"
            report += f"📊 EDGE: +{p['edge']} | CONFIDENCE: {p['confidence']}% | EV: +{p['ev_percent']}%\n"
            report += f"✅ PROJECTION: {p['projection']} pts (L5: {pd['l5_avg']}, L10: {pd['l10_avg']})\n"
            report += f"✅ TREND: {pd['trend'].upper()} | LOCATION: {'HOME' if p['is_home'] else 'AWAY'}\n"
            report += f"✅ RECENT: {[int(x) for x in pd['recent_games']]}\n{'='*70}\n\n"
        return report
    
    def close(self):
        self.cur.close()
        self.conn.close()
        self.engine.close()

if __name__ == '__main__':
    gen = DailyPicksGenerator()
    report = gen.generate_daily_report()
    print(report)
    with open(f"picks_{datetime.now().strftime('%Y%m%d')}.txt", 'w') as f:
        f.write(report)
    print("✅ Saved")
    gen.close()
