#!/usr/bin/env python3
"""
================================================================================
META-MERGE ENGINE v4.0 - ULTIMATE EDITION
================================================================================
The Master Orchestrator - Now with Injury, Calibration, and Uncertainty!

ARCHITECTURE v4.0:
------------------
┌─────────────────────────────────────────────────────────────────────────────┐
│                         META-MERGE ENGINE v4.0                               │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                    UNCERTAINTY ENGINE                                │    │
│  │   Detects: HIGH_VARIANCE / UNSTABLE / AVOID regimes                 │    │
│  │   Output: Kelly multiplier, confidence adjustments                   │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                    │                                         │
│                                    ▼                                         │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                      INJURY ENGINE                                   │    │
│  │   Parses: injuries from news, manual input                          │    │
│  │   Output: spread adjustment, prop boosts, confidence penalty        │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                    │                                         │
│                                    ▼                                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────────┐       │
│  │   SPREAD     │  │    TOTAL     │  │      PLAYER PROP             │       │
│  │   ENGINE     │  │    ENGINE    │  │       ENGINE                 │       │
│  └──────┬───────┘  └──────┬───────┘  └───────────┬──────────────────┘       │
│         │                 │                       │                          │
│         └─────────────────┼───────────────────────┘                          │
│                           ▼                                                  │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                 HISTORICAL PATTERNS ENGINE                           │    │
│  │   L5/L10/L15 Averages, Matchup History, Trends, H2H                 │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                           │                                                  │
│                           ▼                                                  │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                   CALIBRATION ENGINE                                 │    │
│  │   Adjusts: raw probabilities → calibrated probabilities             │    │
│  │   Output: Kelly-safe probabilities, reliability metrics             │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                           │                                                  │
│                           ▼                                                  │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                     KELLY ENGINE                                     │    │
│  │   Calculates: optimal bet sizing with calibrated probabilities      │    │
│  │   Output: stake amounts, grades, risk analysis                      │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                           │                                                  │
│                           ▼                                                  │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                       CLV ENGINE                                     │    │
│  │   Tracks: line movement, sharp action, optimal timing              │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                           │                                                  │
│                           ▼                                                  │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                      FINAL OUTPUT                                    │    │
│  │   • Unified predictions with injury adjustments                     │    │
│  │   • Calibrated confidence scores                                    │    │
│  │   • Regime-adjusted Kelly stakes                                    │    │
│  │   • Optimized bet slip                                              │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘

================================================================================
"""

import numpy as np
from scipy import stats
from datetime import datetime
from sqlalchemy import create_engine, text
from typing import List, Dict, Optional, Tuple
import warnings
warnings.filterwarnings('ignore')

# Import engines
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

ENGINES_AVAILABLE = {
    'historical': False,
    'correlation': False,
    'kelly': False,
    'clv': False,
    'injury': False,
    'calibration': False,
    'uncertainty': False,
}

try:
    from historical_patterns_engine import HistoricalPatternsEngine
    ENGINES_AVAILABLE['historical'] = True
except ImportError:
    pass

try:
    from correlation_engine import CorrelationEngine
    ENGINES_AVAILABLE['correlation'] = True
except ImportError:
    pass

try:
    from kelly_engine import KellyEngine
    ENGINES_AVAILABLE['kelly'] = True
except ImportError:
    pass

try:
    from clv_engine import CLVEngine
    ENGINES_AVAILABLE['clv'] = True
except ImportError:
    pass

try:
    from injury_engine import InjuryEngine
    ENGINES_AVAILABLE['injury'] = True
except ImportError:
    pass

try:
    from calibration_engine import CalibrationEngine
    ENGINES_AVAILABLE['calibration'] = True
except ImportError:
    pass

try:
    from uncertainty_engine import UncertaintyEngine
    ENGINES_AVAILABLE['uncertainty'] = True
except ImportError:
    pass

# ==============================================================================
# CONFIGURATION
# ==============================================================================
DATABASE_URL = "postgresql://sb_algo_db_user:0HDtYp4EY2Lo5At8iyf44PD1zDioSPK7@dpg-d495uhchg0os738l1a50-a.virginia-postgres.render.com/sb_algo_db"

# Edge thresholds for betting
EDGE_THRESHOLDS = {
    'spread': 2.0,
    'total': 3.0,
    'moneyline': 5.0,
    'prop': 8.0,
}


