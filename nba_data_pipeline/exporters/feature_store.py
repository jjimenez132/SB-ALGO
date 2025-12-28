#!/usr/bin/env python3
"""
Feature Store Exporter
Exports processed features ready for model consumption.

Creates consolidated views of:
- Team features (all team stats merged)
- Player features (all player stats merged)
- Matchup features (for upcoming games)
- Historical features (for backtesting)
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Optional, Dict, List
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import get_connection, get_latest_data
from config import DATA_DIR, TEAM_ID_TO_ABBREV


class FeatureExporter:
    """Exports consolidated feature sets for modeling"""
    
    def __init__(self, pull_date: str = None):
        self.pull_date = pull_date or datetime.now().strftime('%Y-%m-%d')
        self.conn = get_connection()
        
    def close(self):
        """Close database connection"""
        self.conn.close()
    
    # =========================================================================
    # TEAM FEATURES
    # =========================================================================
    
    def get_team_features(self) -> pd.DataFrame:
        """
        Get consolidated team features
        
        Merges:
        - Base stats
        - Advanced stats (ORtg, DRtg, Net Rating, Pace)
        - Four Factors
        - Scoring breakdown
        - Opponent stats (defense)
        - Hustle stats
        - Clutch stats
        """
        print("  📊 Building team features...", end=" ", flush=True)
        
        # Load all team tables
        team_base = get_latest_data('team_base_stats', self.pull_date)
        team_adv = get_latest_data('team_advanced_stats', self.pull_date)
        team_ff = get_latest_data('team_four_factors', self.pull_date)
        team_scoring = get_latest_data('team_scoring', self.pull_date)
        team_opp = get_latest_data('team_opponent_stats', self.pull_date)
        team_hustle = get_latest_data('team_hustle', self.pull_date)
        team_clutch = get_latest_data('team_clutch', self.pull_date)
        
        # Start with advanced stats as base (most important)
        if team_adv.empty:
            print("❌ No team data")
            return pd.DataFrame()
        
        # Select key columns from each source to avoid duplicates
        features = team_adv[['TEAM_ID', 'TEAM_NAME', 'GP', 'W', 'L', 'W_PCT',
                            'OFF_RATING', 'DEF_RATING', 'NET_RATING', 'PACE',
                            'AST_PCT', 'AST_TO', 'OREB_PCT', 'DREB_PCT', 'REB_PCT',
                            'TM_TOV_PCT', 'EFG_PCT', 'TS_PCT', 'PIE']].copy()
        
        # Add four factors
        if not team_ff.empty:
            ff_cols = ['TEAM_ID', 'FTA_RATE', 'OPP_EFG_PCT', 'OPP_FTA_RATE', 
                      'OPP_TOV_PCT', 'OPP_OREB_PCT']
            ff_cols = [c for c in ff_cols if c in team_ff.columns]
            features = features.merge(team_ff[ff_cols], on='TEAM_ID', how='left')
        
        # Add scoring breakdown
        if not team_scoring.empty:
            scoring_cols = ['TEAM_ID', 'PCT_FGA_2PT', 'PCT_FGA_3PT', 'PCT_PTS_2PT',
                          'PCT_PTS_3PT', 'PCT_PTS_FB', 'PCT_PTS_FT', 'PCT_PTS_PAINT',
                          'PCT_AST_FGM', 'PCT_UAST_FGM']
            scoring_cols = [c for c in scoring_cols if c in team_scoring.columns]
            features = features.merge(team_scoring[scoring_cols], on='TEAM_ID', how='left')
        
        # Add opponent/defense stats
        if not team_opp.empty:
            opp_cols = ['TEAM_ID', 'OPP_FG_PCT', 'OPP_FG3_PCT', 'OPP_PTS']
            opp_cols = [c for c in opp_cols if c in team_opp.columns]
            features = features.merge(team_opp[opp_cols], on='TEAM_ID', how='left')
        
        # Add hustle stats
        if not team_hustle.empty:
            hustle_cols = ['TEAM_ID', 'DEFLECTIONS', 'CONTESTED_SHOTS', 
                          'LOOSE_BALLS_RECOVERED', 'BOX_OUTS']
            hustle_cols = [c for c in hustle_cols if c in team_hustle.columns]
            features = features.merge(team_hustle[hustle_cols], on='TEAM_ID', how='left')
        
        # Add clutch prefix to clutch stats
        if not team_clutch.empty:
            clutch_cols = ['TEAM_ID', 'FG_PCT', 'FG3_PCT', 'FT_PCT', 'TOV', 'PLUS_MINUS']
            clutch_cols = [c for c in clutch_cols if c in team_clutch.columns]
            clutch_data = team_clutch[clutch_cols].copy()
            clutch_data.columns = ['TEAM_ID'] + ['CLUTCH_' + c for c in clutch_cols[1:]]
            features = features.merge(clutch_data, on='TEAM_ID', how='left')
        
        # Add team abbreviation
        features['TEAM_ABBREV'] = features['TEAM_ID'].map(TEAM_ID_TO_ABBREV)
        
        # Add pull date
        features['pull_date'] = self.pull_date
        
        print(f"✅ {len(features)} teams, {len(features.columns)} features")
        return features
    
    # =========================================================================
    # PLAYER FEATURES
    # =========================================================================
    
    def get_player_features(self, min_games: int = 5) -> pd.DataFrame:
        """
        Get consolidated player features
        
        Merges:
        - Base stats
        - Advanced stats (ORtg, DRtg, USG%, etc.)
        - Scoring breakdown
        - Usage stats
        - Tracking (touches, passes, rebounds)
        - Hustle stats
        - Clutch stats
        - BPM/VORP from BBRef
        """
        print("  📊 Building player features...", end=" ", flush=True)
        
        # Load all player tables
        player_base = get_latest_data('player_base_stats', self.pull_date)
        player_adv = get_latest_data('player_advanced_stats', self.pull_date)
        player_scoring = get_latest_data('player_scoring', self.pull_date)
        player_usage = get_latest_data('player_usage', self.pull_date)
        player_tracking_poss = get_latest_data('player_tracking_possessions', self.pull_date)
        player_tracking_pass = get_latest_data('player_tracking_passes', self.pull_date)
        player_hustle = get_latest_data('player_hustle', self.pull_date)
        player_clutch = get_latest_data('player_clutch', self.pull_date)
        player_bpm = get_latest_data('player_bpm_vorp', self.pull_date)
        
        if player_base.empty:
            print("❌ No player data")
            return pd.DataFrame()
        
        # Filter by minimum games
        player_base = player_base[player_base['GP'] >= min_games]
        
        # Start with base stats
        base_cols = ['PLAYER_ID', 'PLAYER_NAME', 'TEAM_ID', 'TEAM_ABBREVIATION',
                    'AGE', 'GP', 'W', 'L', 'W_PCT', 'MIN', 'PTS', 'FGM', 'FGA',
                    'FG_PCT', 'FG3M', 'FG3A', 'FG3_PCT', 'FTM', 'FTA', 'FT_PCT',
                    'OREB', 'DREB', 'REB', 'AST', 'TOV', 'STL', 'BLK', 'PF', 'PLUS_MINUS']
        base_cols = [c for c in base_cols if c in player_base.columns]
        features = player_base[base_cols].copy()
        
        # Add advanced stats
        if not player_adv.empty:
            adv_cols = ['PLAYER_ID', 'OFF_RATING', 'DEF_RATING', 'NET_RATING',
                       'AST_PCT', 'AST_TO', 'AST_RATIO', 'OREB_PCT', 'DREB_PCT',
                       'REB_PCT', 'TM_TOV_PCT', 'EFG_PCT', 'TS_PCT', 'USG_PCT', 'PACE', 'PIE']
            adv_cols = [c for c in adv_cols if c in player_adv.columns]
            features = features.merge(player_adv[adv_cols], on='PLAYER_ID', how='left')
        
        # Add scoring breakdown
        if not player_scoring.empty:
            scoring_cols = ['PLAYER_ID', 'PCT_FGA_2PT', 'PCT_FGA_3PT', 'PCT_PTS_2PT',
                          'PCT_PTS_3PT', 'PCT_PTS_FB', 'PCT_PTS_FT', 'PCT_PTS_PAINT',
                          'PCT_AST_FGM', 'PCT_UAST_FGM']
            scoring_cols = [c for c in scoring_cols if c in player_scoring.columns]
            features = features.merge(player_scoring[scoring_cols], on='PLAYER_ID', how='left')
        
        # Add usage stats
        if not player_usage.empty:
            usage_cols = ['PLAYER_ID', 'PCT_FGM', 'PCT_FGA', 'PCT_FG3M', 'PCT_FG3A',
                         'PCT_FTM', 'PCT_FTA', 'PCT_OREB', 'PCT_DREB', 'PCT_REB',
                         'PCT_AST', 'PCT_TOV', 'PCT_STL', 'PCT_BLK', 'PCT_PTS']
            usage_cols = [c for c in usage_cols if c in player_usage.columns]
            features = features.merge(player_usage[usage_cols], on='PLAYER_ID', how='left')
        
        # Add tracking - possessions/touches
        if not player_tracking_poss.empty:
            track_cols = ['PLAYER_ID', 'TOUCHES', 'FRONT_CT_TOUCHES', 'TIME_OF_POSS',
                         'AVG_SEC_PER_TOUCH', 'AVG_DRIB_PER_TOUCH', 'PTS_PER_TOUCH',
                         'ELBOW_TOUCHES', 'POST_TOUCHES', 'PAINT_TOUCHES']
            track_cols = [c for c in track_cols if c in player_tracking_poss.columns]
            features = features.merge(player_tracking_poss[track_cols], on='PLAYER_ID', how='left')
        
        # Add tracking - passing
        if not player_tracking_pass.empty:
            pass_cols = ['PLAYER_ID', 'PASSES_MADE', 'PASSES_RECEIVED', 
                        'SECONDARY_AST', 'POTENTIAL_AST', 'AST_PTS_CREATED']
            pass_cols = [c for c in pass_cols if c in player_tracking_pass.columns]
            features = features.merge(player_tracking_pass[pass_cols], on='PLAYER_ID', how='left')
        
        # Add hustle stats
        if not player_hustle.empty:
            hustle_cols = ['PLAYER_ID', 'DEFLECTIONS', 'CONTESTED_SHOTS',
                          'LOOSE_BALLS_RECOVERED', 'BOX_OUTS', 'CHARGES_DRAWN']
            hustle_cols = [c for c in hustle_cols if c in player_hustle.columns]
            features = features.merge(player_hustle[hustle_cols], on='PLAYER_ID', how='left')
        
        # Add clutch stats (with prefix)
        if not player_clutch.empty:
            clutch_cols = ['PLAYER_ID', 'MIN', 'PTS', 'FG_PCT', 'FG3_PCT', 'FT_PCT', 'TOV']
            clutch_cols = [c for c in clutch_cols if c in player_clutch.columns]
            clutch_data = player_clutch[clutch_cols].copy()
            clutch_data.columns = ['PLAYER_ID'] + ['CLUTCH_' + c for c in clutch_cols[1:]]
            features = features.merge(clutch_data, on='PLAYER_ID', how='left')
        
        # Add BPM/VORP (need to fuzzy match on name since BBRef doesn't have IDs)
        if not player_bpm.empty:
            # Simple name match (could be improved with fuzzy matching)
            bpm_cols = ['PLAYER_NAME', 'BPM', 'OBPM', 'DBPM', 'VORP', 'WS', 'WS_48']
            bpm_cols = [c for c in bpm_cols if c in player_bpm.columns]
            bpm_data = player_bpm[bpm_cols].drop_duplicates('PLAYER_NAME')
            features = features.merge(bpm_data, on='PLAYER_NAME', how='left')
        
        # Add derived stats
        features['PTS_PER_MIN'] = features['PTS'] / features['MIN'].replace(0, np.nan)
        features['AST_TO_RATIO'] = features['AST'] / features['TOV'].replace(0, np.nan)
        features['REB_PER_MIN'] = features['REB'] / features['MIN'].replace(0, np.nan)
        
        # Add pull date
        features['pull_date'] = self.pull_date
        
        print(f"✅ {len(features)} players, {len(features.columns)} features")
        return features
    
    # =========================================================================
    # MATCHUP FEATURES
    # =========================================================================
    
    def get_matchup_features(self, 
                            home_team_id: int, 
                            away_team_id: int) -> Optional[Dict]:
        """
        Generate features for a specific matchup
        
        Combines:
        - Team vs team statistical differentials
        - Rest/schedule context
        - Historical head-to-head (if available)
        """
        team_features = self.get_team_features()
        
        if team_features.empty:
            return None
        
        home = team_features[team_features['TEAM_ID'] == home_team_id]
        away = team_features[team_features['TEAM_ID'] == away_team_id]
        
        if home.empty or away.empty:
            return None
        
        home = home.iloc[0]
        away = away.iloc[0]
        
        matchup = {
            'HOME_TEAM_ID': home_team_id,
            'AWAY_TEAM_ID': away_team_id,
            'HOME_TEAM': home.get('TEAM_ABBREV'),
            'AWAY_TEAM': away.get('TEAM_ABBREV'),
            
            # Differentials (home - away)
            'NET_RATING_DIFF': home.get('NET_RATING', 0) - away.get('NET_RATING', 0),
            'OFF_RATING_DIFF': home.get('OFF_RATING', 0) - away.get('OFF_RATING', 0),
            'DEF_RATING_DIFF': home.get('DEF_RATING', 0) - away.get('DEF_RATING', 0),
            'PACE_AVG': (home.get('PACE', 100) + away.get('PACE', 100)) / 2,
            'PACE_DIFF': home.get('PACE', 100) - away.get('PACE', 100),
            
            # Four factors differential
            'EFG_DIFF': home.get('EFG_PCT', 0) - away.get('EFG_PCT', 0),
            'TOV_DIFF': home.get('TM_TOV_PCT', 0) - away.get('TM_TOV_PCT', 0),
            'OREB_DIFF': home.get('OREB_PCT', 0) - away.get('OREB_PCT', 0),
            'FTA_RATE_DIFF': home.get('FTA_RATE', 0) - away.get('FTA_RATE', 0),
            
            # Win percentages
            'HOME_WIN_PCT': home.get('W_PCT', 0.5),
            'AWAY_WIN_PCT': away.get('W_PCT', 0.5),
            'WIN_PCT_DIFF': home.get('W_PCT', 0.5) - away.get('W_PCT', 0.5),
            
            # Home team absolute stats
            'HOME_OFF_RATING': home.get('OFF_RATING'),
            'HOME_DEF_RATING': home.get('DEF_RATING'),
            'HOME_NET_RATING': home.get('NET_RATING'),
            'HOME_PACE': home.get('PACE'),
            
            # Away team absolute stats
            'AWAY_OFF_RATING': away.get('OFF_RATING'),
            'AWAY_DEF_RATING': away.get('DEF_RATING'),
            'AWAY_NET_RATING': away.get('NET_RATING'),
            'AWAY_PACE': away.get('PACE'),
            
            # Predicted total (simplified)
            'PRED_TOTAL': self._estimate_total(home, away),
            
            # Predicted spread (simplified, positive = home favored)
            'PRED_SPREAD': self._estimate_spread(home, away),
        }
        
        return matchup
    
    def _estimate_total(self, home: pd.Series, away: pd.Series) -> float:
        """Simple total estimation based on pace and ratings"""
        # Average pace
        pace = (home.get('PACE', 100) + away.get('PACE', 100)) / 2
        
        # Normalize to possessions per game (pace is per 48 min)
        possessions = pace * (48 / 48)  # ~= pace
        
        # Points per possession
        home_ppp = home.get('OFF_RATING', 110) / 100
        away_ppp = away.get('OFF_RATING', 110) / 100
        
        # Account for defensive impact
        home_def = home.get('DEF_RATING', 110) / 100
        away_def = away.get('DEF_RATING', 110) / 100
        
        # Expected points (rough)
        home_pts = possessions * (home_ppp + away_def) / 2
        away_pts = possessions * (away_ppp + home_def) / 2
        
        return round(home_pts + away_pts, 1)
    
    def _estimate_spread(self, home: pd.Series, away: pd.Series) -> float:
        """Simple spread estimation based on net ratings"""
        # Net rating differential
        net_diff = home.get('NET_RATING', 0) - away.get('NET_RATING', 0)
        
        # Home court advantage (~3 points)
        hca = 3.0
        
        # Rough conversion: 1 net rating point ≈ 0.3 game points
        spread = (net_diff * 0.3) + hca
        
        return round(spread, 1)
    
    # =========================================================================
    # EXPORT FUNCTIONS
    # =========================================================================
    
    def export_all(self, output_dir: str = None) -> Dict[str, str]:
        """Export all feature sets to CSV files"""
        if output_dir is None:
            output_dir = DATA_DIR / 'exports'
        
        output_dir = pd.io.common.Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        date_str = datetime.now().strftime('%Y%m%d')
        exports = {}
        
        print("\n📁 EXPORTING FEATURE SETS")
        print("=" * 50)
        
        # Team features
        team_features = self.get_team_features()
        if not team_features.empty:
            path = output_dir / f'team_features_{date_str}.csv'
            team_features.to_csv(path, index=False)
            exports['team_features'] = str(path)
            print(f"  ✅ Team features: {path}")
        
        # Player features
        player_features = self.get_player_features()
        if not player_features.empty:
            path = output_dir / f'player_features_{date_str}.csv'
            player_features.to_csv(path, index=False)
            exports['player_features'] = str(path)
            print(f"  ✅ Player features: {path}")
        
        print(f"\n📊 Exported {len(exports)} feature sets to {output_dir}")
        
        return exports


def main():
    """CLI interface for feature export"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Export NBA features')
    parser.add_argument('--date', type=str, help='Pull date (YYYY-MM-DD)')
    parser.add_argument('--output', type=str, help='Output directory')
    parser.add_argument('--teams', action='store_true', help='Export team features only')
    parser.add_argument('--players', action='store_true', help='Export player features only')
    args = parser.parse_args()
    
    exporter = FeatureExporter(pull_date=args.date)
    
    if args.teams:
        df = exporter.get_team_features()
        print(df.head())
    elif args.players:
        df = exporter.get_player_features()
        print(df.head())
    else:
        exporter.export_all(output_dir=args.output)
    
    exporter.close()


if __name__ == "__main__":
    main()
