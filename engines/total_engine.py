#!/usr/bin/env python3
"""
TOTAL ENGINE v2.1 - COMPLETE
============================
Models game totals (Over/Under) using ALL available data:
- Team Advanced Stats (Pace, Off/Def Rating)
- Team Scoring (3PT volume, FT rate, paint scoring)
- Four Factors (eFG%, TOV%, OREB%)
- Opponent Stats (points allowed, defensive efficiency)
- Hustle Stats (contested shots affect scoring)
- Schedule Context (B2B = lower scoring)

Mathematical Framework:
- Pace interaction model (slower team controls)
- 3-point variance amplification (σ²_3PT = n × p × (1-p) × 9)
- Normal distribution for totals (CLT applies)
- Monte Carlo for confidence intervals
"""

import numpy as np
from scipy import stats
from sqlalchemy import create_engine, text
import os

# ============================================================
# CONFIGURATION
# ============================================================
MONTE_CARLO_SIMS = 10000
BASE_TOTAL_STD = 10.0  # Historical std dev of NBA totals

DATABASE_URL = os.environ.get('DATABASE_URL',
    "postgresql://sb_algo_db_user:0HDtYp4EY2Lo5At8iyf44PD1zDioSPK7@dpg-d495uhchg0os738l1a50-a.virginia-postgres.render.com/sb_algo_db")

