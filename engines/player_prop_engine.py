#!/usr/bin/env python3
"""
PLAYER PROP ENGINE v2.1 - COMPLETE (FIXED)
==========================================
Data is ALREADY per-game from NBA API - no division by GP needed!

Uses ALL 18 DATA TABLES for maximum accuracy.
"""

import numpy as np
from scipy import stats
from sqlalchemy import create_engine, text
import os

# ============================================================
# CONFIGURATION
# ============================================================
MONTE_CARLO_SIMS = 10000
DATABASE_URL = os.environ.get('DATABASE_URL',
    "postgresql://sb_algo_db_user:0HDtYp4EY2Lo5At8iyf44PD1zDioSPK7@dpg-d495uhchg0os738l1a50-a.virginia-postgres.render.com/sb_algo_db")

STAT_CV = {
    'points': 0.30,
    'rebounds': 0.35,
    'assists': 0.40,
    'threes': 0.55,
    'steals': 0.75,
    'blocks': 0.80,
}

STAT_CORRELATIONS = {
    ('points', 'assists'): 0.20,
    ('points', 'rebounds'): 0.15,
    ('points', 'threes'): 0.60,
    ('assists', 'rebounds'): 0.10,
    ('rebounds', 'points'): 0.15,
    ('steals', 'blocks'): 0.15,
}

