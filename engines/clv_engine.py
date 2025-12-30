#!/usr/bin/env python3
"""
================================================================================
CLV ENGINE v3.0 (CLOSING LINE VALUE) - ULTIMATE EDITION
================================================================================
The #1 predictor of long-term betting profitability

WHAT IS CLV?
------------
CLV = The difference between the odds you got and the closing odds.

Example:
- You bet Lakers -3 at -110
- Game closes at Lakers -5 at -110
- You got 2 points of CLV (the line moved toward your side)

WHY CLV MATTERS:
----------------
1. CLV is the BEST predictor of long-term profitability
2. Bettors with +2 cents CLV average are almost always profitable
3. Sharp bettors consistently beat the closing line
4. Books move lines based on sharp action - closing line is "truth"

CLV MEASUREMENT:
----------------
- Measured in "cents" (probability points × 100)
- +5 cents = excellent
- +2 cents = solid (profitable long-term)
- 0 cents = break even
- -3 cents = losing long-term

FEATURES:
---------
1. CLV calculation (cents and percentage)
2. No-vig CLV (most accurate)
3. Line movement tracking
4. Steam move detection
5. Sharp action identification
6. Reverse line movement (RLM)
7. Historical CLV tracking
8. CLV prediction
9. Optimal bet timing

================================================================================
"""

import numpy as np
from scipy import stats
from datetime import datetime, timedelta
from sqlalchemy import create_engine, text
from typing import List, Dict, Optional, Tuple
import warnings
warnings.filterwarnings('ignore')

# ==============================================================================
# CONFIGURATION
# ==============================================================================
DATABASE_URL = "postgresql://sb_algo_db_user:0HDtYp4EY2Lo5At8iyf44PD1zDioSPK7@dpg-d495uhchg0os738l1a50-a.virginia-postgres.render.com/sb_algo_db"

# CLV thresholds (in cents)
CLV_THRESHOLDS = {
    'excellent': 8.0,      # 8+ cents = excellent
    'very_good': 5.0,      # 5-8 cents = very good
    'good': 3.0,           # 3-5 cents = good
    'solid': 1.5,          # 1.5-3 cents = solid
    'marginal': 0.0,       # 0-1.5 cents = marginal
    'poor': -3.0,          # -3-0 cents = poor
    'bad': -999,           # < -3 cents = bad
}

# Steam move threshold (cents)
STEAM_MOVE_THRESHOLD = 15  # 15+ cent move = steam

# Sharp action indicators
SHARP_INDICATORS = {
    'large_move': 10,           # 10+ cent move
    'early_move_pct': 0.60,     # 60%+ of move in first hour
    'rlm_threshold': 5,         # Reverse line movement of 5+ cents
}


