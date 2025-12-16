"""
NBA BETTING ALGORITHM - COMPLETE MATH ENGINE
"""

import psycopg2
from datetime import datetime, timedelta
import statistics
import math
import random

DATABASE_URL = 'postgresql://sb_algo_db_user:0HDtYp4EY2Lo5At8iyf44PD1zDioSPK7@dpg-d495uhchg0os738l1a50-a.virginia-postgres.render.com/sb_algo_db?sslmode=require'


class NBAMathEngine:
    def __init__(self):
        self.conn = psycopg2.connect(DATABASE_URL)
        self.cur = self.conn.cursor()
        self.NBA_AVG_PACE = 100.0
        self.ALLOWED_STATS = {
            'pts': 'pts',
            'points': 'pts',
            'player_points': 'pts',
            'reb': 'reb',
            'rebounds': 'reb',
            'player_rebounds': 'reb',
            'ast': 'ast',
            'assists': 'ast',
            'player_assists': 'ast',
            'fg3m': 'fg3m',
            'threes': 'fg3m',
            'player_threes': 'fg3m',
            'stl': 'stl',
            'steals': 'stl',
            'blk': 'blk',
            'blocks': 'blk',
            'pra': 'pra',
            'points_rebounds_assists': 'pra'
        }
    
    def get_rolling_average(self, player_name, stat='pts', games=10, days_back=None):
        query = f"SELECT {stat}, game_date FROM player_boxscores WHERE player_name = %s AND {stat} IS NOT NULL"
        params = [player_name]
        if days_back:
            cutoff_date = (datetime.now() - timedelta(days=days_back)).strftime('%Y-%m-%d')
            query += " AND game_date >= %s"
            params.append(cutoff_date)
        query += f" ORDER BY game_date DESC LIMIT %s"
        params.append(games)
        self.cur.execute(query, params)
        results = self.cur.fetchall()
        if not results:
            return None
        values = [float(r[0]) for r in results if r[0] is not None and r[0] > 0]
        if not values:
            return None
        return {
            'average': statistics.mean(values),
            'median': statistics.median(values),
            'stdev': statistics.stdev(values) if len(values) > 1 else 0,
            'min': min(values),
            'max': max(values),
            'games_played': len(values),
            'recent_5': values[:5],
            'trend': self._calculate_trend(values)
        }
    
    def _calculate_trend(self, values):
        if len(values) < 3:
            return 'stable'
        recent = values[:5]
        n = len(recent)
        x = list(range(n))
        x_mean = statistics.mean(x)
        y_mean = statistics.mean(recent)
        numerator = sum((x[i] - x_mean) * (recent[i] - y_mean) for i in range(n))
        denominator = sum((x[i] - x_mean) ** 2 for i in range(n))
        if denominator == 0:
            return 'stable'
        slope = numerator / denominator
        if slope > 0.5:
            return 'up'
        elif slope < -0.5:
            return 'down'
        else:
            return 'stable'
    
    def get_matchup_history(self, player_name, opponent_team, stat='pts', seasons=2):
        cutoff_date = (datetime.now() - timedelta(days=365 * seasons)).strftime('%Y-%m-%d')
        self.cur.execute(f"SELECT pb.{stat}, pb.game_date FROM player_boxscores pb JOIN games g ON pb.game_date = g.date WHERE pb.player_name = %s AND (g.home_team LIKE %s OR g.visitor_team LIKE %s) AND pb.{stat} > 0 AND pb.game_date >= %s ORDER BY pb.game_date DESC", (player_name, f'%{opponent_team}%', f'%{opponent_team}%', cutoff_date))
        results = self.cur.fetchall()
        if len(results) < 3:
            return None
        values = [float(r[0]) for r in results]
        return {
            'average': statistics.mean(values),
            'recent_3': values[:3],
            'games': len(values),
            'stdev': statistics.stdev(values) if len(values) > 1 else 0,
            'trend': self._calculate_trend(values)
        }

    def _normalize_stat_column(self, stat):
        if not stat:
            return 'pts'
        stat_key = str(stat).lower().strip()
        return self.ALLOWED_STATS.get(stat_key)

    def get_recent_stat_samples(self, player_name, stat='pts', games=30):
        column = self._normalize_stat_column(stat)
        if not column:
            return []

        if column == 'pra':
            query = """
                SELECT COALESCE(pts,0) + COALESCE(reb,0) + COALESCE(ast,0) as pra
                FROM player_boxscores
                WHERE player_name = %s
                ORDER BY game_date DESC
                LIMIT %s
            """
        else:
            query = f"""
                SELECT {column}
                FROM player_boxscores
                WHERE player_name = %s AND {column} IS NOT NULL
                ORDER BY game_date DESC
                LIMIT %s
            """

        self.cur.execute(query, (player_name, games))
        results = self.cur.fetchall()
        values = [float(r[0]) for r in results if r[0] is not None]
        return values
    
    def get_home_away_splits(self, player_name, stat='pts', games=20):
        self.cur.execute(f"SELECT pb.{stat}, CASE WHEN g.home_team = pb.team_id THEN 'home' ELSE 'away' END as location FROM player_boxscores pb JOIN games g ON pb.game_date = g.date WHERE pb.player_name = %s AND pb.{stat} > 0 ORDER BY pb.game_date DESC LIMIT %s", (player_name, games * 2))
        results = self.cur.fetchall()
        home_values = [float(r[0]) for r in results if r[1] == 'home']
        away_values = [float(r[0]) for r in results if r[1] == 'away']
        if not home_values or not away_values:
            return None
        return {
            'home_avg': statistics.mean(home_values),
            'away_avg': statistics.mean(away_values),
            'home_games': len(home_values),
            'away_games': len(away_values),
            'differential': statistics.mean(home_values) - statistics.mean(away_values)
        }
    
    def calculate_confidence_interval(self, mean, stdev, confidence=0.68):
        if confidence == 0.68:
            z_score = 1.0
        elif confidence == 0.95:
            z_score = 1.96
        elif confidence == 0.99:
            z_score = 2.58
        else:
            z_score = 1.0
        margin = z_score * stdev
        return {'lower': mean - margin, 'upper': mean + margin, 'confidence': confidence * 100}
    
    def probability_over_under(self, projection, stdev, line):
        if stdev == 0:
            return {'prob_over': 50.0, 'prob_under': 50.0, 'z_score': 0}
        z_score = (line - projection) / stdev
        prob_under = self._normal_cdf(z_score)
        prob_over = 1 - prob_under
        return {'prob_over': round(prob_over * 100, 1), 'prob_under': round(prob_under * 100, 1), 'z_score': round(z_score, 2)}
    
    def _normal_cdf(self, z):
        return (1.0 + math.erf(z / math.sqrt(2.0))) / 2.0
    
    def calculate_expected_value(self, prob_win, odds, stake=100):
        prob_loss = 1 - prob_win
        if odds < 0:
            profit = stake / (abs(odds) / 100)
        else:
            profit = stake * (odds / 100)
        ev = (prob_win * profit) - (prob_loss * stake)
        return {'ev_dollars': round(ev, 2), 'ev_percent': round((ev / stake) * 100, 1), 'roi': round((ev / stake) * 100, 1)}
    
    def kelly_criterion(self, prob_win, odds):
        prob_loss = 1 - prob_win
        if odds < 0:
            decimal_odds = 1 + (100 / abs(odds))
        else:
            decimal_odds = 1 + (odds / 100)
        b = decimal_odds - 1
        kelly = (b * prob_win - prob_loss) / b
        fractional_kelly = kelly * 0.25
        return {'full_kelly': round(max(0, kelly) * 100, 1), 'fractional_kelly': round(max(0, fractional_kelly) * 100, 1), 'recommended': round(max(0, fractional_kelly) * 100, 1)}
    
    def generate_projection(self, player_name, opponent_team, stat='pts', is_home=True):
        l5 = self.get_rolling_average(player_name, stat, 5)
        l10 = self.get_rolling_average(player_name, stat, 10)
        l20 = self.get_rolling_average(player_name, stat, 20)
        if not l10:
            return None
        base = l5['average'] * 0.4 + l10['average'] * 0.4 + (l20['average'] * 0.2 if l20 else l10['average'] * 0.2)
        matchup = self.get_matchup_history(player_name, opponent_team, stat)
        matchup_boost = 0
        if matchup and matchup['games'] >= 5:
            matchup_diff = matchup['average'] - l10['average']
            matchup_boost = matchup_diff * 0.5
        splits = self.get_home_away_splits(player_name, stat)
        location_boost = 0
        if splits:
            if is_home:
                location_boost = (splits['home_avg'] - l10['average']) * 0.3
            else:
                location_boost = (splits['away_avg'] - l10['average']) * 0.3
        trend_boost = 0
        if l5['trend'] == 'up':
            trend_boost = 0.5
        elif l5['trend'] == 'down':
            trend_boost = -0.5
        final_projection = base + matchup_boost + location_boost + trend_boost
        variance_pct = (l10['stdev'] / l10['average']) * 100 if l10['average'] > 0 else 50
        confidence = max(0, min(100, 100 - variance_pct))
        ci_68 = self.calculate_confidence_interval(final_projection, l10['stdev'], 0.68)
        ci_95 = self.calculate_confidence_interval(final_projection, l10['stdev'], 0.95)
        return {
            'player': player_name, 'stat': stat, 'projection': round(final_projection, 1), 'confidence': round(confidence, 0),
            'base_projection': round(base, 1), 'matchup_boost': round(matchup_boost, 1), 'location_boost': round(location_boost, 1),
            'trend_boost': round(trend_boost, 1), 'l5_avg': round(l5['average'], 1), 'l10_avg': round(l10['average'], 1),
            'l20_avg': round(l20['average'], 1) if l20 else None, 'stdev': round(l10['stdev'], 2), 'variance_pct': round(variance_pct, 1),
            'ci_68': ci_68, 'ci_95': ci_95, 'recent_games': l5['recent_5'], 'trend': l5['trend'],
            'matchup_avg': round(matchup['average'], 1) if matchup else None, 'matchup_games': matchup['games'] if matchup else 0,
            'home_avg': round(splits['home_avg'], 1) if splits else None, 'away_avg': round(splits['away_avg'], 1) if splits else None
        }
    
    def evaluate_line(self, projection_data, line, odds=-110):
        projection = projection_data['projection']
        stdev = projection_data['stdev']
        confidence = projection_data['confidence']
        prob = self.probability_over_under(projection, stdev, line)
        edge = projection - line
        if abs(edge) < 1.5:
            return None
        pick = 'OVER' if edge > 0 else 'UNDER'
        win_prob = prob['prob_over'] / 100 if pick == 'OVER' else prob['prob_under'] / 100
        ev = self.calculate_expected_value(win_prob, odds)
        kelly = self.kelly_criterion(win_prob, odds)
        if ev['ev_percent'] < 5:
            return None
        return {
            'pick': pick, 'line': line, 'projection': projection, 'edge': round(abs(edge), 1),
            'win_probability': round(win_prob * 100, 1), 'confidence': confidence, 'ev_dollars': ev['ev_dollars'],
            'ev_percent': ev['ev_percent'], 'roi': ev['roi'], 'kelly_size': kelly['recommended'],
            'reasoning': self._generate_reasoning(projection_data, line, pick, edge)
        }
    
    def _generate_reasoning(self, proj, line, pick, edge):
        reasons = []
        reasons.append(f"Projection ({proj['projection']}) vs Line ({line}) = {abs(edge):.1f} point edge")
        if proj['trend'] == 'up':
            reasons.append(f"Trending UP: Recent 5 games averaging {proj['l5_avg']}")
        elif proj['trend'] == 'down':
            reasons.append(f"Trending DOWN: Recent 5 games averaging {proj['l5_avg']}")
        if proj['variance_pct'] < 20:
            reasons.append(f"High consistency: Only {proj['variance_pct']:.0f}% variance")
        if proj['matchup_avg'] and proj['matchup_games'] >= 5:
            reasons.append(f"vs opponent: {proj['matchup_avg']} avg in {proj['matchup_games']} games")
        recent_avg = sum(proj['recent_games']) / len(proj['recent_games'])
        reasons.append(f"L5 games: {proj['recent_games']} (avg: {recent_avg:.1f})")
        return reasons

    def run_player_monte_carlo(self, player_name, stat='pts', line=None, odds=-110, iterations=5000, games=30):
        """Simulate a single player's outcome distribution and return EV/edge."""
        samples = self.get_recent_stat_samples(player_name, stat, games)
        if not samples or len(samples) < 3:
            return None

        mean = statistics.mean(samples)
        stdev = statistics.stdev(samples) if len(samples) > 1 else max(mean * 0.15, 1.0)
        simulated = [max(0, random.gauss(mean, stdev)) for _ in range(iterations)]
        sim_avg = statistics.mean(simulated)
        sim_std = statistics.stdev(simulated) if len(simulated) > 1 else stdev

        result = {
            'player': player_name,
            'stat': stat.upper() if isinstance(stat, str) else stat,
            'projection': round(sim_avg, 2),
            'historical_avg': round(mean, 2),
            'historical_std': round(stdev, 2),
            'sample_size': len(samples),
            'simulations': iterations
        }

        if line is None:
            return result

        over_prob = sum(1 for val in simulated if val >= line) / iterations
        under_prob = 1 - over_prob
        recommendation = 'OVER' if over_prob >= under_prob else 'UNDER'
        edge = round(sim_avg - line, 2)

        if recommendation == 'UNDER':
            win_probability = under_prob
        else:
            win_probability = over_prob

        ev = self.calculate_expected_value(win_probability, odds)

        result.update({
            'line': line,
            'recommended': recommendation,
            'prob_over': round(over_prob * 100, 1),
            'prob_under': round(under_prob * 100, 1),
            'edge': edge,
            'ev_percent': ev['ev_percent'] if ev else None,
            'ev_dollars': ev['ev_dollars'] if ev else None,
            'sim_std': round(sim_std, 2)
        })

        return result

    def close(self):
        self.cur.close()
        self.conn.close()


def run_player_projection(player_name, line=None, stat='pts', odds=-110, iterations=5000, games=30):
    """Helper to run a one-off player Monte Carlo projection with automatic cleanup."""
    engine = NBAMathEngine()
    try:
        return engine.run_player_monte_carlo(
            player_name=player_name,
            stat=stat,
            line=line,
            odds=odds,
            iterations=iterations,
            games=games
        )
    finally:
        engine.close()
