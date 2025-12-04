"""
Game Predictor - NBA Game Betting Analysis with Memory & Self-Learning
Analyzes spreads, totals, moneylines with pattern recognition
"""

from sqlalchemy import text
from datetime import datetime, timedelta
import math

class GamePredictor:
    def __init__(self, engine=None):
        self.engine = engine
        
    # ========== TEAM STATS ==========
    def get_team_stats(self, team, days=30):
        """Get comprehensive team statistics"""
        if not self.engine:
            return None
            
        with self.engine.connect() as conn:
            result = conn.execute(text("""
                SELECT 
                    COUNT(*) as games,
                    SUM(CASE WHEN (home_team = :team AND home_win = 1) OR 
                                 (visitor_team = :team AND home_win = 0) THEN 1 ELSE 0 END) as wins,
                    AVG(CASE WHEN home_team = :team THEN home_pts ELSE visitor_pts END) as ppg,
                    AVG(CASE WHEN home_team = :team THEN visitor_pts ELSE home_pts END) as opp_ppg,
                    AVG(CASE WHEN home_team = :team THEN home_pts + visitor_pts 
                             ELSE home_pts + visitor_pts END) as avg_total,
                    STDDEV(CASE WHEN home_team = :team THEN home_pts ELSE visitor_pts END) as pts_stddev,
                    -- Home stats
                    SUM(CASE WHEN home_team = :team THEN 1 ELSE 0 END) as home_games,
                    SUM(CASE WHEN home_team = :team AND home_win = 1 THEN 1 ELSE 0 END) as home_wins,
                    AVG(CASE WHEN home_team = :team THEN home_pts END) as home_ppg,
                    -- Away stats
                    SUM(CASE WHEN visitor_team = :team THEN 1 ELSE 0 END) as away_games,
                    SUM(CASE WHEN visitor_team = :team AND home_win = 0 THEN 1 ELSE 0 END) as away_wins,
                    AVG(CASE WHEN visitor_team = :team THEN visitor_pts END) as away_ppg,
                    -- ATS (Against the Spread) - requires betting_odds join
                    -- Last 5 margin
                    (SELECT AVG(margin) FROM (
                        SELECT CASE WHEN home_team = :team THEN home_pts - visitor_pts 
                                    ELSE visitor_pts - home_pts END as margin
                        FROM games 
                        WHERE (home_team = :team OR visitor_team = :team)
                        AND home_pts IS NOT NULL
                        ORDER BY date DESC LIMIT 5
                    ) t) as l5_margin,
                    -- Last 10 margin
                    (SELECT AVG(margin) FROM (
                        SELECT CASE WHEN home_team = :team THEN home_pts - visitor_pts 
                                    ELSE visitor_pts - home_pts END as margin
                        FROM games 
                        WHERE (home_team = :team OR visitor_team = :team)
                        AND home_pts IS NOT NULL
                        ORDER BY date DESC LIMIT 10
                    ) t) as l10_margin
                FROM games
                WHERE (home_team = :team OR visitor_team = :team)
                AND date >= CURRENT_DATE - INTERVAL :days DAY
                AND home_pts IS NOT NULL
            """), {"team": team, "days": f"{days} days"}).fetchone()
            
            if not result or not result[0]:
                return None
                
            games = result[0]
            wins = result[1] or 0
            
            return {
                'team': team,
                'games': games,
                'wins': wins,
                'losses': games - wins,
                'win_pct': wins / games if games > 0 else 0,
                'ppg': float(result[2] or 0),
                'opp_ppg': float(result[3] or 0),
                'avg_total': float(result[4] or 220),
                'pts_stddev': float(result[5] or 10),
                'home_games': result[6] or 0,
                'home_wins': result[7] or 0,
                'home_ppg': float(result[8] or 0),
                'away_games': result[9] or 0,
                'away_wins': result[10] or 0,
                'away_ppg': float(result[11] or 0),
                'l5_margin': float(result[12] or 0),
                'l10_margin': float(result[13] or 0),
                'net_rating': float((result[2] or 0) - (result[3] or 0))
            }
    
    # ========== HEAD TO HEAD ==========
    def get_h2h_stats(self, team1, team2, limit=10):
        """Get head-to-head history between two teams"""
        if not self.engine:
            return None
            
        with self.engine.connect() as conn:
            result = conn.execute(text("""
                SELECT 
                    date, home_team, visitor_team, home_pts, visitor_pts, home_win
                FROM games
                WHERE ((home_team = :t1 AND visitor_team = :t2) OR
                       (home_team = :t2 AND visitor_team = :t1))
                AND home_pts IS NOT NULL
                ORDER BY date DESC
                LIMIT :lim
            """), {"t1": team1, "t2": team2, "lim": limit}).fetchall()
            
            if not result:
                return {'games': 0, 'team1_wins': 0, 'team2_wins': 0, 'avg_margin': 0, 'avg_total': 220}
            
            team1_wins = 0
            total_margin = 0
            total_points = 0
            
            for row in result:
                home, away, home_pts, away_pts, home_win = row[1], row[2], row[3], row[4], row[5]
                total_points += (home_pts + away_pts)
                
                if home == team1:
                    if home_win == 1:
                        team1_wins += 1
                        total_margin += (home_pts - away_pts)
                    else:
                        total_margin -= (away_pts - home_pts)
                else:
                    if home_win == 0:
                        team1_wins += 1
                        total_margin += (away_pts - home_pts)
                    else:
                        total_margin -= (home_pts - away_pts)
            
            return {
                'games': len(result),
                'team1_wins': team1_wins,
                'team2_wins': len(result) - team1_wins,
                'avg_margin': total_margin / len(result),
                'avg_total': total_points / len(result)
            }
    
    # ========== SPREAD PREDICTION ==========
    def predict_spread(self, home_team, away_team):
        """Predict the spread for a game"""
        home_stats = self.get_team_stats(home_team)
        away_stats = self.get_team_stats(away_team)
        h2h = self.get_h2h_stats(home_team, away_team)
        
        if not home_stats or not away_stats:
            return {'predicted_spread': 0, 'confidence': 0}
        
        # Base prediction from net ratings
        home_advantage = 3.0  # NBA home court advantage ~3 points
        
        # Net rating difference
        net_diff = home_stats['net_rating'] - away_stats['net_rating']
        
        # Recent form adjustment (L5 and L10 margins)
        home_form = (home_stats['l5_margin'] * 0.6 + home_stats['l10_margin'] * 0.4)
        away_form = (away_stats['l5_margin'] * 0.6 + away_stats['l10_margin'] * 0.4)
        form_adj = (home_form - away_form) * 0.3
        
        # H2H adjustment
        h2h_adj = 0
        if h2h['games'] >= 3:
            h2h_adj = h2h['avg_margin'] * 0.15
        
        # Home/Away splits adjustment
        if home_stats['home_games'] > 0 and away_stats['away_games'] > 0:
            home_split = home_stats['home_ppg'] - home_stats['ppg']
            away_split = away_stats['away_ppg'] - away_stats['ppg']
            split_adj = (home_split - away_split) * 0.2
        else:
            split_adj = 0
        
        # Final prediction (positive = home favored)
        predicted_spread = -(net_diff + home_advantage + form_adj + h2h_adj + split_adj)
        
        # Confidence based on sample size and consistency
        games_factor = min(1.0, (home_stats['games'] + away_stats['games']) / 40)
        consistency = max(0, 1 - (home_stats['pts_stddev'] + away_stats['pts_stddev']) / 50)
        confidence = max(30, min(95, (games_factor * 0.5 + consistency * 0.5) * 100))
        
        return {
            'predicted_spread': round(predicted_spread, 1),
            'confidence': round(confidence, 1),
            'home_net': round(home_stats['net_rating'], 1),
            'away_net': round(away_stats['net_rating'], 1),
            'home_form': round(home_form, 1),
            'away_form': round(away_form, 1)
        }
    
    # ========== TOTAL PREDICTION ==========
    def predict_total(self, home_team, away_team):
        """Predict the total points for a game"""
        home_stats = self.get_team_stats(home_team)
        away_stats = self.get_team_stats(away_team)
        h2h = self.get_h2h_stats(home_team, away_team)
        
        if not home_stats or not away_stats:
            return {'predicted_total': 220, 'confidence': 0}
        
        # Base: average of both teams' totals
        base_total = (home_stats['avg_total'] + away_stats['avg_total']) / 2
        
        # Pace adjustment (using PPG as proxy)
        pace_factor = ((home_stats['ppg'] + away_stats['ppg']) - 220) * 0.3
        
        # H2H adjustment
        h2h_adj = 0
        if h2h['games'] >= 3:
            h2h_adj = (h2h['avg_total'] - base_total) * 0.2
        
        predicted_total = base_total + pace_factor + h2h_adj
        
        # Confidence
        stddev_avg = (home_stats['pts_stddev'] + away_stats['pts_stddev']) / 2
        consistency = max(0, 1 - stddev_avg / 15) * 100
        
        return {
            'predicted_total': round(predicted_total, 1),
            'confidence': round(consistency, 1),
            'home_avg_total': round(home_stats['avg_total'], 1),
            'away_avg_total': round(away_stats['avg_total'], 1),
            'h2h_avg_total': round(h2h['avg_total'], 1)
        }
    
    # ========== MONEYLINE VALUE ==========
    def analyze_moneyline(self, home_team, away_team, home_ml, away_ml):
        """Analyze moneyline value"""
        spread_pred = self.predict_spread(home_team, away_team)
        
        # Convert spread to win probability
        # Using logistic function: P(win) = 1 / (1 + 10^(spread/10))
        predicted_spread = spread_pred['predicted_spread']
        
        if predicted_spread <= 0:  # Home favored
            home_win_prob = 1 / (1 + math.pow(10, predicted_spread / 10))
        else:  # Away favored
            home_win_prob = 1 / (1 + math.pow(10, predicted_spread / 10))
        
        away_win_prob = 1 - home_win_prob
        
        # Convert ML odds to implied probability
        def ml_to_prob(ml):
            if ml > 0:
                return 100 / (ml + 100)
            else:
                return abs(ml) / (abs(ml) + 100)
        
        home_implied = ml_to_prob(home_ml) if home_ml else 0.5
        away_implied = ml_to_prob(away_ml) if away_ml else 0.5
        
        # Calculate edge
        home_edge = (home_win_prob - home_implied) * 100
        away_edge = (away_win_prob - away_implied) * 100
        
        return {
            'home_win_prob': round(home_win_prob * 100, 1),
            'away_win_prob': round(away_win_prob * 100, 1),
            'home_implied': round(home_implied * 100, 1),
            'away_implied': round(away_implied * 100, 1),
            'home_edge': round(home_edge, 1),
            'away_edge': round(away_edge, 1),
            'best_bet': 'HOME' if home_edge > away_edge else 'AWAY',
            'edge': round(max(home_edge, away_edge), 1)
        }
    
    # ========== FULL GAME ANALYSIS ==========
    def analyze_game(self, home_team, away_team, spread_line=None, total_line=None, home_ml=None, away_ml=None):
        """Complete game analysis with all predictions"""
        spread_pred = self.predict_spread(home_team, away_team)
        total_pred = self.predict_total(home_team, away_team)
        
        analysis = {
            'home_team': home_team,
            'away_team': away_team,
            'spread': spread_pred,
            'total': total_pred,
            'picks': []
        }
        
        # Spread pick
        if spread_line is not None:
            spread_diff = spread_pred['predicted_spread'] - spread_line
            if abs(spread_diff) >= 2:  # Need 2+ point edge
                if spread_diff > 0:
                    analysis['picks'].append({
                        'type': 'SPREAD',
                        'pick': f"{away_team} {spread_line:+.1f}",
                        'edge': round(spread_diff, 1),
                        'confidence': spread_pred['confidence']
                    })
                else:
                    analysis['picks'].append({
                        'type': 'SPREAD',
                        'pick': f"{home_team} {-spread_line:+.1f}",
                        'edge': round(-spread_diff, 1),
                        'confidence': spread_pred['confidence']
                    })
        
        # Total pick
        if total_line is not None:
            total_diff = total_pred['predicted_total'] - total_line
            if abs(total_diff) >= 4:  # Need 4+ point edge
                if total_diff > 0:
                    analysis['picks'].append({
                        'type': 'TOTAL',
                        'pick': f"OVER {total_line}",
                        'edge': round(total_diff, 1),
                        'confidence': total_pred['confidence']
                    })
                else:
                    analysis['picks'].append({
                        'type': 'TOTAL',
                        'pick': f"UNDER {total_line}",
                        'edge': round(-total_diff, 1),
                        'confidence': total_pred['confidence']
                    })
        
        # Moneyline analysis
        if home_ml and away_ml:
            ml_analysis = self.analyze_moneyline(home_team, away_team, home_ml, away_ml)
            analysis['moneyline'] = ml_analysis
            
            if ml_analysis['edge'] >= 5:  # Need 5%+ edge
                best = ml_analysis['best_bet']
                analysis['picks'].append({
                    'type': 'MONEYLINE',
                    'pick': f"{home_team if best == 'HOME' else away_team} ML",
                    'edge': ml_analysis['edge'],
                    'confidence': spread_pred['confidence']
                })
        
        return analysis


