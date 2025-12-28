"""
Derived Stats Calculator
Computes all the meta-stats that aren't available from APIs:
- Points per touch/shot/possession
- AST/TO ratio
- Usage elasticity
- Minutes volatility
- Role stability
- Correlation coefficients
"""

import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, Optional, Tuple
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class DerivedStatsCalculator:
    """Calculates all derived/meta statistics"""
    
    def __init__(self):
        self.pull_date = datetime.now().strftime('%Y-%m-%d')
    
    # =========================================================================
    # PLAYER EFFICIENCY METRICS
    # =========================================================================
    
    def calculate_points_per_shot(self, pts: float, fga: float, fta: float) -> float:
        """Points per shot attempt (includes FT)"""
        total_shots = fga + (fta * 0.44)  # 0.44 FTA = ~1 possession
        if total_shots == 0:
            return 0.0
        return pts / total_shots
    
    def calculate_points_per_touch(self, pts: float, touches: float) -> float:
        """Points per touch"""
        if touches == 0:
            return 0.0
        return pts / touches
    
    def calculate_points_per_possession(self, pts: float, poss: float) -> float:
        """Points per possession used"""
        if poss == 0:
            return 0.0
        return pts / poss
    
    def calculate_ast_to_ratio(self, ast: float, tov: float) -> float:
        """Assist to turnover ratio"""
        if tov == 0:
            return ast * 10 if ast > 0 else 0.0  # Cap at 10:1 if no turnovers
        return ast / tov
    
    def calculate_player_efficiency_metrics(self, 
                                           player_base: pd.DataFrame,
                                           player_tracking: pd.DataFrame) -> pd.DataFrame:
        """Calculate all efficiency metrics for players"""
        
        # Merge base stats with tracking data
        if 'PLAYER_ID' in player_base.columns and 'PLAYER_ID' in player_tracking.columns:
            merged = player_base.merge(
                player_tracking[['PLAYER_ID', 'TOUCHES', 'TIME_OF_POSS', 'AVG_SEC_PER_TOUCH']],
                on='PLAYER_ID',
                how='left'
            )
        else:
            merged = player_base.copy()
            merged['TOUCHES'] = None
        
        # Calculate derived metrics
        results = []
        for _, row in merged.iterrows():
            player_data = {
                'PLAYER_ID': row.get('PLAYER_ID'),
                'PLAYER_NAME': row.get('PLAYER_NAME'),
                'TEAM_ID': row.get('TEAM_ID'),
            }
            
            # Points per shot
            pts = row.get('PTS', 0) or 0
            fga = row.get('FGA', 0) or 0
            fta = row.get('FTA', 0) or 0
            player_data['PTS_PER_SHOT'] = self.calculate_points_per_shot(pts, fga, fta)
            
            # Points per touch
            touches = row.get('TOUCHES', 0) or 0
            player_data['PTS_PER_TOUCH'] = self.calculate_points_per_touch(pts, touches)
            
            # Points per possession (using approximate possessions)
            # Possessions used ≈ FGA + 0.44*FTA + TOV
            tov = row.get('TOV', 0) or 0
            poss_used = fga + (0.44 * fta) + tov
            player_data['PTS_PER_POSS'] = self.calculate_points_per_possession(pts, poss_used)
            
            # AST/TO ratio
            ast = row.get('AST', 0) or 0
            player_data['AST_TO_RATIO'] = self.calculate_ast_to_ratio(ast, tov)
            
            results.append(player_data)
        
        return pd.DataFrame(results)
    
    # =========================================================================
    # VOLATILITY / STABILITY METRICS
    # =========================================================================
    
    def calculate_volatility(self, values: pd.Series) -> float:
        """Calculate coefficient of variation (std/mean) as volatility measure"""
        if len(values) < 3:
            return None
        mean = values.mean()
        if mean == 0:
            return None
        return values.std() / mean
    
    def calculate_rolling_volatility(self, df: pd.DataFrame, column: str, window: int = 10) -> pd.Series:
        """Calculate rolling volatility over last N games"""
        return df[column].rolling(window=window, min_periods=3).std() / df[column].rolling(window=window, min_periods=3).mean()
    
    def calculate_player_volatility_metrics(self, game_logs: pd.DataFrame) -> Dict:
        """
        Calculate volatility metrics from player game logs
        
        Requires game-by-game data with: MIN, PTS, USG_PCT (if available)
        """
        if game_logs is None or len(game_logs) < 5:
            return {
                'USG_VOLATILITY': None,
                'MIN_VOLATILITY': None,
                'PTS_VOLATILITY': None,
                'ROLE_STABILITY': None,
            }
        
        metrics = {}
        
        # Usage volatility
        if 'USG_PCT' in game_logs.columns:
            metrics['USG_VOLATILITY'] = self.calculate_volatility(game_logs['USG_PCT'].dropna())
        else:
            metrics['USG_VOLATILITY'] = None
        
        # Minutes volatility
        if 'MIN' in game_logs.columns:
            metrics['MIN_VOLATILITY'] = self.calculate_volatility(game_logs['MIN'].dropna())
        else:
            metrics['MIN_VOLATILITY'] = None
        
        # Points volatility
        if 'PTS' in game_logs.columns:
            metrics['PTS_VOLATILITY'] = self.calculate_volatility(game_logs['PTS'].dropna())
        else:
            metrics['PTS_VOLATILITY'] = None
        
        # Role stability (inverse of combined volatility)
        # Higher = more stable role
        volatilities = [v for v in [metrics['USG_VOLATILITY'], metrics['MIN_VOLATILITY']] if v is not None]
        if volatilities:
            avg_volatility = np.mean(volatilities)
            metrics['ROLE_STABILITY'] = 1 / (1 + avg_volatility) if avg_volatility > 0 else 1.0
        else:
            metrics['ROLE_STABILITY'] = None
        
        return metrics
    
    # =========================================================================
    # CORRELATION COEFFICIENTS
    # =========================================================================
    
    def calculate_stat_correlations(self, game_logs: pd.DataFrame) -> Dict:
        """
        Calculate correlation coefficients between key stats
        
        Requires game-by-game data with: PTS, AST, REB
        """
        if game_logs is None or len(game_logs) < 10:
            return {
                'PTS_AST_CORR': None,
                'PTS_REB_CORR': None,
                'AST_REB_CORR': None,
            }
        
        correlations = {}
        
        # PTS-AST correlation
        if 'PTS' in game_logs.columns and 'AST' in game_logs.columns:
            valid = game_logs[['PTS', 'AST']].dropna()
            if len(valid) >= 10:
                correlations['PTS_AST_CORR'] = valid['PTS'].corr(valid['AST'])
            else:
                correlations['PTS_AST_CORR'] = None
        else:
            correlations['PTS_AST_CORR'] = None
        
        # PTS-REB correlation
        if 'PTS' in game_logs.columns and 'REB' in game_logs.columns:
            valid = game_logs[['PTS', 'REB']].dropna()
            if len(valid) >= 10:
                correlations['PTS_REB_CORR'] = valid['PTS'].corr(valid['REB'])
            else:
                correlations['PTS_REB_CORR'] = None
        else:
            correlations['PTS_REB_CORR'] = None
        
        # AST-REB correlation
        if 'AST' in game_logs.columns and 'REB' in game_logs.columns:
            valid = game_logs[['AST', 'REB']].dropna()
            if len(valid) >= 10:
                correlations['AST_REB_CORR'] = valid['AST'].corr(valid['REB'])
            else:
                correlations['AST_REB_CORR'] = None
        else:
            correlations['AST_REB_CORR'] = None
        
        return correlations
    
    def calculate_full_correlation_matrix(self, game_logs: pd.DataFrame) -> Optional[pd.DataFrame]:
        """Calculate full correlation matrix for all counting stats"""
        stat_cols = ['PTS', 'AST', 'REB', 'STL', 'BLK', 'TOV', 'FG3M', 'FTM']
        
        available_cols = [c for c in stat_cols if c in game_logs.columns]
        
        if len(available_cols) < 2 or len(game_logs) < 10:
            return None
        
        return game_logs[available_cols].corr()
    
    # =========================================================================
    # TEAM DERIVED METRICS
    # =========================================================================
    
    def calculate_blowout_risk_index(self, 
                                     net_rating: float, 
                                     pace: float,
                                     scoring_variance: float = None) -> float:
        """
        Calculate blowout risk index
        
        Higher values = higher chance of a blowout (either direction)
        Based on: team strength differential, pace, and scoring variance
        """
        # Base on absolute net rating (strength)
        strength_factor = abs(net_rating) / 10  # Normalize
        
        # Pace factor (faster pace = more variance)
        pace_factor = (pace - 95) / 10  # Normalize around league average ~100
        
        # Combine factors
        risk_index = strength_factor * (1 + pace_factor * 0.2)
        
        if scoring_variance:
            risk_index *= (1 + scoring_variance * 0.1)
        
        return min(risk_index, 1.0)  # Cap at 1.0
    
    def calculate_pace_volatility(self, game_logs: pd.DataFrame) -> Optional[float]:
        """Calculate how much a team's pace varies game to game"""
        # Estimate pace from game data if not directly available
        # Pace proxy = (FGA + 0.44*FTA - OREB + TOV) 
        
        if 'PACE' in game_logs.columns:
            return self.calculate_volatility(game_logs['PACE'].dropna())
        
        # Calculate proxy pace
        required_cols = ['FGA', 'FTA', 'OREB', 'TOV', 'MIN']
        if not all(c in game_logs.columns for c in required_cols):
            return None
        
        game_logs = game_logs.copy()
        game_logs['PACE_PROXY'] = (
            (game_logs['FGA'] + 0.44 * game_logs['FTA'] - game_logs['OREB'] + game_logs['TOV'])
            * 48 / game_logs['MIN']
        )
        
        return self.calculate_volatility(game_logs['PACE_PROXY'].dropna())
    
    # =========================================================================
    # USAGE ELASTICITY
    # =========================================================================
    
    def calculate_usage_elasticity(self, 
                                   player_logs: pd.DataFrame,
                                   teammate_absence_games: pd.DataFrame = None) -> Optional[float]:
        """
        Calculate how much a player's usage changes when teammates are out
        
        Usage elasticity = (USG% with teammate out - USG% baseline) / USG% baseline
        
        Higher = more elastic role (expands when others are out)
        """
        if 'USG_PCT' not in player_logs.columns:
            return None
        
        baseline_usg = player_logs['USG_PCT'].mean()
        
        if baseline_usg == 0:
            return None
        
        if teammate_absence_games is not None and len(teammate_absence_games) >= 3:
            absence_usg = teammate_absence_games['USG_PCT'].mean()
            return (absence_usg - baseline_usg) / baseline_usg
        
        # If no teammate absence data, estimate from variance
        # Higher variance suggests more role elasticity
        usg_std = player_logs['USG_PCT'].std()
        return usg_std / baseline_usg
    
    # =========================================================================
    # PROP SENSITIVITY METRICS
    # =========================================================================
    
    def calculate_prop_sensitivity_to_pace(self, 
                                          player_logs: pd.DataFrame,
                                          stat: str = 'PTS') -> Optional[float]:
        """
        Calculate how sensitive a player's stats are to game pace
        
        Returns correlation between stat and game pace
        """
        if stat not in player_logs.columns:
            return None
        
        # Need pace data - try multiple column names
        pace_col = None
        for col in ['PACE', 'POSS', 'pace', 'poss']:
            if col in player_logs.columns:
                pace_col = col
                break
        
        if pace_col is None:
            return None
        
        valid = player_logs[[stat, pace_col]].dropna()
        if len(valid) < 10:
            return None
        
        return valid[stat].corr(valid[pace_col])
    
    # =========================================================================
    # BATCH PROCESSING
    # =========================================================================
    
    def process_all_players(self,
                           player_base: pd.DataFrame,
                           player_tracking: pd.DataFrame = None,
                           player_game_logs: Dict[int, pd.DataFrame] = None) -> pd.DataFrame:
        """
        Process all derived stats for all players
        
        Args:
            player_base: Base player stats DataFrame
            player_tracking: Player tracking data (touches, etc.)
            player_game_logs: Dict mapping player_id to their game logs DataFrame
        """
        print("  📊 Calculating derived player stats...", end=" ", flush=True)
        
        # Start with efficiency metrics
        if player_tracking is not None:
            derived = self.calculate_player_efficiency_metrics(player_base, player_tracking)
        else:
            # Create basic derived stats without tracking
            derived = pd.DataFrame({
                'PLAYER_ID': player_base['PLAYER_ID'],
                'PLAYER_NAME': player_base['PLAYER_NAME'],
                'TEAM_ID': player_base['TEAM_ID'],
            })
            
            # Calculate what we can
            derived['PTS_PER_SHOT'] = player_base.apply(
                lambda r: self.calculate_points_per_shot(
                    r.get('PTS', 0) or 0,
                    r.get('FGA', 0) or 0,
                    r.get('FTA', 0) or 0
                ), axis=1
            )
            derived['AST_TO_RATIO'] = player_base.apply(
                lambda r: self.calculate_ast_to_ratio(
                    r.get('AST', 0) or 0,
                    r.get('TOV', 0) or 0
                ), axis=1
            )
        
        # Add volatility and correlation metrics if game logs available
        if player_game_logs:
            volatility_data = []
            correlation_data = []
            
            for player_id in derived['PLAYER_ID'].unique():
                if player_id in player_game_logs:
                    logs = player_game_logs[player_id]
                    
                    vol = self.calculate_player_volatility_metrics(logs)
                    vol['PLAYER_ID'] = player_id
                    volatility_data.append(vol)
                    
                    corr = self.calculate_stat_correlations(logs)
                    corr['PLAYER_ID'] = player_id
                    correlation_data.append(corr)
            
            if volatility_data:
                vol_df = pd.DataFrame(volatility_data)
                derived = derived.merge(vol_df, on='PLAYER_ID', how='left')
            
            if correlation_data:
                corr_df = pd.DataFrame(correlation_data)
                derived = derived.merge(corr_df, on='PLAYER_ID', how='left')
        
        derived['pull_date'] = self.pull_date
        print(f"✅ {len(derived)} players")
        
        return derived
    
    def process_all_teams(self,
                         team_advanced: pd.DataFrame,
                         team_game_logs: Dict[int, pd.DataFrame] = None) -> pd.DataFrame:
        """
        Process all derived stats for all teams
        """
        print("  📊 Calculating derived team stats...", end=" ", flush=True)
        
        results = []
        
        for _, row in team_advanced.iterrows():
            team_data = {
                'TEAM_ID': row.get('TEAM_ID'),
                'TEAM_ABBREVIATION': row.get('TEAM_NAME', '').split()[-1] if row.get('TEAM_NAME') else None,
            }
            
            # Blowout risk index
            net_rating = row.get('NET_RATING', 0) or 0
            pace = row.get('PACE', 100) or 100
            team_data['BLOWOUT_RISK_INDEX'] = self.calculate_blowout_risk_index(net_rating, pace)
            
            # Pace volatility (if game logs available)
            team_id = row.get('TEAM_ID')
            if team_game_logs and team_id in team_game_logs:
                team_data['PACE_VOLATILITY'] = self.calculate_pace_volatility(team_game_logs[team_id])
            else:
                team_data['PACE_VOLATILITY'] = None
            
            results.append(team_data)
        
        derived = pd.DataFrame(results)
        derived['pull_date'] = self.pull_date
        print(f"✅ {len(derived)} teams")
        
        return derived