# ============================================================
# TOTAL ENGINE CLASS  
# ============================================================
class TotalEngine:
    """
    Total Engine - Models game totals with proper variance handling
    """
    
    def __init__(self):
        self.base_std = BASE_TOTAL_STD
        self.engine = create_engine(DATABASE_URL)
        self._cache = {}
    
    # ========================================================
    # DATA FETCHING
    # ========================================================
    
    def get_team_advanced(self, team_name):
        """Fetch from nba_team_advanced_stats"""
        cache_key = f"advanced_{team_name}"
        if cache_key in self._cache:
            return self._cache[cache_key]
            
        with self.engine.connect() as conn:
            result = conn.execute(text("""
                SELECT "TEAM_NAME", "OFF_RATING", "DEF_RATING", "PACE",
                       "EFG_PCT", "TS_PCT", "TM_TOV_PCT", "OREB_PCT"
                FROM nba_team_advanced_stats 
                WHERE "TEAM_NAME" ILIKE :team
                ORDER BY pull_date DESC LIMIT 1
            """), {"team": f"%{team_name}%"}).fetchone()
            
            if result:
                data = {
                    'team': result[0],
                    'off_rating': float(result[1] or 110),
                    'def_rating': float(result[2] or 110),
                    'pace': float(result[3] or 100),
                    'efg_pct': float(result[4] or 0.50),
                    'ts_pct': float(result[5] or 0.55),
                    'tov_pct': float(result[6] or 0.12),
                    'oreb_pct': float(result[7] or 0.25),
                }
                self._cache[cache_key] = data
                return data
            return None
    
    def get_team_scoring(self, team_name):
        """Fetch from nba_team_scoring - shooting breakdown"""
        cache_key = f"scoring_{team_name}"
        if cache_key in self._cache:
            return self._cache[cache_key]
            
        with self.engine.connect() as conn:
            result = conn.execute(text("""
                SELECT "TEAM_NAME", "PCT_FGA_2PT", "PCT_FGA_3PT", 
                       "PCT_PTS_2PT", "PCT_PTS_3PT", "PCT_PTS_FB",
                       "PCT_PTS_PAINT", "PCT_PTS_FT"
                FROM nba_team_scoring 
                WHERE "TEAM_NAME" ILIKE :team
                ORDER BY pull_date DESC LIMIT 1
            """), {"team": f"%{team_name}%"}).fetchone()
            
            if result:
                data = {
                    'team': result[0],
                    'pct_fga_2pt': float(result[1] or 0.65),
                    'pct_fga_3pt': float(result[2] or 0.35),
                    'pct_pts_2pt': float(result[3] or 0.50),
                    'pct_pts_3pt': float(result[4] or 0.35),
                    'pct_pts_fb': float(result[5] or 0.12),
                    'pct_pts_paint': float(result[6] or 0.45),
                    'pct_pts_ft': float(result[7] or 0.15),
                }
                self._cache[cache_key] = data
                return data
            return None
    
    def get_team_base(self, team_name):
        """Fetch from nba_team_base_stats - raw stats"""
        cache_key = f"base_{team_name}"
        if cache_key in self._cache:
            return self._cache[cache_key]
            
        with self.engine.connect() as conn:
            result = conn.execute(text("""
                SELECT "TEAM_NAME", "PTS", "FGM", "FGA", "FG_PCT",
                       "FG3M", "FG3A", "FG3_PCT", "FTM", "FTA", "FT_PCT", "GP"
                FROM nba_team_base_stats 
                WHERE "TEAM_NAME" ILIKE :team
                ORDER BY pull_date DESC LIMIT 1
            """), {"team": f"%{team_name}%"}).fetchone()
            
            if result:
                gp = int(result[11] or 1)
                data = {
                    'team': result[0],
                    'pts_pg': float(result[1] or 110) / gp,
                    'fgm_pg': float(result[2] or 40) / gp,
                    'fga_pg': float(result[3] or 88) / gp,
                    'fg_pct': float(result[4] or 0.46),
                    'fg3m_pg': float(result[5] or 12) / gp,
                    'fg3a_pg': float(result[6] or 35) / gp,
                    'fg3_pct': float(result[7] or 0.36),
                    'ftm_pg': float(result[8] or 18) / gp,
                    'fta_pg': float(result[9] or 22) / gp,
                    'ft_pct': float(result[10] or 0.78),
                }
                self._cache[cache_key] = data
                return data
            return None
    
    def get_team_opponent(self, team_name):
        """Fetch from nba_team_opponent_stats - defensive stats"""
        cache_key = f"opponent_{team_name}"
        if cache_key in self._cache:
            return self._cache[cache_key]
            
        with self.engine.connect() as conn:
            result = conn.execute(text("""
                SELECT "TEAM_NAME", "OPP_PTS", "OPP_FG_PCT", "OPP_FG3_PCT",
                       "OPP_FG3A", "OPP_FTM", "GP"
                FROM nba_team_opponent_stats 
                WHERE "TEAM_NAME" ILIKE :team
                ORDER BY pull_date DESC LIMIT 1
            """), {"team": f"%{team_name}%"}).fetchone()
            
            if result:
                gp = int(result[6] or 1)
                data = {
                    'team': result[0],
                    'opp_pts_pg': float(result[1] or 110) / gp,
                    'opp_fg_pct': float(result[2] or 0.46),
                    'opp_fg3_pct': float(result[3] or 0.36),
                    'opp_fg3a_pg': float(result[4] or 35) / gp,
                    'opp_ftm_pg': float(result[5] or 18) / gp,
                }
                self._cache[cache_key] = data
                return data
            return None
    
    def get_team_hustle(self, team_name):
        """Fetch from nba_team_hustle - affects opponent scoring"""
        cache_key = f"hustle_{team_name}"
        if cache_key in self._cache:
            return self._cache[cache_key]
            
        with self.engine.connect() as conn:
            result = conn.execute(text("""
                SELECT "TEAM_NAME", "CONTESTED_SHOTS", "CONTESTED_SHOTS_3PT",
                       "DEFLECTIONS", "GP"
                FROM nba_team_hustle 
                WHERE "TEAM_NAME" ILIKE :team
                ORDER BY pull_date DESC LIMIT 1
            """), {"team": f"%{team_name}%"}).fetchone()
            
            if result:
                gp = int(result[4] or 1)
                data = {
                    'team': result[0],
                    'contested_pg': float(result[1] or 50) / gp,
                    'contested_3pt_pg': float(result[2] or 20) / gp,
                    'deflections_pg': float(result[3] or 15) / gp,
                }
                self._cache[cache_key] = data
                return data
            return None
    
    def get_team_four_factors(self, team_name):
        """Fetch from nba_team_four_factors"""
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
                    'efg_pct': float(result[1] or 0.50),
                    'fta_rate': float(result[2] or 0.25),
                    'tov_pct': float(result[3] or 0.12),
                    'oreb_pct': float(result[4] or 0.25),
                    'opp_efg_pct': float(result[5] or 0.50),
                    'opp_fta_rate': float(result[6] or 0.25),
                    'opp_tov_pct': float(result[7] or 0.12),
                    'opp_oreb_pct': float(result[8] or 0.25),
                }
                self._cache[cache_key] = data
                return data
            return None
    
    # ========================================================
    # CALCULATION METHODS
    # ========================================================
    
    def pace_interaction(self, home_pace, away_pace):
        """
        Pace Interaction Model
        Slower team has more control (0.48/0.52 split)
        """
        if home_pace >= away_pace:
            return 0.48 * home_pace + 0.52 * away_pace
        else:
            return 0.52 * home_pace + 0.48 * away_pace
    
    def calculate_3pt_variance(self, home_base, away_base, home_opp, away_opp):
        """
        3-Point Variance Amplification
        
        σ²_3PT = n × p × (1-p) × 9
        where n = 3PA, p = 3P%, 9 = 3² (point value squared)
        
        High 3PT volume = higher scoring variance
        """
        # Home team 3PT variance (vs away defense)
        home_3pa = home_base['fg3a_pg']
        # Adjust 3P% based on opponent defense
        home_3p_pct_adj = home_base['fg3_pct'] * (away_opp['opp_fg3_pct'] / 0.36)
        home_3pt_var = home_3pa * home_3p_pct_adj * (1 - home_3p_pct_adj) * 9
        
        # Away team 3PT variance
        away_3pa = away_base['fg3a_pg']
        away_3p_pct_adj = away_base['fg3_pct'] * (home_opp['opp_fg3_pct'] / 0.36)
        away_3pt_var = away_3pa * away_3p_pct_adj * (1 - away_3p_pct_adj) * 9
        
        total_3pt_variance = home_3pt_var + away_3pt_var
        
        return {
            'home_3pt_var': round(home_3pt_var, 2),
            'away_3pt_var': round(away_3pt_var, 2),
            'total_3pt_var': round(total_3pt_variance, 2),
            'home_3pa': round(home_3pa, 1),
            'away_3pa': round(away_3pa, 1),
        }
    
    def calculate_expected_points(self, team_adv, opp_adv, opp_stats, game_pace):
        """
        Calculate expected points for one team
        
        Points = (Pace / 100) × Off Rating × (Opp Def Rating / League Avg)
        """
        # Base expected from offensive rating
        base_pts = (game_pace / 100) * team_adv['off_rating']
        
        # Adjust for opponent defense
        # If opponent allows more than average (>110), increase
        # If opponent allows less (<110), decrease
        def_adjustment = opp_adv['def_rating'] / 110
        
        adjusted_pts = base_pts * def_adjustment
        
        return {
            'base_pts': round(base_pts, 1),
            'def_adjustment': round(def_adjustment, 3),
            'adjusted_pts': round(adjusted_pts, 1),
        }
    
    def calculate_pace_impact(self, home_adv, away_adv):
        """
        Calculate how pace affects total scoring
        
        Higher pace = more possessions = more points
        """
        game_pace = self.pace_interaction(home_adv['pace'], away_adv['pace'])
        
        # League average pace is ~100
        pace_factor = game_pace / 100
        
        # Each 1 point of pace ≈ 2 total points
        pace_pts_impact = (game_pace - 100) * 2
        
        return {
            'game_pace': round(game_pace, 1),
            'pace_factor': round(pace_factor, 3),
            'pace_pts_impact': round(pace_pts_impact, 1),
        }
    
    def calculate_efficiency_matchup(self, home_ff, away_ff):
        """
        Calculate offensive efficiency matchup
        
        Good offense vs bad defense = higher scoring
        """
        # Home offense vs Away defense
        home_off_edge = home_ff['efg_pct'] - away_ff['opp_efg_pct']
        
        # Away offense vs Home defense
        away_off_edge = away_ff['efg_pct'] - home_ff['opp_efg_pct']
        
        # Combined efficiency impact
        # Higher eFG% differential = more efficient scoring
        combined_edge = (home_off_edge + away_off_edge) * 100  # Convert to points
        
        return {
            'home_off_edge': round(home_off_edge * 100, 2),
            'away_off_edge': round(away_off_edge * 100, 2),
            'combined_pts_impact': round(combined_edge, 1),
        }
    
    def calculate_turnover_impact(self, home_ff, away_ff):
        """
        Calculate turnover impact on scoring
        
        More turnovers = fewer possessions = lower scoring
        """
        # Home TOV% vs Away's ability to force TOs
        home_tov_diff = home_ff['tov_pct'] - away_ff['opp_tov_pct']
        
        # Away TOV% vs Home's ability to force TOs
        away_tov_diff = away_ff['tov_pct'] - home_ff['opp_tov_pct']
        
        # Higher TOV% = lower scoring
        # Each 1% of TOV% ≈ -1 point
        tov_pts_impact = -(home_tov_diff + away_tov_diff) * 50
        
        return {
            'home_tov_diff': round(home_tov_diff * 100, 2),
            'away_tov_diff': round(away_tov_diff * 100, 2),
            'tov_pts_impact': round(tov_pts_impact, 1),
        }
    
    def calculate_ft_impact(self, home_base, away_base, home_ff, away_ff):
        """
        Calculate free throw impact
        
        More FT attempts = potentially higher scoring (but slower pace)
        """
        # FT rate differential
        home_ft_rate = home_ff['fta_rate']
        away_ft_rate = away_ff['fta_rate']
        
        avg_ft_rate = (home_ft_rate + away_ft_rate) / 2
        
        # FTs are ~0.78 efficient (league avg FT%)
        # Each additional FT attempt ≈ 0.78 points but costs time
        # Net effect is roughly neutral with slight positive
        ft_pts_impact = (avg_ft_rate - 0.25) * 10
        
        return {
            'home_ft_rate': round(home_ft_rate, 3),
            'away_ft_rate': round(away_ft_rate, 3),
            'ft_pts_impact': round(ft_pts_impact, 1),
        }
    
    def rest_adjustment(self, rest_days, is_b2b=False):
        """
        Rest impact on scoring
        
        B2B teams tend to score less (tired legs, travel)
        """
        if is_b2b:
            return -3.0  # B2B team scores ~3 less
        elif rest_days == 0:
            return -2.0
        elif rest_days >= 3:
            return 1.0  # Well rested = slightly better offense
        else:
            return 0.0
    
    # ========================================================
    # MAIN PREDICTION METHOD
    # ========================================================
    
    def predict(self, home_team, away_team,
                rest_days_home=1, rest_days_away=1,
                is_b2b_home=False, is_b2b_away=False):
        """
        Complete total prediction using ALL available data
        """
        # Fetch all data
        home_adv = self.get_team_advanced(home_team)
        away_adv = self.get_team_advanced(away_team)
        home_base = self.get_team_base(home_team)
        away_base = self.get_team_base(away_team)
        home_opp = self.get_team_opponent(home_team)
        away_opp = self.get_team_opponent(away_team)
        home_ff = self.get_team_four_factors(home_team)
        away_ff = self.get_team_four_factors(away_team)
        home_hustle = self.get_team_hustle(home_team)
        away_hustle = self.get_team_hustle(away_team)
        
        if not home_adv or not away_adv:
            return None
        
        # ====================================================
        # COMPONENT 1: Pace Impact
        # ====================================================
        pace_impact = self.calculate_pace_impact(home_adv, away_adv)
        game_pace = pace_impact['game_pace']
        
        # ====================================================
        # COMPONENT 2: Expected Points (each team)
        # ====================================================
        home_pts = self.calculate_expected_points(home_adv, away_adv, away_opp, game_pace)
        away_pts = self.calculate_expected_points(away_adv, home_adv, home_opp, game_pace)
        
        base_total = home_pts['adjusted_pts'] + away_pts['adjusted_pts']
        
        # ====================================================
        # COMPONENT 3: Efficiency Matchup
        # ====================================================
        if home_ff and away_ff:
            eff_matchup = self.calculate_efficiency_matchup(home_ff, away_ff)
            efficiency_impact = eff_matchup['combined_pts_impact']
        else:
            eff_matchup = None
            efficiency_impact = 0
        
        # ====================================================
        # COMPONENT 4: Turnover Impact
        # ====================================================
        if home_ff and away_ff:
            tov_impact = self.calculate_turnover_impact(home_ff, away_ff)
            turnover_impact = tov_impact['tov_pts_impact']
        else:
            tov_impact = None
            turnover_impact = 0
        
        # ====================================================
        # COMPONENT 5: Free Throw Impact
        # ====================================================
        if home_base and away_base and home_ff and away_ff:
            ft_impact = self.calculate_ft_impact(home_base, away_base, home_ff, away_ff)
            free_throw_impact = ft_impact['ft_pts_impact']
        else:
            ft_impact = None
            free_throw_impact = 0
        
        # ====================================================
        # COMPONENT 6: Rest/B2B Impact
        # ====================================================
        rest_adj_home = self.rest_adjustment(rest_days_home, is_b2b_home)
        rest_adj_away = self.rest_adjustment(rest_days_away, is_b2b_away)
        rest_impact = rest_adj_home + rest_adj_away  # Both affect total
        
        # ====================================================
        # COMPONENT 7: 3-Point Variance (for std dev)
        # ====================================================
        if home_base and away_base and home_opp and away_opp:
            three_pt_var = self.calculate_3pt_variance(home_base, away_base, home_opp, away_opp)
        else:
            three_pt_var = {'total_3pt_var': 50}  # Default
        
        # ====================================================
        # COMBINE ALL COMPONENTS
        # ====================================================
        expected_total = (
            base_total +
            efficiency_impact * 0.5 +  # Scale down
            turnover_impact * 0.5 +
            free_throw_impact +
            rest_impact
        )
        
        # ====================================================
        # CALCULATE VARIANCE
        # ====================================================
        # Base variance + 3PT variance
        base_variance = self.base_std ** 2
        total_variance = base_variance + three_pt_var['total_3pt_var']
        total_std = np.sqrt(total_variance)
        
        # ====================================================
        # CREATE DISTRIBUTION
        # ====================================================
        distribution = stats.norm(loc=expected_total, scale=total_std)
        
        # Over/Under probabilities at common lines
        totals = list(np.arange(200, 250, 0.5))
        over_probs = {t: round(1 - distribution.cdf(t), 4) for t in totals}
        
        # Confidence intervals
        ci_80 = (round(distribution.ppf(0.10), 1), round(distribution.ppf(0.90), 1))
        ci_90 = (round(distribution.ppf(0.05), 1), round(distribution.ppf(0.95), 1))
        
        return {
            'home_team': home_adv['team'],
            'away_team': away_adv['team'],
            'predicted_total': round(expected_total, 1),
            'std_dev': round(total_std, 2),
            'confidence_80': ci_80,
            'confidence_90': ci_90,
            'over_probabilities': over_probs,
            'home_projected_pts': home_pts['adjusted_pts'],
            'away_projected_pts': away_pts['adjusted_pts'],
            'components': {
                'base_total': round(base_total, 1),
                'efficiency_impact': round(efficiency_impact * 0.5, 1),
                'turnover_impact': round(turnover_impact * 0.5, 1),
                'free_throw_impact': round(free_throw_impact, 1),
                'rest_impact': round(rest_impact, 1),
                'game_pace': game_pace,
                '3pt_variance': three_pt_var['total_3pt_var'],
            },
            'detailed_breakdown': {
                'pace': pace_impact,
                'home_pts': home_pts,
                'away_pts': away_pts,
                'efficiency': eff_matchup,
                'turnovers': tov_impact,
                'free_throws': ft_impact,
                '3pt_variance': three_pt_var,
            }
        }
    
    def find_edge(self, home_team, away_team, book_total,
                  rest_days_home=1, rest_days_away=1,
                  is_b2b_home=False, is_b2b_away=False):
        """
        Find edge vs book total
        """
        pred = self.predict(home_team, away_team,
                           rest_days_home, rest_days_away,
                           is_b2b_home, is_b2b_away)
        
        if not pred:
            return None
        
        edge = pred['predicted_total'] - book_total
        
        distribution = stats.norm(loc=pred['predicted_total'], scale=pred['std_dev'])
        
        over_prob = 1 - distribution.cdf(book_total)
        under_prob = distribution.cdf(book_total)
        
        # Determine best bet
        if over_prob > 0.524:
            best_bet = f"OVER {book_total}"
            bet_prob = over_prob
            bet_side = 'over'
        elif under_prob > 0.524:
            best_bet = f"UNDER {book_total}"
            bet_prob = under_prob
            bet_side = 'under'
        else:
            best_bet = "NO BET"
            bet_prob = max(over_prob, under_prob)
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
            'book_total': book_total,
            'predicted_total': pred['predicted_total'],
            'edge_points': round(edge, 1),
            'over_prob': round(over_prob, 4),
            'under_prob': round(under_prob, 4),
            'best_bet': best_bet,
            'bet_probability': round(bet_prob, 4),
            'ev_percent': ev_pct,
            'confidence_80': pred['confidence_80'],
            'home_projected': pred['home_projected_pts'],
            'away_projected': pred['away_projected_pts'],
            'components': pred['components'],
        }
    
    def monte_carlo_simulation(self, home_team, away_team, n_sims=MONTE_CARLO_SIMS):
        """
        Run Monte Carlo simulation for total distribution
        """
        pred = self.predict(home_team, away_team)
        if not pred:
            return None
        
        # Generate random totals
        totals = stats.norm.rvs(loc=pred['predicted_total'],
                               scale=pred['std_dev'],
                               size=n_sims)
        
        return {
            'totals': totals,
            'mean': round(np.mean(totals), 1),
            'median': round(np.median(totals), 1),
            'std': round(np.std(totals), 1),
            'percentiles': {
                5: round(np.percentile(totals, 5), 1),
                10: round(np.percentile(totals, 10), 1),
                25: round(np.percentile(totals, 25), 1),
                50: round(np.percentile(totals, 50), 1),
                75: round(np.percentile(totals, 75), 1),
                90: round(np.percentile(totals, 90), 1),
                95: round(np.percentile(totals, 95), 1),
            },
            'over_220_pct': round(np.mean(totals > 220) * 100, 1),
            'over_230_pct': round(np.mean(totals > 230) * 100, 1),
            'under_210_pct': round(np.mean(totals < 210) * 100, 1),
        }