class MetaMergeEngine:
    """
    ============================================================================
    META-MERGE ENGINE v4.0 - The Ultimate Orchestrator
    ============================================================================
    """
    
    def __init__(self, bankroll: float = 10000, risk_profile: str = 'moderate'):
        self.db = create_engine(DATABASE_URL)
        self.bankroll = bankroll
        self.risk_profile = risk_profile
        
        # Initialize all engines
        self.historical = HistoricalPatternsEngine() if ENGINES_AVAILABLE['historical'] else None
        self.correlation = CorrelationEngine() if ENGINES_AVAILABLE['correlation'] else None
        self.kelly = KellyEngine(risk_profile=risk_profile) if ENGINES_AVAILABLE['kelly'] else None
        self.clv = CLVEngine() if ENGINES_AVAILABLE['clv'] else None
        self.injury = InjuryEngine() if ENGINES_AVAILABLE['injury'] else None
        self.calibration = CalibrationEngine() if ENGINES_AVAILABLE['calibration'] else None
        self.uncertainty = UncertaintyEngine() if ENGINES_AVAILABLE['uncertainty'] else None
        
        print(f"🔧 Meta-Merge Engine v4.0 initialized")
        print(f"   Engines loaded: {sum(ENGINES_AVAILABLE.values())}/7")
        for name, loaded in ENGINES_AVAILABLE.items():
            status = "✅" if loaded else "❌"
            print(f"   {status} {name}")
    
    # ==========================================================================
    # TEAM DATA
    # ==========================================================================
    
    def get_team_stats(self, team_name: str) -> Dict:
        """Get COMPREHENSIVE team stats from ALL available tables"""
        # Team abbreviation to full name mapping
        TEAM_MAP = {
            'ATL': 'Atlanta Hawks', 'BOS': 'Boston Celtics', 'BKN': 'Brooklyn Nets',
            'CHA': 'Charlotte Hornets', 'CHI': 'Chicago Bulls', 'CLE': 'Cleveland Cavaliers',
            'DAL': 'Dallas Mavericks', 'DEN': 'Denver Nuggets', 'DET': 'Detroit Pistons',
            'GS': 'Golden State Warriors', 'GSW': 'Golden State Warriors',
            'HOU': 'Houston Rockets', 'IND': 'Indiana Pacers',
            'LAC': 'LA Clippers', 'LAL': 'Los Angeles Lakers',
            'MEM': 'Memphis Grizzlies', 'MIA': 'Miami Heat', 'MIL': 'Milwaukee Bucks',
            'MIN': 'Minnesota Timberwolves', 'NO': 'New Orleans Pelicans',
            'NOP': 'New Orleans Pelicans', 'NY': 'New York Knicks', 'NYK': 'New York Knicks',
            'OKC': 'Oklahoma City Thunder', 'ORL': 'Orlando Magic',
            'PHI': 'Philadelphia 76ers', 'PHX': 'Phoenix Suns',
            'POR': 'Portland Trail Blazers', 'SAC': 'Sacramento Kings',
            'SA': 'San Antonio Spurs', 'SAS': 'San Antonio Spurs',
            'TOR': 'Toronto Raptors', 'UTA': 'Utah Jazz', 'WAS': 'Washington Wizards',
        }
        
        full_name = TEAM_MAP.get(team_name.upper(), team_name)
        result = {}
        
        with self.db.connect() as conn:
            # 1. Advanced Stats (pace, ratings)
            adv = conn.execute(text("""
                SELECT * FROM nba_team_advanced_stats
                WHERE "TEAM_NAME" ILIKE :team ORDER BY pull_date DESC LIMIT 1
            """), {"team": f"%{full_name}%"}).fetchone()
            if adv:
                result['advanced'] = dict(adv._mapping)
            
            # 2. Four Factors (Dean Oliver's keys to winning)
            ff = conn.execute(text("""
                SELECT * FROM nba_team_four_factors
                WHERE "TEAM_NAME" ILIKE :team ORDER BY pull_date DESC LIMIT 1
            """), {"team": f"%{full_name}%"}).fetchone()
            if ff:
                result['four_factors'] = dict(ff._mapping)
            
            # 3. Opponent Stats (defensive performance)
            opp = conn.execute(text("""
                SELECT * FROM nba_team_opponent_stats
                WHERE "TEAM_NAME" ILIKE :team ORDER BY pull_date DESC LIMIT 1
            """), {"team": f"%{full_name}%"}).fetchone()
            if opp:
                result['opponent'] = dict(opp._mapping)
            
            # 4. Clutch Stats (close game performance)
            clutch = conn.execute(text("""
                SELECT * FROM nba_team_clutch
                WHERE "TEAM_NAME" ILIKE :team ORDER BY pull_date DESC LIMIT 1
            """), {"team": f"%{full_name}%"}).fetchone()
            if clutch:
                result['clutch'] = dict(clutch._mapping)
            
            # 5. Hustle Stats (effort metrics)
            hustle = conn.execute(text("""
                SELECT * FROM nba_team_hustle
                WHERE "TEAM_NAME" ILIKE :team ORDER BY pull_date DESC LIMIT 1
            """), {"team": f"%{full_name}%"}).fetchone()
            if hustle:
                result['hustle'] = dict(hustle._mapping)
            
            # 6. Base Stats 
            base = conn.execute(text("""
                SELECT * FROM nba_team_base_stats
                WHERE "TEAM_NAME" ILIKE :team ORDER BY pull_date DESC LIMIT 1
            """), {"team": f"%{full_name}%"}).fetchone()
            if base:
                result['base'] = dict(base._mapping)
            
            # 7. Scoring breakdown
            scoring = conn.execute(text("""
                SELECT * FROM nba_team_scoring
                WHERE "TEAM_NAME" ILIKE :team ORDER BY pull_date DESC LIMIT 1
            """), {"team": f"%{full_name}%"}).fetchone()
            if scoring:
                result['scoring'] = dict(scoring._mapping)

            
            # 9. Derived Team Stats
            derived = conn.execute(text("""
                SELECT * FROM nba_derived_team_stats
                WHERE "TEAM_ABBREVIATION" ILIKE :team ORDER BY pull_date DESC LIMIT 1
            """), {"team": f"%{full_name.split()[-1]}%"}).fetchone()
            if derived:
                result['derived'] = dict(derived._mapping)
        
        return result if result.get('advanced') else None

    # ==========================================================================
    # FULL GAME PREDICTION v4.0
    # ==========================================================================
    
    def predict_game(self, home_team: str, away_team: str,
                     book_spread: float = None,
                     book_total: float = None,
                     home_ml: int = None,
                     away_ml: int = None,
                     injuries_home: List[Dict] = None,
                     injuries_away: List[Dict] = None,
                     b2b_home: bool = False,
                     b2b_away: bool = False,
                     spread_odds: int = -110,
                     over_odds: int = -110,
                     under_odds: int = -110) -> Dict:
        """
        Complete game prediction with all engines integrated.
        
        This is the MAIN function that orchestrates everything.
        """
        result = {
            'matchup': f"{away_team} @ {home_team}",
            'timestamp': datetime.now().isoformat(),
            'engines_used': [],
        }
        
        # =====================================================================
        # STEP 1: UNCERTAINTY/REGIME CHECK
        # =====================================================================
        regime_data = None
        kelly_multiplier = 1.0
        
        if self.uncertainty:
            regime_data = self.uncertainty.detect_regime(
                home_team, away_team,
                injuries_home=len(injuries_home) if injuries_home else 0,
                injuries_away=len(injuries_away) if injuries_away else 0,
                b2b_home=b2b_home,
                b2b_away=b2b_away,
            )
            kelly_multiplier = regime_data['kelly_multiplier']
            result['regime'] = {
                'status': regime_data['regime'],
                'confidence': regime_data['confidence_pct'],
                'kelly_multiplier': kelly_multiplier,
                'warnings': regime_data['warnings'],
            }
            result['engines_used'].append('uncertainty')
        
        # =====================================================================
        # STEP 2: INJURY ANALYSIS
        # =====================================================================
        injury_spread_adj = 0
        injury_total_adj = 0
        injury_confidence_penalty = 0
        
        if self.injury:
            injury_analysis = self.injury.analyze_game_injuries(home_team, away_team)
            injury_spread_adj = injury_analysis['net_spread_adjustment']
            injury_total_adj = injury_analysis['net_total_adjustment']
            injury_confidence_penalty = injury_analysis['combined_confidence_penalty']
            
            result['injuries'] = {
                'spread_adjustment': injury_spread_adj,
                'total_adjustment': injury_total_adj,
                'confidence_penalty': injury_confidence_penalty,
                'edge_for': injury_analysis['edge_for'],
            }
            result['engines_used'].append('injury')
        # =====================================================================
        # STEP 3: BASE PREDICTIONS (USING ALL 8 DATA TABLES)
        # =====================================================================
        home_stats = self.get_team_stats(home_team)
        away_stats = self.get_team_stats(away_team)
        
        if not home_stats or not away_stats:
            result['error'] = f"Team data not found"
            return result
        
        # === ADVANCED STATS ===
        home_net = home_stats['advanced'].get('NET_RATING', 0) or 0
        away_net = away_stats['advanced'].get('NET_RATING', 0) or 0
        home_pace = home_stats['advanced'].get('PACE', 100) or 100
        away_pace = away_stats['advanced'].get('PACE', 100) or 100
        home_off = home_stats['advanced'].get('OFF_RATING', 110) or 110
        home_def = home_stats['advanced'].get('DEF_RATING', 110) or 110
        away_off = away_stats['advanced'].get('OFF_RATING', 110) or 110
        away_def = away_stats['advanced'].get('DEF_RATING', 110) or 110
        
        # === FOUR FACTORS (Dean Oliver's Keys) ===
        home_ff = home_stats.get('four_factors', {})
        away_ff = away_stats.get('four_factors', {})
        
        # Effective FG% differential
        home_efg = home_ff.get('EFG_PCT', 0.50) or 0.50
        away_efg = away_ff.get('EFG_PCT', 0.50) or 0.50
        home_opp_efg = home_ff.get('OPP_EFG_PCT', 0.50) or 0.50
        away_opp_efg = away_ff.get('OPP_EFG_PCT', 0.50) or 0.50
        
        # Turnover differential
        home_tov = home_ff.get('TM_TOV_PCT', 0.14) or 0.14
        away_tov = away_ff.get('TM_TOV_PCT', 0.14) or 0.14
        home_opp_tov = home_ff.get('OPP_TOV_PCT', 0.14) or 0.14
        away_opp_tov = away_ff.get('OPP_TOV_PCT', 0.14) or 0.14
        
        # Rebounding
        home_oreb = home_ff.get('OREB_PCT', 0.25) or 0.25
        away_oreb = away_ff.get('OREB_PCT', 0.25) or 0.25
        
        # FT Rate
        home_fta = home_ff.get('FTA_RATE', 0.25) or 0.25
        away_fta = away_ff.get('FTA_RATE', 0.25) or 0.25
        
        # Four Factors Score (weighted by importance)
        # Shooting (40%), Turnovers (25%), Rebounding (20%), FT (15%)
        home_ff_score = (home_efg - away_opp_efg) * 40 + (away_tov - home_tov) * 25 + (home_oreb - 0.25) * 20 + (home_fta - 0.25) * 15
        away_ff_score = (away_efg - home_opp_efg) * 40 + (home_tov - away_tov) * 25 + (away_oreb - 0.25) * 20 + (away_fta - 0.25) * 15
        ff_adjustment = (home_ff_score - away_ff_score) * 0.1  # Scale to points
        
        # === OPPONENT STATS (Defensive Quality) ===
        home_opp = home_stats.get('opponent', {})
        away_opp = away_stats.get('opponent', {})
        
        home_opp_pts = home_opp.get('OPP_PTS', 110) or 110
        away_opp_pts = away_opp.get('OPP_PTS', 110) or 110
        home_opp_fg3 = home_opp.get('OPP_FG3_PCT', 0.36) or 0.36
        away_opp_fg3 = away_opp.get('OPP_FG3_PCT', 0.36) or 0.36
        
        # Defense adjustment (better defense = lower opponent points)
        league_avg_pts = 114
        home_def_factor = home_opp_pts / league_avg_pts
        away_def_factor = away_opp_pts / league_avg_pts
        
        # === CLUTCH STATS ===
        home_clutch = home_stats.get('clutch', {})
        away_clutch = away_stats.get('clutch', {})
        
        home_clutch_wp = home_clutch.get('W_PCT', 0.50) or 0.50
        away_clutch_wp = away_clutch.get('W_PCT', 0.50) or 0.50
        home_clutch_pm = home_clutch.get('PLUS_MINUS', 0) or 0
        away_clutch_pm = away_clutch.get('PLUS_MINUS', 0) or 0
        
        # Clutch adjustment (for close games / spread)
        clutch_adjustment = (home_clutch_wp - away_clutch_wp) * 3  # Up to 1.5 pts
        
        # === HUSTLE STATS ===
        home_hustle = home_stats.get('hustle', {})
        away_hustle = away_stats.get('hustle', {})
        
        home_deflections = home_hustle.get('DEFLECTIONS', 14) or 14
        away_deflections = away_hustle.get('DEFLECTIONS', 14) or 14
        home_contested = home_hustle.get('CONTESTED_SHOTS', 50) or 50
        away_contested = away_hustle.get('CONTESTED_SHOTS', 50) or 50
        home_loose = home_hustle.get('LOOSE_BALLS_RECOVERED', 5) or 5
        away_loose = away_hustle.get('LOOSE_BALLS_RECOVERED', 5) or 5
        
        # Hustle score (effort = extra possessions)
        home_hustle_score = (home_deflections - 14) * 0.3 + (home_contested - 50) * 0.05 + (home_loose - 5) * 0.4
        away_hustle_score = (away_deflections - 14) * 0.3 + (away_contested - 50) * 0.05 + (away_loose - 5) * 0.4
        hustle_adjustment = (home_hustle_score - away_hustle_score) * 0.5
        
        # === SCORING BREAKDOWN ===
        home_scoring = home_stats.get('scoring', {})
        away_scoring = away_stats.get('scoring', {})
        
        # Fast break and paint points indicate pace/style
        home_fb = home_scoring.get('PCT_PTS_FB', 0.12) or 0.12
        away_fb = away_scoring.get('PCT_PTS_FB', 0.12) or 0.12
        home_paint = home_scoring.get('PCT_PTS_PAINT', 0.45) or 0.45
        away_paint = away_scoring.get('PCT_PTS_PAINT', 0.45) or 0.45
        
        # === DERIVED STATS (Rest, Travel, B2B) ===
        home_derived = home_stats.get('derived', {})
        away_derived = away_stats.get('derived', {})
        
        home_rest = home_derived.get('REST_DAYS', 1) or 1
        away_rest = away_derived.get('REST_DAYS', 1) or 1
        home_b2b = home_derived.get('IS_B2B', False) or False
        away_b2b = away_derived.get('IS_B2B', False) or False
        
        # Rest advantage (each rest day = ~1 pt advantage, B2B = -2.5 pts)
        rest_adjustment = (home_rest - away_rest) * 1.0
        if home_b2b:
            rest_adjustment -= 2.5
        if away_b2b:
            rest_adjustment += 2.5
        
        # =====================================================================
        # FINAL CALCULATIONS
        # =====================================================================
        
        # Home court advantage
        home_court = 2.8
        
        # Base margin from net rating
        base_margin = (home_net - away_net) + home_court
        
        # Apply ALL adjustments
        predicted_margin = (
            base_margin 
            + injury_spread_adj 
            + ff_adjustment 
            + clutch_adjustment 
            + hustle_adjustment 
            + rest_adjustment
        )
        predicted_spread = -predicted_margin
        
        # === TOTAL CALCULATION ===
        # Game pace is weighted average of both teams
        game_pace = (home_pace + away_pace) / 2
        
        # Standard NBA points formula:
        # Points = Pace * OffRtg / 100, adjusted for opponent defense
        # League average OffRtg ~114, DefRtg ~114
        LEAGUE_AVG_DEF = 114.0
        
        # Adjust offensive rating based on opponent defense
        # If opponent defense is worse than avg (higher DefRtg), team scores more
        home_pts = game_pace * home_off / 100 * (away_def / LEAGUE_AVG_DEF)
        away_pts = game_pace * away_off / 100 * (home_def / LEAGUE_AVG_DEF)
        
        # Apply defense factors from other calculations
        home_pts *= away_def_factor
        away_pts *= home_def_factor
        
        # Apply injury and pace adjustments
        predicted_total = home_pts + away_pts + injury_total_adj
        
        # Fast break teams in fast-paced games = more points
        if (home_fb > 0.14 or away_fb > 0.14) and game_pace > 100:
            predicted_total += 2.0
        
        # Standard deviations (adjusted by data quality)
        spread_std = 11.5
        total_std = 10.0
        
        result['predictions'] = {
            'margin': round(predicted_margin, 2),
            'spread': round(predicted_spread, 1),
            'total': round(predicted_total, 1),
            'home_pts': round(home_pts, 1),
            'away_pts': round(away_pts, 1),
            'pace': round(game_pace, 1),
        }
        
        result['adjustments'] = {
            'base_margin': round(base_margin, 2),
            'injury': round(injury_spread_adj, 2),
            'four_factors': round(ff_adjustment, 2),
            'clutch': round(clutch_adjustment, 2),
            'hustle': round(hustle_adjustment, 2),
            'rest': round(rest_adjustment, 2),
            'home_def_factor': round(home_def_factor, 3),
            'away_def_factor': round(away_def_factor, 3),
        }
        
        result['data_sources'] = {
            'tables_used': list(home_stats.keys()),
            'total_tables': len(home_stats.keys()),
        }

        # =====================================================================
        # STEP 4: EDGE CALCULATION vs BOOK
        # =====================================================================
        picks = []
        
        # Spread analysis
        if book_spread is not None:
            distribution = stats.t(df=7, loc=predicted_margin, scale=spread_std)
            cover_prob = 1 - distribution.cdf(-book_spread)
            
            if cover_prob > 0.5:
                best_side = 'HOME'
                best_bet = f"{home_team} {book_spread:+.1f}"
                win_prob = cover_prob
            else:
                best_side = 'AWAY'
                best_bet = f"{away_team} {-book_spread:+.1f}"
                win_prob = 1 - cover_prob
            
            edge = abs(book_spread - predicted_spread)
            
            # Calibrate probability
            calibrated_prob = win_prob
            if self.calibration:
                cal_result = self.calibration.adjust_for_kelly(win_prob, 'spread', 
                    100 - injury_confidence_penalty)
                calibrated_prob = cal_result['kelly_safe_probability']
                result['engines_used'].append('calibration')
            
            # Calculate EV and Kelly
            ev_pct = (calibrated_prob * 0.909) - ((1 - calibrated_prob) * 1)
            ev_pct *= 100
            
            kelly_stake = 0
            grade = 'N/A'
            should_bet = False
            
            if self.kelly and calibrated_prob > 0.52 and edge >= EDGE_THRESHOLDS['spread']:
                kelly_result = self.kelly.calculate_bet(calibrated_prob, spread_odds, self.bankroll)
                if kelly_result.get('should_bet'):
                    # Apply regime multiplier
                    kelly_stake = kelly_result['recommended_amount'] * kelly_multiplier
                    grade = kelly_result['grade']
                    should_bet = True
                    result['engines_used'].append('kelly')
            
            spread_pick = {
                'type': 'SPREAD',
                'pick': best_bet,
                'raw_prob': round(win_prob, 4),
                'calibrated_prob': round(calibrated_prob, 4),
                'edge': round(edge, 1),
                'ev_pct': round(ev_pct, 2),
                'grade': grade,
                'stake': round(kelly_stake, 2),
                'should_bet': should_bet,
                'odds': spread_odds,
            }
            
            if should_bet:
                picks.append(spread_pick)
            
            result['spread_analysis'] = spread_pick
        
        # Total analysis
        if book_total is not None:
            distribution = stats.norm(loc=predicted_total, scale=total_std)
            over_prob = 1 - distribution.cdf(book_total)
            
            if over_prob > 0.5:
                best_bet = f"OVER {book_total}"
                win_prob = over_prob
            else:
                best_bet = f"UNDER {book_total}"
                win_prob = 1 - over_prob
            
            edge = abs(predicted_total - book_total)
            
            # Calibrate
            calibrated_prob = win_prob
            if self.calibration:
                cal_result = self.calibration.adjust_for_kelly(win_prob, 'total',
                    100 - injury_confidence_penalty)
                calibrated_prob = cal_result['kelly_safe_probability']
            
            ev_pct = (calibrated_prob * 0.909) - ((1 - calibrated_prob) * 1)
            ev_pct *= 100
            
            kelly_stake = 0
            grade = 'N/A'
            should_bet = False
            
            if self.kelly and calibrated_prob > 0.52 and edge >= EDGE_THRESHOLDS['total']:
                total_odds = over_odds if best_bet.startswith('OVER') else under_odds
                kelly_result = self.kelly.calculate_bet(calibrated_prob, total_odds, self.bankroll)
                if kelly_result.get('should_bet'):
                    kelly_stake = kelly_result['recommended_amount'] * kelly_multiplier
                    grade = kelly_result['grade']
                    should_bet = True
            
            total_pick = {
                'type': 'TOTAL',
                'pick': best_bet,
                'raw_prob': round(win_prob, 4),
                'calibrated_prob': round(calibrated_prob, 4),
                'edge': round(edge, 1),
                'ev_pct': round(ev_pct, 2),
                'grade': grade,
                'stake': round(kelly_stake, 2),
                'should_bet': should_bet,
                'odds': total_odds if 'total_odds' in dir() else (over_odds if best_bet.startswith('OVER') else under_odds),
            }
            
            if should_bet:
                picks.append(total_pick)
            
            result['total_analysis'] = total_pick
        
        # =====================================================================
        # STEP 5: MONEYLINE ANALYSIS
        # =====================================================================
        if home_ml and away_ml:
            distribution = stats.t(df=7, loc=predicted_margin, scale=spread_std)
            home_win_prob = 1 - distribution.cdf(0)
            
            # Book implied
            if home_ml > 0:
                home_implied = 100 / (home_ml + 100)
            else:
                home_implied = abs(home_ml) / (abs(home_ml) + 100)
            
            ml_edge = (home_win_prob - home_implied) * 100
            
            result['moneyline_analysis'] = {
                'home_win_prob': round(home_win_prob, 4),
                'away_win_prob': round(1 - home_win_prob, 4),
                'home_implied': round(home_implied, 4),
                'edge_pct': round(ml_edge, 2),
                'best_bet': f"{home_team} ML" if ml_edge > 0 else f"{away_team} ML",
            }
        
        # =====================================================================
        # STEP 6: COMPILE FINAL OUTPUT
        # =====================================================================
        result['picks'] = picks
        result['total_picks'] = len(picks)
        result['total_stake'] = sum(p['stake'] for p in picks)
        result['has_value'] = len(picks) > 0
        
        # Final recommendation
        if regime_data and regime_data['regime'] == 'AVOID':
            result['recommendation'] = '🔴 AVOID - High uncertainty, do not bet'
        elif not picks:
            result['recommendation'] = '⚪ NO VALUE - No edges found'
        elif regime_data and regime_data['regime'] == 'HIGH_VARIANCE':
            result['recommendation'] = f'🟡 REDUCED SIZE - {len(picks)} picks, ${result["total_stake"]:.0f} total'
        else:
            result['recommendation'] = f'🟢 PROCEED - {len(picks)} picks, ${result["total_stake"]:.0f} total'
        
        return result
    
    # ==========================================================================
    # PLAYER PROP PREDICTION v4.0
    # ==========================================================================
    
    def predict_prop(self, player_name: str, stat: str, book_line: float,
                     opponent: str = None, player_out: str = None) -> Dict:
        """
        Player prop prediction with injury and calibration adjustments.
        
        Args:
            player_name: Player name
            stat: Stat type (pts, reb, ast, etc.)
            book_line: Book's line
            opponent: Opponent team
            player_out: If a key teammate is out, boost this player
        """
        if not self.historical:
            return {'error': 'Historical engine not available'}
        
        result = {
            'player': player_name,
            'stat': stat,
            'book_line': book_line,
            'opponent': opponent,
        }
        
        # Get base projection
        projection = self.historical.get_weighted_projection(player_name, stat)
        
        if 'error' in projection:
            return projection
        
        base_proj = projection['projection']
        std_dev = projection['std_dev'] or base_proj * 0.25
        
        # Matchup adjustment
        matchup_adj = 0
        if opponent:
            try:
                matchup = self.historical.get_player_vs_team_comparison(player_name, opponent)
                if 'adjustments' in matchup and stat in matchup['adjustments']:
                    matchup_adj = matchup['adjustments'][stat]['difference']
            except:
                pass
        
        # Teammate out boost
        boost = 0
        if player_out and self.injury:
            try:
                realloc = self.injury.calculate_usage_reallocation(
                    self.historical._player_cache.get(player_name.lower(), {}).get('team', ''),
                    player_out
                )
                if 'reallocation' in realloc:
                    for r in realloc['reallocation']:
                        if r['player'].lower() == player_name.lower():
                            boost = r.get(f'{stat}_boost', 0)
                            break
            except:
                pass
        
        # Final projection
        final_proj = base_proj + matchup_adj + boost
        
        # Probability
        distribution = stats.norm(loc=final_proj, scale=std_dev)
        over_prob = 1 - distribution.cdf(book_line)
        
        if over_prob > 0.5:
            best_bet = f"OVER {book_line}"
            win_prob = over_prob
        else:
            best_bet = f"UNDER {book_line}"
            win_prob = 1 - over_prob
        
        edge_pct = ((final_proj - book_line) / book_line) * 100
        
        # Calibrate
        calibrated_prob = win_prob
        if self.calibration:
            cal = self.calibration.adjust_for_kelly(win_prob, 'player_prop')
            calibrated_prob = cal['kelly_safe_probability']
        
        # EV and Kelly
        ev_pct = (calibrated_prob * 0.909) - ((1 - calibrated_prob) * 1)
        ev_pct *= 100
        
        kelly_stake = 0
        grade = 'N/A'
        should_bet = False
        
        if self.kelly and calibrated_prob > 0.52 and abs(edge_pct) >= EDGE_THRESHOLDS['prop']:
            kelly_result = self.kelly.calculate_bet(calibrated_prob, -110, self.bankroll)
            if kelly_result.get('should_bet'):
                kelly_stake = kelly_result['recommended_amount']
                grade = kelly_result['grade']
                should_bet = True
        
        result.update({
            'base_projection': round(base_proj, 2),
            'matchup_adjustment': round(matchup_adj, 2),
            'teammate_out_boost': round(boost, 2),
            'final_projection': round(final_proj, 2),
            'std_dev': round(std_dev, 2),
            
            'over_prob': round(over_prob, 4),
            'calibrated_prob': round(calibrated_prob, 4),
            'edge_pct': round(edge_pct, 2),
            'ev_pct': round(ev_pct, 2),
            
            'best_bet': best_bet,
            'grade': grade,
            'stake': round(kelly_stake, 2),
            'should_bet': should_bet,
        })
        
        return result
    
    # ==========================================================================
    # DAILY SLATE ANALYSIS
    # ==========================================================================
    
    def analyze_slate(self, games: List[Dict]) -> Dict:
        """
        Analyze a full slate of games.
        
        Args:
            games: List of game dicts with keys:
                   home_team, away_team, spread, total, home_ml, away_ml
        
        Returns:
            Complete slate analysis with bet slip
        """
        print(f"\n{'='*70}")
        print(f"📊 ANALYZING {len(games)} GAMES")
        print(f"{'='*70}")
        
        all_picks = []
        game_results = []
        
        for game in games:
            print(f"\n  Analyzing: {game.get('away_team', '?')} @ {game.get('home_team', '?')}...")
            
            result = self.predict_game(
                home_team=game.get('home_team'),
                away_team=game.get('away_team'),
                book_spread=game.get('spread'),
                book_total=game.get('total'),
                home_ml=game.get('home_ml'),
                away_ml=game.get('away_ml'),
                b2b_home=game.get('b2b_home', False),
                b2b_away=game.get('b2b_away', False),
                spread_odds=game.get('spread_odds', -110),
                over_odds=game.get('over_odds', -110),
                under_odds=game.get('under_odds', -110),
            )
            
            game_results.append(result)
            
            # Collect picks with FULL context for explanations
            for pick in result.get('picks', []):
                pick['game'] = result['matchup']
                # Add prediction data for explanation engine
                if 'predictions' in result:
                    pick['model_total'] = result['predictions'].get('total')
                    pick['model_home_pts'] = result['predictions'].get('home_pts')
                    pick['model_away_pts'] = result['predictions'].get('away_pts')
                    pick['model_pace'] = result['predictions'].get('pace')
                    pick['model_margin'] = result['predictions'].get('margin')
                # Add regime data
                if 'regime' in result:
                    pick['regime_status'] = result['regime'].get('status')
                    pick['regime_confidence'] = result['regime'].get('confidence')
                # Add injury data
                if 'injuries' in result:
                    pick['injury_adjustment'] = result['injuries'].get('total_adjustment', 0)
                    pick['injury_edge'] = result['injuries'].get('edge_for', 'NEUTRAL')
                all_picks.append(pick)
        
        # Sort by EV
        all_picks.sort(key=lambda x: x.get('ev_pct', 0), reverse=True)
        
        # Build bet slip
        bet_slip = {
            'generated_at': datetime.now().isoformat(),
            'bankroll': self.bankroll,
            'games_analyzed': len(games),
            'total_picks': len(all_picks),
            'total_stake': sum(p['stake'] for p in all_picks),
            'avg_ev': round(np.mean([p['ev_pct'] for p in all_picks]), 2) if all_picks else 0,
            'picks': all_picks,
        }
        
        return {
            'game_results': game_results,
            'bet_slip': bet_slip,
        }


