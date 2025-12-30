#!/usr/bin/env python3
"""
================================================================================
UNCERTAINTY / REGIME ENGINE v3.0
================================================================================
Knows when NOT to bet. Detects high-variance situations.

PURPOSE:
--------
Not a prediction engine - a RISK STATE DETECTOR.

Pros don't just predict - they know when conditions are unfavorable.
This engine tells you WHEN to be aggressive and WHEN to stay away.

REGIME TYPES:
-------------
1. NORMAL - Standard conditions, full confidence
2. HIGH_VARIANCE - Elevated uncertainty, reduce bet sizes
3. UNSTABLE - Rotations unclear, questionable data, consider passing
4. AVOID - Known problematic situations (tanking, rest, etc.)

================================================================================
"""

import numpy as np
from datetime import datetime, timedelta
from sqlalchemy import create_engine, text
from typing import List, Dict, Optional, Tuple
import warnings
warnings.filterwarnings('ignore')

# ==============================================================================
# CONFIGURATION
# ==============================================================================
DATABASE_URL = "postgresql://sb_algo_db_user:0HDtYp4EY2Lo5At8iyf44PD1zDioSPK7@dpg-d495uhchg0os738l1a50-a.virginia-postgres.render.com/sb_algo_db"

# Regime thresholds
REGIME_THRESHOLDS = {
    'normal': 0.85,
    'high_variance': 0.70,
    'unstable': 0.55,
    'avoid': 0.0,
}

# Risk factors and their weights
RISK_WEIGHTS = {
    '3pt_variance': 0.15,
    'pace_variance': 0.10,
    'rotation_instability': 0.25,
    'seasonal_factor': 0.15,
    'schedule_factor': 0.15,
    'historical_volatility': 0.10,
    'injury_uncertainty': 0.10,
}


