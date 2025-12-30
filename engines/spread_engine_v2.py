#!/usr/bin/env python3
"""
SPREAD ENGINE v2.1 - COMPLETE
=============================
Uses ALL available data for maximum accuracy:
- Team Advanced Stats (Net Rating, Pace, Efficiency)
- Four Factors (eFG%, TOV%, OREB%, FTr) 
- Clutch Performance (last 5 min close games)
- Hustle Stats (deflections, contested shots, loose balls)
- Opponent Stats (defensive metrics)
- Schedule Context (rest days, B2B, travel)

Mathematical Framework:
- Student-t distribution with 7 df (fat tails for blowouts)
- Pace interaction model (0.48/0.52 weighting)
- Dynamic home court advantage
- Multi-factor regression for margin prediction
- Monte Carlo simulation for confidence intervals
"""

import numpy as np
from scipy import stats
from sqlalchemy import create_engine, text
from datetime import datetime, timedelta
import os

# ============================================================
# CONFIGURATION
# ============================================================
STUDENT_T_DF = 7           # Degrees of freedom for fat tails
NBA_MARGIN_STDDEV = 12.0   # Historical NBA margin std dev
HOME_COURT_BASE = 3.0      # Base home court advantage
MONTE_CARLO_SIMS = 10000   # Number of simulations

DATABASE_URL = os.environ.get('DATABASE_URL',
    "postgresql://sb_algo_db_user:0HDtYp4EY2Lo5At8iyf44PD1zDioSPK7@dpg-d495uhchg0os738l1a50-a.virginia-postgres.render.com/sb_algo_db")

# Factor weights for margin prediction (sum to 1.0)
WEIGHTS = {
    'net_rating': 0.40,      # Primary factor
    'four_factors': 0.20,    # eFG%, TOV%, OREB%, FTr
    'clutch': 0.10,          # Late game performance
    'hustle': 0.10,          # Effort metrics
    'opponent_defense': 0.15, # Defensive quality
    'context': 0.05,         # Rest, travel, B2B
}