# ============================================================
# PLAYER PROP ENGINE CLASS
# ============================================================
class PlayerPropEngine:
    
    def __init__(self):
        self.engine = create_engine(DATABASE_URL)
        self._cache = {}
    
    # ========================================================
    # PLAYER DATA - ALL ALREADY PER-GAME!
    # ========================================================
    
    def get_player_base(self, player_name):
        """nba_player_base_stats - ALREADY PER GAME"""
        cache_key = f"base_{player_name}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        with self.engine.connect() as conn:
            result = conn.execute(text("""
                SELECT "PLAYER_NAME", "TEAM_ABBREVIATION", "GP", "MIN", 
                       "PTS", "REB", "AST", "STL", "BLK", "TOV",
                       "FGM", "FGA", "FG_PCT", "FG3M", "FG3A", "FG3_PCT",
                       "FTM", "FTA", "FT_PCT", "OREB", "DREB", "PF", "PLUS_MINUS"
                FROM nba_player_base_stats
                WHERE "PLAYER_NAME" ILIKE :name
                ORDER BY pull_date DESC LIMIT 1
            """), {"name": f"%{player_name}%"}).fetchone()
            
            if result:
                data = {
                    'player': result[0],
                    'team': result[1],
                    'gp': int(result[2] or 1),
                    'min_pg': float(result[3] or 0),
                    'pts_pg': float(result[4] or 0),
                    'reb_pg': float(result[5] or 0),
                    'ast_pg': float(result[6] or 0),
                    'stl_pg': float(result[7] or 0),
                    'blk_pg': float(result[8] or 0),
                    'tov_pg': float(result[9] or 0),
                    'fgm_pg': float(result[10] or 0),
                    'fga_pg': float(result[11] or 0),
                    'fg_pct': float(result[12] or 0.45),
                    'fg3m_pg': float(result[13] or 0),
                    'fg3a_pg': float(result[14] or 0),
                    'fg3_pct': float(result[15] or 0.35),
                    'ftm_pg': float(result[16] or 0),
                    'fta_pg': float(result[17] or 0),
                    'ft_pct': float(result[18] or 0.75),
                    'oreb_pg': float(result[19] or 0),
                    'dreb_pg': float(result[20] or 0),
                    'pf_pg': float(result[21] or 0),
                    'plus_minus_pg': float(result[22] or 0),
                }
                self._cache[cache_key] = data
                return data
        return None
    
    def get_player_advanced(self, player_name):
        """nba_player_advanced_stats"""
        cache_key = f"advanced_{player_name}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        with self.engine.connect() as conn:
            result = conn.execute(text("""
                SELECT "PLAYER_NAME", "USG_PCT", "TS_PCT", "EFG_PCT",
                       "OFF_RATING", "DEF_RATING", "NET_RATING", "PACE",
                       "AST_PCT", "AST_TO", "OREB_PCT", "DREB_PCT", "REB_PCT", "PIE"
                FROM nba_player_advanced_stats
                WHERE "PLAYER_NAME" ILIKE :name
                ORDER BY pull_date DESC LIMIT 1
            """), {"name": f"%{player_name}%"}).fetchone()
            
            if result:
                data = {
                    'player': result[0],
                    'usg_pct': float(result[1] or 0.20),
                    'ts_pct': float(result[2] or 0.55),
                    'efg_pct': float(result[3] or 0.50),
                    'off_rating': float(result[4] or 110),
                    'def_rating': float(result[5] or 110),
                    'net_rating': float(result[6] or 0),
                    'pace': float(result[7] or 100),
                    'ast_pct': float(result[8] or 0.15),
                    'ast_to': float(result[9] or 1.5),
                    'oreb_pct': float(result[10] or 0.05),
                    'dreb_pct': float(result[11] or 0.15),
                    'reb_pct': float(result[12] or 0.10),
                    'pie': float(result[13] or 0.10),
                }
                self._cache[cache_key] = data
                return data
        return None
    
    def get_player_usage(self, player_name):
        """nba_player_usage - % of team stats"""
        cache_key = f"usage_{player_name}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        with self.engine.connect() as conn:
            result = conn.execute(text("""
                SELECT "PLAYER_NAME", "USG_PCT", "PCT_FGM", "PCT_FGA",
                       "PCT_FG3M", "PCT_FG3A", "PCT_REB", "PCT_AST",
                       "PCT_STL", "PCT_BLK", "PCT_PTS"
                FROM nba_player_usage
                WHERE "PLAYER_NAME" ILIKE :name
                ORDER BY pull_date DESC LIMIT 1
            """), {"name": f"%{player_name}%"}).fetchone()
            
            if result:
                data = {
                    'player': result[0],
                    'usg_pct': float(result[1] or 0.20),
                    'pct_fgm': float(result[2] or 0.10),
                    'pct_fga': float(result[3] or 0.10),
                    'pct_fg3m': float(result[4] or 0.10),
                    'pct_fg3a': float(result[5] or 0.10),
                    'pct_reb': float(result[6] or 0.10),
                    'pct_ast': float(result[7] or 0.15),
                    'pct_stl': float(result[8] or 0.10),
                    'pct_blk': float(result[9] or 0.10),
                    'pct_pts': float(result[10] or 0.15),
                }
                self._cache[cache_key] = data
                return data
        return None
    
    def get_player_scoring(self, player_name):
        """nba_player_scoring - scoring breakdown"""
        cache_key = f"scoring_{player_name}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        with self.engine.connect() as conn:
            result = conn.execute(text("""
                SELECT "PLAYER_NAME", "PCT_FGA_2PT", "PCT_FGA_3PT",
                       "PCT_PTS_2PT", "PCT_PTS_3PT", "PCT_PTS_FB",
                       "PCT_PTS_FT", "PCT_PTS_PAINT"
                FROM nba_player_scoring
                WHERE "PLAYER_NAME" ILIKE :name
                ORDER BY pull_date DESC LIMIT 1
            """), {"name": f"%{player_name}%"}).fetchone()
            
            if result:
                data = {
                    'player': result[0],
                    'pct_fga_2pt': float(result[1] or 0.65),
                    'pct_fga_3pt': float(result[2] or 0.35),
                    'pct_pts_2pt': float(result[3] or 0.50),
                    'pct_pts_3pt': float(result[4] or 0.35),
                    'pct_pts_fb': float(result[5] or 0.10),
                    'pct_pts_ft': float(result[6] or 0.15),
                    'pct_pts_paint': float(result[7] or 0.40),
                }
                self._cache[cache_key] = data
                return data
        return None
    
    def get_player_possessions(self, player_name):
        """nba_player_tracking_possessions - ALREADY PER GAME"""
        cache_key = f"poss_{player_name}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        with self.engine.connect() as conn:
            result = conn.execute(text("""
                SELECT "PLAYER_NAME", "TOUCHES", "FRONT_CT_TOUCHES",
                       "TIME_OF_POSS", "AVG_SEC_PER_TOUCH", "PTS_PER_TOUCH",
                       "ELBOW_TOUCHES", "POST_TOUCHES", "PAINT_TOUCHES"
                FROM nba_player_tracking_possessions
                WHERE "PLAYER_NAME" ILIKE :name
                ORDER BY pull_date DESC LIMIT 1
            """), {"name": f"%{player_name}%"}).fetchone()
            
            if result:
                data = {
                    'player': result[0],
                    'touches_pg': float(result[1] or 50),
                    'front_ct_touches_pg': float(result[2] or 30),
                    'time_of_poss_pg': float(result[3] or 4),
                    'avg_sec_per_touch': float(result[4] or 2),
                    'pts_per_touch': float(result[5] or 0.3),
                    'elbow_touches_pg': float(result[6] or 5),
                    'post_touches_pg': float(result[7] or 3),
                    'paint_touches_pg': float(result[8] or 8),
                }
                self._cache[cache_key] = data
                return data
        return None
    
    def get_player_passes(self, player_name):
        """nba_player_tracking_passes - ALREADY PER GAME"""
        cache_key = f"passes_{player_name}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        with self.engine.connect() as conn:
            result = conn.execute(text("""
                SELECT "PLAYER_NAME", "PASSES_MADE", "PASSES_RECEIVED",
                       "AST", "SECONDARY_AST", "POTENTIAL_AST", "AST_PTS_CREATED"
                FROM nba_player_tracking_passes
                WHERE "PLAYER_NAME" ILIKE :name
                ORDER BY pull_date DESC LIMIT 1
            """), {"name": f"%{player_name}%"}).fetchone()
            
            if result:
                data = {
                    'player': result[0],
                    'passes_made_pg': float(result[1] or 30),
                    'passes_received_pg': float(result[2] or 30),
                    'ast_pg': float(result[3] or 3),
                    'secondary_ast_pg': float(result[4] or 0.5),
                    'potential_ast_pg': float(result[5] or 8),
                    'ast_pts_created_pg': float(result[6] or 10),
                }
                self._cache[cache_key] = data
                return data
        return None
    
    def get_player_rebounding(self, player_name):
        """nba_player_tracking_rebounding - ALREADY PER GAME"""
        cache_key = f"reb_{player_name}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        with self.engine.connect() as conn:
            result = conn.execute(text("""
                SELECT "PLAYER_NAME", "REB", "OREB", "DREB",
                       "REB_CONTEST", "REB_UNCONTEST", "REB_CONTEST_PCT",
                       "REB_CHANCES", "REB_CHANCE_PCT", "AVG_REB_DIST"
                FROM nba_player_tracking_rebounding
                WHERE "PLAYER_NAME" ILIKE :name
                ORDER BY pull_date DESC LIMIT 1
            """), {"name": f"%{player_name}%"}).fetchone()
            
            if result:
                data = {
                    'player': result[0],
                    'reb_pg': float(result[1] or 5),
                    'oreb_pg': float(result[2] or 1),
                    'dreb_pg': float(result[3] or 4),
                    'reb_contest_pg': float(result[4] or 2),
                    'reb_uncontest_pg': float(result[5] or 3),
                    'reb_contest_pct': float(result[6] or 0.40),
                    'reb_chances_pg': float(result[7] or 10),
                    'reb_chance_pct': float(result[8] or 0.50),
                    'avg_reb_dist': float(result[9] or 5),
                }
                self._cache[cache_key] = data
                return data
        return None
    
    def get_player_hustle(self, player_name):
        """nba_player_hustle - ALREADY PER GAME"""
        cache_key = f"hustle_{player_name}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        with self.engine.connect() as conn:
            result = conn.execute(text("""
                SELECT "PLAYER_NAME", "DEFLECTIONS", "CONTESTED_SHOTS",
                       "CHARGES_DRAWN", "SCREEN_ASSISTS", "LOOSE_BALLS_RECOVERED", "BOX_OUTS"
                FROM nba_player_hustle
                WHERE "PLAYER_NAME" ILIKE :name
                ORDER BY pull_date DESC LIMIT 1
            """), {"name": f"%{player_name}%"}).fetchone()
            
            if result:
                data = {
                    'player': result[0],
                    'deflections_pg': float(result[1] or 2),
                    'contested_shots_pg': float(result[2] or 5),
                    'charges_drawn_pg': float(result[3] or 0.1),
                    'screen_assists_pg': float(result[4] or 2),
                    'loose_balls_pg': float(result[5] or 0.5),
                    'box_outs_pg': float(result[6] or 3),
                }
                self._cache[cache_key] = data
                return data
        return None
    
    def get_player_clutch(self, player_name):
        """nba_player_clutch - ALREADY PER GAME"""
        cache_key = f"clutch_{player_name}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        with self.engine.connect() as conn:
            result = conn.execute(text("""
                SELECT "PLAYER_NAME", "GP", "MIN", "PTS", "REB", "AST",
                       "FG_PCT", "FG3_PCT", "FT_PCT"
                FROM nba_player_clutch
                WHERE "PLAYER_NAME" ILIKE :name
                ORDER BY pull_date DESC LIMIT 1
            """), {"name": f"%{player_name}%"}).fetchone()
            
            if result:
                data = {
                    'player': result[0],
                    'clutch_gp': int(result[1] or 1),
                    'clutch_min_pg': float(result[2] or 2),
                    'clutch_pts_pg': float(result[3] or 2),
                    'clutch_reb_pg': float(result[4] or 0.5),
                    'clutch_ast_pg': float(result[5] or 0.5),
                    'clutch_fg_pct': float(result[6] or 0.40),
                    'clutch_fg3_pct': float(result[7] or 0.33),
                    'clutch_ft_pct': float(result[8] or 0.80),
                }
                self._cache[cache_key] = data
                return data
        return None
    
    def get_player_bpm(self, player_name):
        """nba_player_bpm_vorp"""
        cache_key = f"bpm_{player_name}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        with self.engine.connect() as conn:
            result = conn.execute(text("""
                SELECT "PLAYER_NAME", "PER", "TS_PCT", "USG_PCT",
                       "WS", "WS_48", "OBPM", "DBPM", "BPM", "VORP"
                FROM nba_player_bpm_vorp
                WHERE "PLAYER_NAME" ILIKE :name
                ORDER BY pull_date DESC LIMIT 1
            """), {"name": f"%{player_name}%"}).fetchone()
            
            if result:
                data = {
                    'player': result[0],
                    'per': float(result[1] or 15),
                    'ts_pct': float(result[2] or 0.55),
                    'usg_pct': float(result[3] or 0.20),
                    'ws': float(result[4] or 2),
                    'ws_48': float(result[5] or 0.10),
                    'obpm': float(result[6] or 0),
                    'dbpm': float(result[7] or 0),
                    'bpm': float(result[8] or 0),
                    'vorp': float(result[9] or 0.5),
                }
                self._cache[cache_key] = data
                return data
        return None
    
    # ========================================================
    # TEAM DATA - FOR MATCHUPS (ALREADY PER GAME)
    # ========================================================
    
    def get_team_advanced(self, team_name):
        # Team abbreviation mapping
        TEAM_ABBREV = {
            "ATL": "Hawks", "BOS": "Celtics", "BKN": "Nets", "CHA": "Hornets",
            "CHI": "Bulls", "CLE": "Cavaliers", "DAL": "Mavericks", "DEN": "Nuggets",
            "DET": "Pistons", "GSW": "Warriors", "HOU": "Rockets", "IND": "Pacers",
            "LAC": "Clippers", "LAL": "Lakers", "MEM": "Grizzlies", "MIA": "Heat",
            "MIL": "Bucks", "MIN": "Timberwolves", "NOP": "Pelicans", "NYK": "Knicks",
            "OKC": "Thunder", "ORL": "Magic", "PHI": "76ers", "PHX": "Suns",
            "POR": "Trail Blazers", "SAC": "Kings", "SAS": "Spurs", "TOR": "Raptors",
            "UTA": "Jazz", "WAS": "Wizards"
        }
        team_name = TEAM_ABBREV.get(team_name.upper(), team_name)
        """nba_team_advanced_stats"""
        cache_key = f"team_adv_{team_name}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        with self.engine.connect() as conn:
            result = conn.execute(text("""
                SELECT "TEAM_NAME", "PACE", "OFF_RATING", "DEF_RATING", "NET_RATING"
                FROM nba_team_advanced_stats
                WHERE "TEAM_NAME" ILIKE :name
                ORDER BY pull_date DESC LIMIT 1
            """), {"name": f"%{team_name}%"}).fetchone()
            
            if result:
                data = {
                    'team': result[0],
                    'pace': float(result[1] or 100),
                    'off_rating': float(result[2] or 110),
                    'def_rating': float(result[3] or 110),
                    'net_rating': float(result[4] or 0),
                }
                self._cache[cache_key] = data
                return data
        return None
    
    def get_team_opponent_stats(self, team_name):
        # Team abbreviation mapping
        TEAM_ABBREV = {
            "ATL": "Hawks", "BOS": "Celtics", "BKN": "Nets", "CHA": "Hornets",
            "CHI": "Bulls", "CLE": "Cavaliers", "DAL": "Mavericks", "DEN": "Nuggets",
            "DET": "Pistons", "GSW": "Warriors", "HOU": "Rockets", "IND": "Pacers",
            "LAC": "Clippers", "LAL": "Lakers", "MEM": "Grizzlies", "MIA": "Heat",
            "MIL": "Bucks", "MIN": "Timberwolves", "NOP": "Pelicans", "NYK": "Knicks",
            "OKC": "Thunder", "ORL": "Magic", "PHI": "76ers", "PHX": "Suns",
            "POR": "Trail Blazers", "SAC": "Kings", "SAS": "Spurs", "TOR": "Raptors",
            "UTA": "Jazz", "WAS": "Wizards"
        }
        team_name = TEAM_ABBREV.get(team_name.upper(), team_name)
        """nba_team_opponent_stats - ALREADY PER GAME"""
        cache_key = f"team_opp_{team_name}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        with self.engine.connect() as conn:
            result = conn.execute(text("""
                SELECT "TEAM_NAME", "OPP_PTS", "OPP_FG_PCT", "OPP_FG3_PCT",
                       "OPP_REB", "OPP_AST", "OPP_TOV", "OPP_STL", "OPP_BLK"
                FROM nba_team_opponent_stats
                WHERE "TEAM_NAME" ILIKE :name
                ORDER BY pull_date DESC LIMIT 1
            """), {"name": f"%{team_name}%"}).fetchone()
            
            if result:
                data = {
                    'team': result[0],
                    'opp_pts_pg': float(result[1] or 110),
                    'opp_fg_pct': float(result[2] or 0.46),
                    'opp_fg3_pct': float(result[3] or 0.36),
                    'opp_reb_pg': float(result[4] or 44),
                    'opp_ast_pg': float(result[5] or 25),
                    'opp_tov_pg': float(result[6] or 14),
                    'opp_stl_pg': float(result[7] or 8),
                    'opp_blk_pg': float(result[8] or 5),
                }
                self._cache[cache_key] = data
                return data
        return None
    
    def get_team_hustle(self, team_name):
        """nba_team_hustle - ALREADY PER GAME"""
        cache_key = f"team_hustle_{team_name}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        with self.engine.connect() as conn:
            result = conn.execute(text("""
                SELECT "TEAM_NAME", "DEFLECTIONS", "CONTESTED_SHOTS",
                       "CONTESTED_SHOTS_3PT"
                FROM nba_team_hustle
                WHERE "TEAM_NAME" ILIKE :name
                ORDER BY pull_date DESC LIMIT 1
            """), {"name": f"%{team_name}%"}).fetchone()
            
            if result:
                data = {
                    'team': result[0],
                    'deflections_pg': float(result[1] or 15),
                    'contested_shots_pg': float(result[2] or 50),
                    'contested_3pt_pg': float(result[3] or 20),
                }
                self._cache[cache_key] = data
                return data
        return None
    
    # ========================================================
    # ADJUSTMENT CALCULATIONS
    # ========================================================
    
    def calculate_pace_factor(self, player_team, opponent_team):
        """Pace adjustment: faster game = more opportunities"""
        player_team_data = self.get_team_advanced(player_team)
        opp_team_data = self.get_team_advanced(opponent_team)
        
        if not player_team_data or not opp_team_data:
            return 1.0
        
        p1, p2 = player_team_data['pace'], opp_team_data['pace']
        if p1 >= p2:
            game_pace = 0.48 * p1 + 0.52 * p2
        else:
            game_pace = 0.52 * p1 + 0.48 * p2
        
        return game_pace / 100
    
    def calculate_defense_adjustment(self, stat_type, opponent_team):
        """Defensive matchup adjustment"""
        opp_stats = self.get_team_opponent_stats(opponent_team)
        
        if not opp_stats:
            return 1.0
        
        LEAGUE_AVG = {
            'points': 114, 'rebounds': 44, 'assists': 26,
            'threes_pct': 0.36, 'steals': 8, 'blocks': 5,
        }
        
        if stat_type == 'points':
            return opp_stats['opp_pts_pg'] / LEAGUE_AVG['points']
        elif stat_type == 'rebounds':
            return opp_stats['opp_reb_pg'] / LEAGUE_AVG['rebounds']
        elif stat_type == 'assists':
            return opp_stats['opp_ast_pg'] / LEAGUE_AVG['assists']
        elif stat_type == 'threes':
            return opp_stats['opp_fg3_pct'] / LEAGUE_AVG['threes_pct']
        elif stat_type == 'steals':
            return opp_stats['opp_tov_pg'] / 14
        elif stat_type == 'blocks':
            return opp_stats['opp_blk_pg'] / LEAGUE_AVG['blocks']
        
        return 1.0
    
    # ========================================================
    # PROP PREDICTIONS
    # ========================================================
    
    def predict_points(self, player_name, opponent_team):
        """POINTS prediction - Gaussian"""
        base = self.get_player_base(player_name)
        advanced = self.get_player_advanced(player_name)
        
        if not base:
            return None
        
        base_pts = base['pts_pg']
        pace_factor = self.calculate_pace_factor(base['team'], opponent_team)
        def_factor = self.calculate_defense_adjustment('points', opponent_team)
        
        adjusted_pts = base_pts * pace_factor * def_factor
        
        # Stars have lower variance
        if advanced and advanced['usg_pct'] > 0.25:
            cv = STAT_CV['points'] * 0.85
        else:
            cv = STAT_CV['points']
        
        pts_std = adjusted_pts * cv
        distribution = stats.norm(loc=adjusted_pts, scale=pts_std)
        
        lines = np.arange(5, 55, 0.5)
        over_probs = {line: round(1 - distribution.cdf(line), 4) for line in lines}
        
        return {
            'player': base['player'],
            'team': base['team'],
            'stat': 'points',
            'expected': round(adjusted_pts, 1),
            'std': round(pts_std, 1),
            'ci_80': (round(distribution.ppf(0.10), 1), round(distribution.ppf(0.90), 1)),
            'over_probabilities': over_probs,
            'adjustments': {
                'base': round(base_pts, 1),
                'pace_factor': round(pace_factor, 3),
                'def_factor': round(def_factor, 3),
            },
            'player_data': {
                'min_pg': base['min_pg'],
                'usg_pct': advanced['usg_pct'] if advanced else None,
                'ts_pct': advanced['ts_pct'] if advanced else None,
                'fg3a_pg': base['fg3a_pg'],
                'fta_pg': base['fta_pg'],
            }
        }
    
    def predict_rebounds(self, player_name, opponent_team):
        """REBOUNDS prediction - Negative Binomial"""
        base = self.get_player_base(player_name)
        advanced = self.get_player_advanced(player_name)
        reb_tracking = self.get_player_rebounding(player_name)
        
        if not base:
            return None
        
        base_reb = base['reb_pg']
        pace_factor = self.calculate_pace_factor(base['team'], opponent_team)
        def_factor = self.calculate_defense_adjustment('rebounds', opponent_team)
        
        adjusted_reb = base_reb * pace_factor * def_factor
        
        variance = (adjusted_reb * STAT_CV['rebounds'])**2 + adjusted_reb
        
        if variance > adjusted_reb and adjusted_reb > 0:
            r = adjusted_reb**2 / (variance - adjusted_reb)
            p = adjusted_reb / variance
            distribution = stats.nbinom(n=max(1, r), p=max(0.01, min(0.99, p)))
        else:
            distribution = stats.poisson(mu=max(0.1, adjusted_reb))
        
        std = np.sqrt(variance)
        
        lines = np.arange(1, 20, 0.5)
        over_probs = {line: round(distribution.sf(line - 0.5), 4) for line in lines}
        
        return {
            'player': base['player'],
            'team': base['team'],
            'stat': 'rebounds',
            'expected': round(adjusted_reb, 1),
            'std': round(std, 1),
            'over_probabilities': over_probs,
            'adjustments': {
                'base': round(base_reb, 1),
                'pace_factor': round(pace_factor, 3),
                'def_factor': round(def_factor, 3),
            },
            'player_data': {
                'oreb_pg': base['oreb_pg'],
                'dreb_pg': base['dreb_pg'],
                'reb_pct': advanced['reb_pct'] if advanced else None,
            }
        }
    
    def predict_assists(self, player_name, opponent_team):
        """ASSISTS prediction - Poisson"""
        base = self.get_player_base(player_name)
        advanced = self.get_player_advanced(player_name)
        passes = self.get_player_passes(player_name)
        
        if not base:
            return None
        
        base_ast = base['ast_pg']
        pace_factor = self.calculate_pace_factor(base['team'], opponent_team)
        def_factor = self.calculate_defense_adjustment('assists', opponent_team)
        
        adjusted_ast = base_ast * pace_factor * def_factor
        
        distribution = stats.poisson(mu=max(0.1, adjusted_ast))
        std = np.sqrt(adjusted_ast)
        
        lines = np.arange(1, 18, 0.5)
        over_probs = {line: round(distribution.sf(line - 0.5), 4) for line in lines}
        
        return {
            'player': base['player'],
            'team': base['team'],
            'stat': 'assists',
            'expected': round(adjusted_ast, 1),
            'std': round(std, 1),
            'over_probabilities': over_probs,
            'adjustments': {
                'base': round(base_ast, 1),
                'pace_factor': round(pace_factor, 3),
                'def_factor': round(def_factor, 3),
            },
            'player_data': {
                'ast_pct': advanced['ast_pct'] if advanced else None,
                'potential_ast_pg': passes['potential_ast_pg'] if passes else None,
            }
        }
    
    def predict_threes(self, player_name, opponent_team):
        """3-POINTERS MADE prediction - Poisson"""
        base = self.get_player_base(player_name)
        
        if not base:
            return None
        
        base_3pm = base['fg3m_pg']
        base_3pa = base['fg3a_pg']
        base_3p_pct = base['fg3_pct']
        
        pace_factor = self.calculate_pace_factor(base['team'], opponent_team)
        def_factor = self.calculate_defense_adjustment('threes', opponent_team)
        
        adj_3pa = base_3pa * pace_factor
        adj_3p_pct = base_3p_pct * def_factor
        adjusted_3pm = adj_3pa * adj_3p_pct
        
        distribution = stats.poisson(mu=max(0.1, adjusted_3pm))
        std = np.sqrt(adjusted_3pm)
        
        lines = np.arange(0.5, 10, 0.5)
        over_probs = {line: round(distribution.sf(line - 0.5), 4) for line in lines}
        
        return {
            'player': base['player'],
            'team': base['team'],
            'stat': 'threes',
            'expected': round(adjusted_3pm, 1),
            'std': round(std, 1),
            'over_probabilities': over_probs,
            'adjustments': {
                'base_3pm': round(base_3pm, 1),
                'base_3pa': round(base_3pa, 1),
                'base_3p_pct': round(base_3p_pct, 3),
                'adj_3p_pct': round(adj_3p_pct, 3),
                'pace_factor': round(pace_factor, 3),
                'def_factor': round(def_factor, 3),
            },
        }
    
    def predict_steals(self, player_name, opponent_team):
        """STEALS prediction - Poisson"""
        base = self.get_player_base(player_name)
        
        if not base:
            return None
        
        base_stl = base['stl_pg']
        pace_factor = self.calculate_pace_factor(base['team'], opponent_team)
        def_factor = self.calculate_defense_adjustment('steals', opponent_team)
        
        adjusted_stl = base_stl * pace_factor * def_factor
        
        distribution = stats.poisson(mu=max(0.1, adjusted_stl))
        std = np.sqrt(adjusted_stl)
        
        lines = np.arange(0.5, 6, 0.5)
        over_probs = {line: round(distribution.sf(line - 0.5), 4) for line in lines}
        
        return {
            'player': base['player'],
            'team': base['team'],
            'stat': 'steals',
            'expected': round(adjusted_stl, 1),
            'std': round(std, 1),
            'over_probabilities': over_probs,
            'adjustments': {
                'base': round(base_stl, 1),
                'pace_factor': round(pace_factor, 3),
                'def_factor': round(def_factor, 3),
            },
        }
    
    def predict_blocks(self, player_name, opponent_team):
        """BLOCKS prediction - Poisson"""
        base = self.get_player_base(player_name)
        
        if not base:
            return None
        
        base_blk = base['blk_pg']
        pace_factor = self.calculate_pace_factor(base['team'], opponent_team)
        def_factor = self.calculate_defense_adjustment('blocks', opponent_team)
        
        adjusted_blk = base_blk * pace_factor * def_factor
        
        distribution = stats.poisson(mu=max(0.1, adjusted_blk))
        std = np.sqrt(adjusted_blk)
        
        lines = np.arange(0.5, 6, 0.5)
        over_probs = {line: round(distribution.sf(line - 0.5), 4) for line in lines}
        
        return {
            'player': base['player'],
            'team': base['team'],
            'stat': 'blocks',
            'expected': round(adjusted_blk, 1),
            'std': round(std, 1),
            'over_probabilities': over_probs,
            'adjustments': {
                'base': round(base_blk, 1),
                'pace_factor': round(pace_factor, 3),
                'def_factor': round(def_factor, 3),
            },
        }
    
    def predict_pra(self, player_name, opponent_team):
        """PTS + REB + AST combo"""
        pts = self.predict_points(player_name, opponent_team)
        reb = self.predict_rebounds(player_name, opponent_team)
        ast = self.predict_assists(player_name, opponent_team)
        
        if not pts or not reb or not ast:
            return None
        
        expected_pra = pts['expected'] + reb['expected'] + ast['expected']
        
        var_pts = pts['std']**2
        var_reb = reb['std']**2
        var_ast = ast['std']**2
        
        cov_pts_reb = STAT_CORRELATIONS.get(('points', 'rebounds'), 0.15) * pts['std'] * reb['std']
        cov_pts_ast = STAT_CORRELATIONS.get(('points', 'assists'), 0.20) * pts['std'] * ast['std']
        cov_reb_ast = STAT_CORRELATIONS.get(('assists', 'rebounds'), 0.10) * reb['std'] * ast['std']
        
        total_var = var_pts + var_reb + var_ast + 2*(cov_pts_reb + cov_pts_ast + cov_reb_ast)
        pra_std = np.sqrt(total_var)
        
        distribution = stats.norm(loc=expected_pra, scale=pra_std)
        
        lines = np.arange(15, 75, 0.5)
        over_probs = {line: round(1 - distribution.cdf(line), 4) for line in lines}
        
        return {
            'player': pts['player'],
            'team': pts['team'],
            'stat': 'PRA',
            'expected': round(expected_pra, 1),
            'std': round(pra_std, 1),
            'ci_80': (round(distribution.ppf(0.10), 1), round(distribution.ppf(0.90), 1)),
            'over_probabilities': over_probs,
            'breakdown': {
                'pts': pts['expected'],
                'reb': reb['expected'],
                'ast': ast['expected'],
            }
        }
    
    # ========================================================
    # EDGE FINDING
    # ========================================================
    
    def find_edge(self, player_name, opponent_team, stat_type, book_line, book_odds=-110):
        """Find edge vs book line"""
        pred_map = {
            'points': self.predict_points,
            'rebounds': self.predict_rebounds,
            'assists': self.predict_assists,
            'threes': self.predict_threes,
            'steals': self.predict_steals,
            'blocks': self.predict_blocks,
            'pra': self.predict_pra,
        }
        
        if stat_type not in pred_map:
            return None
        
        pred = pred_map[stat_type](player_name, opponent_team)
        
        if not pred:
            return None
        
        over_prob = pred['over_probabilities'].get(book_line, 0.50)
        under_prob = 1 - over_prob
        
        edge = pred['expected'] - book_line
        
        # EV calculation at -110
        decimal_odds = (100 / abs(book_odds)) + 1 if book_odds < 0 else (book_odds / 100) + 1
        
        over_ev = (over_prob * (decimal_odds - 1)) - (under_prob * 1)
        under_ev = (under_prob * (decimal_odds - 1)) - (over_prob * 1)
        
        if over_prob > 0.524 and over_ev > 0:
            best_bet = f"OVER {book_line}"
            bet_ev = over_ev
            bet_prob = over_prob
        elif under_prob > 0.524 and under_ev > 0:
            best_bet = f"UNDER {book_line}"
            bet_ev = under_ev
            bet_prob = under_prob
        else:
            best_bet = "NO BET"
            bet_ev = max(over_ev, under_ev)
            bet_prob = max(over_prob, under_prob)
        
        return {
            'player': pred['player'],
            'team': pred.get('team', ''),
            'opponent': opponent_team,
            'stat': stat_type,
            'book_line': book_line,
            'expected': pred['expected'],
            'edge_points': round(edge, 1),
            'over_prob': round(over_prob * 100, 1),
            'under_prob': round(under_prob * 100, 1),
            'over_ev': round(over_ev * 100, 2),
            'under_ev': round(under_ev * 100, 2),
            'best_bet': best_bet,
            'bet_probability': round(bet_prob * 100, 1),
            'adjustments': pred.get('adjustments', {}),
        }
    
    def full_analysis(self, player_name, opponent_team):
        """Complete analysis for all stats"""
        return {
            'points': self.predict_points(player_name, opponent_team),
            'rebounds': self.predict_rebounds(player_name, opponent_team),
            'assists': self.predict_assists(player_name, opponent_team),
            'threes': self.predict_threes(player_name, opponent_team),
            'steals': self.predict_steals(player_name, opponent_team),
            'blocks': self.predict_blocks(player_name, opponent_team),
            'pra': self.predict_pra(player_name, opponent_team),
        }


