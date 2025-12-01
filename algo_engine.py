#!/usr/bin/env python3
"""
SB-ALGO Edge Engine
Generates betting picks based on statistical analysis
"""

from sqlalchemy import create_engine, text
from datetime import datetime, timedelta
import os

DATABASE_URL = os.environ.get('DATABASE_URL', 
    "postgresql://sb_algo_db_user:0HDtYp4EY2Lo5At8iyf44PD1zDioSPK7@dpg-d495uhchg0os738l1a50-a.virginia-postgres.render.com/sb_algo_db?sslmode=require")

TEAM_MAP = {
    "ATL": "ATL", "BOS": "BOS", "BKN": "BKN", "CHA": "CHA", "CHI": "CHI",
    "CLE": "CLE", "DAL": "DAL", "DEN": "DEN", "DET": "DET", "GS": "GSW", "GSW": "GSW",
    "HOU": "HOU", "IND": "IND", "LAC": "LAC", "LAL": "LAL", "MEM": "MEM",
    "MIA": "MIA", "MIL": "MIL", "MIN": "MIN", "NO": "NOP", "NOP": "NOP",
    "NY": "NYK", "NYK": "NYK", "OKC": "OKC", "ORL": "ORL", "PHI": "PHI",
    "PHO": "PHX", "PHX": "PHX", "POR": "POR", "SA": "SAS", "SAS": "SAS",
    "SAC": "SAC", "TOR": "TOR", "UTA": "UTA", "WAS": "WAS"
}

