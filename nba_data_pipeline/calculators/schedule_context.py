"""
Schedule Context Calculator
Computes schedule-based contextual variables:
- Rest days
- Back-to-back games
- 3-in-4, 4-in-6 situations
- Travel distance
- Timezone changes
- Altitude changes
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from math import radians, cos, sin, asin, sqrt
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import TEAM_LOCATIONS, TEAM_ID_TO_ABBREV


class ScheduleContextCalculator:
    """Calculates all schedule-related contextual variables"""
    
    # Timezone offset from ET (for timezone change calculations)
    TIMEZONE_OFFSETS = {
        'America/New_York': 0,
        'America/Detroit': 0,
        'America/Indiana/Indianapolis': 0,
        'America/Toronto': 0,
        'America/Chicago': -1,
        'America/Denver': -2,
        'America/Phoenix': -2,  # No DST
        'America/Los_Angeles': -3,
    }
    
    def __init__(self):
        self.team_locations = TEAM_LOCATIONS
        
    def haversine_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """
        Calculate the great circle distance between two points in miles
        """
        # Convert to radians
        lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
        
        # Haversine formula
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * asin(sqrt(a))
        
        # Earth's radius in miles
        r = 3956
        
        return c * r
    
    def get_team_location(self, team_abbrev: str) -> Optional[Dict]:
        """Get location data for a team"""
        return self.team_locations.get(team_abbrev)
    
    def calculate_travel_distance(self, from_team: str, to_team: str) -> float:
        """Calculate travel distance between two teams' arenas in miles"""
        from_loc = self.get_team_location(from_team)
        to_loc = self.get_team_location(to_team)
        
        if not from_loc or not to_loc:
            return 0.0
        
        return self.haversine_distance(
            from_loc['lat'], from_loc['lon'],
            to_loc['lat'], to_loc['lon']
        )
    
    def calculate_timezone_change(self, from_team: str, to_team: str) -> int:
        """Calculate timezone change (hours) between two teams"""
        from_loc = self.get_team_location(from_team)
        to_loc = self.get_team_location(to_team)
        
        if not from_loc or not to_loc:
            return 0
        
        from_offset = self.TIMEZONE_OFFSETS.get(from_loc['timezone'], 0)
        to_offset = self.TIMEZONE_OFFSETS.get(to_loc['timezone'], 0)
        
        return to_offset - from_offset
    
    def calculate_altitude_change(self, from_team: str, to_team: str) -> float:
        """Calculate altitude change (feet) between two teams"""
        from_loc = self.get_team_location(from_team)
        to_loc = self.get_team_location(to_team)
        
        if not from_loc or not to_loc:
            return 0.0
        
        return to_loc['altitude'] - from_loc['altitude']
    
    def parse_matchup(self, matchup: str) -> Tuple[str, str, bool]:
        """
        Parse matchup string to get teams and home/away status
        
        Returns: (team_abbrev, opponent_abbrev, is_home)
        """
        if ' vs. ' in matchup:
            # Home game: "LAL vs. BOS"
            parts = matchup.split(' vs. ')
            return parts[0].strip(), parts[1].strip(), True
        elif ' @ ' in matchup:
            # Away game: "LAL @ BOS"
            parts = matchup.split(' @ ')
            return parts[0].strip(), parts[1].strip(), False
        else:
            return None, None, None
    
    def calculate_rest_days(self, game_date: datetime, previous_game_date: datetime) -> int:
        """Calculate days of rest between games"""
        if previous_game_date is None:
            return 7  # Assume well-rested if no previous game
        
        delta = game_date - previous_game_date
        return delta.days - 1  # -1 because the game day itself isn't rest
    
    def is_back_to_back(self, rest_days: int) -> bool:
        """Check if this is a back-to-back game"""
        return rest_days == 0
    
    def check_3_in_4(self, game_dates: List[datetime], current_game_date: datetime) -> bool:
        """Check if team is playing 3rd game in 4 days"""
        if len(game_dates) < 2:
            return False
        
        # Look at last 3 days before current game
        start_date = current_game_date - timedelta(days=3)
        games_in_window = sum(1 for d in game_dates if start_date <= d < current_game_date)
        
        return games_in_window >= 2  # Current game would be the 3rd
    
    def check_4_in_6(self, game_dates: List[datetime], current_game_date: datetime) -> bool:
        """Check if team is playing 4th game in 6 days"""
        if len(game_dates) < 3:
            return False
        
        start_date = current_game_date - timedelta(days=5)
        games_in_window = sum(1 for d in game_dates if start_date <= d < current_game_date)
        
        return games_in_window >= 3  # Current game would be the 4th
    
    def process_team_schedule(self, schedule_df: pd.DataFrame, team_id: int) -> pd.DataFrame:
        """
        Process schedule for a single team and add all context variables
        
        Args:
            schedule_df: Schedule DataFrame with GAME_DATE, MATCHUP columns
            team_id: Team ID to process
        """
        # Filter to team's games
        team_df = schedule_df[schedule_df['TEAM_ID'] == team_id].copy()
        
        if team_df.empty:
            return pd.DataFrame()
        
        # Sort by date
        team_df['GAME_DATE'] = pd.to_datetime(team_df['GAME_DATE'])
        team_df = team_df.sort_values('GAME_DATE').reset_index(drop=True)
        
        # Get team abbreviation
        team_abbrev = TEAM_ID_TO_ABBREV.get(team_id)
        
        results = []
        game_dates = []
        previous_location = team_abbrev  # Start at home
        
        for idx, row in team_df.iterrows():
            game_date = row['GAME_DATE']
            matchup = row.get('MATCHUP', '')
            
            # Parse matchup
            team, opponent, is_home = self.parse_matchup(matchup)
            if team is None:
                continue
            
            # Determine current location
            current_location = team if is_home else opponent
            
            # Calculate rest days
            previous_game_date = game_dates[-1] if game_dates else None
            rest_days = self.calculate_rest_days(game_date, previous_game_date)
            
            # Calculate travel (from previous game location)
            if previous_location and current_location:
                travel_distance = self.calculate_travel_distance(previous_location, current_location)
                timezone_change = self.calculate_timezone_change(previous_location, current_location)
                altitude_change = self.calculate_altitude_change(previous_location, current_location)
            else:
                travel_distance = 0
                timezone_change = 0
                altitude_change = 0
            
            # Check schedule density
            is_b2b = self.is_back_to_back(rest_days)
            is_3in4 = self.check_3_in_4(game_dates, game_date)
            is_4in6 = self.check_4_in_6(game_dates, game_date)
            
            # Altitude factor (Denver/Utah are significant)
            is_high_altitude = current_location in ['DEN', 'UTA']
            altitude_adjustment = 0.0
            if is_high_altitude and altitude_change > 3000:
                # Significant altitude jump - affects visitor performance
                altitude_adjustment = -1.5  # Net rating adjustment
            
            results.append({
                'TEAM_ID': team_id,
                'TEAM_ABBREVIATION': team_abbrev,
                'GAME_DATE': game_date,
                'GAME_ID': row.get('GAME_ID'),
                'MATCHUP': matchup,
                'OPPONENT': opponent,
                'IS_HOME': is_home,
                'REST_DAYS': rest_days,
                'IS_B2B': int(is_b2b),
                'IS_3IN4': int(is_3in4),
                'IS_4IN6': int(is_4in6),
                'TRAVEL_DISTANCE': travel_distance,
                'TIMEZONE_CHANGE': timezone_change,
                'ALTITUDE_CHANGE': altitude_change,
                'IS_HIGH_ALTITUDE': int(is_high_altitude),
                'ALTITUDE_ADJUSTMENT': altitude_adjustment,
            })
            
            # Update state
            game_dates.append(game_date)
            previous_location = current_location
        
        return pd.DataFrame(results)
    
    def process_all_teams(self, schedule_df: pd.DataFrame) -> pd.DataFrame:
        """Process schedule context for all teams"""
        print("  📊 Calculating schedule context...", end=" ", flush=True)
        
        all_results = []
        
        team_ids = schedule_df['TEAM_ID'].unique()
        
        for team_id in team_ids:
            team_context = self.process_team_schedule(schedule_df, team_id)
            if not team_context.empty:
                all_results.append(team_context)
        
        if all_results:
            combined = pd.concat(all_results, ignore_index=True)
            print(f"✅ {len(combined)} game contexts")
            return combined
        
        print("⚠️  No data")
        return pd.DataFrame()
    
    def get_upcoming_game_context(self, 
                                  schedule_df: pd.DataFrame, 
                                  team_id: int, 
                                  game_date: datetime = None) -> Optional[Dict]:
        """
        Get context for a specific upcoming game
        
        If game_date is None, gets context for next game
        """
        team_context = self.process_team_schedule(schedule_df, team_id)
        
        if team_context.empty:
            return None
        
        if game_date is None:
            # Get next game
            today = datetime.now()
            future_games = team_context[team_context['GAME_DATE'] >= today]
            if future_games.empty:
                return None
            game_row = future_games.iloc[0]
        else:
            # Get specific game
            game_mask = team_context['GAME_DATE'].dt.date == game_date.date()
            if not game_mask.any():
                return None
            game_row = team_context[game_mask].iloc[0]
        
        return game_row.to_dict()
    
    def calculate_fatigue_score(self, context: Dict) -> float:
        """
        Calculate overall fatigue score based on schedule context
        
        Higher score = more fatigued
        Scale: 0-10
        """
        score = 0.0
        
        # Rest days impact
        rest_days = context.get('REST_DAYS', 1)
        if rest_days == 0:  # B2B
            score += 3.0
        elif rest_days == 1:
            score += 0.5
        # 2+ days rest = no penalty
        
        # 3-in-4 / 4-in-6
        if context.get('IS_3IN4'):
            score += 2.0
        if context.get('IS_4IN6'):
            score += 2.5
        
        # Travel
        travel_distance = context.get('TRAVEL_DISTANCE', 0)
        if travel_distance > 2000:  # Cross-country
            score += 1.5
        elif travel_distance > 1000:
            score += 0.75
        elif travel_distance > 500:
            score += 0.25
        
        # Timezone change
        tz_change = abs(context.get('TIMEZONE_CHANGE', 0))
        score += tz_change * 0.5
        
        # Altitude (visiting high altitude)
        if context.get('IS_HIGH_ALTITUDE') and not context.get('IS_HOME'):
            score += 1.0
        
        return min(score, 10.0)  # Cap at 10
    
    def estimate_performance_adjustment(self, context: Dict) -> float:
        """
        Estimate net rating adjustment based on schedule context
        
        Returns: Adjustment to expected net rating (negative = worse performance)
        """
        adjustment = 0.0
        
        # B2B penalty
        if context.get('IS_B2B'):
            adjustment -= 3.0
        
        # Rest advantage
        rest_days = context.get('REST_DAYS', 1)
        if rest_days >= 3:
            adjustment += 1.0
        elif rest_days >= 2:
            adjustment += 0.5
        
        # Schedule density
        if context.get('IS_3IN4'):
            adjustment -= 1.5
        if context.get('IS_4IN6'):
            adjustment -= 2.0
        
        # Long travel
        travel = context.get('TRAVEL_DISTANCE', 0)
        if travel > 2000:
            adjustment -= 1.2
        elif travel > 1500:
            adjustment -= 0.8
        
        # Altitude (visitor penalty at Denver/Utah)
        adjustment += context.get('ALTITUDE_ADJUSTMENT', 0)
        
        return adjustment