class UncertaintyEngine:
    """
    Detects high-risk betting situations and recommends caution.
    """
    
    def __init__(self):
        self.engine = create_engine(DATABASE_URL)
        self._team_cache = {}
        self._load_team_stats()
    
    def _load_team_stats(self):
        # Team name to abbreviation mapping
        self._team_abbr_map = {
            'Atlanta Hawks': 'ATL', 'Boston Celtics': 'BOS', 'Brooklyn Nets': 'BKN',
            'Charlotte Hornets': 'CHA', 'Chicago Bulls': 'CHI', 'Cleveland Cavaliers': 'CLE',
            'Dallas Mavericks': 'DAL', 'Denver Nuggets': 'DEN', 'Detroit Pistons': 'DET',
            'Golden State Warriors': 'GSW', 'Houston Rockets': 'HOU', 'Indiana Pacers': 'IND',
            'LA Clippers': 'LAC', 'Los Angeles Lakers': 'LAL', 'Memphis Grizzlies': 'MEM',
            'Miami Heat': 'MIA', 'Milwaukee Bucks': 'MIL', 'Minnesota Timberwolves': 'MIN',
            'New Orleans Pelicans': 'NOP', 'New York Knicks': 'NYK', 'Oklahoma City Thunder': 'OKC',
            'Orlando Magic': 'ORL', 'Philadelphia 76ers': 'PHI', 'Phoenix Suns': 'PHX',
            'Portland Trail Blazers': 'POR', 'Sacramento Kings': 'SAC', 'San Antonio Spurs': 'SAS',
            'Toronto Raptors': 'TOR', 'Utah Jazz': 'UTA', 'Washington Wizards': 'WAS',
        }
        
        try:
            with self.engine.connect() as conn:
                query = """
                    SELECT "TEAM_NAME", "PACE", "W", "L"
                    FROM nba_team_advanced_stats
                """
                result = conn.execute(text(query))
                for row in result:
                    r = dict(row._mapping)
                    team_name = r.get('TEAM_NAME', '')
                    abbr = self._team_abbr_map.get(team_name, team_name[:3].upper())
                    self._team_cache[abbr] = {
                        'name': team_name,
                        'pace': r.get('PACE', 100),
                        'wins': r.get('W', 0),
                        'losses': r.get('L', 0),
                    }
        except Exception as e:
            print(f"Warning: Could not load team stats: {e}")
    
    def detect_regime(self, home_team: str, away_team: str,
                      injuries_home: int = 0, injuries_away: int = 0,
                      questionable_home: int = 0, questionable_away: int = 0,
                      b2b_home: bool = False, b2b_away: bool = False,
                      rest_home: int = 1, rest_away: int = 1,
                      game_number_home: int = 41, game_number_away: int = 41,
                      season_phase: str = 'regular') -> Dict:
        """
        Detect the regime for a game matchup.
        """
        factors = {}
        warnings = []
        
        # 1. 3-Point Variance Factor
        factors['3pt_variance'] = 0.15
        
        # 2. Pace Variance Factor
        home_pace = self._team_cache.get(home_team, {}).get('pace', 100)
        away_pace = self._team_cache.get(away_team, {}).get('pace', 100)
        
        pace_diff = abs(home_pace - away_pace)
        avg_pace = (home_pace + away_pace) / 2
        
        if pace_diff > 5:
            pace_risk = 0.30
            warnings.append(f"PACE_MISMATCH: {pace_diff:.1f} pace difference")
        elif avg_pace > 105:
            pace_risk = 0.25
            warnings.append(f"HIGH_PACE: Both teams play fast ({avg_pace:.1f})")
        elif avg_pace < 96:
            pace_risk = 0.20
            warnings.append(f"SLOW_PACE: Grinding game expected ({avg_pace:.1f})")
        else:
            pace_risk = 0.10
        
        factors['pace_variance'] = pace_risk
        
        # 3. Rotation Instability Factor
        total_injuries = injuries_home + injuries_away
        total_questionable = questionable_home + questionable_away
        
        rotation_risk = 0.0
        
        if total_injuries >= 4:
            rotation_risk = 0.50
            warnings.append(f"HEAVY_INJURIES: {total_injuries} players OUT")
        elif total_injuries >= 2:
            rotation_risk = 0.30
            warnings.append(f"MULTIPLE_INJURIES: {total_injuries} players OUT")
        elif total_injuries >= 1:
            rotation_risk = 0.15
        
        if total_questionable >= 3:
            rotation_risk += 0.25
            warnings.append(f"HIGH_UNCERTAINTY: {total_questionable} players QUESTIONABLE")
        elif total_questionable >= 1:
            rotation_risk += 0.10
        
        factors['rotation_instability'] = min(0.60, rotation_risk)
        
        # 4. Seasonal Factor
        avg_games = (game_number_home + game_number_away) / 2
        
        if season_phase == 'playoffs':
            seasonal_risk = 0.15
        elif avg_games < 10:
            seasonal_risk = 0.40
            warnings.append("EARLY_SEASON: Small sample size (<10 games)")
        elif avg_games < 20:
            seasonal_risk = 0.25
            warnings.append("SAMPLE_SIZE: Limited data (<20 games)")
        elif avg_games > 75:
            seasonal_risk = 0.35
            warnings.append("LATE_SEASON: Potential tanking/rest")
        else:
            seasonal_risk = 0.10
        
        factors['seasonal_factor'] = seasonal_risk
        
        # 5. Schedule Factor
        schedule_risk = 0.0
        
        if b2b_home and b2b_away:
            schedule_risk = 0.35
            warnings.append("DOUBLE_B2B: Both teams on back-to-back")
        elif b2b_home or b2b_away:
            schedule_risk = 0.15
        
        rest_diff = abs(rest_home - rest_away)
        if rest_diff >= 4:
            schedule_risk += 0.15
            warnings.append(f"REST_MISMATCH: {rest_diff} days difference")
        
        factors['schedule_factor'] = min(0.40, schedule_risk)
        
        # 6. Historical Volatility Factor
        factors['historical_volatility'] = 0.15
        
        # 7. Injury Uncertainty Factor
        injury_uncertainty = questionable_home * 0.10 + questionable_away * 0.10
        factors['injury_uncertainty'] = min(0.40, injury_uncertainty)
        
        # CALCULATE OVERALL CONFIDENCE
        weighted_risk = sum(factors[k] * RISK_WEIGHTS[k] for k in factors)
        confidence = 1 - weighted_risk
        confidence = max(0.3, min(1.0, confidence))
        
        # DETERMINE REGIME
        if confidence >= REGIME_THRESHOLDS['normal']:
            regime = 'NORMAL'
            regime_color = '🟢'
            recommendation = 'Full confidence in predictions'
        elif confidence >= REGIME_THRESHOLDS['high_variance']:
            regime = 'HIGH_VARIANCE'
            regime_color = '🟡'
            recommendation = 'Reduce bet sizes by 25-50%'
        elif confidence >= REGIME_THRESHOLDS['unstable']:
            regime = 'UNSTABLE'
            regime_color = '🟠'
            recommendation = 'Consider passing or minimal bets only'
        else:
            regime = 'AVOID'
            regime_color = '🔴'
            recommendation = 'Do not bet this game'
        
        weight_adjustments = self._calculate_weight_adjustments(factors, regime)
        
        return {
            'matchup': f"{away_team} @ {home_team}",
            'regime': regime,
            'regime_indicator': regime_color,
            'confidence_multiplier': round(confidence, 3),
            'confidence_pct': round(confidence * 100, 1),
            'risk_factors': {k: round(v, 3) for k, v in factors.items()},
            'total_weighted_risk': round(weighted_risk, 3),
            'warnings': warnings,
            'warning_count': len(warnings),
            'recommendation': recommendation,
            'kelly_multiplier': self._kelly_multiplier(regime),
            'weight_adjustments': weight_adjustments,
            'summary': f"{regime_color} {regime}: {confidence*100:.0f}% confidence - {recommendation}",
        }
    
    def _kelly_multiplier(self, regime: str) -> float:
        multipliers = {
            'NORMAL': 1.0,
            'HIGH_VARIANCE': 0.60,
            'UNSTABLE': 0.30,
            'AVOID': 0.0,
        }
        return multipliers.get(regime, 0.5)
    
    def _calculate_weight_adjustments(self, factors: Dict, regime: str) -> Dict:
        adjustments = {
            'spread_confidence': 1.0,
            'total_confidence': 1.0,
            'moneyline_confidence': 1.0,
            'prop_confidence': 1.0,
        }
        
        if factors.get('rotation_instability', 0) > 0.30:
            adjustments['prop_confidence'] = 0.60
        
        if factors.get('pace_variance', 0) > 0.25:
            adjustments['total_confidence'] = 0.75
        
        if factors.get('seasonal_factor', 0) > 0.30:
            adjustments['spread_confidence'] = 0.80
            adjustments['total_confidence'] = 0.80
        
        if factors.get('injury_uncertainty', 0) > 0.25:
            adjustments['prop_confidence'] = 0.50
        
        return adjustments
    
    def is_high_variance_game(self, home_team: str, away_team: str) -> Dict:
        home_pace = self._team_cache.get(home_team, {}).get('pace', 100)
        away_pace = self._team_cache.get(away_team, {}).get('pace', 100)
        
        avg_pace = (home_pace + away_pace) / 2
        
        high_pace = avg_pace > 103
        pace_mismatch = abs(home_pace - away_pace) > 4
        
        is_high_var = high_pace or pace_mismatch
        
        variance_factors = []
        if high_pace:
            variance_factors.append(f"High pace ({avg_pace:.1f})")
        if pace_mismatch:
            variance_factors.append(f"Pace mismatch ({abs(home_pace - away_pace):.1f})")
        
        return {
            'is_high_variance': is_high_var,
            'factors': variance_factors,
            'avg_pace': round(avg_pace, 1),
            'recommendation': 'Widen confidence intervals' if is_high_var else 'Standard variance expected',
        }
    
    def detect_tanking_rest(self, team: str, game_number: int,
                            wins: int = None, losses: int = None) -> Dict:
        team_data = self._team_cache.get(team, {})
        
        if wins is None:
            wins = team_data.get('wins', 20)
        if losses is None:
            losses = team_data.get('losses', 20)
        
        total_games = wins + losses
        win_pct = wins / max(total_games, 1)
        
        is_late_season = game_number > 70
        is_bad_record = win_pct < 0.35
        is_playoff_eliminated = is_late_season and win_pct < 0.40
        
        tanking_risk = 0.0
        indicators = []
        
        if is_late_season and is_bad_record:
            tanking_risk = 0.80
            indicators.append("Late season with poor record")
        elif is_playoff_eliminated:
            tanking_risk = 0.60
            indicators.append("Likely eliminated from playoffs")
        elif is_late_season:
            tanking_risk = 0.30
            indicators.append("Late season - rest possible")
        elif is_bad_record:
            tanking_risk = 0.20
            indicators.append("Poor record")
        
        return {
            'team': team,
            'tanking_risk': round(tanking_risk, 2),
            'indicators': indicators,
            'game_number': game_number,
            'record': f"{wins}-{losses}",
            'win_pct': round(win_pct, 3),
            'recommendation': 'CAUTION - Check lineups' if tanking_risk > 0.40 else 'Normal game expected',
        }
    
    def assess_sample_size(self, game_number: int) -> Dict:
        if game_number < 5:
            reliability = 0.30
            status = 'VERY_EARLY'
            note = 'Extremely limited data - high uncertainty'
        elif game_number < 10:
            reliability = 0.50
            status = 'EARLY'
            note = 'Limited data - rely more on preseason projections'
        elif game_number < 20:
            reliability = 0.70
            status = 'DEVELOPING'
            note = 'Stats starting to stabilize'
        elif game_number < 30:
            reliability = 0.85
            status = 'STABLE'
            note = 'Good sample size'
        else:
            reliability = 0.95
            status = 'RELIABLE'
            note = 'Full sample - stats are reliable'
        
        return {
            'game_number': game_number,
            'reliability': round(reliability, 2),
            'status': status,
            'note': note,
            'confidence_adjustment': round(reliability, 2),
        }
    
    def full_game_assessment(self, home_team: str, away_team: str,
                              injuries_home: int = 0, injuries_away: int = 0,
                              questionable_home: int = 0, questionable_away: int = 0,
                              b2b_home: bool = False, b2b_away: bool = False,
                              rest_home: int = 1, rest_away: int = 1,
                              game_number_home: int = 41, game_number_away: int = 41) -> Dict:
        regime = self.detect_regime(
            home_team, away_team,
            injuries_home, injuries_away,
            questionable_home, questionable_away,
            b2b_home, b2b_away,
            rest_home, rest_away,
            game_number_home, game_number_away
        )
        
        variance = self.is_high_variance_game(home_team, away_team)
        tanking_home = self.detect_tanking_rest(home_team, game_number_home)
        tanking_away = self.detect_tanking_rest(away_team, game_number_away)
        sample_home = self.assess_sample_size(game_number_home)
        sample_away = self.assess_sample_size(game_number_away)
        
        should_bet = regime['regime'] in ['NORMAL', 'HIGH_VARIANCE']
        
        if regime['regime'] == 'AVOID':
            action = '🔴 DO NOT BET'
        elif regime['regime'] == 'UNSTABLE':
            action = '🟠 PASS OR MINIMAL'
        elif regime['regime'] == 'HIGH_VARIANCE':
            action = '🟡 REDUCE SIZE'
        else:
            action = '🟢 PROCEED'
        
        return {
            'matchup': f"{away_team} @ {home_team}",
            'regime': regime,
            'variance_check': variance,
            'tanking_check': {'home': tanking_home, 'away': tanking_away},
            'sample_size': {'home': sample_home, 'away': sample_away},
            'should_bet': should_bet,
            'action': action,
            'kelly_multiplier': regime['kelly_multiplier'],
            'weight_adjustments': regime['weight_adjustments'],
            'all_warnings': regime['warnings'] + variance['factors'] + 
                           tanking_home['indicators'] + tanking_away['indicators'],
        }
    
    def analyze_slate(self, games: List[Dict]) -> Dict:
        results = []
        
        for game in games:
            assessment = self.full_game_assessment(
                game.get('home_team', ''),
                game.get('away_team', ''),
                game.get('injuries_home', 0),
                game.get('injuries_away', 0),
                game.get('questionable_home', 0),
                game.get('questionable_away', 0),
                game.get('b2b_home', False),
                game.get('b2b_away', False),
            )
            results.append(assessment)
        
        results.sort(key=lambda x: x['regime']['confidence_multiplier'], reverse=True)
        
        bet_games = [r for r in results if r['should_bet']]
        avoid_games = [r for r in results if not r['should_bet']]
        
        return {
            'total_games': len(games),
            'bettable_games': len(bet_games),
            'avoid_games': len(avoid_games),
            'best_confidence': results[0] if results else None,
            'worst_confidence': results[-1] if results else None,
            'all_assessments': results,
            'summary': f"{len(bet_games)}/{len(games)} games suitable for betting",
        }


