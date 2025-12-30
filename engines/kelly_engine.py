#!/usr/bin/env python3
"""
================================================================================
KELLY CRITERION ENGINE v3.0 - ULTIMATE EDITION
================================================================================
Optimal bet sizing for maximum long-term growth

THE KELLY CRITERION:
--------------------
f* = (bp - q) / b

Where:
- f* = Optimal fraction of bankroll to bet
- b = Net odds (decimal odds - 1)
- p = Probability of winning
- q = Probability of losing (1 - p)

WHY KELLY MATTERS:
------------------
1. Maximizes long-term geometric growth rate
2. Minimizes risk of ruin
3. Automatically sizes bets based on edge
4. Balances aggression with preservation

THE PROBLEM WITH FULL KELLY:
----------------------------
Full Kelly is mathematically optimal but practically dangerous:
- High variance (50%+ drawdowns common)
- Assumes perfect probability estimates
- Emotionally difficult to execute

SOLUTION: FRACTIONAL KELLY
--------------------------
We use 20-30% of full Kelly to:
- Reduce variance by 80%+
- Account for estimation errors
- Maintain emotional stability
- Still capture most of the growth

KEY FEATURES:
-------------
1. Full Kelly calculation
2. Fractional Kelly (1/4, 1/3, 1/2)
3. Simultaneous bet optimization
4. Risk of ruin analysis
5. Drawdown simulation
6. Bankroll growth projections
7. Unit size recommendations
8. Max bet limits
9. Edge-based bet grading

================================================================================
"""

import numpy as np
from scipy import stats
from scipy.optimize import minimize
from typing import List, Dict, Optional, Tuple
import warnings
warnings.filterwarnings('ignore')

# ==============================================================================
# CONFIGURATION
# ==============================================================================

# Kelly fractions by risk profile
KELLY_FRACTIONS = {
    'ultra_conservative': 0.10,   # 10% Kelly - minimal variance
    'conservative': 0.20,         # 20% Kelly - low variance
    'moderate': 0.25,             # 25% Kelly - balanced (RECOMMENDED)
    'aggressive': 0.33,           # 33% Kelly - higher variance
    'full': 1.00,                 # 100% Kelly - maximum growth, max variance
}

# Maximum bet as percentage of bankroll
MAX_BET_LIMITS = {
    'ultra_conservative': 0.02,   # 2% max
    'conservative': 0.03,         # 3% max
    'moderate': 0.05,             # 5% max
    'aggressive': 0.08,           # 8% max
    'full': 0.15,                 # 15% max
}

# Minimum edge required to bet
MIN_EDGE_THRESHOLD = 0.02  # 2% minimum edge

# Number of simulations for Monte Carlo
MONTE_CARLO_SIMS = 10000