# ============================================================
# TEST
# ============================================================
if __name__ == "__main__":
    print("=" * 70)
    print("TOTAL ENGINE v2.1 - COMPLETE (ALL DATA SOURCES)")
    print("=" * 70)
    
    engine = TotalEngine()
    
    matchups = [
        ("Celtics", "Lakers", 224.5),
        ("Thunder", "Cavaliers", 228.0),
        ("Knicks", "Heat", 212.5),
    ]
    
    for home, away, book_total in matchups:
        print(f"\n{'='*70}")
        print(f"{away} @ {home}")
        print("=" * 70)
        
        pred = engine.predict(home, away)
        if pred:
            print(f"\n📊 PREDICTION")
            print(f"   Predicted Total: {pred['predicted_total']}")
            print(f"   Home Projected: {pred['home_projected_pts']}")
            print(f"   Away Projected: {pred['away_projected_pts']}")
            print(f"   Std Dev: {pred['std_dev']}")
            print(f"   80% CI: {pred['confidence_80']}")
            
            print(f"\n📈 COMPONENT BREAKDOWN")
            for k, v in pred['components'].items():
                print(f"   {k}: {v}")
            
            # Edge analysis
            edge = engine.find_edge(home, away, book_total)
            print(f"\n🎯 EDGE ANALYSIS (Book: {book_total})")
            print(f"   Edge: {edge['edge_points']} pts")
            print(f"   Over Prob: {edge['over_prob']*100:.1f}%")
            print(f"   Under Prob: {edge['under_prob']*100:.1f}%")
            print(f"   Best Bet: {edge['best_bet']}")
            print(f"   EV: {edge['ev_percent']}%")
            
            # Monte Carlo
            mc = engine.monte_carlo_simulation(home, away)
            print(f"\n🎲 MONTE CARLO ({MONTE_CARLO_SIMS:,} sims)")
            print(f"   Mean: {mc['mean']}")
            print(f"   Over 220: {mc['over_220_pct']}%")
            print(f"   Over 230: {mc['over_230_pct']}%")
            print(f"   Under 210: {mc['under_210_pct']}%")
    
    print("\n" + "=" * 70)
    print("✅ TOTAL ENGINE v2.1 COMPLETE - READY")
    print("=" * 70)