# ==============================================================================
# TEST SUITE
# ==============================================================================
if __name__ == "__main__":
    print("=" * 80)
    print("UNCERTAINTY / REGIME ENGINE v3.0 - TEST SUITE")
    print("=" * 80)
    
    engine = UncertaintyEngine()
    
    # Test 1: Normal game
    print("\n" + "=" * 80)
    print("TEST 1: NORMAL GAME")
    print("=" * 80)
    
    normal = engine.detect_regime('BOS', 'MIA', injuries_home=0, injuries_away=1)
    print(f"\n  {normal['matchup']}")
    print(f"  {normal['summary']}")
    print(f"  Kelly Multiplier: {normal['kelly_multiplier']}")
    
    # Test 2: High variance game
    print("\n" + "=" * 80)
    print("TEST 2: HIGH VARIANCE GAME")
    print("=" * 80)
    
    high_var = engine.detect_regime('OKC', 'IND', injuries_home=1, injuries_away=1,
                                     questionable_home=2, questionable_away=1)
    print(f"\n  {high_var['matchup']}")
    print(f"  {high_var['summary']}")
    if high_var['warnings']:
        print(f"\n  ⚠️ Warnings:")
        for w in high_var['warnings']:
            print(f"    - {w}")
    
    # Test 3: Unstable game
    print("\n" + "=" * 80)
    print("TEST 3: UNSTABLE GAME (INJURIES)")
    print("=" * 80)
    
    unstable = engine.detect_regime('LAL', 'GSW', injuries_home=3, injuries_away=2,
                                     questionable_home=2, questionable_away=3, b2b_home=True)
    print(f"\n  {unstable['matchup']}")
    print(f"  {unstable['summary']}")
    print(f"  Kelly Multiplier: {unstable['kelly_multiplier']}")
    
    # Test 4: Tanking detection
    print("\n" + "=" * 80)
    print("TEST 4: TANKING DETECTION")
    print("=" * 80)
    
    tank = engine.detect_tanking_rest('WAS', game_number=75, wins=15, losses=55)
    print(f"\n  Team: {tank['team']}")
    print(f"  Record: {tank['record']} ({tank['win_pct']:.1%})")
    print(f"  Tanking Risk: {tank['tanking_risk']:.0%}")
    print(f"  Recommendation: {tank['recommendation']}")
    
    # Test 5: Full assessment
    print("\n" + "=" * 80)
    print("TEST 5: FULL GAME ASSESSMENT")
    print("=" * 80)
    
    full = engine.full_game_assessment('BOS', 'LAL', injuries_home=0, injuries_away=2,
                                        questionable_home=1, questionable_away=2,
                                        b2b_home=False, b2b_away=True)
    print(f"\n  {full['matchup']}")
    print(f"  Action: {full['action']}")
    print(f"  Kelly Multiplier: {full['kelly_multiplier']}")
    
    # Test 6: Slate analysis
    print("\n" + "=" * 80)
    print("TEST 6: SLATE ANALYSIS")
    print("=" * 80)
    
    slate = [
        {'home_team': 'BOS', 'away_team': 'MIA'},
        {'home_team': 'LAL', 'away_team': 'GSW', 'injuries_home': 3, 'injuries_away': 2},
        {'home_team': 'OKC', 'away_team': 'CLE'},
        {'home_team': 'NYK', 'away_team': 'PHI', 'b2b_home': True, 'b2b_away': True},
    ]
    
    analysis = engine.analyze_slate(slate)
    print(f"\n  {analysis['summary']}")
    print(f"  Bettable: {analysis['bettable_games']}")
    print(f"  Avoid: {analysis['avoid_games']}")
    
    print("\n" + "=" * 80)
    print("✅ UNCERTAINTY ENGINE v3.0 - ALL TESTS COMPLETE")
    print("=" * 80)