class AlgoEngine:
    def __init__(self):
        self.engine = create_engine(DATABASE_URL)
    
    def get_team_stats(self, team, days=30):
        team = TEAM_MAP.get(team, team)
        query = text("""
            WITH team_games AS (
                SELECT 
                    CASE WHEN home_team = :team THEN home_pts ELSE visitor_pts END as pts_for,
                    CASE WHEN home_team = :team THEN visitor_pts ELSE home_pts END as pts_against,
                    CASE WHEN home_team = :team THEN 1 ELSE 0 END as is_home,
                    CASE WHEN (home_team = :team AND home_win = 1) OR 
                              (visitor_team = :team AND home_win = 0) THEN 1 ELSE 0 END as win,
                    total_points
                FROM games
                WHERE (home_team = :team OR visitor_team = :team)
                AND date >= CURRENT_DATE - :days
                AND date < CURRENT_DATE
                AND home_pts > 0
            )
            SELECT 
                COUNT(*) as games,
                SUM(win) as wins,
                ROUND(AVG(pts_for)::numeric, 1) as avg_pts_for,
                ROUND(AVG(pts_against)::numeric, 1) as avg_pts_against,
                ROUND(AVG(pts_for - pts_against)::numeric, 1) as avg_margin,
                ROUND(AVG(total_points)::numeric, 1) as avg_total
            FROM team_games
        """)
        
        with self.engine.connect() as conn:
            result = conn.execute(query, {"team": team, "days": days}).fetchone()
            if result and result[0] > 0:
                return {
                    'games': result[0],
                    'wins': result[1],
                    'win_pct': round(result[1] / result[0] * 100, 1) if result[0] > 0 else 0,
                    'avg_pts_for': float(result[2] or 0),
                    'avg_pts_against': float(result[3] or 0),
                    'avg_margin': float(result[4] or 0),
                    'avg_total': float(result[5] or 220)
                }
        return None
    
    def get_team_rest_days(self, team, game_date):
        team = TEAM_MAP.get(team, team)
        query = text("""
            SELECT date FROM games
            WHERE (home_team = :team OR visitor_team = :team)
            AND date < :game_date
            ORDER BY date DESC
            LIMIT 1
        """)
        
        with self.engine.connect() as conn:
            result = conn.execute(query, {"team": team, "game_date": game_date}).fetchone()
            if result:
                last_game = result[0]
                if isinstance(game_date, str):
                    game_date = datetime.strptime(game_date, '%Y-%m-%d').date()
                return (game_date - last_game).days
        return 3
    
    def get_team_injuries(self, team):
        team = TEAM_MAP.get(team, team)
        query = text("""
            SELECT player_name, status FROM injuries
            WHERE team_abbr = :team AND LOWER(status) IN ('out', 'doubtful')
        """)
        with self.engine.connect() as conn:
            result = conn.execute(query, {"team": team}).fetchall()
            return [{'player': row[0], 'status': row[1]} for row in result]
    
    def get_h2h_stats(self, team1, team2, games=5):
        team1, team2 = TEAM_MAP.get(team1, team1), TEAM_MAP.get(team2, team2)
        query = text("""
            SELECT home_team, home_pts, visitor_pts, home_win
            FROM games
            WHERE ((home_team = :t1 AND visitor_team = :t2) OR (home_team = :t2 AND visitor_team = :t1))
            AND home_pts > 0
            ORDER BY date DESC LIMIT :games
        """)
        with self.engine.connect() as conn:
            result = conn.execute(query, {"t1": team1, "t2": team2, "games": games}).fetchall()
            if not result:
                return None
            t1_wins = sum(1 for r in result if (r[0]==team1 and r[3]) or (r[0]==team2 and not r[3]))
            avg_total = sum(r[1]+r[2] for r in result) / len(result)
            return {'games': len(result), 'team1_wins': t1_wins, 'avg_total': round(avg_total, 1)}
    
    def predict_spread(self, home_team, away_team, game_date):
        home_team, away_team = TEAM_MAP.get(home_team, home_team), TEAM_MAP.get(away_team, away_team)
        home_stats, away_stats = self.get_team_stats(home_team), self.get_team_stats(away_team)
        
        if not home_stats or not away_stats:
            return None, 0, {}
        
        factors = {}
        predicted_margin = home_stats['avg_margin'] - away_stats['avg_margin']
        
        # Home court +3
        predicted_margin += 3.0
        factors['home_court'] = "+3.0 pts"
        
        # Rest
        home_rest = self.get_team_rest_days(home_team, game_date)
        away_rest = self.get_team_rest_days(away_team, game_date)
        rest_adj = max(-3, min(3, (home_rest - away_rest) * 0.5))
        predicted_margin += rest_adj
        factors['rest'] = f"H:{home_rest}d A:{away_rest}d ({rest_adj:+.1f})"
        
        # B2B
        if home_rest == 1:
            predicted_margin -= 2.0
            factors['home_b2b'] = "-2.0 pts"
        if away_rest == 1:
            predicted_margin += 2.0
            factors['away_b2b'] = "+2.0 pts"
        
        # Injuries
        home_inj, away_inj = len(self.get_team_injuries(home_team)), len(self.get_team_injuries(away_team))
        inj_adj = max(-4, min(4, (away_inj - home_inj) * 1.0))
        predicted_margin += inj_adj
        factors['injuries'] = f"H:{home_inj} A:{away_inj} out ({inj_adj:+.1f})"
        
        confidence = 65 + (10 if abs(predicted_margin) > 7 else 0) + (5 if abs(home_rest - away_rest) >= 2 else 0)
        return round(predicted_margin, 1), min(90, confidence), factors
    
    def predict_total(self, home_team, away_team, game_date):
        home_team, away_team = TEAM_MAP.get(home_team, home_team), TEAM_MAP.get(away_team, away_team)
        home_stats, away_stats = self.get_team_stats(home_team), self.get_team_stats(away_team)
        
        if not home_stats or not away_stats:
            return None, 0, {}
        
        factors = {}
        base_total = (home_stats['avg_total'] + away_stats['avg_total']) / 2
        factors['base'] = f"Avg totals: {base_total:.1f}"
        
        # Pace
        pace = ((home_stats['avg_pts_for'] + away_stats['avg_pts_for']) - 220) * 0.3
        base_total += pace
        factors['pace'] = f"{pace:+.1f}"
        
        # Fatigue
        home_rest = self.get_team_rest_days(home_team, game_date)
        away_rest = self.get_team_rest_days(away_team, game_date)
        if home_rest == 1 or away_rest == 1:
            base_total -= 2.0
            factors['fatigue'] = "-2.0 (B2B)"
        
        return round(base_total, 1), 65, factors
    
    def get_best_odds(self, game_date):
        query = text("""
            SELECT game_id, home_team, away_team, sportsbook, home_spread, total, home_ml, away_ml
            FROM betting_odds WHERE game_date = :game_date
        """)
        games = {}
        with self.engine.connect() as conn:
            for row in conn.execute(query, {"game_date": game_date}).fetchall():
                gid = row[0]
                if gid not in games:
                    games[gid] = {'home_team': row[1], 'away_team': row[2], 'spreads': [], 'totals': [], 'books': {}}
                if row[4]: games[gid]['spreads'].append(float(row[4]))
                if row[5]: games[gid]['totals'].append(float(row[5]))
                games[gid]['books'][row[3]] = {'spread': row[4], 'total': row[5], 'home_ml': row[6], 'away_ml': row[7]}
        
        for g in games.values():
            g['consensus_spread'] = round(sum(g['spreads'])/len(g['spreads']), 1) if g['spreads'] else None
            g['consensus_total'] = round(sum(g['totals'])/len(g['totals']), 1) if g['totals'] else None
        return games
    
    def generate_picks(self, game_date):
        if isinstance(game_date, str):
            game_date_obj = datetime.strptime(game_date, '%Y-%m-%d').date()
        else:
            game_date_obj = game_date
        
        games = self.get_best_odds(game_date_obj)
        if not games:
            return []
        
        picks = []
        for game_id, game in games.items():
            home, away = game['home_team'], game['away_team']
            
            pred_margin, spread_conf, spread_factors = self.predict_spread(home, away, game_date_obj)
            pred_total, total_conf, total_factors = self.predict_total(home, away, game_date_obj)
            
            line_spread = game['consensus_spread']
            line_total = game['consensus_total']
            
            # Spread edge
            spread_edge, spread_pick = 0, None
            if pred_margin is not None and line_spread is not None:
                edge_value = pred_margin - (-line_spread)
                spread_edge = abs(edge_value)
                if spread_edge >= 1.5:
                    spread_pick = f"{home} {line_spread}" if edge_value > 0 else f"{away} +{-line_spread}"
            
            # Total edge
            total_edge, total_pick = 0, None
            if pred_total is not None and line_total is not None:
                total_edge = abs(pred_total - line_total)
                if total_edge >= 2:
                    total_pick = f"Over {line_total}" if pred_total > line_total else f"Under {line_total}"
            
            picks.append({
                'game_id': game_id, 'home_team': home, 'away_team': away,
                'matchup': f"{away} @ {home}",
                'predicted_margin': pred_margin, 'line_spread': line_spread,
                'spread_edge': round(spread_edge, 1), 'spread_pick': spread_pick,
                'spread_confidence': spread_conf, 'spread_factors': spread_factors,
                'predicted_total': pred_total, 'line_total': line_total,
                'total_edge': round(total_edge, 1), 'total_pick': total_pick,
                'total_confidence': total_conf, 'total_factors': total_factors,
                'best_pick': spread_pick if spread_edge > total_edge else total_pick,
                'best_confidence': spread_conf if spread_edge > total_edge else total_conf,
                'best_edge': max(spread_edge, total_edge)
            })
        
        picks.sort(key=lambda x: x['best_edge'], reverse=True)
        return picks