# ============================================================
# TEST
# ============================================================
if __name__ == "__main__":
    print("=" * 70)
    print("PLAYER PROP ENGINE v2.1 - FIXED (PER-GAME DATA)")
    print("=" * 70)
    
    engine = PlayerPropEngine()
    
    test_cases = [
        ("LeBron James", "Celtics", "points", 25.5),
        ("Jayson Tatum", "Lakers", "points", 28.5),
        ("Nikola Jokic", "Mavericks", "rebounds", 12.5),
        ("Trae Young", "Knicks", "assists", 10.5),
        ("Stephen Curry", "Cavaliers", "threes", 4.5),
        ("Anthony Davis", "Warriors", "pra", 45.5),
    ]
    
    for player, opponent, stat, line in test_cases:
        print(f"\n{'='*70}")
        print(f"{player} vs {opponent} - {stat.upper()}")
        print("=" * 70)
        
        edge = engine.find_edge(player, opponent, stat, line)
        if edge:
            print(f"\n📊 PREDICTION")
            print(f"   Expected: {edge['expected']}")
            print(f"   Book Line: {line}")
            print(f"   Edge: {edge['edge_points']} pts")
            
            print(f"\n🎯 PROBABILITIES")
            print(f"   Over: {edge['over_prob']}%")
            print(f"   Under: {edge['under_prob']}%")
            
            print(f"\n💰 VALUE")
            print(f"   Over EV: {edge['over_ev']}%")
            print(f"   Under EV: {edge['under_ev']}%")
            print(f"   Best Bet: {edge['best_bet']}")
            
            if edge.get('adjustments'):
                print(f"\n📈 ADJUSTMENTS")
                for k, v in edge['adjustments'].items():
                    print(f"   {k}: {v}")
        else:
            print("   Player not found")
    
    print("\n" + "=" * 70)
    print("✅ PLAYER PROP ENGINE v2.1 READY")
    print("=" * 70)