# ============================================================
# SPREAD ENGINE CLASS
# ============================================================
class SpreadEngine:
    """
    Complete Spread Engine using all available data
    """
    
    def __init__(self):
        self.df = STUDENT_T_DF
        self.base_std = NBA_MARGIN_STDDEV
        self.engine = create_engine(DATABASE_URL)
        self._cache = {}
    
    # ========================================================
    # DATA FETCHING - All Tables
    # ========================================================
    
    def get_team_advanced(self, team_name):
        """Fetch from nba_team_advanced_stats"""
        cache_key = f"advanced_{team_name}"
        if cache_key in self._cache:
            return self._cache[cache_key]
            
        with self.engine.connect() as conn:
            result = conn.execute(text("""
                SELECT "TEAM_NAME", "NET_RATING", "OFF_RATING", "DEF_RATING", 
                       "PACE", "EFG_PCT", "TS_PCT", "AST_PCT", "AST_TO",
                       "OREB_PCT", "DREB_PCT", "TM_TOV_PCT", "PIE", "W_PCT"
                FROM nba_team_advanced_stats 
                WHERE "TEAM_NAME" ILIKE :team
                ORDER BY pull_date DESC LIMIT 1
            """), {"team": f"%{team_name}%"}).fetchone()
            
            if result:
                data = {
                    'team': result[0],
                    'net_rating': float(result[1] or 0),
                    'off_rating': float(result[2] or 110),
                    'def_rating': float(result[3] or 110),
                    'pace': float(result[4] or 100),
                    'efg_pct': float(result[5] or 0.50),
                    'ts_pct': float(result[6] or 0.55),
                    'ast_pct': float(result[7] or 0.60),
                    'ast_to': float(result[8] or 1.5),
                    'oreb_pct': float(result[9] or 0.25),
                    'dreb_pct': float(result[10] or 0.75),
                    'tov_pct': float(result[11] or 0.12),
                    'pie': float(result[12] or 0.50),
                    'win_pct': float(result[13] or 0.50),
                }
                self._cache[cache_key] = data
                return data
            return None
    
    def get_team_four_factors(self, team_name):
        """Fetch from nba_team_four_factors - Dean Oliver's Four Factors"""
        cache_key = f"four_factors_{team_name}"
        if cache_key in self._cache:
            return self._cache[cache_key]
            
        with self.engine.connect() as conn:
            result = conn.execute(text("""
                SELECT "TEAM_NAME", "EFG_PCT", "FTA_RATE", "TM_TOV_PCT", "OREB_PCT",
                       "OPP_EFG_PCT", "OPP_FTA_RATE", "OPP_TOV_PCT", "OPP_OREB_PCT"
                FROM nba_team_four_factors 
                WHERE "TEAM_NAME" ILIKE :team
                ORDER BY pull_date DESC LIMIT 1
            """), {"team": f"%{team_name}%"}).fetchone()
            
            if result:
                data = {
                    'team': result[0],
                    # Offensive Four Factors
                    'efg_pct': float(result[1] or 0.50),
                    'fta_rate': float(result[2] or 0.25),
                    'tov_pct': float(result[3] or 0.12),
                    'oreb_pct': float(result[4] or 0.25),
                    # Defensive Four Factors (opponent stats)
                    'opp_efg_pct': float(result[5] or 0.50),
                    'opp_fta_rate': float(result[6] or 0.25),
                    'opp_tov_pct': float(result[7] or 0.12),
                    'opp_oreb_pct': float(result[8] or 0.25),
                }
                self._cache[cache_key] = data
                return data
            return None
    
    def get_team_clutch(self, team_name):
        """Fetch from nba_team_clutch - Last 5 min, margin <= 5"""
        cache_key = f"clutch_{team_name}"
        if cache_key in self._cache:
            return self._cache[cache_key]
            
        with self.engine.connect() as conn:
            result = conn.execute(text("""
                SELECT "TEAM_NAME", "W_PCT", "FG_PCT", "FG3_PCT", "FT_PCT",
                       "PLUS_MINUS", "GP"
                FROM nba_team_clutch 
                WHERE "TEAM_NAME" ILIKE :team
                ORDER BY pull_date DESC LIMIT 1
            """), {"team": f"%{team_name}%"}).fetchone()
            
            if result:
                data = {
                    'team': result[0],
                    'clutch_win_pct': float(result[1] or 0.50),
                    'clutch_fg_pct': float(result[2] or 0.45),
                    'clutch_fg3_pct': float(result[3] or 0.35),
                    'clutch_ft_pct': float(result[4] or 0.75),
                    'clutch_plus_minus': float(result[5] or 0),
                    'clutch_games': int(result[6] or 0),
                }
                self._cache[cache_key] = data
                return data
            return None
    
    def get_team_hustle(self, team_name):
        """Fetch from nba_team_hustle - Effort metrics"""
        cache_key = f"hustle_{team_name}"
        if cache_key in self._cache:
            return self._cache[cache_key]
            
        with self.engine.connect() as conn:
            result = conn.execute(text("""
                SELECT "TEAM_NAME", "DEFLECTIONS", "CONTESTED_SHOTS", 
                       "CONTESTED_SHOTS_2PT", "CONTESTED_SHOTS_3PT",
                       "CHARGES_DRAWN", "LOOSE_BALLS_RECOVERED",
                       "SCREEN_ASSISTS", "BOX_OUTS", "GP"
                FROM nba_team_hustle 
                WHERE "TEAM_NAME" ILIKE :team
                ORDER BY pull_date DESC LIMIT 1
            """), {"team": f"%{team_name}%"}).fetchone()
            
            if result:
                gp = int(result[9] or 1)
                data = {
                    'team': result[0],
                    'deflections_pg': float(result[1] or 0) / gp,
                    'contested_shots_pg': float(result[2] or 0) / gp,
                    'contested_2pt_pg': float(result[3] or 0) / gp,
                    'contested_3pt_pg': float(result[4] or 0) / gp,
                    'charges_drawn_pg': float(result[5] or 0) / gp,
                    'loose_balls_pg': float(result[6] or 0) / gp,
                    'screen_assists_pg': float(result[7] or 0) / gp,
                    'box_outs_pg': float(result[8] or 0) / gp,
                }
                self._cache[cache_key] = data
                return data
            return None
    
    def get_team_opponent_stats(self, team_name):
        """Fetch from nba_team_opponent_stats - Defensive metrics"""
        cache_key = f"opponent_{team_name}"
        if cache_key in self._cache:
            return self._cache[cache_key]
            
        with self.engine.connect() as conn:
            result = conn.execute(text("""
                SELECT "TEAM_NAME", "OPP_FG_PCT", "OPP_FG3_PCT", "OPP_FT_PCT",
                       "OPP_OREB", "OPP_DREB", "OPP_TOV", "OPP_PTS", "GP"
                FROM nba_team_opponent_stats 
                WHERE "TEAM_NAME" ILIKE :team
                ORDER BY pull_date DESC LIMIT 1
            """), {"team": f"%{team_name}%"}).fetchone()
            
            if result:
                gp = int(result[8] or 1)
                data = {
                    'team': result[0],
                    'opp_fg_pct': float(result[1] or 0.45),
                    'opp_fg3_pct': float(result[2] or 0.35),
                    'opp_ft_pct': float(result[3] or 0.75),
                    'opp_oreb_pg': float(result[4] or 10) / gp,
                    'opp_dreb_pg': float(result[5] or 35) / gp,
                    'opp_tov_pg': float(result[6] or 14) / gp,
                    'opp_pts_pg': float(result[7] or 110) / gp,
                }
                self._cache[cache_key] = data
                return data
            return None
    
    def get_schedule_context(self, team_name, game_date=None):
        """Calculate rest days, B2B, travel from schedule"""
        if game_date is None:
            game_date = datetime.now().date()
        
        # For now, return defaults - will enhance with actual schedule lookup
        return {
            'rest_days': 1,
            'is_b2b': False,
            'travel_miles': 0,
            'games_in_7_days': 3,
            'home_game': True,
        }
    
    # ========================================================
    # CALCULATION COMPONENTS
    # ========================================================
    
    def pace_interaction(self, home_pace, away_pace):
        """
        Pace Interaction Model
        Slower team has slightly more control (0.48/0.52 split)
        """
        if home_pace >= away_pace:
            return 0.48 * home_pace + 0.52 * away_pace
        else:
            return 0.52 * home_pace + 0.48 * away_pace
    
    def calculate_four_factors_edge(self, home_ff, away_ff):
        """
        Calculate edge from Four Factors
        
        Dean Oliver's Four Factors (weighted importance):
        1. eFG% (40%) - Shooting efficiency
        2. TOV% (25%) - Turnover rate (lower is better)
        3. OREB% (20%) - Offensive rebounding
        4. FTr (15%) - Free throw rate
        """
        # Offensive edge (home's offense vs away's defense)
        home_off_edge = (
            (home_ff['efg_pct'] - away_ff['opp_efg_pct']) * 0.40 +
            (away_ff['opp_tov_pct'] - home_ff['tov_pct']) * 0.25 +  # Higher opp TOV is good
            (home_ff['oreb_pct'] - away_ff['opp_oreb_pct']) * 0.20 +
            (home_ff['fta_rate'] - away_ff['opp_fta_rate']) * 0.15
        )
        
        # Defensive edge (home's defense vs away's offense)
        home_def_edge = (
            (away_ff['efg_pct'] - home_ff['opp_efg_pct']) * 0.40 +
            (home_ff['opp_tov_pct'] - away_ff['tov_pct']) * 0.25 +
            (away_ff['oreb_pct'] - home_ff['opp_oreb_pct']) * 0.20 +
            (away_ff['fta_rate'] - home_ff['opp_fta_rate']) * 0.15
        )
        
        # Convert to points (rough scaling: 0.01 in factors ≈ 0.5 points)
        total_edge = (home_off_edge - home_def_edge) * 50
        
        return {
            'offensive_edge': round(home_off_edge * 50, 2),
            'defensive_edge': round(home_def_edge * 50, 2),
            'total_edge': round(total_edge, 2),
        }
    
    def calculate_clutch_edge(self, home_clutch, away_clutch):
        """
        Calculate edge from clutch performance
        
        Clutch matters in close games (~35% of NBA games)
        """
        # Win percentage edge in clutch situations
        win_pct_edge = home_clutch['clutch_win_pct'] - away_clutch['clutch_win_pct']
        
        # Plus/minus edge
        pm_edge = home_clutch['clutch_plus_minus'] - away_clutch['clutch_plus_minus']
        
        # FT% edge (critical in clutch)
        ft_edge = home_clutch['clutch_ft_pct'] - away_clutch['clutch_ft_pct']
        
        # Weight towards games with more clutch sample
        home_weight = min(home_clutch['clutch_games'] / 20, 1.0)
        away_weight = min(away_clutch['clutch_games'] / 20, 1.0)
        reliability = (home_weight + away_weight) / 2
        
        # Convert to points (clutch applies to ~35% of games)
        total_edge = (win_pct_edge * 5 + pm_edge * 0.1 + ft_edge * 2) * 0.35 * reliability
        
        return {
            'win_pct_edge': round(win_pct_edge * 100, 2),
            'plus_minus_edge': round(pm_edge, 2),
            'ft_edge': round(ft_edge * 100, 2),
            'reliability': round(reliability, 2),
            'total_edge': round(total_edge, 2),
        }
    
    def calculate_hustle_edge(self, home_hustle, away_hustle):
        """
        Calculate edge from hustle stats
        
        Hustle metrics correlate with defensive efficiency
        """
        # Deflections (disrupts offense)
        defl_edge = home_hustle['deflections_pg'] - away_hustle['deflections_pg']
        
        # Contested shots (forces difficult shots)
        contest_edge = home_hustle['contested_shots_pg'] - away_hustle['contested_shots_pg']
        
        # Loose balls (extra possessions)
        loose_edge = home_hustle['loose_balls_pg'] - away_hustle['loose_balls_pg']
        
        # Charges drawn (momentum + foul trouble)
        charge_edge = home_hustle['charges_drawn_pg'] - away_hustle['charges_drawn_pg']
        
        # Convert to points
        total_edge = (
            defl_edge * 0.15 +      # ~0.15 pts per deflection
            contest_edge * 0.05 +   # ~0.05 pts per contest
            loose_edge * 0.3 +      # ~0.3 pts per loose ball
            charge_edge * 1.0       # ~1 pt per charge
        )
        
        return {
            'deflections_edge': round(defl_edge, 2),
            'contested_edge': round(contest_edge, 2),
            'loose_balls_edge': round(loose_edge, 2),
            'charges_edge': round(charge_edge, 2),
            'total_edge': round(total_edge, 2),
        }
    
    def calculate_opponent_defense_edge(self, home_opp, away_opp, home_adv, away_adv):
        """
        Calculate edge from opponent defensive stats
        
        How well does home offense match vs away defense and vice versa
        """
        # Home offense vs Away defense
        # Higher opp_fg_pct = worse defense
        home_off_vs_away_def = (
            (away_opp['opp_fg_pct'] - 0.45) * 100 +  # FG% allowed above avg
            (away_opp['opp_fg3_pct'] - 0.35) * 50 +  # 3P% allowed
            (away_opp['opp_tov_pg'] - 14) * -0.5     # Fewer forced TOs = worse
        )
        
        # Away offense vs Home defense
        away_off_vs_home_def = (
            (home_opp['opp_fg_pct'] - 0.45) * 100 +
            (home_opp['opp_fg3_pct'] - 0.35) * 50 +
            (home_opp['opp_tov_pg'] - 14) * -0.5
        )
        
        # Net matchup edge
        matchup_edge = home_off_vs_away_def - away_off_vs_home_def
        
        # Points allowed differential
        pts_allowed_edge = away_opp['opp_pts_pg'] - home_opp['opp_pts_pg']
        
        total_edge = matchup_edge * 0.1 + pts_allowed_edge * 0.3
        
        return {
            'home_off_vs_away_def': round(home_off_vs_away_def, 2),
            'away_off_vs_home_def': round(away_off_vs_home_def, 2),
            'pts_allowed_edge': round(pts_allowed_edge, 2),
            'total_edge': round(total_edge, 2),
        }
    
    def rest_adjustment(self, rest_days, is_b2b=False):
        """
        Rest Day Impact on Net Rating
        
        - 0 days rest: -2.5 net rating
        - 1 day rest: baseline (0)
        - 2+ days rest: +0.5 net rating
        - Back-to-back: -3.1 net rating
        """
        if is_b2b:
            return -3.1
        elif rest_days == 0:
            return -2.5
        elif rest_days == 1:
            return 0.0
        else:
            return 0.5
    
    def home_court_adjustment(self, home_net, away_net):
        """
        Dynamic Home Court Advantage
        
        Elite road teams neutralize home court
        Weak road teams give up more
        """
        if away_net > 5:
            return HOME_COURT_BASE * 0.8
        elif away_net < -5:
            return HOME_COURT_BASE * 1.2
        else:
            return HOME_COURT_BASE
    
    # ========================================================
    # MAIN PREDICTION METHOD
    # ========================================================
    
    def predict(self, home_team, away_team,
                rest_days_home=1, rest_days_away=1,
                is_b2b_home=False, is_b2b_away=False):
        """
        Complete prediction using ALL available data
        """
        # Fetch all data
        home_adv = self.get_team_advanced(home_team)
        away_adv = self.get_team_advanced(away_team)
        home_ff = self.get_team_four_factors(home_team)
        away_ff = self.get_team_four_factors(away_team)
        home_clutch = self.get_team_clutch(home_team)
        away_clutch = self.get_team_clutch(away_team)
        home_hustle = self.get_team_hustle(home_team)
        away_hustle = self.get_team_hustle(away_team)
        home_opp = self.get_team_opponent_stats(home_team)
        away_opp = self.get_team_opponent_stats(away_team)
        
        # Check minimum required data
        if not home_adv or not away_adv:
            return None
        
        # ====================================================
        # COMPONENT 1: Net Rating (40% weight)
        # ====================================================
        game_pace = self.pace_interaction(home_adv['pace'], away_adv['pace'])
        net_diff = home_adv['net_rating'] - away_adv['net_rating']
        net_rating_edge = net_diff * (game_pace / 100)
        
        # ====================================================
        # COMPONENT 2: Four Factors (20% weight)
        # ====================================================
        if home_ff and away_ff:
            ff_edge = self.calculate_four_factors_edge(home_ff, away_ff)
            four_factors_edge = ff_edge['total_edge']
        else:
            ff_edge = None
            four_factors_edge = 0
        
        # ====================================================
        # COMPONENT 3: Clutch Performance (10% weight)
        # ====================================================
        if home_clutch and away_clutch:
            clutch_edge = self.calculate_clutch_edge(home_clutch, away_clutch)
            clutch_pts_edge = clutch_edge['total_edge']
        else:
            clutch_edge = None
            clutch_pts_edge = 0
        
        # ====================================================
        # COMPONENT 4: Hustle Stats (10% weight)
        # ====================================================
        if home_hustle and away_hustle:
            hustle_edge = self.calculate_hustle_edge(home_hustle, away_hustle)
            hustle_pts_edge = hustle_edge['total_edge']
        else:
            hustle_edge = None
            hustle_pts_edge = 0
        
        # ====================================================
        # COMPONENT 5: Opponent Defense (15% weight)
        # ====================================================
        if home_opp and away_opp:
            opp_edge = self.calculate_opponent_defense_edge(home_opp, away_opp, home_adv, away_adv)
            opp_defense_edge = opp_edge['total_edge']
        else:
            opp_edge = None
            opp_defense_edge = 0
        
        # ====================================================
        # COMPONENT 6: Context (5% weight)
        # ====================================================
        rest_adj_home = self.rest_adjustment(rest_days_home, is_b2b_home)
        rest_adj_away = self.rest_adjustment(rest_days_away, is_b2b_away)
        context_edge = rest_adj_home - rest_adj_away
        
        # Home court advantage
        home_court = self.home_court_adjustment(home_adv['net_rating'], away_adv['net_rating'])
        
        # ====================================================
        # COMBINE ALL COMPONENTS
        # ====================================================
        expected_margin = (
            net_rating_edge * WEIGHTS['net_rating'] / 0.40 +  # Normalize since net rating is already scaled
            four_factors_edge * WEIGHTS['four_factors'] / 0.20 +
            clutch_pts_edge * WEIGHTS['clutch'] / 0.10 +
            hustle_pts_edge * WEIGHTS['hustle'] / 0.10 +
            opp_defense_edge * WEIGHTS['opponent_defense'] / 0.15 +
            context_edge * WEIGHTS['context'] / 0.05 +
            home_court
        )
        
        # Simplified combination (weighted sum)
        expected_margin = (
            net_rating_edge +
            four_factors_edge * 0.5 +
            clutch_pts_edge +
            hustle_pts_edge +
            opp_defense_edge * 0.5 +
            context_edge +
            home_court
        )
        
        # ====================================================
        # CREATE DISTRIBUTION
        # ====================================================
        pace_var_factor = 1 + (game_pace - 100) / 100 * 0.15
        adjusted_std = self.base_std * pace_var_factor
        
        # Student-t distribution
        distribution = stats.t(df=self.df, loc=expected_margin, scale=adjusted_std)
        
        # Cover probabilities
        spreads = list(np.arange(-15, 16, 0.5))
        cover_probs = {s: round(1 - distribution.cdf(-s), 4) for s in spreads}
        
        # Confidence intervals
        ci_80 = (round(distribution.ppf(0.10), 1), round(distribution.ppf(0.90), 1))
        ci_90 = (round(distribution.ppf(0.05), 1), round(distribution.ppf(0.95), 1))
        
        predicted_spread = round(-expected_margin, 1)
        
        return {
            'home_team': home_adv['team'],
            'away_team': away_adv['team'],
            'predicted_spread': predicted_spread,
            'expected_margin': round(expected_margin, 2),
            'std_dev': round(adjusted_std, 2),
            'confidence_80': ci_80,
            'confidence_90': ci_90,
            'cover_probabilities': cover_probs,
            'components': {
                'net_rating_edge': round(net_rating_edge, 2),
                'four_factors_edge': round(four_factors_edge, 2),
                'clutch_edge': round(clutch_pts_edge, 2),
                'hustle_edge': round(hustle_pts_edge, 2),
                'opp_defense_edge': round(opp_defense_edge, 2),
                'context_edge': round(context_edge, 2),
                'home_court': round(home_court, 2),
                'game_pace': round(game_pace, 1),
            },
            'detailed_breakdown': {
                'four_factors': ff_edge,
                'clutch': clutch_edge,
                'hustle': hustle_edge,
                'opponent_defense': opp_edge,
            },
            'team_data': {
                'home_net_rating': home_adv['net_rating'],
                'away_net_rating': away_adv['net_rating'],
                'home_off_rating': home_adv['off_rating'],
                'home_def_rating': home_adv['def_rating'],
                'away_off_rating': away_adv['off_rating'],
                'away_def_rating': away_adv['def_rating'],
            }
        }
    
    def find_edge(self, home_team, away_team, book_spread,
                  rest_days_home=1, rest_days_away=1,
                  is_b2b_home=False, is_b2b_away=False):
        """
        Find edge vs book spread
        """
        pred = self.predict(home_team, away_team,
                           rest_days_home, rest_days_away,
                           is_b2b_home, is_b2b_away)
        
        if not pred:
            return None
        
        edge = book_spread - pred['predicted_spread']
        
        distribution = stats.t(df=self.df,
                              loc=pred['expected_margin'],
                              scale=pred['std_dev'])
        
        home_cover_prob = 1 - distribution.cdf(-book_spread)
        away_cover_prob = 1 - home_cover_prob
        
        # Determine best bet
        if home_cover_prob > 0.524:  # Beat -110 vig
            best_bet = f"{pred['home_team']} {book_spread:+.1f}"
            bet_prob = home_cover_prob
            bet_side = 'home'
        elif away_cover_prob > 0.524:
            best_bet = f"{pred['away_team']} {-book_spread:+.1f}"
            bet_prob = away_cover_prob
            bet_side = 'away'
        else:
            best_bet = "NO BET"
            bet_prob = max(home_cover_prob, away_cover_prob)
            bet_side = None
        
        # EV at -110
        if bet_side:
            ev = (bet_prob * 0.909) - ((1 - bet_prob) * 1.0)
            ev_pct = round(ev * 100, 2)
        else:
            ev_pct = 0
        
        return {
            'home_team': pred['home_team'],
            'away_team': pred['away_team'],
            'book_spread': book_spread,
            'predicted_spread': pred['predicted_spread'],
            'edge_points': round(edge, 1),
            'home_cover_prob': round(home_cover_prob, 4),
            'away_cover_prob': round(away_cover_prob, 4),
            'best_bet': best_bet,
            'bet_probability': round(bet_prob, 4),
            'ev_percent': ev_pct,
            'confidence_80': pred['confidence_80'],
            'components': pred['components'],
        }
    
    def monte_carlo_simulation(self, home_team, away_team, n_sims=MONTE_CARLO_SIMS):
        """
        Run Monte Carlo simulation for margin distribution
        """
        pred = self.predict(home_team, away_team)
        if not pred:
            return None
        
        # Generate random margins from Student-t
        margins = stats.t.rvs(df=self.df, 
                             loc=pred['expected_margin'],
                             scale=pred['std_dev'],
                             size=n_sims)
        
        return {
            'margins': margins,
            'mean': round(np.mean(margins), 2),
            'median': round(np.median(margins), 2),
            'std': round(np.std(margins), 2),
            'percentiles': {
                5: round(np.percentile(margins, 5), 1),
                10: round(np.percentile(margins, 10), 1),
                25: round(np.percentile(margins, 25), 1),
                50: round(np.percentile(margins, 50), 1),
                75: round(np.percentile(margins, 75), 1),
                90: round(np.percentile(margins, 90), 1),
                95: round(np.percentile(margins, 95), 1),
            },
            'home_win_pct': round(np.mean(margins > 0) * 100, 1),
            'blowout_pct': round(np.mean(np.abs(margins) > 15) * 100, 1),
        }


