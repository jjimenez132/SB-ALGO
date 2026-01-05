#!/usr/bin/env python3
"""
================================================================================
ADVANCED STATS ENGINE v1.0
================================================================================
Adds pace, offensive/defensive ratings, and matchup analysis to SB-ALGO.

STATS USED:
- PACE: Possessions per 48 minutes (affects totals)
- OFF_RATING: Points per 100 possessions (offensive efficiency)
- DEF_RATING: Points allowed per 100 possessions (defensive efficiency)
- NET_RATING: OFF_RATING - DEF_RATING (overall team strength)
- EFG_PCT: Effective field goal percentage
- TS_PCT: True shooting percentage

MATCHUP FACTORS:
- Pace differential (fast vs slow teams)
- Offensive vs Defensive matchups
- Rest advantage
- Home court advantage with pace context

================================================================================
"""

import os
from sqlalchemy import create_engine, text
from typing import Dict, List, Optional, Tuple
from datetime import datetime

class AdvancedStatsEngine:
    """Engine for advanced NBA statistics and matchup analysis"""
    
    # League averages (2024-25 season approximations)
    LEAGUE_AVG_PACE = 99.5
    LEAGUE_AVG_OFF_RATING = 114.0
    LEAGUE_AVG_DEF_RATING = 114.0
    LEAGUE_AVG_TOTAL = 224.0
    
    # Home court advantage factors
    HOME_COURT_POINTS = 3.0
    HOME_PACE_BOOST = 0.5
    
    def __init__(self):
        self.db = self._get_engine()
        self._team_stats_cache = {}
        self._load_team_stats()
    
    def _get_engine(self):
        database_url = os.getenv('DATABASE_URL')
        if not database_url:
            database_url = "postgresql://sb_algo_db_user:0HDtYp4EY2Lo5At8iyf44PD1zDioSPK7@dpg-d495uhchg0os738l1a50-a.virginia-postgres.render.com/sb_algo_db"
        return create_engine(database_url)
    
    def _load_team_stats(self):
        """Load all team advanced stats into cache"""
        try:
            with self.db.connect() as conn:
                result = conn.execute(text("""
                    SELECT "TEAM_NAME", "PACE", "OFF_RATING", "DEF_RATING", "NET_RATING", 
                           "EFG_PCT", "TS_PCT", "AST_PCT", "OREB_PCT", "DREB_PCT", 
                           "TM_TOV_PCT", "GP", "W", "L"
                    FROM nba_team_advanced_stats
                """)).fetchall()
                
                for row in result:
                    team_name = row[0]
                    self._team_stats_cache[team_name] = {
                        'pace': float(row[1] or self.LEAGUE_AVG_PACE),
                        'off_rating': float(row[2] or self.LEAGUE_AVG_OFF_RATING),
                        'def_rating': float(row[3] or self.LEAGUE_AVG_DEF_RATING),
                        'net_rating': float(row[4] or 0),
                        'efg_pct': float(row[5] or 0.50),
                        'ts_pct': float(row[6] or 0.55),
                        'ast_pct': float(row[7] or 0.60),
                        'oreb_pct': float(row[8] or 0.25),
                        'dreb_pct': float(row[9] or 0.75),
                        'tov_pct': float(row[10] or 0.12),
                        'gp': int(row[11] or 0),
                        'wins': int(row[12] or 0),
                        'losses': int(row[13] or 0),
                    }
                print(f"   ✅ Advanced Stats Engine: Loaded {len(self._team_stats_cache)} teams")
        except Exception as e:
            print(f"   ⚠️ Advanced Stats Engine error: {e}")
    
    def get_team_stats(self, team_name: str) -> Dict:
        """Get advanced stats for a team"""
        # Try exact match first
        if team_name in self._team_stats_cache:
            return self._team_stats_cache[team_name]
        
        # Try partial match
        for cached_name, stats in self._team_stats_cache.items():
            if team_name.lower() in cached_name.lower() or cached_name.lower() in team_name.lower():
                return stats
        
        # Return league average if not found
        return {
            'pace': self.LEAGUE_AVG_PACE,
            'off_rating': self.LEAGUE_AVG_OFF_RATING,
            'def_rating': self.LEAGUE_AVG_DEF_RATING,
            'net_rating': 0,
            'efg_pct': 0.50,
            'ts_pct': 0.55,
            'ast_pct': 0.60,
            'oreb_pct': 0.25,
            'dreb_pct': 0.75,
            'tov_pct': 0.12,
            'gp': 0,
            'wins': 0,
            'losses': 0,
        }
    
    def predict_game_total(self, home_team: str, away_team: str, 
                           home_b2b: bool = False, away_b2b: bool = False) -> Dict:
        """
        Predict game total using pace and efficiency metrics.
        
        Formula:
        Expected Possessions = (Home Pace + Away Pace) / 2
        Home Points = (Home OFF_RATING * Expected Poss / 100) adjusted for Away DEF
        Away Points = (Away OFF_RATING * Expected Poss / 100) adjusted for Home DEF
        """
        home_stats = self.get_team_stats(home_team)
        away_stats = self.get_team_stats(away_team)
        
        # Calculate expected pace (average of both teams)
        expected_pace = (home_stats['pace'] + away_stats['pace']) / 2
        
        # Adjust for home court (slightly faster pace at home)
        expected_pace += self.HOME_PACE_BOOST
        
        # Calculate expected points for each team
        # Home team: their offense vs away defense
        home_off_factor = home_stats['off_rating'] / self.LEAGUE_AVG_OFF_RATING
        away_def_factor = away_stats['def_rating'] / self.LEAGUE_AVG_DEF_RATING
        home_points = (expected_pace * home_off_factor * away_def_factor * self.LEAGUE_AVG_TOTAL / 200)
        
        # Away team: their offense vs home defense
        away_off_factor = away_stats['off_rating'] / self.LEAGUE_AVG_OFF_RATING
        home_def_factor = home_stats['def_rating'] / self.LEAGUE_AVG_DEF_RATING
        away_points = (expected_pace * away_off_factor * home_def_factor * self.LEAGUE_AVG_TOTAL / 200)
        
        # Home court advantage
        home_points += self.HOME_COURT_POINTS / 2
        away_points -= self.HOME_COURT_POINTS / 2
        
        # B2B adjustments (tired teams score less, allow more)
        if home_b2b:
            home_points -= 2.5
            away_points += 1.5
        if away_b2b:
            away_points -= 2.5
            home_points += 1.5
        
        predicted_total = home_points + away_points
        
        # Pace classification
        if expected_pace > 101:
            pace_class = "FAST"
            pace_impact = "Favors OVER"
        elif expected_pace < 97:
            pace_class = "SLOW"
            pace_impact = "Favors UNDER"
        else:
            pace_class = "AVERAGE"
            pace_impact = "Neutral"
        
        return {
            'predicted_total': round(predicted_total, 1),
            'home_points': round(home_points, 1),
            'away_points': round(away_points, 1),
            'expected_pace': round(expected_pace, 1),
            'pace_class': pace_class,
            'pace_impact': pace_impact,
            'home_off_rating': home_stats['off_rating'],
            'away_off_rating': away_stats['off_rating'],
            'home_def_rating': home_stats['def_rating'],
            'away_def_rating': away_stats['def_rating'],
        }
    
    def predict_spread(self, home_team: str, away_team: str,
                       home_b2b: bool = False, away_b2b: bool = False) -> Dict:
        """
        Predict spread using net ratings and matchup analysis.
        
        Formula:
        Base Spread = (Home NET_RATING - Away NET_RATING) / 3.5
        Adjusted for home court, B2B, matchup factors
        """
        home_stats = self.get_team_stats(home_team)
        away_stats = self.get_team_stats(away_team)
        
        # Net rating difference (scaled to spread)
        net_diff = home_stats['net_rating'] - away_stats['net_rating']
        base_spread = net_diff / 3.5  # Roughly 3.5 net rating = 1 point spread
        
        # Home court advantage
        base_spread += self.HOME_COURT_POINTS
        
        # B2B adjustments
        if home_b2b:
            base_spread -= 3.0
        if away_b2b:
            base_spread += 3.0
        
        # Matchup factors
        # If home team is better offensively and away is bad defensively = bigger edge
        off_def_matchup = (home_stats['off_rating'] - self.LEAGUE_AVG_OFF_RATING) - \
                          (away_stats['def_rating'] - self.LEAGUE_AVG_DEF_RATING)
        base_spread += off_def_matchup / 10  # Small adjustment
        
        # Win probability estimate
        # Using a simple conversion: spread of 0 = 50%, each point = ~3.5% change
        home_win_prob = 50 + (base_spread * 3.5)
        home_win_prob = max(5, min(95, home_win_prob))  # Clamp to 5-95%
        
        return {
            'predicted_spread': round(base_spread, 1),
            'home_win_prob': round(home_win_prob, 1),
            'away_win_prob': round(100 - home_win_prob, 1),
            'home_net_rating': home_stats['net_rating'],
            'away_net_rating': away_stats['net_rating'],
            'matchup_edge': round(off_def_matchup / 10, 2),
        }
    
    def analyze_matchup(self, home_team: str, away_team: str,
                        book_spread: float = None, book_total: float = None,
                        home_b2b: bool = False, away_b2b: bool = False) -> Dict:
        """
        Complete matchup analysis combining all factors.
        Returns edges for spread and total.
        """
        spread_pred = self.predict_spread(home_team, away_team, home_b2b, away_b2b)
        total_pred = self.predict_game_total(home_team, away_team, home_b2b, away_b2b)
        
        result = {
            'home_team': home_team,
            'away_team': away_team,
            'spread_prediction': spread_pred,
            'total_prediction': total_pred,
            'edges': [],
        }
        
        # Calculate spread edge
        if book_spread is not None:
            # Positive book_spread means home is favorite (e.g., -5.5)
            # Our predicted_spread is from home perspective (positive = home favored)
            model_spread = spread_pred['predicted_spread']
            
            # Edge = difference between model and book
            # If model says -7 and book says -5, we like home (edge = 2)
            spread_edge = model_spread - (-book_spread)  # book_spread comes as positive for home favorite
            
            if abs(spread_edge) >= 2.0:  # Minimum 2 point edge
                if spread_edge > 0:
                    result['edges'].append({
                        'type': 'SPREAD',
                        'pick': f"{home_team} {-book_spread:+.1f}",
                        'edge': abs(spread_edge),
                        'model': model_spread,
                        'book': -book_spread,
                        'confidence': min(90, 60 + abs(spread_edge) * 5),
                    })
                else:
                    result['edges'].append({
                        'type': 'SPREAD',
                        'pick': f"{away_team} {book_spread:+.1f}",
                        'edge': abs(spread_edge),
                        'model': model_spread,
                        'book': -book_spread,
                        'confidence': min(90, 60 + abs(spread_edge) * 5),
                    })
        
        # Calculate total edge
        if book_total is not None:
            total_edge = total_pred['predicted_total'] - book_total
            
            if abs(total_edge) >= 3.0:  # Minimum 3 point edge for totals
                if total_edge > 0:
                    result['edges'].append({
                        'type': 'TOTAL',
                        'pick': f"OVER {book_total}",
                        'edge': total_edge,
                        'model': total_pred['predicted_total'],
                        'book': book_total,
                        'confidence': min(90, 60 + abs(total_edge) * 3),
                        'pace_factor': total_pred['pace_class'],
                    })
                else:
                    result['edges'].append({
                        'type': 'TOTAL',
                        'pick': f"UNDER {book_total}",
                        'edge': abs(total_edge),
                        'model': total_pred['predicted_total'],
                        'book': book_total,
                        'confidence': min(90, 60 + abs(total_edge) * 3),
                        'pace_factor': total_pred['pace_class'],
                    })
        
        return result
    
    def get_pace_matchup_analysis(self, home_team: str, away_team: str) -> str:
        """Get human-readable pace matchup analysis"""
        home_stats = self.get_team_stats(home_team)
        away_stats = self.get_team_stats(away_team)
        
        home_pace = home_stats['pace']
        away_pace = away_stats['pace']
        avg_pace = (home_pace + away_pace) / 2
        
        analysis = []
        
        if home_pace > 101 and away_pace > 101:
            analysis.append("🏃 FAST vs FAST: Both teams play uptempo. High total expected.")
        elif home_pace < 97 and away_pace < 97:
            analysis.append("🐢 SLOW vs SLOW: Both teams play slow. Low total expected.")
        elif abs(home_pace - away_pace) > 5:
            faster = home_team if home_pace > away_pace else away_team
            slower = away_team if home_pace > away_pace else home_team
            analysis.append(f"⚡ PACE MISMATCH: {faster} plays fast, {slower} plays slow.")
        
        if home_stats['off_rating'] > 116 and away_stats['def_rating'] > 116:
            analysis.append(f"🔥 OFFENSIVE OPPORTUNITY: {home_team} elite offense vs weak defense.")
        if away_stats['off_rating'] > 116 and home_stats['def_rating'] > 116:
            analysis.append(f"🔥 OFFENSIVE OPPORTUNITY: {away_team} elite offense vs weak defense.")
        
        if home_stats['def_rating'] < 110 and away_stats['off_rating'] < 110:
            analysis.append(f"🛡️ DEFENSIVE GAME: {home_team} elite defense vs struggling offense.")
        
        return " | ".join(analysis) if analysis else "Standard matchup, no extreme factors."