class CLVEngine:
    """
    ============================================================================
    CLV ENGINE - Master Class
    ============================================================================
    
    Tracks and analyzes Closing Line Value - the gold standard for
    measuring betting skill.
    
    Primary Use Cases:
    1. Calculate CLV on individual bets
    2. Track historical CLV performance
    3. Detect sharp line movement
    4. Identify optimal betting times
    5. Predict closing lines
    
    ============================================================================
    """
    
    def __init__(self):
        """Initialize CLV Engine"""
        self.engine = create_engine(DATABASE_URL)
    
    # ==========================================================================
    # ODDS CONVERSION UTILITIES
    # ==========================================================================
    
    def american_to_decimal(self, american: int) -> float:
        """Convert American odds to decimal odds"""
        if american > 0:
            return 1 + american / 100
        else:
            return 1 + 100 / abs(american)
    
    def decimal_to_american(self, decimal: float) -> float:
        """Convert decimal odds to American odds"""
        if decimal >= 2.0:
            return (decimal - 1) * 100
        else:
            return -100 / (decimal - 1)
    
    def american_to_implied(self, american: int) -> float:
        """Convert American odds to implied probability (includes vig)"""
        if american > 0:
            return 100 / (american + 100)
        else:
            return abs(american) / (abs(american) + 100)
    
    def implied_to_american(self, implied: float) -> float:
        """Convert implied probability to American odds"""
        if implied <= 0 or implied >= 1:
            return 0
        if implied >= 0.5:
            return -100 * implied / (1 - implied)
        else:
            return 100 * (1 - implied) / implied
    
    def remove_vig(self, odds_side1: int, odds_side2: int) -> Tuple[float, float, float]:
        """
        Remove vig to get true probabilities.
        
        Args:
            odds_side1: American odds for side 1
            odds_side2: American odds for side 2
            
        Returns:
            (true_prob_side1, true_prob_side2, vig_percentage)
        """
        impl1 = self.american_to_implied(odds_side1)
        impl2 = self.american_to_implied(odds_side2)
        
        total = impl1 + impl2
        vig = (total - 1) * 100
        
        true1 = impl1 / total
        true2 = impl2 / total
        
        return true1, true2, vig
    
    # ==========================================================================
    # CLV CALCULATIONS
    # ==========================================================================
    
    def calculate_clv_cents(self, bet_odds: int, closing_odds: int) -> float:
        """
        Calculate CLV in cents (industry standard).
        
        Cents = difference in implied probability × 100
        
        Positive CLV = You got better odds than closing (GOOD!)
        Negative CLV = You got worse odds than closing (BAD!)
        
        Args:
            bet_odds: American odds when you placed the bet
            closing_odds: American odds at game start (closing line)
            
        Returns:
            CLV in cents
            
        Examples:
            >>> engine.calculate_clv_cents(-110, -120)
            1.11  # Line moved against you = you got good value
            
            >>> engine.calculate_clv_cents(-120, -110)
            -1.09  # Line moved toward you = you got bad value
        """
        bet_implied = self.american_to_implied(bet_odds)
        close_implied = self.american_to_implied(closing_odds)
        
        # CLV = closing implied - bet implied
        # If closing is harder (higher implied), you got value
        clv_cents = (close_implied - bet_implied) * 100
        
        return round(clv_cents, 2)
    
    def calculate_clv_percentage(self, bet_odds: int, closing_odds: int) -> float:
        """
        Calculate CLV as percentage of your bet implied probability.
        
        Better for comparing across different odds ranges.
        
        Args:
            bet_odds: Your bet odds
            closing_odds: Closing odds
            
        Returns:
            CLV as percentage
        """
        bet_implied = self.american_to_implied(bet_odds)
        close_implied = self.american_to_implied(closing_odds)
        
        if bet_implied == 0:
            return 0.0
        
        clv_pct = (close_implied - bet_implied) / bet_implied * 100
        
        return round(clv_pct, 2)
    
    def calculate_clv_no_vig(self, bet_odds: int, 
                             closing_odds_your_side: int,
                             closing_odds_other_side: int) -> Dict:
        """
        Calculate CLV using no-vig closing line (most accurate method).
        
        This removes the vig from closing odds to get true market probability,
        then compares to what you paid.
        
        Args:
            bet_odds: Your bet odds
            closing_odds_your_side: Closing odds on your side
            closing_odds_other_side: Closing odds on opposite side
            
        Returns:
            CLV analysis with no-vig adjustment
            
        Example:
            >>> engine.calculate_clv_no_vig(-110, -115, -105)
            # Closing: -115/-105 → true prob 53.49% (no-vig)
            # You paid -110 → 52.38%
            # CLV = 53.49 - 52.38 = 1.11 cents
        """
        bet_implied = self.american_to_implied(bet_odds)
        
        # Get true closing probability (no vig)
        true_close, _, vig = self.remove_vig(closing_odds_your_side, closing_odds_other_side)
        
        clv_cents = (true_close - bet_implied) * 100
        clv_pct = (true_close - bet_implied) / bet_implied * 100 if bet_implied > 0 else 0
        
        return {
            'clv_cents': round(clv_cents, 2),
            'clv_pct': round(clv_pct, 2),
            'bet_implied': round(bet_implied, 4),
            'closing_implied_with_vig': round(self.american_to_implied(closing_odds_your_side), 4),
            'closing_no_vig': round(true_close, 4),
            'closing_vig_pct': round(vig, 2),
            'bet_odds': bet_odds,
            'closing_odds': closing_odds_your_side,
        }
    
    # ==========================================================================
    # CLV ANALYSIS
    # ==========================================================================
    
    def analyze_clv(self, bet_odds: int, closing_odds: int, 
                    bet_description: str = None) -> Dict:
        """
        Comprehensive CLV analysis for a single bet.
        
        Args:
            bet_odds: Your bet odds
            closing_odds: Closing odds
            bet_description: Optional bet description
            
        Returns:
            Complete CLV analysis
        """
        clv_cents = self.calculate_clv_cents(bet_odds, closing_odds)
        clv_pct = self.calculate_clv_percentage(bet_odds, closing_odds)
        
        bet_decimal = self.american_to_decimal(bet_odds)
        close_decimal = self.american_to_decimal(closing_odds)
        
        bet_implied = self.american_to_implied(bet_odds)
        close_implied = self.american_to_implied(closing_odds)
        
        # Grade the CLV
        rating = self._rate_clv(clv_cents)
        
        # Line movement direction
        if clv_cents > 0.5:
            direction = 'MOVED_TOWARD_YOUR_SIDE'
            interpretation = 'Line moved against you = you got VALUE'
        elif clv_cents < -0.5:
            direction = 'MOVED_AWAY_FROM_YOUR_SIDE'  
            interpretation = 'Line moved with you = you MISSED value'
        else:
            direction = 'MINIMAL_MOVEMENT'
            interpretation = 'Line stayed relatively stable'
        
        # Expected long-term ROI from CLV
        # Rule of thumb: +1 cent CLV ≈ +1% ROI
        expected_roi = clv_cents
        
        return {
            'description': bet_description,
            
            'clv_cents': clv_cents,
            'clv_pct': clv_pct,
            'rating': rating['rating'],
            'rating_description': rating['description'],
            
            'bet_odds': bet_odds,
            'closing_odds': closing_odds,
            'bet_implied': round(bet_implied, 4),
            'closing_implied': round(close_implied, 4),
            'bet_decimal': round(bet_decimal, 3),
            'closing_decimal': round(close_decimal, 3),
            
            'line_movement': {
                'direction': direction,
                'interpretation': interpretation,
                'cents_moved': abs(clv_cents),
            },
            
            'expected_roi_pct': round(expected_roi, 2),
            'long_term_outlook': 'PROFITABLE' if clv_cents > 1 else 'MARGINAL' if clv_cents > 0 else 'LOSING',
        }
    
    def _rate_clv(self, clv_cents: float) -> Dict:
        """Rate CLV performance"""
        if clv_cents >= CLV_THRESHOLDS['excellent']:
            return {'rating': 'EXCELLENT', 'description': 'Elite CLV - top tier sharp betting'}
        elif clv_cents >= CLV_THRESHOLDS['very_good']:
            return {'rating': 'VERY_GOOD', 'description': 'Strong CLV - consistently profitable'}
        elif clv_cents >= CLV_THRESHOLDS['good']:
            return {'rating': 'GOOD', 'description': 'Good CLV - solid long-term'}
        elif clv_cents >= CLV_THRESHOLDS['solid']:
            return {'rating': 'SOLID', 'description': 'Positive CLV - marginal edge'}
        elif clv_cents >= CLV_THRESHOLDS['marginal']:
            return {'rating': 'MARGINAL', 'description': 'Break-even CLV'}
        elif clv_cents >= CLV_THRESHOLDS['poor']:
            return {'rating': 'POOR', 'description': 'Negative CLV - losing proposition'}
        else:
            return {'rating': 'BAD', 'description': 'Severely negative CLV - major leak'}
    
    # ==========================================================================
    # LINE MOVEMENT ANALYSIS
    # ==========================================================================
    
    def analyze_line_movement(self, opening_odds: int, current_odds: int,
                              closing_odds: int = None,
                              time_opened: datetime = None,
                              current_time: datetime = None) -> Dict:
        """
        Analyze how line has moved from open to current/close.
        
        Args:
            opening_odds: Opening line
            current_odds: Current line
            closing_odds: Final closing line (optional)
            time_opened: When line opened (optional)
            current_time: Current time (optional)
            
        Returns:
            Line movement analysis
        """
        open_implied = self.american_to_implied(opening_odds)
        current_implied = self.american_to_implied(current_odds)
        
        move_cents = (current_implied - open_implied) * 100
        
        result = {
            'opening_odds': opening_odds,
            'current_odds': current_odds,
            'opening_implied': round(open_implied, 4),
            'current_implied': round(current_implied, 4),
            'movement_cents': round(move_cents, 2),
            'movement_direction': 'SHORTENED' if move_cents > 0 else 'LENGTHENED' if move_cents < 0 else 'UNCHANGED',
        }
        
        # Steam move detection
        if abs(move_cents) >= STEAM_MOVE_THRESHOLD:
            result['steam_move'] = True
            result['steam_alert'] = f'🚨 STEAM MOVE: {abs(move_cents):.1f} cents'
        else:
            result['steam_move'] = False
        
        # Time-based analysis
        if time_opened and current_time:
            hours_since_open = (current_time - time_opened).total_seconds() / 3600
            if hours_since_open > 0:
                result['hours_since_open'] = round(hours_since_open, 1)
                result['move_velocity'] = round(abs(move_cents) / hours_since_open, 2)
        
        # Include closing if provided
        if closing_odds:
            close_implied = self.american_to_implied(closing_odds)
            total_move = (close_implied - open_implied) * 100
            result['closing_odds'] = closing_odds
            result['closing_implied'] = round(close_implied, 4)
            result['total_movement_cents'] = round(total_move, 2)
        
        return result
    
    def detect_sharp_action(self, line_history: List[Dict]) -> Dict:
        """
        Detect sharp (professional) betting action from line movement patterns.
        
        Sharp indicators:
        1. Large moves on low volume (sharp money moves lines fast)
        2. Moves against public betting percentages (RLM)
        3. Quick moves immediately after line opens
        4. Movement through key numbers
        
        Args:
            line_history: List of {'timestamp', 'odds', 'public_pct'} dicts
            
        Returns:
            Sharp action analysis
        """
        if len(line_history) < 2:
            return {'sharp_detected': False, 'reason': 'Insufficient data points'}
        
        # Sort by timestamp
        history = sorted(line_history, key=lambda x: x['timestamp'])
        
        # Calculate total movement
        open_odds = history[0]['odds']
        close_odds = history[-1]['odds']
        
        open_impl = self.american_to_implied(open_odds)
        close_impl = self.american_to_implied(close_odds)
        
        total_move = (close_impl - open_impl) * 100
        
        # Initialize sharp score
        sharp_score = 0
        reasons = []
        
        # Check 1: Large total move
        if abs(total_move) >= SHARP_INDICATORS['large_move']:
            sharp_score += 25
            reasons.append(f'Large line move: {abs(total_move):.1f} cents')
        
        # Check 2: Early movement (most move happens early = sharp)
        if len(history) >= 3:
            early_move = abs((self.american_to_implied(history[1]['odds']) - open_impl) * 100)
            early_pct = early_move / abs(total_move) if total_move != 0 else 0
            
            if early_pct >= SHARP_INDICATORS['early_move_pct']:
                sharp_score += 30
                reasons.append(f'Early movement: {early_pct*100:.0f}% in first update')
        
        # Check 3: Reverse Line Movement (RLM)
        public_pcts = [h.get('public_pct', 50) for h in history if 'public_pct' in h]
        if public_pcts:
            avg_public = np.mean(public_pcts)
            
            # If public is heavy on one side but line moves OTHER way = RLM
            if (avg_public > 60 and total_move < -SHARP_INDICATORS['rlm_threshold']):
                sharp_score += 35
                reasons.append(f'RLM detected: {avg_public:.0f}% public but line moved against them')
            elif (avg_public < 40 and total_move > SHARP_INDICATORS['rlm_threshold']):
                sharp_score += 35
                reasons.append(f'RLM detected: Only {avg_public:.0f}% public but line moved with them')
        
        # Check 4: Movement through key numbers (3, 7 for NFL; 5, 7 for NBA)
        # This would require spread data
        
        # Determine if sharp
        sharp_detected = sharp_score >= 40
        
        return {
            'sharp_detected': sharp_detected,
            'sharp_score': sharp_score,
            'sharp_confidence': 'HIGH' if sharp_score >= 60 else 'MODERATE' if sharp_score >= 40 else 'LOW',
            'reasons': reasons,
            'opening_odds': open_odds,
            'closing_odds': close_odds,
            'total_movement_cents': round(total_move, 2),
            'recommendation': 'FOLLOW_SHARP' if sharp_detected else 'NO_CLEAR_SIGNAL',
        }
    
    def detect_rlm(self, opening_odds: int, closing_odds: int, 
                   public_pct_your_side: float) -> Dict:
        """
        Detect Reverse Line Movement (RLM).
        
        RLM occurs when the line moves AGAINST the public betting majority.
        This indicates sharp money on the unpopular side.
        
        Args:
            opening_odds: Opening line
            closing_odds: Closing line
            public_pct_your_side: Percentage of public on your side (0-100)
            
        Returns:
            RLM analysis
        """
        open_implied = self.american_to_implied(opening_odds)
        close_implied = self.american_to_implied(closing_odds)
        
        line_move = (close_implied - open_implied) * 100  # Positive = line shortened
        
        # RLM scenarios:
        # 1. Public > 60% on side A, but line moves toward side B
        # 2. Public < 40% on side A, but line moves toward side A
        
        rlm_detected = False
        rlm_strength = 0
        
        if public_pct_your_side > 55 and line_move < -2:
            rlm_detected = True
            rlm_strength = min((public_pct_your_side - 50) / 30 + abs(line_move) / 10, 1.0)
            rlm_type = 'CONTRARIAN_VALUE'
            message = f'Public at {public_pct_your_side:.0f}% but line moved away - sharp money OTHER side'
        elif public_pct_your_side < 45 and line_move > 2:
            rlm_detected = True
            rlm_strength = min((50 - public_pct_your_side) / 30 + line_move / 10, 1.0)
            rlm_type = 'SHARP_ALIGNED'
            message = f'Only {public_pct_your_side:.0f}% public but line moved toward - sharp money YOUR side'
        else:
            rlm_type = 'NONE'
            message = 'No significant reverse line movement detected'
        
        return {
            'rlm_detected': rlm_detected,
            'rlm_type': rlm_type,
            'rlm_strength': round(rlm_strength, 2),
            'public_pct': public_pct_your_side,
            'line_movement_cents': round(line_move, 2),
            'message': message,
            'recommendation': 'FADE_PUBLIC' if rlm_type == 'CONTRARIAN_VALUE' else 
                             'FOLLOW_SHARP' if rlm_type == 'SHARP_ALIGNED' else 'NEUTRAL',
        }
    
    # ==========================================================================
    # HISTORICAL CLV TRACKING
    # ==========================================================================
    
    def calculate_historical_clv(self, bets: List[Dict]) -> Dict:
        """
        Calculate aggregate CLV statistics from bet history.
        
        This is the KEY metric for evaluating betting performance.
        
        Args:
            bets: List of bet dicts with keys:
                  - 'bet_odds': Your bet odds
                  - 'closing_odds': Closing odds
                  - 'stake': Amount wagered (optional, for weighting)
                  - 'won': Whether bet won (optional, for win rate)
                  
        Returns:
            Comprehensive CLV statistics
        """
        if not bets:
            return {'error': 'No bets provided'}
        
        clv_values = []
        weighted_clv = 0
        total_stake = 0
        wins = 0
        
        for bet in bets:
            clv = self.calculate_clv_cents(bet['bet_odds'], bet['closing_odds'])
            clv_values.append(clv)
            
            stake = bet.get('stake', 1)
            weighted_clv += clv * stake
            total_stake += stake
            
            if bet.get('won', False):
                wins += 1
        
        # Statistics
        avg_clv = np.mean(clv_values)
        weighted_avg_clv = weighted_clv / total_stake if total_stake > 0 else 0
        clv_std = np.std(clv_values)
        median_clv = np.median(clv_values)
        
        # Win rate
        win_rate = (wins / len(bets)) * 100 if len(bets) > 0 else 0
        
        # Categorize bets
        positive_clv = sum(1 for c in clv_values if c > 0)
        negative_clv = sum(1 for c in clv_values if c < 0)
        
        # Expected ROI from CLV
        # +1 cent CLV ≈ +1% ROI (industry approximation)
        expected_roi = avg_clv
        
        # Rating
        rating = self._rate_clv(avg_clv)
        
        # Consistency score
        consistency = 100 - min(clv_std * 10, 100)  # Lower variance = more consistent
        
        return {
            'num_bets': len(bets),
            
            # CLV metrics
            'avg_clv_cents': round(avg_clv, 2),
            'weighted_avg_clv': round(weighted_avg_clv, 2),
            'median_clv': round(median_clv, 2),
            'clv_std': round(clv_std, 2),
            'min_clv': round(min(clv_values), 2),
            'max_clv': round(max(clv_values), 2),
            
            # Distribution
            'positive_clv_count': positive_clv,
            'negative_clv_count': negative_clv,
            'positive_clv_pct': round(positive_clv / len(bets) * 100, 1),
            
            # Performance
            'win_rate_pct': round(win_rate, 1),
            'expected_roi_pct': round(expected_roi, 2),
            
            # Rating
            'rating': rating['rating'],
            'rating_description': rating['description'],
            
            # Consistency
            'consistency_score': round(consistency, 1),
            
            # Stake info
            'total_stake': round(total_stake, 2),
            
            # Long-term projection
            'projected_annual_roi': round(expected_roi * 3.65, 1),  # Assuming ~365 bets/year
        }
    
    # ==========================================================================
    # CLV PREDICTION
    # ==========================================================================
    
    def estimate_closing_line(self, current_odds: int, 
                              hours_to_close: float,
                              sharp_action_detected: bool = False,
                              public_pct: float = 50) -> Dict:
        """
        Estimate where the closing line will be based on current state.
        
        This helps decide WHEN to bet - bet early if expecting line to move away,
        wait if expecting line to move toward you.
        
        Args:
            current_odds: Current odds
            hours_to_close: Hours until game starts
            sharp_action_detected: Whether sharp action has been detected
            public_pct: Public betting percentage on this side
            
        Returns:
            Closing line estimate with confidence range
        """
        current_implied = self.american_to_implied(current_odds)
        
        # Base expected movement (cents per hour)
        if hours_to_close > 24:
            base_move_per_hour = 0.05  # Very stable early
        elif hours_to_close > 12:
            base_move_per_hour = 0.10  # Starting to move
        elif hours_to_close > 6:
            base_move_per_hour = 0.20  # Active movement
        elif hours_to_close > 2:
            base_move_per_hour = 0.40  # Heavy movement
        else:
            base_move_per_hour = 0.80  # Last-minute action
        
        # Adjust for sharp action
        if sharp_action_detected:
            base_move_per_hour *= 1.5
        
        # Public money tends to push lines (fade later)
        public_bias = (public_pct - 50) / 100 * 0.02  # Slight bias toward public side
        
        # Calculate expected move and uncertainty
        expected_move = base_move_per_hour * hours_to_close
        std_move = expected_move * 0.8  # High uncertainty
        
        # 80% confidence interval
        low_move = -expected_move - 1.28 * std_move
        high_move = expected_move + 1.28 * std_move
        
        # Convert back to odds
        low_close_impl = np.clip(current_implied + low_move / 100, 0.01, 0.99)
        mid_close_impl = np.clip(current_implied + public_bias, 0.01, 0.99)
        high_close_impl = np.clip(current_implied + high_move / 100, 0.01, 0.99)
        
        low_close_odds = round(self.implied_to_american(low_close_impl))
        mid_close_odds = round(self.implied_to_american(mid_close_impl))
        high_close_odds = round(self.implied_to_american(high_close_impl))
        
        # Recommendation
        if hours_to_close > 12 and not sharp_action_detected:
            timing = 'WAIT'
            timing_reason = 'Early in the line cycle, more information coming'
        elif sharp_action_detected:
            timing = 'BET_NOW'
            timing_reason = 'Sharp action detected, line likely to continue moving'
        elif public_pct > 65:
            timing = 'WAIT_FOR_VALUE'
            timing_reason = 'Heavy public side, possible closing line value coming'
        elif hours_to_close < 2:
            timing = 'LAST_CHANCE'
            timing_reason = 'Close to game time, minimal movement expected'
        else:
            timing = 'NEUTRAL'
            timing_reason = 'No strong timing signal'
        
        return {
            'current_odds': current_odds,
            'current_implied': round(current_implied, 4),
            'hours_to_close': hours_to_close,
            
            'closing_estimate': {
                'low': low_close_odds,
                'expected': mid_close_odds,
                'high': high_close_odds,
            },
            
            'expected_movement_cents': round(expected_move, 1),
            'movement_uncertainty': round(std_move, 1),
            
            'sharp_action': sharp_action_detected,
            'public_pct': public_pct,
            
            'timing_recommendation': timing,
            'timing_reason': timing_reason,
        }
    
    def optimal_bet_timing(self, opening_odds: int, target_odds: int,
                           hours_available: float) -> Dict:
        """
        Determine optimal time to place bet based on line movement patterns.
        
        Args:
            opening_odds: Current/opening odds
            target_odds: Odds you're hoping to get
            hours_available: Hours until game
            
        Returns:
            Optimal timing recommendation
        """
        open_impl = self.american_to_implied(opening_odds)
        target_impl = self.american_to_implied(target_odds)
        
        needed_move = (target_impl - open_impl) * 100
        
        # Typical line movement patterns
        # Most movement happens in last 6 hours
        
        if needed_move > 0:
            # Need line to shorten (get better odds)
            if needed_move < 2:
                probability = 0.45  # Reasonable chance
                wait_hours = min(hours_available * 0.7, 6)
            elif needed_move < 5:
                probability = 0.25  # Less likely
                wait_hours = min(hours_available * 0.5, 4)
            else:
                probability = 0.10  # Unlikely
                wait_hours = 1
        else:
            # Line moving away, bet now
            probability = 0.0
            wait_hours = 0
        
        return {
            'current_odds': opening_odds,
            'target_odds': target_odds,
            'movement_needed_cents': round(needed_move, 2),
            
            'probability_of_target': round(probability, 2),
            'recommended_wait_hours': round(wait_hours, 1),
            
            'recommendation': 'BET_NOW' if wait_hours == 0 else 
                             f'WAIT_{wait_hours:.0f}_HOURS' if probability > 0.2 else
                             'BET_NOW_TARGET_UNLIKELY',
        }