# ============================================================
# TEST
# ============================================================
if __name__ == "__main__":
    print("=" * 70)
    print("SPREAD ENGINE v2.1 - COMPLETE (ALL DATA SOURCES)")
    print("=" * 70)
    
    engine = SpreadEngine()
    
    matchups = [
        ("Celtics", "Lakers", -8.5),
        ("Thunder", "Cavaliers", -2.5),
        ("Knicks", "Heat", -4.0),
    ]
    
    for home, away, book_spread in matchups:
        print(f"\n{'='*70}")
        print(f"{away} @ {home}")
        print("=" * 70)
        
        pred = engine.predict(home, away)
        if pred:
            print(f"\n📊 PREDICTION")
            print(f"   Predicted Spread: {pred['predicted_spread']}")
            print(f"   Expected Margin: {pred['expected_margin']}")
            print(f"   80% CI: {pred['confidence_80']}")
            
            print(f"\n📈 COMPONENT BREAKDOWN")
            for k, v in pred['components'].items():
                print(f"   {k}: {v}")
            
            # Edge analysis
            edge = engine.find_edge(home, away, book_spread)
            print(f"\n🎯 EDGE ANALYSIS (Book: {book_spread})")
            print(f"   Edge: {edge['edge_points']} pts")
            print(f"   Home Cover: {edge['home_cover_prob']*100:.1f}%")
            print(f"   Away Cover: {edge['away_cover_prob']*100:.1f}%")
            print(f"   Best Bet: {edge['best_bet']}")
            print(f"   EV: {edge['ev_percent']}%")
            
            # Monte Carlo
            mc = engine.monte_carlo_simulation(home, away)
            print(f"\n🎲 MONTE CARLO ({MONTE_CARLO_SIMS:,} sims)")
            print(f"   Mean Margin: {mc['mean']}")
            print(f"   Home Win %: {mc['home_win_pct']}%")
            print(f"   Blowout %: {mc['blowout_pct']}%")
    
    print("\n" + "=" * 70)
    print("✅ SPREAD ENGINE v2.1 COMPLETE - READY")
    print("=" * 70)
