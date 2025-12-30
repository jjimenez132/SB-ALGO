#!/usr/bin/env python3
"""
================================================================================
META-MERGE ENGINE v3.0 - ULTIMATE EDITION
================================================================================
The Master Orchestrator - Combines ALL engines into unified predictions

ARCHITECTURE:
-------------
┌─────────────────────────────────────────────────────────────────────┐
│                        META-MERGE ENGINE                             │
│                                                                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐  │
│  │   SPREAD     │  │    TOTAL     │  │      MONEYLINE           │  │
│  │   ENGINE     │  │    ENGINE    │  │       ENGINE             │  │
│  └──────┬───────┘  └──────┬───────┘  └───────────┬──────────────┘  │
│         │                 │                       │                 │
│         ▼                 ▼                       ▼                 │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │              HISTORICAL PATTERNS ENGINE                       │  │
│  │   • L5/L10/L15 Averages    • Matchup History                 │  │
│  │   • Trends (Hot/Cold)      • Home/Away Splits                │  │
│  │   • Consistency Scores     • Rest Impact                     │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                              │                                      │
│                              ▼                                      │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                 CORRELATION ENGINE                            │  │
│  │   • SGP Correlations       • Teammate Effects                │  │
│  │   • Player-Game Correlations                                 │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                              │                                      │
│                              ▼                                      │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                   KELLY ENGINE                                │  │
│  │   • Optimal Bet Sizing     • Risk Analysis                   │  │
│  │   • Bankroll Management                                      │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                              │                                      │
│                              ▼                                      │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                    CLV ENGINE                                 │  │
│  │   • Line Movement          • Sharp Detection                 │  │
│  │   • Bet Timing                                               │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                              │                                      │
│                              ▼                                      │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                    FINAL OUTPUT                               │  │
│  │   • Unified Predictions    • Bet Slip                        │  │
│  │   • Confidence Scores      • Risk Assessment                 │  │
│  └──────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘

OUTPUT:
-------
For each game/prop:
1. Predicted value (spread, total, probability, player stat)
2. Edge vs book line
3. Confidence score (0-100)
4. Recommended bet size (Kelly)
5. Bet grade (A+ to F)
6. Historical context
7. Correlation adjustments
8. Final recommendation

================================================================================
"""

import numpy as np
from scipy import stats
from datetime import datetime
from sqlalchemy import create_engine, text
from typing import List, Dict, Optional, Tuple
import warnings
warnings.filterwarnings('ignore')

# Import our engines
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from historical_patterns_engine import HistoricalPatternsEngine
    from correlation_engine import CorrelationEngine
    from kelly_engine import KellyEngine
    from clv_engine import CLVEngine
    ENGINES_AVAILABLE = True
except ImportError:
    ENGINES_AVAILABLE = False
    print("⚠️ Some engines not found - running in standalone mode")

# ==============================================================================
# CONFIGURATION
# ==============================================================================
DATABASE_URL = "postgresql://sb_algo_db_user:0HDtYp4EY2Lo5At8iyf44PD1zDioSPK7@dpg-d495uhchg0os738l1a50-a.virginia-postgres.render.com/sb_algo_db"

# Confidence thresholds
CONFIDENCE_THRESHOLDS = {
    'very_high': 80,    # 80%+ confidence
    'high': 70,         # 70-80%
    'moderate': 60,     # 60-70%
    'low': 50,          # 50-60%
    'very_low': 0,      # Below 50%
}

# Edge thresholds for betting
EDGE_THRESHOLDS = {
    'spread': 2.0,      # 2 point edge
    'total': 3.0,       # 3 point edge
    'moneyline': 5.0,   # 5% edge
    'prop': 8.0,        # 8% edge
}

# Weight for each factor in confidence calculation
CONFIDENCE_WEIGHTS = {
    'edge_strength': 0.30,
    'historical_consistency': 0.20,
    'trend_alignment': 0.15,
    'matchup_history': 0.15,
    'rest_advantage': 0.10,
    'home_court': 0.10,
}