def main():
    print("=" * 60)
    print("SB-ALGO EDGE ENGINE TEST")
    print("=" * 60)
    
    engine = AlgoEngine()
    today = datetime.now().strftime('%Y-%m-%d')
    print(f"\nGenerating picks for {today}...")
    
    picks = engine.generate_picks(today)
    
    if not picks:
        print("No picks generated")
        return
    
    print(f"\n{len(picks)} games analyzed:\n")
    
    for i, p in enumerate(picks, 1):
        print(f"Game {i}: {p['matchup']}")
        print(f"  Spread: Line {p['line_spread']}, Predicted {p['predicted_margin']}")
        if p['spread_pick']:
            print(f"  >>> PICK: {p['spread_pick']} (Edge: {p['spread_edge']}, Conf: {p['spread_confidence']}%)")
        print(f"  Total: Line {p['line_total']}, Predicted {p['predicted_total']}")
        if p['total_pick']:
            print(f"  >>> PICK: {p['total_pick']} (Edge: {p['total_edge']}, Conf: {p['total_confidence']}%)")
        print(f"  Factors: {p['spread_factors']}")
        print()
    
    spread_picks = [p for p in picks if p['spread_pick']]
    total_picks = [p for p in picks if p['total_pick']]
    print(f"SUMMARY: {len(spread_picks)} spread picks, {len(total_picks)} total picks")


if __name__ == "__main__":
    main()
