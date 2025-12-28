"""
NBA Stats Puller
Fetches all data from NBA.com Stats API
"""

import requests
import pandas as pd
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import (
    NBA_STATS_BASE_URL, 
    NBA_STATS_HEADERS, 
    NBA_ENDPOINTS, 
    NBA_DELAY_SECONDS,
    CURRENT_SEASON
)


class NBAStatsPuller:
    """Pulls all stats from NBA.com Stats API"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(NBA_STATS_HEADERS)
        self.pull_date = datetime.now().strftime('%Y-%m-%d')
        
    def _make_request(self, endpoint: str, params: Dict) -> Optional[Dict]:
        """Make a request to NBA.com API with retry logic"""
        url = f"{NBA_STATS_BASE_URL}/{endpoint}"
        
        for attempt in range(3):
            try:
                response = self.session.get(url, params=params, timeout=30)
                response.raise_for_status()
                return response.json()
            except requests.exceptions.RequestException as e:
                print(f"  ⚠️  Attempt {attempt + 1}/3 failed: {str(e)[:50]}")
                if attempt < 2:
                    time.sleep(5 * (attempt + 1))  # Exponential backoff
                else:
                    print(f"  ❌ Failed to fetch {endpoint}")
                    return None
        return None
    
    def _parse_response(self, data: Dict, result_set_index: int = 0) -> Optional[pd.DataFrame]:
        """Parse NBA.com API response into DataFrame"""
        if not data or 'resultSets' not in data:
            return None
        
        if len(data['resultSets']) <= result_set_index:
            return None
            
        result_set = data['resultSets'][result_set_index]
        headers = result_set.get('headers', [])
        rows = result_set.get('rowSet', [])
        
        if not headers or not rows:
            return None
            
        return pd.DataFrame(rows, columns=headers)
    
    def pull_endpoint(self, endpoint_key: str) -> Optional[pd.DataFrame]:
        """Pull data for a specific endpoint configuration"""
        if endpoint_key not in NBA_ENDPOINTS:
            print(f"  ❌ Unknown endpoint: {endpoint_key}")
            return None
            
        config = NBA_ENDPOINTS[endpoint_key]
        endpoint = config['endpoint']
        params = config['params']
        
        print(f"  📡 Pulling {endpoint_key}...", end=" ", flush=True)
        
        data = self._make_request(endpoint, params)
        if data is None:
            return None
            
        df = self._parse_response(data)
        if df is not None:
            print(f"✅ {len(df)} rows")
        else:
            print("⚠️  No data")
            
        time.sleep(NBA_DELAY_SECONDS)
        return df
    
    def pull_shot_zones(self) -> Optional[pd.DataFrame]:
        """Pull shot zone data - requires special parsing due to multi-header structure"""
        config = NBA_ENDPOINTS.get('player_shots_general')
        if not config:
            return None
            
        print(f"  📡 Pulling player_shots_general...", end=" ", flush=True)
        
        try:
            data = self._make_request(config['endpoint'], config['params'])
            if not data:
                print("⚠️  Skipped (no data)")
                time.sleep(NBA_DELAY_SECONDS)
                return None
            
            # Handle different response structures
            result_set = None
            if 'resultSets' in data:
                if isinstance(data['resultSets'], list) and len(data['resultSets']) > 0:
                    result_set = data['resultSets'][0]
                elif isinstance(data['resultSets'], dict):
                    result_set = data['resultSets']
            elif 'resultSet' in data:
                result_set = data['resultSet']
            
            if not result_set:
                print("⚠️  Skipped (unexpected format)")
                time.sleep(NBA_DELAY_SECONDS)
                return None
            
            # Get headers and rows
            headers = result_set.get('headers', [])
            rows = result_set.get('rowSet', [])
            
            if not rows:
                print("⚠️  Skipped (no rows)")
                time.sleep(NBA_DELAY_SECONDS)
                return None
            
            # If we have headers, use them directly
            if headers:
                df = pd.DataFrame(rows, columns=headers)
                print(f"✅ {len(df)} rows")
                time.sleep(NBA_DELAY_SECONDS)
                return df
            
            # Otherwise create DataFrame without headers and try to map
            df = pd.DataFrame(rows)
            
            # Basic columns mapping (simplified - actual structure is complex)
            if len(df.columns) >= 7:
                zone_mapping = [
                    ('RA', 7),      # Restricted Area
                    ('PAINT', 10),  # Paint (Non-RA)
                    ('MR', 13),     # Mid-Range
                    ('LC3', 16),    # Left Corner 3
                    ('RC3', 19),    # Right Corner 3
                    ('AB3', 22),    # Above Break 3
                    ('BC', 25),     # Backcourt
                ]
                
                result_data = []
                for _, row in df.iterrows():
                    player_data = {
                        'PLAYER_ID': row.iloc[0] if len(row) > 0 else None,
                        'PLAYER_NAME': row.iloc[1] if len(row) > 1 else None,
                        'TEAM_ID': row.iloc[2] if len(row) > 2 else None,
                        'TEAM_ABBREVIATION': row.iloc[3] if len(row) > 3 else None,
                        'AGE': row.iloc[4] if len(row) > 4 else None,
                        'GP': row.iloc[5] if len(row) > 5 else None,
                    }
                    
                    for zone_name, start_idx in zone_mapping:
                        if len(row) > start_idx + 2:
                            player_data[f'{zone_name}_FGM'] = row.iloc[start_idx]
                            player_data[f'{zone_name}_FGA'] = row.iloc[start_idx + 1]
                            player_data[f'{zone_name}_FG_PCT'] = row.iloc[start_idx + 2]
                    
                    result_data.append(player_data)
                
                result_df = pd.DataFrame(result_data)
                print(f"✅ {len(result_df)} rows")
                time.sleep(NBA_DELAY_SECONDS)
                return result_df
            
            print("⚠️  Unexpected structure")
            time.sleep(NBA_DELAY_SECONDS)
            return None
            
        except Exception as e:
            print(f"⚠️  Skipped (error: {str(e)[:30]})")
            time.sleep(NBA_DELAY_SECONDS)
            return None
    
    def pull_all_team_stats(self) -> Dict[str, pd.DataFrame]:
        """Pull all team-level statistics"""
        print("\n🏀 PULLING TEAM STATS")
        print("=" * 50)
        
        results = {}
        team_endpoints = [
            'team_base',
            'team_advanced', 
            'team_four_factors',
            'team_scoring',
            'team_opponent',
            'team_hustle',
            'team_clutch',
        ]
        
        for endpoint_key in team_endpoints:
            df = self.pull_endpoint(endpoint_key)
            if df is not None:
                results[endpoint_key] = df
                
        return results
    
    def pull_all_player_stats(self) -> Dict[str, pd.DataFrame]:
        """Pull all player-level statistics"""
        print("\n👤 PULLING PLAYER STATS")
        print("=" * 50)
        
        results = {}
        player_endpoints = [
            'player_base',
            'player_advanced',
            'player_scoring',
            'player_usage',
            'player_tracking_touches',
            'player_tracking_passes',
            'player_tracking_rebounding',
            'player_hustle',
            'player_clutch',
            'player_on_off',
        ]
        
        for endpoint_key in player_endpoints:
            df = self.pull_endpoint(endpoint_key)
            if df is not None:
                results[endpoint_key] = df
        
        # Shot zones need special handling
        shot_zones = self.pull_shot_zones()
        if shot_zones is not None:
            results['player_shots_general'] = shot_zones
                
        return results
    
    def pull_lineups(self) -> Optional[pd.DataFrame]:
        """Pull lineup statistics"""
        print("\n👥 PULLING LINEUP STATS")
        print("=" * 50)
        return self.pull_endpoint('lineups')
    
    def pull_defense_dashboard(self) -> Optional[pd.DataFrame]:
        """Pull defense dashboard stats"""
        print("\n🛡️ PULLING DEFENSE DASHBOARD")
        print("=" * 50)
        return self.pull_endpoint('defense_dashboard')
    
    def pull_schedule(self) -> Optional[pd.DataFrame]:
        """Pull schedule/game log data"""
        print("\n📅 PULLING SCHEDULE")
        print("=" * 50)
        return self.pull_endpoint('schedule')
    
    def pull_all(self) -> Dict[str, pd.DataFrame]:
        """Pull ALL data from NBA.com"""
        print("\n" + "=" * 60)
        print("🚀 NBA.COM FULL DATA PULL")
        print(f"📅 Date: {self.pull_date}")
        print(f"🏀 Season: {CURRENT_SEASON}")
        print("=" * 60)
        
        all_results = {}
        
        # Team Stats
        team_results = self.pull_all_team_stats()
        all_results.update(team_results)
        
        # Player Stats
        player_results = self.pull_all_player_stats()
        all_results.update(player_results)
        
        # Lineups
        lineups = self.pull_lineups()
        if lineups is not None:
            all_results['lineups'] = lineups
        
        # Defense Dashboard
        defense = self.pull_defense_dashboard()
        if defense is not None:
            all_results['defense_dashboard'] = defense
        
        # Schedule
        schedule = self.pull_schedule()
        if schedule is not None:
            all_results['schedule'] = schedule
        
        # Summary
        print("\n" + "=" * 60)
        print("📊 PULL SUMMARY")
        print("=" * 60)
        total_rows = 0
        for key, df in all_results.items():
            rows = len(df)
            total_rows += rows
            print(f"  {key}: {rows} rows")
        print(f"\n  TOTAL: {total_rows} rows across {len(all_results)} tables")
        print("=" * 60)
        
        return all_results


def pull_player_game_logs(player_id: int, season: str = CURRENT_SEASON) -> Optional[pd.DataFrame]:
    """Pull individual player game logs for volatility calculations"""
    
    session = requests.Session()
    session.headers.update(NBA_STATS_HEADERS)
    
    url = f"{NBA_STATS_BASE_URL}/playergamelog"
    params = {
        'PlayerID': player_id,
        'Season': season,
        'SeasonType': 'Regular Season',
    }
    
    try:
        response = session.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        if 'resultSets' in data and len(data['resultSets']) > 0:
            result = data['resultSets'][0]
            df = pd.DataFrame(result['rowSet'], columns=result['headers'])
            return df
    except Exception as e:
        print(f"Error fetching game logs for player {player_id}: {e}")
    
    return None


def pull_team_game_logs(team_id: int, season: str = CURRENT_SEASON) -> Optional[pd.DataFrame]:
    """Pull team game logs for schedule/rest calculations"""
    
    session = requests.Session()
    session.headers.update(NBA_STATS_HEADERS)
    
    url = f"{NBA_STATS_BASE_URL}/teamgamelog"
    params = {
        'TeamID': team_id,
        'Season': season,
        'SeasonType': 'Regular Season',
    }
    
    try:
        response = session.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        if 'resultSets' in data and len(data['resultSets']) > 0:
            result = data['resultSets'][0]
            df = pd.DataFrame(result['rowSet'], columns=result['headers'])
            return df
    except Exception as e:
        print(f"Error fetching game logs for team {team_id}: {e}")
    
    return None


if __name__ == "__main__":
    # Test the puller
    puller = NBAStatsPuller()
    results = puller.pull_all()