class KellyEngine:
    """
    ============================================================================
    KELLY CRITERION ENGINE - Master Class
    ============================================================================
    
    Calculates optimal bet sizes based on edge and probability.
    
    Primary Use Cases:
    1. Size individual bets optimally
    2. Manage simultaneous bet exposure
    3. Analyze risk of ruin
    4. Project bankroll growth
    5. Set appropriate unit sizes
    
    ============================================================================
    """
    
    def __init__(self, risk_profile: str = 'moderate'):
        """
        Initialize Kelly Engine with risk profile.
        
        Args:
            risk_profile: One of 'ultra_conservative', 'conservative', 
                         'moderate', 'aggressive', 'full'
        """
        self.risk_profile = risk_profile
        self.kelly_fraction = KELLY_FRACTIONS.get(risk_profile, 0.25)
        self.max_bet_pct = MAX_BET_LIMITS.get(risk_profile, 0.05)
        self.min_edge = MIN_EDGE_THRESHOLD
    
    # ==========================================================================
    # ODDS CONVERSION
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
    # KELLY CALCULATIONS
    # ==========================================================================
    
    def full_kelly(self, win_prob: float, american_odds: int) -> float:
        """
        Calculate full Kelly stake.
        
        Formula: f* = (bp - q) / b
        
        Args:
            win_prob: True probability of winning (0 to 1)
            american_odds: American odds offered
            
        Returns:
            Optimal fraction of bankroll to bet (can be negative = don't bet)
            
        Examples:
            >>> engine.full_kelly(0.55, -110)
            0.05  # Bet 5% of bankroll
            
            >>> engine.full_kelly(0.45, -110)
            -0.05  # Negative edge, don't bet
        """
        if win_prob <= 0 or win_prob >= 1:
            return 0.0
        
        decimal_odds = self.american_to_decimal(american_odds)
        b = decimal_odds - 1  # Net odds (profit per $1 bet)
        p = win_prob
        q = 1 - p
        
        # Kelly formula: f* = (bp - q) / b
        kelly = (b * p - q) / b
        
        return kelly
    
    def fractional_kelly(self, win_prob: float, american_odds: int, 
                         fraction: float = None) -> float:
        """
        Calculate fractional Kelly stake.
        
        Fractional Kelly reduces variance while maintaining positive expected growth.
        
        Args:
            win_prob: True probability of winning
            american_odds: American odds
            fraction: Kelly fraction (default uses risk profile)
            
        Returns:
            Recommended stake as fraction of bankroll
        """
        if fraction is None:
            fraction = self.kelly_fraction
        
        full = self.full_kelly(win_prob, american_odds)
        
        if full <= 0:
            return 0.0
        
        fractional = full * fraction
        
        # Apply maximum bet limit
        return min(fractional, self.max_bet_pct)
    
    def kelly_from_edge(self, edge: float, american_odds: int) -> float:
        """
        Calculate Kelly from edge percentage.
        
        Args:
            edge: Edge as decimal (e.g., 0.05 for 5% edge)
            american_odds: American odds
            
        Returns:
            Kelly stake
        """
        implied = self.american_to_implied(american_odds)
        true_prob = implied + edge
        return self.full_kelly(true_prob, american_odds)
    
    # ==========================================================================
    # COMPREHENSIVE BET SIZING
    # ==========================================================================
    
    def calculate_bet(self, win_prob: float, american_odds: int, 
                      bankroll: float, description: str = None) -> Dict:
        """
        Complete bet sizing calculation with all metrics.
        
        Args:
            win_prob: True probability of winning
            american_odds: American odds offered
            bankroll: Current bankroll
            description: Optional bet description
            
        Returns:
            Comprehensive bet sizing analysis
            
        Example:
            >>> engine.calculate_bet(0.58, -110, 10000, "Thunder -3.5")
        """
        decimal_odds = self.american_to_decimal(american_odds)
        implied = self.american_to_implied(american_odds)
        edge = win_prob - implied
        edge_pct = edge * 100
        
        # Check minimum edge
        if edge < self.min_edge:
            return {
                'should_bet': False,
                'reason': f'Edge {edge_pct:.1f}% below minimum threshold {self.min_edge*100:.0f}%',
                'edge_pct': round(edge_pct, 2),
                'win_prob': round(win_prob, 4),
                'implied_prob': round(implied, 4),
            }
        
        # Calculate all Kelly variants
        full = self.full_kelly(win_prob, american_odds)
        quarter = self.fractional_kelly(win_prob, american_odds, 0.25)
        third = self.fractional_kelly(win_prob, american_odds, 0.33)
        half = self.fractional_kelly(win_prob, american_odds, 0.50)
        recommended = self.fractional_kelly(win_prob, american_odds)
        
        # Expected Value
        profit_if_win = decimal_odds - 1
        ev = (win_prob * profit_if_win) - ((1 - win_prob) * 1)
        ev_pct = ev * 100
        
        # Bet amounts
        recommended_amount = recommended * bankroll
        
        # Unit sizing (1 unit = recommended Kelly)
        # But also calculate traditional units
        unit_size_1pct = bankroll * 0.01
        units_recommended = recommended_amount / unit_size_1pct if unit_size_1pct > 0 else 0
        
        # Confidence/Grade based on edge and Kelly
        grade = self._grade_bet(edge, full)
        
        # Variance impact
        variance_per_bet = win_prob * (1 - win_prob) * (profit_if_win ** 2)
        
        return {
            'should_bet': True,
            'description': description,
            
            # Core metrics
            'win_prob': round(win_prob, 4),
            'implied_prob': round(implied, 4),
            'edge': round(edge, 4),
            'edge_pct': round(edge_pct, 2),
            'ev': round(ev, 4),
            'ev_pct': round(ev_pct, 2),
            
            # Odds
            'american_odds': american_odds,
            'decimal_odds': round(decimal_odds, 3),
            
            # Kelly variants
            'full_kelly_pct': round(full * 100, 2),
            'quarter_kelly_pct': round(quarter * 100, 2),
            'third_kelly_pct': round(third * 100, 2),
            'half_kelly_pct': round(half * 100, 2),
            
            # Recommended bet
            'recommended_pct': round(recommended * 100, 2),
            'recommended_amount': round(recommended_amount, 2),
            'recommended_units': round(units_recommended, 1),
            
            # Context
            'bankroll': bankroll,
            'risk_profile': self.risk_profile,
            'kelly_fraction': self.kelly_fraction,
            'max_bet_pct': self.max_bet_pct * 100,
            
            # Grade
            'grade': grade['grade'],
            'confidence': grade['confidence'],
            
            # Variance
            'variance_per_bet': round(variance_per_bet, 4),
        }
    
    def _grade_bet(self, edge: float, full_kelly: float) -> Dict:
        """Grade bet quality based on edge and Kelly"""
        if full_kelly >= 0.10:
            grade = 'A+'
            confidence = 'VERY_HIGH'
        elif full_kelly >= 0.07:
            grade = 'A'
            confidence = 'HIGH'
        elif full_kelly >= 0.05:
            grade = 'B+'
            confidence = 'GOOD'
        elif full_kelly >= 0.03:
            grade = 'B'
            confidence = 'MODERATE'
        elif full_kelly >= 0.02:
            grade = 'C+'
            confidence = 'FAIR'
        elif full_kelly > 0:
            grade = 'C'
            confidence = 'LOW'
        else:
            grade = 'F'
            confidence = 'NONE'
        
        return {'grade': grade, 'confidence': confidence}
    
    # ==========================================================================
    # SIMULTANEOUS BETS
    # ==========================================================================
    
    def calculate_simultaneous_bets(self, bets: List[Dict], 
                                     bankroll: float) -> Dict:
        """
        Optimize bet sizing for multiple simultaneous bets.
        
        When placing multiple bets at once, we need to:
        1. Calculate individual Kelly for each
        2. Scale down if total exposure exceeds limits
        3. Consider correlation between bets
        
        Args:
            bets: List of bet dicts with 'win_prob', 'american_odds', 'description'
            bankroll: Current bankroll
            
        Returns:
            Optimized bet sizes for all bets
            
        Example:
            >>> bets = [
            ...     {'win_prob': 0.55, 'american_odds': -110, 'description': 'Celtics -5'},
            ...     {'win_prob': 0.58, 'american_odds': -110, 'description': 'Thunder ML'},
            ...     {'win_prob': 0.52, 'american_odds': 100, 'description': 'Over 224'},
            ... ]
            >>> engine.calculate_simultaneous_bets(bets, 10000)
        """
        if not bets:
            return {'error': 'No bets provided'}
        
        # Calculate individual Kelly for each bet
        individual_results = []
        total_kelly = 0
        valid_bets = 0
        
        for bet in bets:
            result = self.calculate_bet(
                bet['win_prob'], 
                bet['american_odds'], 
                bankroll, 
                bet.get('description')
            )
            individual_results.append(result)
            
            if result['should_bet']:
                total_kelly += result['recommended_pct'] / 100
                valid_bets += 1
        
        # Maximum total exposure
        max_total_exposure = self.max_bet_pct * len(bets) * 0.8  # 80% of per-bet max * num bets
        max_total_exposure = min(max_total_exposure, 0.20)  # Never more than 20% total
        
        # Scale factor if needed
        if total_kelly > max_total_exposure:
            scale_factor = max_total_exposure / total_kelly
        else:
            scale_factor = 1.0
        
        # Apply scaling and calculate final bets
        final_bets = []
        total_stake = 0
        
        for i, result in enumerate(individual_results):
            if result['should_bet']:
                adjusted_pct = result['recommended_pct'] * scale_factor
                adjusted_amount = adjusted_pct / 100 * bankroll
                total_stake += adjusted_amount
                
                final_bets.append({
                    'description': result.get('description', f'Bet {i+1}'),
                    'win_prob': result['win_prob'],
                    'american_odds': result['american_odds'],
                    'edge_pct': result['edge_pct'],
                    'ev_pct': result['ev_pct'],
                    'grade': result['grade'],
                    'original_kelly_pct': result['recommended_pct'],
                    'adjusted_kelly_pct': round(adjusted_pct, 2),
                    'stake': round(adjusted_amount, 2),
                })
            else:
                final_bets.append({
                    'description': bets[i].get('description', f'Bet {i+1}'),
                    'should_bet': False,
                    'reason': result.get('reason', 'No edge'),
                    'stake': 0,
                })
        
        # Calculate combined expected value
        combined_ev = sum(b.get('ev_pct', 0) * b.get('stake', 0) / total_stake 
                        for b in final_bets if b.get('stake', 0) > 0) if total_stake > 0 else 0
        
        return {
            'num_bets': len(bets),
            'valid_bets': valid_bets,
            'scale_factor': round(scale_factor, 3),
            'total_stake': round(total_stake, 2),
            'total_stake_pct': round(total_stake / bankroll * 100, 2),
            'combined_ev_pct': round(combined_ev, 2),
            'bankroll': bankroll,
            'bets': final_bets,
        }
    
    # ==========================================================================
    # RISK OF RUIN ANALYSIS
    # ==========================================================================
    
    def risk_of_ruin(self, win_prob: float, american_odds: int, 
                     num_bets: int = 500, ruin_threshold: float = 0.50,
                     n_sims: int = MONTE_CARLO_SIMS) -> Dict:
        """
        Calculate probability of hitting a drawdown threshold.
        
        Uses Monte Carlo simulation to estimate risk of losing X% of bankroll.
        
        Args:
            win_prob: Win probability per bet
            american_odds: Odds per bet
            num_bets: Number of bets to simulate
            ruin_threshold: Fraction of bankroll loss to consider "ruin" (e.g., 0.5 = 50% loss)
            n_sims: Number of simulations
            
        Returns:
            Risk of ruin analysis
        """
        kelly = self.fractional_kelly(win_prob, american_odds)
        decimal_odds = self.american_to_decimal(american_odds)
        profit_if_win = decimal_odds - 1
        
        ruin_count = 0
        final_bankrolls = []
        max_drawdowns = []
        
        for _ in range(n_sims):
            bankroll = 1.0
            peak = 1.0
            max_dd = 0.0
            ruined = False
            
            for _ in range(num_bets):
                bet_size = kelly * bankroll
                
                if np.random.random() < win_prob:
                    bankroll += bet_size * profit_if_win
                else:
                    bankroll -= bet_size
                
                # Track peak and drawdown
                if bankroll > peak:
                    peak = bankroll
                
                dd = (peak - bankroll) / peak
                if dd > max_dd:
                    max_dd = dd
                
                # Check for ruin
                if bankroll < (1 - ruin_threshold) and not ruined:
                    ruin_count += 1
                    ruined = True
            
            final_bankrolls.append(bankroll)
            max_drawdowns.append(max_dd)
        
        return {
            'num_bets': num_bets,
            'kelly_used_pct': round(kelly * 100, 2),
            'win_prob': win_prob,
            'american_odds': american_odds,
            
            'risk_of_ruin': round(ruin_count / n_sims, 4),
            'risk_of_ruin_pct': round(ruin_count / n_sims * 100, 2),
            'ruin_threshold': f'{ruin_threshold*100:.0f}% loss',
            
            'avg_max_drawdown_pct': round(np.mean(max_drawdowns) * 100, 1),
            'median_max_drawdown_pct': round(np.median(max_drawdowns) * 100, 1),
            'worst_drawdown_pct': round(np.max(max_drawdowns) * 100, 1),
            'p90_drawdown_pct': round(np.percentile(max_drawdowns, 90) * 100, 1),
            
            'avg_final_bankroll': round(np.mean(final_bankrolls), 3),
            'median_final_bankroll': round(np.median(final_bankrolls), 3),
            'p10_final_bankroll': round(np.percentile(final_bankrolls, 10), 3),
            'p90_final_bankroll': round(np.percentile(final_bankrolls, 90), 3),
            
            'profitable_pct': round(np.mean([b > 1 for b in final_bankrolls]) * 100, 1),
            'double_up_pct': round(np.mean([b > 2 for b in final_bankrolls]) * 100, 1),
        }
    
    # ==========================================================================
    # EXPECTED GROWTH RATE
    # ==========================================================================
    
    def expected_growth_rate(self, win_prob: float, american_odds: int,
                              kelly_fraction: float = None) -> Dict:
        """
        Calculate expected geometric growth rate.
        
        G = p * ln(1 + f*b) + q * ln(1 - f)
        
        This is what Kelly maximizes.
        
        Args:
            win_prob: Win probability
            american_odds: Odds
            kelly_fraction: Fraction of Kelly to use
            
        Returns:
            Expected growth rate per bet
        """
        if kelly_fraction is None:
            kelly_fraction = self.kelly_fraction
        
        decimal_odds = self.american_to_decimal(american_odds)
        b = decimal_odds - 1
        p = win_prob
        q = 1 - p
        
        kelly = self.full_kelly(win_prob, american_odds) * kelly_fraction
        
        if kelly <= 0:
            return {
                'growth_rate': 0,
                'message': 'No edge, no growth'
            }
        
        # Geometric growth rate formula
        growth = p * np.log(1 + kelly * b) + q * np.log(1 - kelly)
        
        # Annualized (assuming 365 bets/year)
        annual_growth = (1 + growth) ** 365 - 1
        
        return {
            'kelly_pct': round(kelly * 100, 2),
            'growth_rate_per_bet': round(growth, 6),
            'growth_rate_per_bet_pct': round(growth * 100, 4),
            'annual_growth_rate': round(annual_growth, 4),
            'annual_growth_rate_pct': round(annual_growth * 100, 2),
            'doubling_time_bets': round(np.log(2) / growth, 0) if growth > 0 else float('inf'),
        }
    
    # ==========================================================================
    # BANKROLL PROJECTION
    # ==========================================================================
    
    def project_bankroll(self, win_prob: float, american_odds: int,
                         starting_bankroll: float, num_bets: int = 100,
                         n_sims: int = 1000) -> Dict:
        """
        Project bankroll growth over time with confidence intervals.
        
        Args:
            win_prob: Win probability per bet
            american_odds: Odds
            starting_bankroll: Starting amount
            num_bets: Number of bets to project
            n_sims: Number of simulations
            
        Returns:
            Bankroll projections with percentiles
        """
        kelly = self.fractional_kelly(win_prob, american_odds)
        decimal_odds = self.american_to_decimal(american_odds)
        profit_if_win = decimal_odds - 1
        
        # Simulate many paths
        all_paths = []
        
        for _ in range(n_sims):
            bankroll = starting_bankroll
            path = [bankroll]
            
            for _ in range(num_bets):
                bet_size = kelly * bankroll
                
                if np.random.random() < win_prob:
                    bankroll += bet_size * profit_if_win
                else:
                    bankroll -= bet_size
                
                path.append(bankroll)
            
            all_paths.append(path)
        
        # Convert to array for percentile calculation
        paths_array = np.array(all_paths)
        
        # Calculate percentiles at each time step
        p10 = np.percentile(paths_array, 10, axis=0)
        p25 = np.percentile(paths_array, 25, axis=0)
        p50 = np.percentile(paths_array, 50, axis=0)
        p75 = np.percentile(paths_array, 75, axis=0)
        p90 = np.percentile(paths_array, 90, axis=0)
        mean = np.mean(paths_array, axis=0)
        
        # Key milestones
        milestones = {}
        for milestone_bets in [25, 50, 100, 200, 500]:
            if milestone_bets <= num_bets:
                milestones[f'after_{milestone_bets}_bets'] = {
                    'p10': round(p10[milestone_bets], 2),
                    'p25': round(p25[milestone_bets], 2),
                    'median': round(p50[milestone_bets], 2),
                    'p75': round(p75[milestone_bets], 2),
                    'p90': round(p90[milestone_bets], 2),
                    'mean': round(mean[milestone_bets], 2),
                }
        
        return {
            'starting_bankroll': starting_bankroll,
            'num_bets': num_bets,
            'kelly_used_pct': round(kelly * 100, 2),
            'win_prob': win_prob,
            
            'final_bankroll': {
                'p10': round(p10[-1], 2),
                'p25': round(p25[-1], 2),
                'median': round(p50[-1], 2),
                'p75': round(p75[-1], 2),
                'p90': round(p90[-1], 2),
                'mean': round(mean[-1], 2),
            },
            
            'milestones': milestones,
            
            'expected_roi_pct': round((mean[-1] / starting_bankroll - 1) * 100, 1),
            'median_roi_pct': round((p50[-1] / starting_bankroll - 1) * 100, 1),
        }
    
    # ==========================================================================
    # UNIT SIZE RECOMMENDATIONS
    # ==========================================================================
    
    def recommend_unit_size(self, bankroll: float, 
                            risk_tolerance: str = 'moderate') -> Dict:
        """
        Recommend appropriate unit size based on bankroll and risk tolerance.
        
        Args:
            bankroll: Total bankroll
            risk_tolerance: 'conservative', 'moderate', 'aggressive'
            
        Returns:
            Unit size recommendations
        """
        unit_pcts = {
            'conservative': 0.005,   # 0.5% per unit
            'moderate': 0.01,        # 1% per unit
            'aggressive': 0.02,      # 2% per unit
        }
        
        kelly_fracs = {
            'conservative': 0.20,
            'moderate': 0.25,
            'aggressive': 0.33,
        }
        
        max_bets = {
            'conservative': 0.03,
            'moderate': 0.05,
            'aggressive': 0.08,
        }
        
        unit_pct = unit_pcts.get(risk_tolerance, 0.01)
        kelly_frac = kelly_fracs.get(risk_tolerance, 0.25)
        max_bet = max_bets.get(risk_tolerance, 0.05)
        
        unit_size = bankroll * unit_pct
        
        return {
            'bankroll': bankroll,
            'risk_tolerance': risk_tolerance,
            
            'unit_size': round(unit_size, 2),
            'unit_pct': round(unit_pct * 100, 2),
            
            'kelly_fraction': kelly_frac,
            'max_bet_pct': round(max_bet * 100, 1),
            'max_bet_amount': round(bankroll * max_bet, 2),
            
            'bet_sizes': {
                '1_unit': round(unit_size * 1, 2),
                '1.5_units': round(unit_size * 1.5, 2),
                '2_units': round(unit_size * 2, 2),
                '2.5_units': round(unit_size * 2.5, 2),
                '3_units': round(unit_size * 3, 2),
                '4_units': round(unit_size * 4, 2),
                '5_units': round(unit_size * 5, 2),
            },
            
            'daily_limits': {
                'max_bets_per_day': 10,
                'max_exposure_pct': round(max_bet * 100 * 3, 1),
                'max_exposure_amount': round(bankroll * max_bet * 3, 2),
            }
        }
    
    # ==========================================================================
    # COMPARE KELLY FRACTIONS
    # ==========================================================================
    
    def compare_kelly_fractions(self, win_prob: float, american_odds: int,
                                 num_bets: int = 200) -> Dict:
        """
        Compare different Kelly fractions to help choose risk level.
        
        Args:
            win_prob: Win probability
            american_odds: Odds
            num_bets: Bets to simulate
            
        Returns:
            Comparison of different Kelly fractions
        """
        fractions = [0.10, 0.20, 0.25, 0.33, 0.50, 1.00]
        names = ['10% (Ultra Conservative)', '20% (Conservative)', 
                 '25% (Moderate)', '33% (Aggressive)', 
                 '50% (Very Aggressive)', '100% (Full Kelly)']
        
        results = []
        
        for frac, name in zip(fractions, names):
            # Growth rate
            growth = self.expected_growth_rate(win_prob, american_odds, frac)
            
            # Risk of ruin (simplified - 50% threshold)
            ror = self.risk_of_ruin(win_prob, american_odds, num_bets, 0.50, 
                                    n_sims=2000)
            
            results.append({
                'fraction': frac,
                'name': name,
                'kelly_pct': round(self.full_kelly(win_prob, american_odds) * frac * 100, 2),
                'growth_per_bet_pct': growth['growth_rate_per_bet_pct'],
                'risk_of_50pct_loss': ror['risk_of_ruin_pct'],
                'avg_max_drawdown_pct': ror['avg_max_drawdown_pct'],
                'median_final_bankroll': ror['median_final_bankroll'],
                'profitable_pct': ror['profitable_pct'],
            })
        
        return {
            'win_prob': win_prob,
            'american_odds': american_odds,
            'num_bets_simulated': num_bets,
            'comparisons': results,
            'recommendation': self._recommend_kelly_fraction(results),
        }
    
    def _recommend_kelly_fraction(self, results: List[Dict]) -> str:
        """Generate recommendation based on comparison results"""
        # Find the fraction with best risk-adjusted return
        # We want good growth but low risk of ruin
        
        best_score = 0
        best_name = results[2]['name']  # Default to moderate
        
        for r in results:
            if r['risk_of_50pct_loss'] < 10:  # Acceptable risk
                # Score = growth / (1 + drawdown)
                score = r['growth_per_bet_pct'] / (1 + r['avg_max_drawdown_pct'] / 100)
                if score > best_score:
                    best_score = score
                    best_name = r['name']
        
        return f"Recommended: {best_name}"