class BettingMemory:
    """Track predictions vs results for self-learning"""
    
    def __init__(self, engine=None):
        self.engine = engine
        self._ensure_table()
    
    def _ensure_table(self):
        """Create predictions tracking table if not exists"""
        if not self.engine:
            return
            
        with self.engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS algo_predictions (
                    id SERIAL PRIMARY KEY,
                    game_date DATE,
                    home_team VARCHAR(10),
                    away_team VARCHAR(10),
                    prediction_type VARCHAR(20),
                    pick VARCHAR(100),
                    predicted_value FLOAT,
                    line_value FLOAT,
                    edge FLOAT,
                    confidence FLOAT,
                    actual_result FLOAT,
                    hit BOOLEAN,
                    created_at TIMESTAMP DEFAULT NOW(),
                    graded_at TIMESTAMP,
                    UNIQUE(game_date, home_team, away_team, prediction_type)
                )
            """))
            conn.commit()
    
    def save_prediction(self, game_date, home_team, away_team, pred_type, pick, 
                       predicted_value, line_value, edge, confidence):
        """Save a prediction for later grading"""
        if not self.engine:
            return
            
        with self.engine.connect() as conn:
            conn.execute(text("""
                INSERT INTO algo_predictions 
                (game_date, home_team, away_team, prediction_type, pick, 
                 predicted_value, line_value, edge, confidence)
                VALUES (:gd, :ht, :at, :pt, :pick, :pv, :lv, :edge, :conf)
                ON CONFLICT (game_date, home_team, away_team, prediction_type) 
                DO UPDATE SET 
                    pick = :pick, predicted_value = :pv, line_value = :lv,
                    edge = :edge, confidence = :conf, created_at = NOW()
            """), {
                'gd': game_date, 'ht': home_team, 'at': away_team,
                'pt': pred_type, 'pick': pick, 'pv': predicted_value,
                'lv': line_value, 'edge': edge, 'conf': confidence
            })
            conn.commit()
    
    def grade_predictions(self, game_date):
        """Grade predictions against actual results"""
        if not self.engine:
            return
            
        with self.engine.connect() as conn:
            # Get ungraded predictions for the date
            preds = conn.execute(text("""
                SELECT p.id, p.home_team, p.away_team, p.prediction_type, 
                       p.predicted_value, p.line_value, p.pick,
                       g.home_pts, g.visitor_pts
                FROM algo_predictions p
                JOIN games g ON p.game_date = g.date 
                    AND p.home_team = g.home_team 
                    AND p.away_team = g.visitor_team
                WHERE p.game_date = :gd AND p.graded_at IS NULL
                AND g.home_pts IS NOT NULL
            """), {"gd": game_date}).fetchall()
            
            for pred in preds:
                pred_id, home, away, pred_type, pred_val, line_val, pick = pred[:7]
                home_pts, away_pts = pred[7], pred[8]
                
                actual = None
                hit = None
                
                if pred_type == 'SPREAD':
                    actual = home_pts - away_pts  # Home margin
                    # If pick contains away team, they need to cover
                    if away in pick:
                        hit = (away_pts + line_val) > home_pts
                    else:
                        hit = (home_pts - line_val) > away_pts
                        
                elif pred_type == 'TOTAL':
                    actual = home_pts + away_pts
                    if 'OVER' in pick:
                        hit = actual > line_val
                    else:
                        hit = actual < line_val
                        
                elif pred_type == 'MONEYLINE':
                    actual = home_pts - away_pts
                    if home in pick:
                        hit = home_pts > away_pts
                    else:
                        hit = away_pts > home_pts
                
                # Update the prediction
                conn.execute(text("""
                    UPDATE algo_predictions 
                    SET actual_result = :actual, hit = :hit, graded_at = NOW()
                    WHERE id = :id
                """), {"actual": actual, "hit": hit, "id": pred_id})
            
            conn.commit()
            return len(preds)
    
    def get_performance_stats(self, days=30):
        """Get algorithm performance statistics"""
        if not self.engine:
            return {}
            
        with self.engine.connect() as conn:
            result = conn.execute(text("""
                SELECT 
                    prediction_type,
                    COUNT(*) as total,
                    SUM(CASE WHEN hit = true THEN 1 ELSE 0 END) as wins,
                    AVG(edge) as avg_edge,
                    AVG(confidence) as avg_confidence,
                    AVG(CASE WHEN hit = true THEN edge ELSE 0 END) as avg_winning_edge,
                    AVG(CASE WHEN hit = false THEN edge ELSE 0 END) as avg_losing_edge
                FROM algo_predictions
                WHERE graded_at IS NOT NULL
                AND game_date >= CURRENT_DATE - INTERVAL :days DAY
                GROUP BY prediction_type
            """), {"days": f"{days} days"}).fetchall()
            
            stats = {}
            for row in result:
                pred_type = row[0]
                total = row[1]
                wins = row[2]
                stats[pred_type] = {
                    'total': total,
                    'wins': wins,
                    'losses': total - wins,
                    'win_rate': round(wins / total * 100, 1) if total > 0 else 0,
                    'avg_edge': round(row[3] or 0, 1),
                    'avg_confidence': round(row[4] or 0, 1),
                    'avg_winning_edge': round(row[5] or 0, 1),
                    'avg_losing_edge': round(row[6] or 0, 1)
                }
            
            return stats
    
    def get_insights(self):
        """Generate insights from historical performance"""
        stats = self.get_performance_stats(days=60)
        insights = []
        
        for pred_type, data in stats.items():
            if data['total'] < 10:
                continue
                
            # Check if certain edge thresholds perform better
            if data['avg_winning_edge'] > data['avg_losing_edge'] + 2:
                insights.append(f"✅ {pred_type}: Higher edge picks ({data['avg_winning_edge']:.1f}) winning more than lower edge ({data['avg_losing_edge']:.1f})")
            
            if data['win_rate'] >= 55:
                insights.append(f"🔥 {pred_type}: Hitting at {data['win_rate']:.1f}% - PROFITABLE")
            elif data['win_rate'] < 48:
                insights.append(f"⚠️ {pred_type}: Only {data['win_rate']:.1f}% - Need higher edge threshold")
        
        return insights


class GameBettingMemory:
    """Track game predictions vs results for self-learning"""
    
    def __init__(self, engine=None):
        self.engine = engine
        self._ensure_table()
    
    def _ensure_table(self):
        """Create game predictions tracking table if not exists"""
        if not self.engine:
            return
            
        with self.engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS algo_game_predictions (
                    id SERIAL PRIMARY KEY,
                    game_date DATE,
                    home_team VARCHAR(10),
                    away_team VARCHAR(10),
                    prediction_type VARCHAR(20),
                    pick VARCHAR(100),
                    predicted_value FLOAT,
                    line_value FLOAT,
                    edge FLOAT,
                    confidence FLOAT,
                    home_net_rating FLOAT,
                    away_net_rating FLOAT,
                    home_form FLOAT,
                    away_form FLOAT,
                    sportsbook VARCHAR(50),
                    odds INTEGER,
                    units_bet FLOAT,
                    actual_home_score INTEGER,
                    actual_away_score INTEGER,
                    actual_value FLOAT,
                    hit BOOLEAN,
                    units_result FLOAT,
                    created_at TIMESTAMP DEFAULT NOW(),
                    graded_at TIMESTAMP,
                    UNIQUE(game_date, home_team, away_team, prediction_type)
                )
            """))
            conn.commit()
    
    def save_prediction(self, game_date, home_team, away_team, pred_type, pick,
                       predicted_value, line_value, edge, confidence,
                       home_net=None, away_net=None, home_form=None, away_form=None,
                       sportsbook=None, odds=-110, units_bet=1.0):
        """Save a game prediction for later grading"""
        if not self.engine:
            return
            
        with self.engine.connect() as conn:
            conn.execute(text("""
                INSERT INTO algo_game_predictions 
                (game_date, home_team, away_team, prediction_type, pick,
                 predicted_value, line_value, edge, confidence,
                 home_net_rating, away_net_rating, home_form, away_form,
                 sportsbook, odds, units_bet)
                VALUES (:gd, :ht, :at, :pt, :pick, :pv, :lv, :edge, :conf,
                        :hnet, :anet, :hform, :aform, :sb, :odds, :units)
                ON CONFLICT (game_date, home_team, away_team, prediction_type) 
                DO UPDATE SET 
                    pick = :pick, predicted_value = :pv, line_value = :lv,
                    edge = :edge, confidence = :conf, home_net_rating = :hnet,
                    away_net_rating = :anet, home_form = :hform, away_form = :aform,
                    sportsbook = :sb, odds = :odds, units_bet = :units, created_at = NOW()
            """), {
                'gd': game_date, 'ht': home_team, 'at': away_team,
                'pt': pred_type, 'pick': pick, 'pv': predicted_value,
                'lv': line_value, 'edge': edge, 'conf': confidence,
                'hnet': home_net, 'anet': away_net, 'hform': home_form,
                'aform': away_form, 'sb': sportsbook, 'odds': odds, 'units': units_bet
            })
            conn.commit()
    
    def grade_predictions(self, game_date=None):
        """Grade predictions against actual results"""
        if not self.engine:
            return 0
            
        with self.engine.connect() as conn:
            # Get ungraded predictions
            query = """
                SELECT p.id, p.home_team, p.away_team, p.prediction_type,
                       p.pick, p.line_value, p.odds, p.units_bet,
                       g.home_pts, g.visitor_pts
                FROM algo_game_predictions p
                JOIN games g ON p.game_date = g.date 
                    AND p.home_team = g.home_team 
                    AND p.away_team = g.visitor_team
                WHERE p.graded_at IS NULL
                AND g.home_pts IS NOT NULL
            """
            if game_date:
                query += " AND p.game_date = :gd"
                preds = conn.execute(text(query), {"gd": game_date}).fetchall()
            else:
                preds = conn.execute(text(query)).fetchall()
            
            graded = 0
            for pred in preds:
                pred_id = pred[0]
                home_team, away_team = pred[1], pred[2]
                pred_type, pick, line_value = pred[3], pred[4], pred[5]
                odds, units_bet = pred[6] or -110, pred[7] or 1.0
                home_pts, away_pts = float(pred[8]), float(pred[9])
                
                actual = None
                hit = None
                
                if pred_type == 'SPREAD':
                    actual = home_pts - away_pts  # Home margin
                    # Check if pick is on home or away
                    if home_team in pick:
                        # Home covering: home_margin > -spread (or home_margin > spread if home is dog)
                        hit = actual > -line_value
                    else:
                        # Away covering: away needs to beat spread
                        hit = actual < line_value
                        
                elif pred_type == 'TOTAL':
                    actual = home_pts + away_pts
                    if 'OVER' in pick:
                        hit = actual > line_value
                    else:
                        hit = actual < line_value
                        
                elif pred_type == 'MONEYLINE':
                    actual = home_pts - away_pts
                    if home_team in pick:
                        hit = home_pts > away_pts
                    else:
                        hit = away_pts > home_pts
                
                # Calculate units result
                if hit:
                    if odds > 0:
                        units_result = units_bet * (odds / 100)
                    else:
                        units_result = units_bet * (100 / abs(odds))
                else:
                    units_result = -units_bet
                
                # Update prediction
                conn.execute(text("""
                    UPDATE algo_game_predictions 
                    SET actual_home_score = :hs, actual_away_score = :as,
                        actual_value = :actual, hit = :hit, 
                        units_result = :units_result, graded_at = NOW()
                    WHERE id = :id
                """), {
                    "hs": int(home_pts), "as": int(away_pts),
                    "actual": actual, "hit": hit, 
                    "units_result": units_result, "id": pred_id
                })
                graded += 1
            
            conn.commit()
            return graded
    
    def get_performance_stats(self, days=30):
        """Get game betting performance statistics"""
        if not self.engine:
            return {}
            
        with self.engine.connect() as conn:
            # Overall by type
            by_type = conn.execute(text("""
                SELECT 
                    prediction_type,
                    COUNT(*) as total,
                    SUM(CASE WHEN hit = true THEN 1 ELSE 0 END) as wins,
                    SUM(units_bet) as total_units_bet,
                    SUM(units_result) as total_units_result,
                    AVG(edge) as avg_edge,
                    AVG(confidence) as avg_confidence,
                    AVG(CASE WHEN hit = true THEN edge END) as avg_winning_edge,
                    AVG(CASE WHEN hit = false THEN edge END) as avg_losing_edge
                FROM algo_game_predictions
                WHERE graded_at IS NOT NULL
                AND game_date >= CURRENT_DATE - INTERVAL :days DAY
                GROUP BY prediction_type
            """), {"days": f"{days} days"}).fetchall()
            
            # By edge threshold
            by_edge = conn.execute(text("""
                SELECT 
                    prediction_type,
                    CASE 
                        WHEN edge >= 5 THEN '5+ pts'
                        WHEN edge >= 3 THEN '3-5 pts'
                        WHEN edge >= 2 THEN '2-3 pts'
                        ELSE '<2 pts'
                    END as edge_tier,
                    COUNT(*) as total,
                    SUM(CASE WHEN hit = true THEN 1 ELSE 0 END) as wins,
                    SUM(units_result) as units_profit
                FROM algo_game_predictions
                WHERE graded_at IS NOT NULL
                AND game_date >= CURRENT_DATE - INTERVAL :days DAY
                GROUP BY prediction_type, edge_tier
                ORDER BY prediction_type, MIN(edge) DESC
            """), {"days": f"{days} days"}).fetchall()
            
            # By home/away
            home_away = conn.execute(text("""
                SELECT 
                    prediction_type,
                    CASE WHEN pick LIKE '%' || home_team || '%' THEN 'HOME' ELSE 'AWAY' END as side,
                    COUNT(*) as total,
                    SUM(CASE WHEN hit = true THEN 1 ELSE 0 END) as wins,
                    SUM(units_result) as units_profit
                FROM algo_game_predictions
                WHERE graded_at IS NOT NULL
                AND game_date >= CURRENT_DATE - INTERVAL :days DAY
                AND prediction_type IN ('SPREAD', 'MONEYLINE')
                GROUP BY prediction_type, side
            """), {"days": f"{days} days"}).fetchall()
            
            stats = {
                'by_type': {},
                'by_edge': [],
                'by_side': []
            }
            
            for row in by_type:
                pred_type = row[0]
                total = row[1]
                wins = row[2]
                stats['by_type'][pred_type] = {
                    'total': total,
                    'wins': wins,
                    'losses': total - wins,
                    'win_rate': round(wins / total * 100, 1) if total > 0 else 0,
                    'units_bet': round(row[3] or 0, 2),
                    'units_profit': round(row[4] or 0, 2),
                    'roi': round((row[4] or 0) / (row[3] or 1) * 100, 1),
                    'avg_edge': round(row[5] or 0, 1),
                    'avg_confidence': round(row[6] or 0, 1),
                    'avg_winning_edge': round(row[7] or 0, 1),
                    'avg_losing_edge': round(row[8] or 0, 1)
                }
            
            for row in by_edge:
                stats['by_edge'].append({
                    'type': row[0],
                    'tier': row[1],
                    'total': row[2],
                    'wins': row[3],
                    'win_rate': round(row[3] / row[2] * 100, 1) if row[2] > 0 else 0,
                    'units_profit': round(row[4] or 0, 2)
                })
            
            for row in home_away:
                stats['by_side'].append({
                    'type': row[0],
                    'side': row[1],
                    'total': row[2],
                    'wins': row[3],
                    'win_rate': round(row[3] / row[2] * 100, 1) if row[2] > 0 else 0,
                    'units_profit': round(row[4] or 0, 2)
                })
            
            return stats
    
    def get_insights(self):
        """Generate actionable insights from historical performance"""
        stats = self.get_performance_stats(days=60)
        insights = []
        
        # By prediction type
        for pred_type, data in stats.get('by_type', {}).items():
            if data['total'] < 10:
                continue
            
            if data['win_rate'] >= 55:
                insights.append(f"🔥 {pred_type}: {data['win_rate']}% ({data['wins']}-{data['losses']}) +{data['units_profit']}u PROFITABLE")
            elif data['win_rate'] >= 52:
                insights.append(f"📈 {pred_type}: {data['win_rate']}% ({data['wins']}-{data['losses']}) {data['units_profit']:+.1f}u")
            else:
                insights.append(f"⚠️ {pred_type}: {data['win_rate']}% ({data['wins']}-{data['losses']}) {data['units_profit']:.1f}u - NEEDS ADJUSTMENT")
            
            # Edge analysis
            if data['avg_winning_edge'] > data['avg_losing_edge'] + 1:
                insights.append(f"   💡 {pred_type}: Higher edge picks winning ({data['avg_winning_edge']:.1f} vs {data['avg_losing_edge']:.1f})")
        
        # Edge tier analysis
        for tier_data in stats.get('by_edge', []):
            if tier_data['total'] >= 5:
                if '5+ pts' in tier_data['tier'] and tier_data['win_rate'] >= 58:
                    insights.append(f"💎 {tier_data['type']} 5+ edge: {tier_data['win_rate']}% - PRIORITIZE")
                elif '<2 pts' in tier_data['tier'] and tier_data['win_rate'] < 50:
                    insights.append(f"🚫 {tier_data['type']} <2 edge: {tier_data['win_rate']}% - SKIP")
        
        # Home/Away bias
        for side_data in stats.get('by_side', []):
            if side_data['total'] >= 10:
                if side_data['win_rate'] >= 58:
                    insights.append(f"✅ {side_data['type']} {side_data['side']}: {side_data['win_rate']}% - LEAN THIS WAY")
                elif side_data['win_rate'] < 45:
                    insights.append(f"❌ {side_data['type']} {side_data['side']}: {side_data['win_rate']}% - FADE THIS")
        
        return insights
    
    def get_recommended_filters(self):
        """Based on performance, recommend minimum thresholds"""
        stats = self.get_performance_stats(days=60)
        
        recommendations = {
            'SPREAD': {'min_edge': 2.0, 'min_confidence': 60},
            'TOTAL': {'min_edge': 4.0, 'min_confidence': 60},
            'MONEYLINE': {'min_edge': 5.0, 'min_confidence': 65}
        }
        
        # Adjust based on actual performance
        for tier_data in stats.get('by_edge', []):
            pred_type = tier_data['type']
            if tier_data['total'] >= 10 and tier_data['win_rate'] >= 55:
                if '5+ pts' in tier_data['tier']:
                    recommendations[pred_type]['min_edge'] = 5.0
                elif '3-5 pts' in tier_data['tier']:
                    recommendations[pred_type]['min_edge'] = 3.0
        
        return recommendations