# =============================================================================
# TEST
# =============================================================================
if __name__ == "__main__":
    print("=" * 70)
    print("🏀 ADVANCED STATS ENGINE TEST")
    print("=" * 70)
    
    engine = AdvancedStatsEngine()
    
    # Test with today's games
    test_games = [
        ("Utah Jazz", "Boston Celtics"),
        ("Los Angeles Lakers", "Detroit Pistons"),
        ("Memphis Grizzlies", "Philadelphia 76ers"),
        ("LA Clippers", "Sacramento Kings"),
    ]
    
    for home, away in test_games:
        print(f"\n{'='*60}")
        print(f"🏀 {away} @ {home}")
        print("=" * 60)
        
        # Get predictions
        total_pred = engine.predict_game_total(home, away)
        spread_pred = engine.predict_spread(home, away)
        
        print(f"\n📊 TOTAL PREDICTION:")
        print(f"   Expected Pace: {total_pred['expected_pace']} ({total_pred['pace_class']})")
        print(f"   {home}: {total_pred['home_points']} pts (OFF: {total_pred['home_off_rating']})")
        print(f"   {away}: {total_pred['away_points']} pts (OFF: {total_pred['away_off_rating']})")
        print(f"   Predicted Total: {total_pred['predicted_total']}")
        print(f"   Pace Impact: {total_pred['pace_impact']}")
        
        print(f"\n📊 SPREAD PREDICTION:")
        print(f"   {home} NET: {spread_pred['home_net_rating']:+.1f}")
        print(f"   {away} NET: {spread_pred['away_net_rating']:+.1f}")
        print(f"   Predicted Spread: {home} {spread_pred['predicted_spread']:+.1f}")
        print(f"   Win Prob: {home} {spread_pred['home_win_prob']:.0f}% | {away} {spread_pred['away_win_prob']:.0f}%")
        
        print(f"\n💡 MATCHUP ANALYSIS:")
        print(f"   {engine.get_pace_matchup_analysis(home, away)}")
    
    print("\n" + "=" * 70)
    print("✅ ADVANCED STATS ENGINE TEST COMPLETE")
    print("=" * 70)