# ==============================================================================
# TEST SUITE
# ==============================================================================
if __name__ == "__main__":
    print("=" * 80)
    print("META-MERGE ENGINE v4.0 - ULTIMATE TEST")
    print("=" * 80)
    
    engine = MetaMergeEngine(bankroll=10000, risk_profile='moderate')
    
    # -------------------------------------------------------------------------
    # Test 1: Single game prediction
    # -------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("TEST 1: SINGLE GAME PREDICTION")
    print("=" * 80)
    
    game = engine.predict_game(
        home_team="Celtics",
        away_team="Lakers",
        book_spread=-8.5,
        book_total=224.5,
        home_ml=-350,
        away_ml=280,
        b2b_away=True,
    )
    
    print(f"\n  🏀 {game['matchup']}")
    
    if 'regime' in game:
        print(f"\n  📊 REGIME: {game['regime']['status']} ({game['regime']['confidence']}% confidence)")
        print(f"     Kelly Multiplier: {game['regime']['kelly_multiplier']}")
        if game['regime']['warnings']:
            print(f"     Warnings: {', '.join(game['regime']['warnings'][:2])}")
    
    if 'injuries' in game:
        print(f"\n  🏥 INJURIES:")
        print(f"     Spread Adj: {game['injuries']['spread_adjustment']:+.1f}")
        print(f"     Total Adj: {game['injuries']['total_adjustment']:+.1f}")
    
    if 'predictions' in game:
        print(f"\n  📈 PREDICTIONS:")
        print(f"     Margin: {game['predictions']['margin']:+.1f}")
        print(f"     Spread: {game['predictions']['spread']}")
        print(f"     Total: {game['predictions']['total']}")
    
    if 'spread_analysis' in game:
        sa = game['spread_analysis']
        print(f"\n  🎯 SPREAD ANALYSIS:")
        print(f"     Pick: {sa['pick']}")
        print(f"     Raw Prob: {sa['raw_prob']:.1%} → Calibrated: {sa['calibrated_prob']:.1%}")
        print(f"     Edge: {sa['edge']:.1f} pts | EV: {sa['ev_pct']:.1f}%")
        print(f"     Grade: {sa['grade']} | Stake: ${sa['stake']:.0f}")
    
    print(f"\n  📋 {game['recommendation']}")
    print(f"     Engines used: {', '.join(game['engines_used'])}")
    
    # -------------------------------------------------------------------------
    # Test 2: Player prop with teammate out
    # -------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("TEST 2: PLAYER PROP (TEAMMATE OUT)")
    print("=" * 80)
    
    if ENGINES_AVAILABLE['historical']:
        prop = engine.predict_prop(
            player_name="Austin Reaves",
            stat="pts",
            book_line=20.5,
            opponent="BOS",
            player_out="LeBron James"
        )
        
        if 'error' not in prop:
            print(f"\n  🏀 {prop['player']} {prop['stat'].upper()} vs {prop['opponent']}")
            print(f"\n  📊 PROJECTION:")
            print(f"     Base: {prop['base_projection']}")
            print(f"     Matchup Adj: {prop['matchup_adjustment']:+.1f}")
            print(f"     Teammate Out Boost: {prop['teammate_out_boost']:+.1f}")
            print(f"     Final: {prop['final_projection']}")
            print(f"\n  🎯 ANALYSIS:")
            print(f"     Book: {prop['book_line']} | Edge: {prop['edge_pct']:+.1f}%")
            print(f"     Best Bet: {prop['best_bet']} | EV: {prop['ev_pct']:.1f}%")
            print(f"     Grade: {prop['grade']} | Stake: ${prop['stake']:.0f}")
    
    # -------------------------------------------------------------------------
    # Test 3: Full slate analysis
    # -------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("TEST 3: FULL SLATE ANALYSIS")
    print("=" * 80)
    
    slate = [
        {'home_team': 'Celtics', 'away_team': 'Lakers', 'spread': -8.5, 'total': 224.5},
        {'home_team': 'Thunder', 'away_team': 'Cavaliers', 'spread': -2.5, 'total': 228.0},
        {'home_team': 'Knicks', 'away_team': 'Heat', 'spread': -4.0, 'total': 212.5},
    ]
    
    analysis = engine.analyze_slate(slate)
    
    print(f"\n  💰 BET SLIP")
    print(f"     Bankroll: ${analysis['bet_slip']['bankroll']:,}")
    print(f"     Games Analyzed: {analysis['bet_slip']['games_analyzed']}")
    print(f"     Total Picks: {analysis['bet_slip']['total_picks']}")
    print(f"     Total Stake: ${analysis['bet_slip']['total_stake']:.0f}")
    print(f"     Average EV: {analysis['bet_slip']['avg_ev']:.1f}%")
    
    if analysis['bet_slip']['picks']:
        print(f"\n  📋 PICKS:")
        for pick in analysis['bet_slip']['picks'][:5]:
            print(f"     ${pick['stake']:.0f} | {pick['game']} | {pick['pick']} | {pick['grade']}")
    
    # -------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("✅ META-MERGE ENGINE v4.0 - ALL TESTS COMPLETE")
    print("=" * 80)