# Precompute all pairwise distances
def build_distance_matrix() -> pd.DataFrame:
    """Build matrix of distances between all team arenas"""
    calc = ScheduleContextCalculator()
    
    teams = list(TEAM_LOCATIONS.keys())
    distances = []
    
    for from_team in teams:
        for to_team in teams:
            dist = calc.calculate_travel_distance(from_team, to_team)
            distances.append({
                'from_team': from_team,
                'to_team': to_team,
                'distance_miles': dist,
            })
    
    return pd.DataFrame(distances)


if __name__ == "__main__":
    print("\n🧪 Testing Schedule Context Calculator")
    print("=" * 50)
    
    calc = ScheduleContextCalculator()
    
    # Test distance calculations
    print("\n📍 Distance Tests:")
    test_routes = [
        ('LAL', 'BOS'),  # Cross-country
        ('LAL', 'LAC'),  # Same city
        ('NYK', 'BKN'),  # Same city
        ('MIA', 'DEN'),  # To altitude
    ]
    
    for from_team, to_team in test_routes:
        dist = calc.calculate_travel_distance(from_team, to_team)
        tz = calc.calculate_timezone_change(from_team, to_team)
        alt = calc.calculate_altitude_change(from_team, to_team)
        print(f"  {from_team} → {to_team}: {dist:.0f} mi, TZ: {tz:+d}h, Alt: {alt:+.0f} ft")
    
    # Test fatigue scoring
    print("\n😴 Fatigue Score Tests:")
    
    # Worst case: B2B, 3-in-4, cross-country to Denver
    worst_case = {
        'REST_DAYS': 0,
        'IS_B2B': True,
        'IS_3IN4': True,
        'IS_4IN6': False,
        'TRAVEL_DISTANCE': 2500,
        'TIMEZONE_CHANGE': -3,
        'IS_HIGH_ALTITUDE': True,
        'IS_HOME': False,
    }
    print(f"  Worst case scenario: {calc.calculate_fatigue_score(worst_case):.1f}/10")
    
    # Best case: 3 days rest, home game, no travel
    best_case = {
        'REST_DAYS': 3,
        'IS_B2B': False,
        'IS_3IN4': False,
        'IS_4IN6': False,
        'TRAVEL_DISTANCE': 0,
        'TIMEZONE_CHANGE': 0,
        'IS_HIGH_ALTITUDE': False,
        'IS_HOME': True,
    }
    print(f"  Best case scenario: {calc.calculate_fatigue_score(best_case):.1f}/10")
    
    # Typical case
    typical = {
        'REST_DAYS': 1,
        'IS_B2B': False,
        'IS_3IN4': False,
        'IS_4IN6': False,
        'TRAVEL_DISTANCE': 800,
        'TIMEZONE_CHANGE': -1,
        'IS_HIGH_ALTITUDE': False,
        'IS_HOME': False,
    }
    print(f"  Typical road game: {calc.calculate_fatigue_score(typical):.1f}/10")
    
    # Performance adjustments
    print("\n📊 Performance Adjustment Tests:")
    print(f"  Worst case net rating adj: {calc.estimate_performance_adjustment(worst_case):+.1f}")
    print(f"  Best case net rating adj: {calc.estimate_performance_adjustment(best_case):+.1f}")
    print(f"  Typical case net rating adj: {calc.estimate_performance_adjustment(typical):+.1f}")