class MetaMergeEngine:
    """
    ============================================================================
    META-MERGE ENGINE - The Master Orchestrator
    ============================================================================
    
    Combines all individual engines into unified, actionable predictions.
    
    This is the BRAIN of the SB-ALGO system.
    
    ============================================================================
    """
    
    def __init__(self, bankroll: float = 10000, risk_profile: str = 'moderate'):
        """
        Initialize Meta-Merge Engine with all sub-engines.
        
        Args:
            bankroll: Current bankroll for bet sizing
            risk_profile: Risk profile for Kelly calculations
        """
        self.db = create_engine(DATABASE_URL)
        self.bankroll = bankroll
        self.risk_profile = risk_profile
        
        # Initialize sub-engines
        if ENGINES_AVAILABLE:
            self.historical = HistoricalPatternsEngine()
            self.correlation = CorrelationEngine()
            self.kelly = KellyEngine(risk_profile=risk_profile)
            self.clv = CLVEngine()
        else:
            self.historical = None
            self.correlation = None
            self.kelly = None
            self.clv = None
        
        # Cache for efficiency
        self._cache = {}
    
    # ==========================================================================
    # TEAM DATA GATHERING
    # ==========================================================================
    
    def get_team_stats(self, team_name: str) -> Dict:
        """Get comprehensive team stats from database"""
        with self.db.connect() as conn:
            # Advanced stats
            adv = conn.execute(text("""
                SELECT * FROM nba_team_advanced_stats 
                WHERE "TEAM_NAME" ILIKE :team LIMIT 1
            """), {"team": f"%{team_name}%"}).fetchone()
            
            # Four factors
            ff = conn.execute(text("""
                SELECT * FROM nba_team_four_factors 
                WHERE "TEAM_NAME" ILIKE :team LIMIT 1
            """), {"team": f"%{team_name}%"}).fetchone()
            
            # Clutch
            clutch = conn.execute(text("""
                SELECT * FROM nba_team_clutch 
                WHERE "TEAM_NAME" ILIKE :team LIMIT 1
            """), {"team": f"%{team_name}%"}).fetchone()
            
            # Hustle
            hustle = conn.execute(text("""
                SELECT * FROM nba_team_hustle 
                WHERE "TEAM_NAME" ILIKE :team LIMIT 1
            """), {"team": f"%{team_name}%"}).fetchone()
            
            # Opponent stats
            opp = conn.execute(text("""
                SELECT * FROM nba_team_opponent_stats 
                WHERE "TEAM_NAME" ILIKE :team LIMIT 1
            """), {"team": f"%{team_name}%"}).fetchone()
            
            if not adv:
                return None
            
            return {
                'advanced': dict(adv._mapping) if adv else {},
                'four_factors': dict(ff._mapping) if ff else {},
                'clutch': dict(clutch._mapping) if clutch else {},
                'hustle': dict(hustle._mapping) if hustle else {},
                'opponent': dict(opp._mapping) if opp else {},
            }
    
    # ==========================================================================
    # SPREAD PREDICTION
    # ==========================================================================
    
    def predict_spread(self, home_team: str, away_team: str,
                       book_spread: float = None,
                       rest_home: int = 1, rest_away: int = 1,
                       b2b_home: bool = False, b2b_away: bool = False) -> Dict:
        """
        Generate comprehensive spread prediction.
        
        Combines:
        - Team advanced stats (net rating, pace, efficiency)
        - Four factors analysis
        - Head-to-head history
        - Rest/B2B adjustments
        - Home court advantage
        """
        home = self.get_team_stats(home_team)
        away = self.get_team_stats(away_team)
        
        if not home or not away:
            return {'error': f'Team data not found for {home_team} or {away_team}'}
        
        # =====================================================================
        # COMPONENT CALCULATIONS
        # =====================================================================
        components = {}
        
        # 1. Net Rating Edge
        home_net = home['advanced'].get('NET_RATING', 0) or 0
        away_net = away['advanced'].get('NET_RATING', 0) or 0
        components['net_rating'] = home_net - away_net
        
        # 2. Offensive/Defensive Rating
        home_off = home['advanced'].get('OFF_RATING', 110) or 110
        home_def = home['advanced'].get('DEF_RATING', 110) or 110
        away_off = away['advanced'].get('OFF_RATING', 110) or 110
        away_def = away['advanced'].get('DEF_RATING', 110) or 110
        
        # Expected scoring
        home_expected = (home_off + (220 - away_def)) / 2
        away_expected = (away_off + (220 - home_def)) / 2
        components['efficiency'] = home_expected - away_expected
        
        # 3. Four Factors
        home_efg = home['four_factors'].get('EFG_PCT', 0.5) or 0.5
        away_efg = away['four_factors'].get('EFG_PCT', 0.5) or 0.5
        home_tov = home['four_factors'].get('TM_TOV_PCT', 0.12) or 0.12
        away_tov = away['four_factors'].get('TM_TOV_PCT', 0.12) or 0.12
        
        ff_edge = ((home_efg - away_efg) * 100 + (away_tov - home_tov) * 50)
        components['four_factors'] = ff_edge
        
        # 4. Clutch Performance
        home_clutch = home['clutch'].get('PLUS_MINUS', 0) or 0
        away_clutch = away['clutch'].get('PLUS_MINUS', 0) or 0
        components['clutch'] = (home_clutch - away_clutch) / 10
        
        # 5. Pace Interaction
        home_pace = home['advanced'].get('PACE', 100) or 100
        away_pace = away['advanced'].get('PACE', 100) or 100
        game_pace = 0.48 * max(home_pace, away_pace) + 0.52 * min(home_pace, away_pace)
        components['pace'] = game_pace
        
        # 6. Rest Adjustment
        rest_adj = 0
        if b2b_home:
            rest_adj -= 3.0
        elif rest_home == 0:
            rest_adj -= 2.5
        elif rest_home >= 3:
            rest_adj += 0.8
            
        if b2b_away:
            rest_adj += 3.0
        elif rest_away == 0:
            rest_adj += 2.5
        elif rest_away >= 3:
            rest_adj -= 0.8
        components['rest'] = rest_adj
        
        # 7. Home Court Advantage (dynamic based on team strength)
        home_court = 2.5 + (home_net / 20)  # Better teams have stronger home court
        home_court = max(1.5, min(4.0, home_court))
        components['home_court'] = home_court
        
        # =====================================================================
        # HISTORICAL PATTERNS
        # =====================================================================
        h2h_adjustment = 0
        h2h_data = None
        
        if self.historical:
            try:
                h2h = self.historical.get_head_to_head(home_team, away_team, n_games=10)
                if h2h.get('h2h_games', 0) >= 3:
                    h2h_data = h2h
                    # Adjust based on historical margin
                    # If home team typically wins by more than expected, add adjustment
                    historical_margin = (h2h['team1_win_pct'] - 50) / 10
                    h2h_adjustment = historical_margin
            except:
                pass
        
        components['h2h_history'] = h2h_adjustment
        
        # =====================================================================
        # WEIGHTED COMBINATION
        # =====================================================================
        weights = {
            'net_rating': 0.30,
            'efficiency': 0.20,
            'four_factors': 0.15,
            'clutch': 0.10,
            'rest': 0.15,
            'h2h_history': 0.10,
        }
        
        weighted_edge = sum(components.get(k, 0) * v for k, v in weights.items())
        
        # Final predicted margin
        predicted_margin = weighted_edge + home_court
        predicted_spread = -predicted_margin  # Spread is inverse of margin
        
        # Standard deviation (based on pace)
        std_dev = 11.0 + (game_pace - 100) * 0.1
        
        # =====================================================================
        # EDGE VS BOOK
        # =====================================================================
        edge = 0
        cover_prob = 0.5
        ev_pct = 0
        best_bet = None
        grade = 'N/A'
        should_bet = False
        kelly_stake = 0
        
        if book_spread is not None:
            # Using Student-t for fat tails
            distribution = stats.t(df=7, loc=predicted_margin, scale=std_dev)
            cover_prob = 1 - distribution.cdf(-book_spread)
            
            edge = book_spread - predicted_spread
            
            # Determine best side
            if cover_prob > 0.5:
                best_side = 'HOME'
                best_bet = f"{home_team} {book_spread:+.1f}"
                win_prob = cover_prob
            else:
                best_side = 'AWAY'
                best_bet = f"{away_team} {-book_spread:+.1f}"
                win_prob = 1 - cover_prob
            
            # EV at standard -110
            ev_pct = (win_prob * 0.909) - ((1 - win_prob) * 1)
            ev_pct *= 100
            
            # Kelly sizing
            if self.kelly and win_prob > 0.52:
                kelly_result = self.kelly.calculate_bet(win_prob, -110, self.bankroll)
                if kelly_result.get('should_bet'):
                    kelly_stake = kelly_result['recommended_amount']
                    grade = kelly_result['grade']
                    should_bet = True
        
        # =====================================================================
        # CONFIDENCE SCORE
        # =====================================================================
        confidence = self._calculate_confidence(
            edge=abs(edge) if book_spread else 0,
            edge_threshold=EDGE_THRESHOLDS['spread'],
            cover_prob=max(cover_prob, 1 - cover_prob),
            has_h2h=h2h_data is not None,
            rest_advantage=abs(rest_adj) > 1,
        )
        
        return {
            'type': 'SPREAD',
            'home_team': home_team,
            'away_team': away_team,
            'matchup': f"{away_team} @ {home_team}",
            
            # Prediction
            'predicted_margin': round(predicted_margin, 2),
            'predicted_spread': round(predicted_spread, 1),
            'std_dev': round(std_dev, 2),
            'game_pace': round(game_pace, 1),
            
            # Book comparison
            'book_spread': book_spread,
            'edge_points': round(edge, 1) if book_spread else None,
            'cover_probability': round(cover_prob, 4),
            'ev_pct': round(ev_pct, 2),
            
            # Recommendation
            'best_bet': best_bet,
            'should_bet': should_bet,
            'grade': grade,
            'kelly_stake': round(kelly_stake, 2),
            'confidence': confidence['score'],
            'confidence_level': confidence['level'],
            
            # Components
            'components': {k: round(v, 2) for k, v in components.items()},
            
            # Historical
            'h2h_data': h2h_data,
        }
    
    # ==========================================================================
    # TOTAL PREDICTION
    # ==========================================================================
    
    def predict_total(self, home_team: str, away_team: str,
                      book_total: float = None,
                      rest_home: int = 1, rest_away: int = 1) -> Dict:
        """
        Generate comprehensive total (over/under) prediction.
        """
        home = self.get_team_stats(home_team)
        away = self.get_team_stats(away_team)
        
        if not home or not away:
            return {'error': f'Team data not found'}
        
        # Pace
        home_pace = home['advanced'].get('PACE', 100) or 100
        away_pace = away['advanced'].get('PACE', 100) or 100
        game_pace = 0.48 * max(home_pace, away_pace) + 0.52 * min(home_pace, away_pace)
        
        # Expected possessions
        expected_possessions = game_pace * 0.96  # 48 minutes
        
        # Efficiency
        home_off = home['advanced'].get('OFF_RATING', 110) or 110
        home_def = home['advanced'].get('DEF_RATING', 110) or 110
        away_off = away['advanced'].get('OFF_RATING', 110) or 110
        away_def = away['advanced'].get('DEF_RATING', 110) or 110
        
        # Points per 100 possessions, scaled
        home_pts = expected_possessions * (home_off + (220 - away_def)) / 200
        away_pts = expected_possessions * (away_off + (220 - home_def)) / 200
        
        predicted_total = home_pts + away_pts
        
        # Adjustments
        # 3-point variance
        home_3pa = 35  # Default
        away_3pa = 35
        three_pt_factor = (home_3pa + away_3pa) / 70
        
        # Rest impact
        rest_adj = 0
        if rest_home == 0 or rest_away == 0:
            rest_adj -= 3
        
        predicted_total += rest_adj
        
        # Standard deviation
        std_dev = 9.5 * three_pt_factor
        
        # Edge vs book
        edge = 0
        over_prob = 0.5
        ev_pct = 0
        best_bet = None
        should_bet = False
        kelly_stake = 0
        grade = 'N/A'
        
        if book_total is not None:
            distribution = stats.norm(loc=predicted_total, scale=std_dev)
            over_prob = 1 - distribution.cdf(book_total)
            edge = predicted_total - book_total
            
            if over_prob > 0.5:
                best_bet = f"OVER {book_total}"
                win_prob = over_prob
            else:
                best_bet = f"UNDER {book_total}"
                win_prob = 1 - over_prob
            
            ev_pct = (win_prob * 0.909) - ((1 - win_prob) * 1)
            ev_pct *= 100
            
            if self.kelly and win_prob > 0.52:
                kelly_result = self.kelly.calculate_bet(win_prob, -110, self.bankroll)
                if kelly_result.get('should_bet'):
                    kelly_stake = kelly_result['recommended_amount']
                    grade = kelly_result['grade']
                    should_bet = True
        
        confidence = self._calculate_confidence(
            edge=abs(edge) if book_total else 0,
            edge_threshold=EDGE_THRESHOLDS['total'],
            cover_prob=max(over_prob, 1 - over_prob),
        )
        
        return {
            'type': 'TOTAL',
            'home_team': home_team,
            'away_team': away_team,
            'matchup': f"{away_team} @ {home_team}",
            
            'predicted_total': round(predicted_total, 1),
            'home_projected': round(home_pts, 1),
            'away_projected': round(away_pts, 1),
            'std_dev': round(std_dev, 2),
            'game_pace': round(game_pace, 1),
            
            'book_total': book_total,
            'edge_points': round(edge, 1) if book_total else None,
            'over_probability': round(over_prob, 4),
            'under_probability': round(1 - over_prob, 4),
            'ev_pct': round(ev_pct, 2),
            
            'best_bet': best_bet,
            'should_bet': should_bet,
            'grade': grade,
            'kelly_stake': round(kelly_stake, 2),
            'confidence': confidence['score'],
            'confidence_level': confidence['level'],
        }
    
    # ==========================================================================
    # PLAYER PROP PREDICTION
    # ==========================================================================
    
    def predict_player_prop(self, player_name: str, stat: str,
                            book_line: float, opponent: str = None) -> Dict:
        """
        Generate comprehensive player prop prediction.
        
        Uses historical patterns engine for:
        - L5/L10/L15/Season averages
        - Matchup-specific history
        - Trend detection
        - Consistency analysis
        """
        if not self.historical:
            return {'error': 'Historical engine not available'}
        
        # Get weighted projection
        projection = self.historical.get_weighted_projection(player_name, stat)
        
        if 'error' in projection:
            return projection
        
        # Get full averages
        averages = self.historical.get_player_averages(player_name)
        
        # Get trend
        trend = self.historical.detect_player_trend(player_name, stat)
        
        # Get consistency
        consistency = self.historical.get_player_consistency(player_name)
        
        # Matchup adjustment
        matchup_adj = 0
        matchup_data = None
        if opponent:
            try:
                matchup = self.historical.get_player_vs_team_comparison(player_name, opponent)
                if 'adjustments' in matchup and stat in matchup['adjustments']:
                    adj = matchup['adjustments'][stat]
                    matchup_adj = adj['difference']
                    matchup_data = adj
            except:
                pass
        
        # Final projection
        base_projection = projection['projection']
        adjusted_projection = base_projection + matchup_adj
        
        # Standard deviation
        std_dev = projection['std_dev']
        if std_dev == 0:
            std_dev = base_projection * 0.25  # Fallback: 25% of mean
        
        # Probability calculation
        distribution = stats.norm(loc=adjusted_projection, scale=std_dev)
        over_prob = 1 - distribution.cdf(book_line)
        
        # Edge
        edge = adjusted_projection - book_line
        edge_pct = (edge / book_line) * 100 if book_line > 0 else 0
        
        # Best bet
        if over_prob > 0.5:
            best_bet = f"OVER {book_line}"
            win_prob = over_prob
        else:
            best_bet = f"UNDER {book_line}"
            win_prob = 1 - over_prob
        
        # EV
        ev_pct = (win_prob * 0.909) - ((1 - win_prob) * 1)
        ev_pct *= 100
        
        # Kelly
        should_bet = False
        kelly_stake = 0
        grade = 'N/A'
        
        if self.kelly and win_prob > 0.52:
            kelly_result = self.kelly.calculate_bet(win_prob, -110, self.bankroll)
            if kelly_result.get('should_bet'):
                kelly_stake = kelly_result['recommended_amount']
                grade = kelly_result['grade']
                should_bet = True
        
        # Confidence
        consistency_score = consistency.get('consistency_scores', {}).get(stat, {}).get('consistency_score', 50)
        confidence = self._calculate_prop_confidence(
            edge_pct=abs(edge_pct),
            win_prob=max(over_prob, 1 - over_prob),
            consistency=consistency_score,
            has_matchup=matchup_data is not None,
            trend=trend.get('trend', 'STABLE'),
        )
        
        return {
            'type': 'PLAYER_PROP',
            'player': projection['player'],
            'stat': stat,
            'opponent': opponent,
            
            # Projection
            'base_projection': round(base_projection, 2),
            'matchup_adjustment': round(matchup_adj, 2),
            'final_projection': round(adjusted_projection, 2),
            'std_dev': round(std_dev, 2),
            
            # Components
            'last_5': projection['components'].get('last_5'),
            'last_10': projection['components'].get('last_10'),
            'season': projection['components'].get('season'),
            
            # Book comparison
            'book_line': book_line,
            'edge': round(edge, 2),
            'edge_pct': round(edge_pct, 2),
            'over_probability': round(over_prob, 4),
            'under_probability': round(1 - over_prob, 4),
            'ev_pct': round(ev_pct, 2),
            
            # Recommendation
            'best_bet': best_bet,
            'should_bet': should_bet,
            'grade': grade,
            'kelly_stake': round(kelly_stake, 2),
            'confidence': confidence['score'],
            'confidence_level': confidence['level'],
            
            # Context
            'trend': trend.get('trend', 'UNKNOWN'),
            'trend_interpretation': trend.get('interpretation', ''),
            'consistency_score': round(consistency_score, 1),
            'matchup_data': matchup_data,
        }
    
    # ==========================================================================
    # FULL GAME ANALYSIS
    # ==========================================================================
    
    def analyze_full_game(self, home_team: str, away_team: str,
                          book_spread: float = None,
                          book_total: float = None,
                          home_ml: int = None,
                          away_ml: int = None,
                          rest_home: int = 1, rest_away: int = 1,
                          b2b_home: bool = False, b2b_away: bool = False) -> Dict:
        """
        Complete game analysis combining spread, total, and moneyline.
        """
        # Spread prediction
        spread_pred = self.predict_spread(
            home_team, away_team, book_spread,
            rest_home, rest_away, b2b_home, b2b_away
        )
        
        # Total prediction
        total_pred = self.predict_total(
            home_team, away_team, book_total,
            rest_home, rest_away
        )
        
        # Moneyline from spread
        if spread_pred.get('predicted_margin'):
            margin = spread_pred['predicted_margin']
            std_dev = spread_pred['std_dev']
            distribution = stats.t(df=7, loc=margin, scale=std_dev)
            home_win_prob = 1 - distribution.cdf(0)
        else:
            home_win_prob = 0.5
        
        # ML analysis
        ml_edge = None
        ml_ev = 0
        ml_best_bet = None
        
        if home_ml and away_ml:
            if home_ml > 0:
                home_implied = 100 / (home_ml + 100)
            else:
                home_implied = abs(home_ml) / (abs(home_ml) + 100)
            
            ml_edge = (home_win_prob - home_implied) * 100
            
            if ml_edge > 0:
                ml_best_bet = f"{home_team} ML ({home_ml:+d})"
                ml_win_prob = home_win_prob
            else:
                ml_best_bet = f"{away_team} ML ({away_ml:+d})"
                ml_win_prob = 1 - home_win_prob
                ml_edge = abs(ml_edge)
        
        # Collect value picks
        picks = []
        
        if spread_pred.get('should_bet'):
            picks.append({
                'type': 'SPREAD',
                'pick': spread_pred['best_bet'],
                'edge': spread_pred['edge_points'],
                'ev_pct': spread_pred['ev_pct'],
                'confidence': spread_pred['confidence'],
                'grade': spread_pred['grade'],
                'stake': spread_pred['kelly_stake'],
            })
        
        if total_pred.get('should_bet'):
            picks.append({
                'type': 'TOTAL',
                'pick': total_pred['best_bet'],
                'edge': total_pred['edge_points'],
                'ev_pct': total_pred['ev_pct'],
                'confidence': total_pred['confidence'],
                'grade': total_pred['grade'],
                'stake': total_pred['kelly_stake'],
            })
        
        if ml_edge and ml_edge >= EDGE_THRESHOLDS['moneyline']:
            picks.append({
                'type': 'MONEYLINE',
                'pick': ml_best_bet,
                'edge': round(ml_edge, 1),
                'ev_pct': round((ml_win_prob * 0.909 - (1-ml_win_prob)) * 100, 2),
                'confidence': 70,
                'grade': 'B+',
                'stake': 0,
            })
        
        return {
            'game': f"{away_team} @ {home_team}",
            'spread': spread_pred,
            'total': total_pred,
            'moneyline': {
                'home_win_prob': round(home_win_prob, 4),
                'away_win_prob': round(1 - home_win_prob, 4),
                'edge_pct': round(ml_edge, 2) if ml_edge else None,
                'best_bet': ml_best_bet,
            },
            'picks': picks,
            'has_value': len(picks) > 0,
            'total_stake': sum(p.get('stake', 0) for p in picks),
        }
    
    # ==========================================================================
    # BET SLIP GENERATION
    # ==========================================================================
    
    def generate_bet_slip(self, analyses: List[Dict]) -> Dict:
        """
        Generate optimized bet slip from multiple game analyses.
        
        Args:
            analyses: List of analyze_full_game results
            
        Returns:
            Optimized bet slip with sizing
        """
        all_picks = []
        
        for analysis in analyses:
            if analysis.get('picks'):
                for pick in analysis['picks']:
                    pick['game'] = analysis['game']
                    all_picks.append(pick)
        
        if not all_picks:
            return {
                'bets': [],
                'total_stake': 0,
                'message': 'No value picks found',
            }
        
        # Sort by EV
        all_picks.sort(key=lambda x: x.get('ev_pct', 0), reverse=True)
        
        # Optimize with Kelly
        if self.kelly:
            bets_for_kelly = [
                {
                    'win_prob': 0.52 + p.get('ev_pct', 0) / 200,  # Approximate
                    'american_odds': -110,
                    'description': f"{p['game']} - {p['pick']}",
                }
                for p in all_picks if p.get('ev_pct', 0) > 0
            ]
            
            if bets_for_kelly:
                multi_kelly = self.kelly.calculate_simultaneous_bets(bets_for_kelly, self.bankroll)
                
                # Map back to picks
                for i, bet in enumerate(multi_kelly.get('bets', [])):
                    if i < len(all_picks):
                        all_picks[i]['optimized_stake'] = bet.get('stake', 0)
        
        # Build final bet slip
        bets = []
        total_stake = 0
        
        for pick in all_picks:
            stake = pick.get('optimized_stake', pick.get('stake', 0))
            if stake > 0:
                total_stake += stake
                bets.append({
                    'game': pick['game'],
                    'type': pick['type'],
                    'pick': pick['pick'],
                    'edge': pick.get('edge'),
                    'ev_pct': pick.get('ev_pct'),
                    'grade': pick.get('grade'),
                    'confidence': pick.get('confidence'),
                    'stake': round(stake, 2),
                })
        
        return {
            'generated_at': datetime.now().isoformat(),
            'bankroll': self.bankroll,
            'num_bets': len(bets),
            'total_stake': round(total_stake, 2),
            'total_stake_pct': round(total_stake / self.bankroll * 100, 2),
            'avg_ev': round(np.mean([b['ev_pct'] for b in bets]), 2) if bets else 0,
            'bets': bets,
        }
    
    # ==========================================================================
    # CONFIDENCE CALCULATIONS
    # ==========================================================================
    
    def _calculate_confidence(self, edge: float, edge_threshold: float,
                              cover_prob: float, has_h2h: bool = False,
                              rest_advantage: bool = False) -> Dict:
        """Calculate confidence score (0-100)"""
        score = 50  # Base
        
        # Edge contribution (up to 25 points)
        if edge > 0:
            edge_score = min(25, (edge / edge_threshold) * 15)
            score += edge_score
        
        # Probability contribution (up to 25 points)
        prob_score = (cover_prob - 0.5) * 50
        score += prob_score
        
        # H2H bonus
        if has_h2h:
            score += 5
        
        # Rest bonus
        if rest_advantage:
            score += 5
        
        score = max(0, min(100, score))
        
        level = 'VERY_HIGH' if score >= 80 else \
                'HIGH' if score >= 70 else \
                'MODERATE' if score >= 60 else \
                'LOW' if score >= 50 else 'VERY_LOW'
        
        return {'score': round(score, 1), 'level': level}
    
    def _calculate_prop_confidence(self, edge_pct: float, win_prob: float,
                                   consistency: float, has_matchup: bool,
                                   trend: str) -> Dict:
        """Calculate confidence for player props"""
        score = 50
        
        # Edge contribution
        score += min(15, edge_pct / 2)
        
        # Probability contribution
        score += (win_prob - 0.5) * 40
        
        # Consistency bonus
        score += (consistency - 50) / 10
        
        # Matchup bonus
        if has_matchup:
            score += 5
        
        # Trend alignment
        if trend in ['HOT_STREAK', 'TRENDING_UP']:
            score += 3
        elif trend in ['COLD_STREAK', 'TRENDING_DOWN']:
            score -= 3
        
        score = max(0, min(100, score))
        
        level = 'VERY_HIGH' if score >= 80 else \
                'HIGH' if score >= 70 else \
                'MODERATE' if score >= 60 else \
                'LOW' if score >= 50 else 'VERY_LOW'
        
        return {'score': round(score, 1), 'level': level}