# ==============================================================================
# TEST SUITE
# ==============================================================================
if __name__ == "__main__":
    print("=" * 80)
    print("KELLY CRITERION ENGINE v3.0 - COMPREHENSIVE TEST")
    print("=" * 80)
    
    engine = KellyEngine(risk_profile='moderate')
    bankroll = 10000
    
    # -------------------------------------------------------------------------
    # Test 1: Basic Kelly Calculation
    # -------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("TEST 1: BASIC KELLY CALCULATION")
    print("=" * 80)
    
    win_prob = 0.55
    odds = -110
    
    full = engine.full_kelly(win_prob, odds)
    quarter = engine.fractional_kelly(win_prob, odds, 0.25)
    third = engine.fractional_kelly(win_prob, odds, 0.33)
    half = engine.fractional_kelly(win_prob, odds, 0.50)
    
    print(f"\n  Scenario: {win_prob*100:.0f}% win prob at {odds}")
    print(f"  Full Kelly: {full*100:.2f}% of bankroll")
    print(f"  Quarter Kelly: {quarter*100:.2f}%")
    print(f"  Third Kelly: {third*100:.2f}%")
    print(f"  Half Kelly: {half*100:.2f}%")
    
    # -------------------------------------------------------------------------
    # Test 2: Comprehensive Bet Sizing
    # -------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("TEST 2: COMPREHENSIVE BET SIZING")
    print("=" * 80)
    
    bet = engine.calculate_bet(0.58, -110, bankroll, "Thunder -3.5")
    
    print(f"\n  Bet: {bet.get('description', 'N/A')}")
    print(f"  Should Bet: {'YES' if bet['should_bet'] else 'NO'}")
    
    if bet['should_bet']:
        print(f"\n  📊 ANALYSIS")
        print(f"     Win Prob: {bet['win_prob']*100:.1f}%")
        print(f"     Implied: {bet['implied_prob']*100:.1f}%")
        print(f"     Edge: {bet['edge_pct']:.1f}%")
        print(f"     EV: {bet['ev_pct']:.1f}%")
        print(f"     Grade: {bet['grade']} ({bet['confidence']})")
        
        print(f"\n  💰 BET SIZING")
        print(f"     Full Kelly: {bet['full_kelly_pct']:.2f}%")
        print(f"     Recommended ({engine.risk_profile}): {bet['recommended_pct']:.2f}%")
        print(f"     Bet Amount: ${bet['recommended_amount']:.2f}")
        print(f"     Units: {bet['recommended_units']:.1f}")
    
    # -------------------------------------------------------------------------
    # Test 3: Simultaneous Bets
    # -------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("TEST 3: SIMULTANEOUS BETS")
    print("=" * 80)
    
    bets = [
        {'win_prob': 0.55, 'american_odds': -110, 'description': 'Celtics -5.5'},
        {'win_prob': 0.58, 'american_odds': -110, 'description': 'Thunder ML'},
        {'win_prob': 0.52, 'american_odds': 100, 'description': 'Over 224.5'},
        {'win_prob': 0.45, 'american_odds': -110, 'description': 'Bad Bet (No Edge)'},
    ]
    
    multi = engine.calculate_simultaneous_bets(bets, bankroll)
    
    print(f"\n  Bets Analyzed: {multi['num_bets']}")
    print(f"  Valid Bets: {multi['valid_bets']}")
    print(f"  Scale Factor: {multi['scale_factor']}")
    print(f"  Total Stake: ${multi['total_stake']:.2f} ({multi['total_stake_pct']:.1f}%)")
    
    print(f"\n  Individual Bets:")
    for b in multi['bets']:
        if b.get('stake', 0) > 0:
            print(f"    {b['description']}: ${b['stake']:.2f} ({b['adjusted_kelly_pct']:.2f}%) - Grade: {b['grade']}")
        else:
            print(f"    {b['description']}: NO BET - {b.get('reason', 'No edge')}")
    
    # -------------------------------------------------------------------------
    # Test 4: Risk of Ruin
    # -------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("TEST 4: RISK OF RUIN ANALYSIS")
    print("=" * 80)
    
    ror = engine.risk_of_ruin(0.55, -110, num_bets=500, ruin_threshold=0.50)
    
    print(f"\n  Scenario: 500 bets at 55% win rate, -110 odds")
    print(f"  Kelly Used: {ror['kelly_used_pct']:.2f}%")
    
    print(f"\n  📉 RISK METRICS")
    print(f"     Risk of 50% Loss: {ror['risk_of_ruin_pct']:.1f}%")
    print(f"     Avg Max Drawdown: {ror['avg_max_drawdown_pct']:.1f}%")
    print(f"     Worst Drawdown (P100): {ror['worst_drawdown_pct']:.1f}%")
    print(f"     P90 Drawdown: {ror['p90_drawdown_pct']:.1f}%")
    
    print(f"\n  📈 OUTCOME METRICS")
    print(f"     Profitable: {ror['profitable_pct']:.1f}%")
    print(f"     Double Up: {ror['double_up_pct']:.1f}%")
    print(f"     Median Final: {ror['median_final_bankroll']:.2f}x")
    print(f"     P90 Final: {ror['p90_final_bankroll']:.2f}x")
    
    # -------------------------------------------------------------------------
    # Test 5: Growth Rate
    # -------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("TEST 5: EXPECTED GROWTH RATE")
    print("=" * 80)
    
    for frac in [0.25, 0.50, 1.00]:
        growth = engine.expected_growth_rate(0.55, -110, frac)
        print(f"\n  {frac*100:.0f}% Kelly:")
        print(f"    Growth per bet: {growth['growth_rate_per_bet_pct']:.4f}%")
        print(f"    Annual growth: {growth['annual_growth_rate_pct']:.1f}%")
        print(f"    Bets to double: {growth['doubling_time_bets']:.0f}")
    
    # -------------------------------------------------------------------------
    # Test 6: Bankroll Projection
    # -------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("TEST 6: BANKROLL PROJECTION")
    print("=" * 80)
    
    projection = engine.project_bankroll(0.55, -110, 10000, num_bets=200)
    
    print(f"\n  Starting: ${projection['starting_bankroll']:,}")
    print(f"  Bets: {projection['num_bets']}")
    print(f"  Kelly: {projection['kelly_used_pct']:.2f}%")
    
    print(f"\n  After {projection['num_bets']} bets:")
    print(f"    P10 (Bad luck): ${projection['final_bankroll']['p10']:,.0f}")
    print(f"    Median: ${projection['final_bankroll']['median']:,.0f}")
    print(f"    P90 (Good luck): ${projection['final_bankroll']['p90']:,.0f}")
    print(f"    Expected ROI: {projection['expected_roi_pct']:.1f}%")
    
    # -------------------------------------------------------------------------
    # Test 7: Unit Size Recommendations
    # -------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("TEST 7: UNIT SIZE RECOMMENDATIONS")
    print("=" * 80)
    
    for risk in ['conservative', 'moderate', 'aggressive']:
        rec = engine.recommend_unit_size(bankroll, risk)
        print(f"\n  {risk.upper()}:")
        print(f"    1 Unit = ${rec['bet_sizes']['1_unit']:.0f}")
        print(f"    Max Bet = ${rec['max_bet_amount']:.0f} ({rec['max_bet_pct']}%)")
    
    # -------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("✅ KELLY CRITERION ENGINE v3.0 - ALL TESTS COMPLETE")
    print("=" * 80)