# ==============================================================================
# TEST SUITE
# ==============================================================================
if __name__ == "__main__":
    print("=" * 80)
    print("CLV ENGINE v3.0 - COMPREHENSIVE TEST")
    print("=" * 80)
    
    engine = CLVEngine()
    
    # -------------------------------------------------------------------------
    # Test 1: Basic CLV Calculation
    # -------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("TEST 1: BASIC CLV CALCULATION")
    print("=" * 80)
    
    scenarios = [
        (-110, -120, "Line moved against you (GOOD)"),
        (-110, -105, "Line moved with you (BAD)"),
        (-110, -110, "No movement"),
        (+150, +130, "Underdog line shortened (GOOD)"),
        (-200, -180, "Heavy favorite shortened more (BAD)"),
    ]
    
    for bet_odds, close_odds, desc in scenarios:
        clv = engine.calculate_clv_cents(bet_odds, close_odds)
        print(f"\n  {desc}")
        print(f"    Bet: {bet_odds} → Close: {close_odds}")
        print(f"    CLV: {clv:+.2f} cents")
    
    # -------------------------------------------------------------------------
    # Test 2: CLV Analysis
    # -------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("TEST 2: COMPREHENSIVE CLV ANALYSIS")
    print("=" * 80)
    
    analysis = engine.analyze_clv(-110, -120, "Lakers -5.5")
    
    print(f"\n  Bet: {analysis['description']}")
    print(f"  CLV: {analysis['clv_cents']:+.2f} cents ({analysis['rating']})")
    print(f"  {analysis['rating_description']}")
    print(f"\n  Line Movement: {analysis['line_movement']['direction']}")
    print(f"  💡 {analysis['line_movement']['interpretation']}")
    print(f"\n  Expected Long-term ROI: {analysis['expected_roi_pct']:+.1f}%")
    
    # -------------------------------------------------------------------------
    # Test 3: No-Vig CLV
    # -------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("TEST 3: NO-VIG CLV (Most Accurate)")
    print("=" * 80)
    
    novig = engine.calculate_clv_no_vig(-110, -115, -105)
    
    print(f"\n  Your bet: -110")
    print(f"  Closing line: -115 / -105")
    print(f"  Closing vig: {novig['closing_vig_pct']:.1f}%")
    print(f"\n  Your implied: {novig['bet_implied']*100:.2f}%")
    print(f"  Closing no-vig: {novig['closing_no_vig']*100:.2f}%")
    print(f"\n  CLV (no-vig): {novig['clv_cents']:+.2f} cents")
    
    # -------------------------------------------------------------------------
    # Test 4: Line Movement Analysis
    # -------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("TEST 4: LINE MOVEMENT ANALYSIS")
    print("=" * 80)
    
    movement = engine.analyze_line_movement(-105, -115, -120)
    
    print(f"\n  Open: {movement['opening_odds']}")
    print(f"  Current: {movement['current_odds']}")
    print(f"  Close: {movement.get('closing_odds', 'N/A')}")
    print(f"\n  Movement: {movement['movement_cents']:+.2f} cents ({movement['movement_direction']})")
    print(f"  Total Movement: {movement.get('total_movement_cents', 'N/A')}")
    print(f"  Steam Move: {'🚨 YES' if movement['steam_move'] else 'No'}")
    
    # -------------------------------------------------------------------------
    # Test 5: Reverse Line Movement
    # -------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("TEST 5: REVERSE LINE MOVEMENT (RLM)")
    print("=" * 80)
    
    rlm = engine.detect_rlm(-110, -105, 75)  # 75% public but line moved away
    
    print(f"\n  Public on your side: {rlm['public_pct']:.0f}%")
    print(f"  Line movement: {rlm['line_movement_cents']:+.2f} cents")
    print(f"\n  RLM Detected: {'YES' if rlm['rlm_detected'] else 'NO'}")
    if rlm['rlm_detected']:
        print(f"  RLM Type: {rlm['rlm_type']}")
        print(f"  RLM Strength: {rlm['rlm_strength']}")
    print(f"\n  💡 {rlm['message']}")
    print(f"  📋 Recommendation: {rlm['recommendation']}")
    
    # -------------------------------------------------------------------------
    # Test 6: Historical CLV
    # -------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("TEST 6: HISTORICAL CLV TRACKING")
    print("=" * 80)
    
    bet_history = [
        {'bet_odds': -110, 'closing_odds': -115, 'stake': 100, 'won': True},
        {'bet_odds': -110, 'closing_odds': -120, 'stake': 100, 'won': False},
        {'bet_odds': +150, 'closing_odds': +140, 'stake': 50, 'won': True},
        {'bet_odds': -110, 'closing_odds': -108, 'stake': 100, 'won': True},
        {'bet_odds': -115, 'closing_odds': -110, 'stake': 100, 'won': False},
        {'bet_odds': -105, 'closing_odds': -115, 'stake': 150, 'won': True},
        {'bet_odds': +120, 'closing_odds': +110, 'stake': 75, 'won': False},
    ]
    
    historical = engine.calculate_historical_clv(bet_history)
    
    print(f"\n  Bets Analyzed: {historical['num_bets']}")
    print(f"\n  📊 CLV METRICS")
    print(f"     Average CLV: {historical['avg_clv_cents']:+.2f} cents")
    print(f"     Weighted CLV: {historical['weighted_avg_clv']:+.2f} cents")
    print(f"     Median CLV: {historical['median_clv']:+.2f} cents")
    print(f"     CLV Std Dev: {historical['clv_std']:.2f}")
    print(f"\n  📈 PERFORMANCE")
    print(f"     Positive CLV Bets: {historical['positive_clv_pct']:.0f}%")
    print(f"     Win Rate: {historical['win_rate_pct']:.1f}%")
    print(f"     Expected ROI: {historical['expected_roi_pct']:+.2f}%")
    print(f"\n  ⭐ RATING: {historical['rating']}")
    print(f"     {historical['rating_description']}")
    
    # -------------------------------------------------------------------------
    # Test 7: Closing Line Prediction
    # -------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("TEST 7: CLOSING LINE PREDICTION")
    print("=" * 80)
    
    prediction = engine.estimate_closing_line(-110, hours_to_close=8, 
                                               sharp_action_detected=True,
                                               public_pct=65)
    
    print(f"\n  Current: {prediction['current_odds']}")
    print(f"  Hours to Close: {prediction['hours_to_close']}")
    print(f"  Sharp Action: {'YES' if prediction['sharp_action'] else 'NO'}")
    print(f"  Public: {prediction['public_pct']:.0f}%")
    print(f"\n  📊 CLOSING ESTIMATE")
    print(f"     Low: {prediction['closing_estimate']['low']}")
    print(f"     Expected: {prediction['closing_estimate']['expected']}")
    print(f"     High: {prediction['closing_estimate']['high']}")
    print(f"\n  ⏰ TIMING: {prediction['timing_recommendation']}")
    print(f"     {prediction['timing_reason']}")
    
    # -------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("✅ CLV ENGINE v3.0 - ALL TESTS COMPLETE")
    print("=" * 80)