# ==============================================================================
# TEST SUITE
# ==============================================================================
if __name__ == "__main__":
    print("=" * 80)
    print("META-MERGE ENGINE v3.0 - COMPREHENSIVE TEST")
    print("=" * 80)
    
    engine = MetaMergeEngine(bankroll=10000, risk_profile='moderate')
    
    # -------------------------------------------------------------------------
    # Test 1: Spread Prediction
    # -------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("TEST 1: SPREAD PREDICTION")
    print("=" * 80)
    
    spread = engine.predict_spread("Celtics", "Lakers", book_spread=-8.5)
    
    if 'error' not in spread:
        print(f"\n  🏀 {spread['matchup']}")
        print(f"\n  📊 PREDICTION")
        print(f"     Predicted Margin: {spread['predicted_margin']:+.1f}")
        print(f"     Predicted Spread: {spread['predicted_spread']}")
        print(f"     Std Dev: {spread['std_dev']}")
        
        print(f"\n  📈 VS BOOK")
        print(f"     Book Spread: {spread['book_spread']}")
        print(f"     Edge: {spread['edge_points']} points")
        print(f"     Cover Prob: {spread['cover_probability']*100:.1f}%")
        print(f"     EV: {spread['ev_pct']:.1f}%")
        
        print(f"\n  🎯 RECOMMENDATION")
        print(f"     Best Bet: {spread['best_bet']}")
        print(f"     Grade: {spread['grade']}")
        print(f"     Stake: ${spread['kelly_stake']:.0f}")
        print(f"     Confidence: {spread['confidence']} ({spread['confidence_level']})")
    
    # -------------------------------------------------------------------------
    # Test 2: Total Prediction
    # -------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("TEST 2: TOTAL PREDICTION")
    print("=" * 80)
    
    total = engine.predict_total("Thunder", "Cavaliers", book_total=228.5)
    
    if 'error' not in total:
        print(f"\n  🏀 {total['matchup']}")
        print(f"\n  📊 PREDICTION")
        print(f"     Predicted Total: {total['predicted_total']}")
        print(f"     Home Projected: {total['home_projected']}")
        print(f"     Away Projected: {total['away_projected']}")
        
        print(f"\n  📈 VS BOOK")
        print(f"     Book Total: {total['book_total']}")
        print(f"     Edge: {total['edge_points']} points")
        print(f"     Over Prob: {total['over_probability']*100:.1f}%")
        
        print(f"\n  🎯 RECOMMENDATION")
        print(f"     Best Bet: {total['best_bet']}")
        print(f"     Confidence: {total['confidence']} ({total['confidence_level']})")
    
    # -------------------------------------------------------------------------
    # Test 3: Player Prop
    # -------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("TEST 3: PLAYER PROP PREDICTION")
    print("=" * 80)
    
    if ENGINES_AVAILABLE:
        prop = engine.predict_player_prop("LeBron James", "pts", 25.5, opponent="BOS")
        
        if 'error' not in prop:
            print(f"\n  🏀 {prop['player']} {prop['stat'].upper()} vs {prop['opponent']}")
            print(f"\n  📊 PROJECTION")
            print(f"     Base: {prop['base_projection']}")
            print(f"     Matchup Adj: {prop['matchup_adjustment']:+.1f}")
            print(f"     Final: {prop['final_projection']}")
            
            print(f"\n  📈 VS BOOK")
            print(f"     Book Line: {prop['book_line']}")
            print(f"     Edge: {prop['edge']:+.1f} ({prop['edge_pct']:+.1f}%)")
            print(f"     Over Prob: {prop['over_probability']*100:.1f}%")
            
            print(f"\n  🎯 RECOMMENDATION")
            print(f"     Best Bet: {prop['best_bet']}")
            print(f"     Grade: {prop['grade']}")
            print(f"     Confidence: {prop['confidence']} ({prop['confidence_level']})")
            
            print(f"\n  📋 CONTEXT")
            print(f"     Trend: {prop['trend']}")
            print(f"     Consistency: {prop['consistency_score']}")
    
    # -------------------------------------------------------------------------
    # Test 4: Full Game Analysis
    # -------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("TEST 4: FULL GAME ANALYSIS")
    print("=" * 80)
    
    full = engine.analyze_full_game(
        "Celtics", "Lakers",
        book_spread=-8.5,
        book_total=224.5,
        home_ml=-350,
        away_ml=280
    )
    
    print(f"\n  🏀 {full['game']}")
    print(f"\n  📊 PREDICTIONS")
    print(f"     Spread: {full['spread']['predicted_spread']} (Book: {full['spread']['book_spread']})")
    print(f"     Total: {full['total']['predicted_total']} (Book: {full['total']['book_total']})")
    print(f"     Home Win: {full['moneyline']['home_win_prob']*100:.1f}%")
    
    if full['picks']:
        print(f"\n  🎯 VALUE PICKS:")
        for pick in full['picks']:
            print(f"     {pick['type']}: {pick['pick']} | Edge: {pick['edge']} | Grade: {pick['grade']}")
    else:
        print(f"\n  ❌ No value picks found")
    
    # -------------------------------------------------------------------------
    # Test 5: Bet Slip
    # -------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("TEST 5: BET SLIP GENERATION")
    print("=" * 80)
    
    # Analyze multiple games
    games = [
        engine.analyze_full_game("Celtics", "Lakers", -8.5, 224.5, -350, 280),
        engine.analyze_full_game("Thunder", "Cavaliers", -2.5, 228.0, -150, 130),
        engine.analyze_full_game("Knicks", "Heat", -4.0, 212.5, -180, 155),
    ]
    
    bet_slip = engine.generate_bet_slip(games)
    
    print(f"\n  💰 BET SLIP")
    print(f"     Bankroll: ${bet_slip['bankroll']:,}")
    print(f"     Total Bets: {bet_slip['num_bets']}")
    print(f"     Total Stake: ${bet_slip['total_stake']:.0f} ({bet_slip['total_stake_pct']:.1f}%)")
    print(f"     Average EV: {bet_slip['avg_ev']:.1f}%")
    
    if bet_slip['bets']:
        print(f"\n  📋 BETS:")
        for bet in bet_slip['bets']:
            print(f"     ${bet['stake']:.0f} | {bet['game']} | {bet['pick']} | Grade: {bet['grade']}")
    
    # -------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("✅ META-MERGE ENGINE v3.0 - ALL TESTS COMPLETE")
    print("=" * 80)