if __name__ == "__main__":
    # Test with sample data
    print("\n🧪 Testing Derived Stats Calculator")
    print("=" * 50)
    
    calc = DerivedStatsCalculator()
    
    # Test efficiency metrics
    print("\n📊 Testing efficiency calculations:")
    print(f"  PTS per shot (25 PTS, 15 FGA, 8 FTA): {calc.calculate_points_per_shot(25, 15, 8):.2f}")
    print(f"  PTS per touch (25 PTS, 50 touches): {calc.calculate_points_per_touch(25, 50):.2f}")
    print(f"  AST/TO ratio (8 AST, 2 TOV): {calc.calculate_ast_to_ratio(8, 2):.2f}")
    
    # Test volatility
    print("\n📊 Testing volatility calculations:")
    sample_data = pd.Series([25, 22, 30, 18, 28, 24, 35, 20, 27, 23])
    print(f"  Volatility of {sample_data.tolist()}: {calc.calculate_volatility(sample_data):.3f}")
    
    # Test blowout risk
    print("\n📊 Testing blowout risk:")
    print(f"  Risk (Net +10, Pace 105): {calc.calculate_blowout_risk_index(10, 105):.3f}")
    print(f"  Risk (Net +2, Pace 95): {calc.calculate_blowout_risk_index(2, 95):.3f}")
    print(f"  Risk (Net -8, Pace 102): {calc.calculate_blowout_risk_index(-8, 102):.3f}")
