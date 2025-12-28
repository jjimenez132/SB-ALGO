"""
Odds Math Calculator
Handles all betting math:
- Implied probability conversion
- Vig removal (no-vig probabilities)
- Closing Line Value (CLV)
- Expected Value (EV) calculations
- Kelly Criterion sizing
- Line movement analysis
"""

import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class OddsMathCalculator:
    """All betting math calculations"""
    
    # =========================================================================
    # ODDS CONVERSION
    # =========================================================================
    
    @staticmethod
    def american_to_decimal(american: float) -> float:
        """Convert American odds to decimal odds"""
        if american > 0:
            return (american / 100) + 1
        else:
            return (100 / abs(american)) + 1
    
    @staticmethod
    def decimal_to_american(decimal: float) -> float:
        """Convert decimal odds to American odds"""
        if decimal >= 2.0:
            return (decimal - 1) * 100
        else:
            return -100 / (decimal - 1)
    
    @staticmethod
    def american_to_implied_prob(american: float) -> float:
        """Convert American odds to implied probability"""
        if american > 0:
            return 100 / (american + 100)
        else:
            return abs(american) / (abs(american) + 100)
    
    @staticmethod
    def implied_prob_to_american(prob: float) -> float:
        """Convert implied probability to American odds"""
        if prob <= 0 or prob >= 1:
            return None
        if prob >= 0.5:
            return -100 * prob / (1 - prob)
        else:
            return 100 * (1 - prob) / prob
    
    # =========================================================================
    # VIG CALCULATIONS
    # =========================================================================
    
    def calculate_vig(self, odds1: float, odds2: float) -> float:
        """
        Calculate the vig/juice percentage for a two-way market
        
        Args:
            odds1, odds2: American odds for each side
        
        Returns:
            Vig as a percentage (e.g., 4.5 for 4.5% vig)
        """
        prob1 = self.american_to_implied_prob(odds1)
        prob2 = self.american_to_implied_prob(odds2)
        return (prob1 + prob2 - 1) * 100
    
    def calculate_no_vig_prob(self, odds1: float, odds2: float) -> Tuple[float, float]:
        """
        Calculate vig-free (true) probabilities for a two-way market
        
        Returns:
            Tuple of (prob1, prob2) that sum to 1.0
        """
        prob1 = self.american_to_implied_prob(odds1)
        prob2 = self.american_to_implied_prob(odds2)
        
        total = prob1 + prob2
        
        return prob1 / total, prob2 / total
    
    def remove_vig_from_odds(self, odds1: float, odds2: float) -> Tuple[float, float]:
        """
        Remove vig and return fair American odds
        
        Returns:
            Tuple of (fair_odds1, fair_odds2)
        """
        no_vig1, no_vig2 = self.calculate_no_vig_prob(odds1, odds2)
        
        fair_odds1 = self.implied_prob_to_american(no_vig1)
        fair_odds2 = self.implied_prob_to_american(no_vig2)
        
        return fair_odds1, fair_odds2
    
    # =========================================================================
    # EXPECTED VALUE
    # =========================================================================
    
    def calculate_ev(self, 
                    true_prob: float, 
                    american_odds: float, 
                    stake: float = 100) -> float:
        """
        Calculate Expected Value of a bet
        
        Args:
            true_prob: Your estimated true probability of winning
            american_odds: The odds you're getting
            stake: Bet size (default 100 for percentage calculation)
        
        Returns:
            EV in dollars (negative = -EV, positive = +EV)
        """
        decimal_odds = self.american_to_decimal(american_odds)
        
        # EV = (prob_win * profit) - (prob_lose * stake)
        profit_if_win = stake * (decimal_odds - 1)
        ev = (true_prob * profit_if_win) - ((1 - true_prob) * stake)
        
        return ev
    
    def calculate_ev_percentage(self, true_prob: float, american_odds: float) -> float:
        """
        Calculate EV as a percentage of stake
        
        Returns:
            EV% (e.g., 5.0 means 5% edge)
        """
        return self.calculate_ev(true_prob, american_odds, 100)
    
    def find_break_even_prob(self, american_odds: float) -> float:
        """Find the probability needed to break even at given odds"""
        return self.american_to_implied_prob(american_odds)
    
    def find_edge(self, true_prob: float, american_odds: float) -> float:
        """
        Calculate edge over the market
        
        Returns:
            Edge as decimal (e.g., 0.05 = 5% edge)
        """
        break_even = self.find_break_even_prob(american_odds)
        return true_prob - break_even
    
    # =========================================================================
    # KELLY CRITERION
    # =========================================================================
    
    def kelly_criterion(self, 
                       true_prob: float, 
                       american_odds: float) -> float:
        """
        Calculate optimal Kelly bet size as fraction of bankroll
        
        Args:
            true_prob: Your estimated true probability
            american_odds: The odds offered
        
        Returns:
            Optimal fraction of bankroll to bet (0 to 1)
            Returns 0 if bet is -EV
        """
        decimal_odds = self.american_to_decimal(american_odds)
        b = decimal_odds - 1  # Net odds (profit per dollar wagered)
        p = true_prob
        q = 1 - p
        
        # Kelly formula: f* = (bp - q) / b
        kelly = (b * p - q) / b
        
        # Never bet negative amounts
        return max(0, kelly)
    
    def fractional_kelly(self, 
                        true_prob: float, 
                        american_odds: float,
                        fraction: float = 0.5) -> float:
        """
        Calculate fractional Kelly bet size
        
        Args:
            fraction: What fraction of Kelly to use (0.5 = half Kelly)
        """
        full_kelly = self.kelly_criterion(true_prob, american_odds)
        return full_kelly * fraction
    
    def kelly_with_edge_threshold(self,
                                  true_prob: float,
                                  american_odds: float,
                                  min_edge: float = 0.03,
                                  max_bet: float = 0.05) -> float:
        """
        Kelly with practical constraints:
        - Minimum edge required
        - Maximum bet size cap
        """
        edge = self.find_edge(true_prob, american_odds)
        
        # Don't bet if edge is below threshold
        if edge < min_edge:
            return 0.0
        
        kelly = self.kelly_criterion(true_prob, american_odds)
        
        # Cap at max bet
        return min(kelly, max_bet)
    
    # =========================================================================
    # CLOSING LINE VALUE (CLV)
    # =========================================================================
    
    def calculate_clv(self, 
                     bet_odds: float, 
                     closing_odds: float) -> float:
        """
        Calculate Closing Line Value
        
        CLV measures how much better your odds were vs the closing line.
        Positive CLV = you beat the market.
        
        Returns:
            CLV in cents (e.g., 5 = 5 cents better)
        """
        # Simple version: difference in implied probability
        bet_prob = self.american_to_implied_prob(bet_odds)
        close_prob = self.american_to_implied_prob(closing_odds)
        
        # Convert to cents (typical measurement)
        clv_prob = close_prob - bet_prob  # Positive = you got better odds
        
        # Express as percentage points
        return clv_prob * 100
    
    def calculate_clv_no_vig(self,
                            bet_odds: float,
                            closing_odds_side1: float,
                            closing_odds_side2: float,
                            bet_on_side1: bool = True) -> float:
        """
        Calculate CLV using no-vig closing line
        
        More accurate measure of true CLV
        """
        bet_prob = self.american_to_implied_prob(bet_odds)
        
        # Get no-vig closing probability
        close_prob1, close_prob2 = self.calculate_no_vig_prob(
            closing_odds_side1, closing_odds_side2
        )
        
        close_prob = close_prob1 if bet_on_side1 else close_prob2
        
        return (close_prob - bet_prob) * 100
    
    # =========================================================================
    # LINE MOVEMENT ANALYSIS
    # =========================================================================
    
    def calculate_line_movement(self,
                               opening_odds: float,
                               current_odds: float) -> Dict:
        """
        Analyze line movement from open to current
        """
        open_prob = self.american_to_implied_prob(opening_odds)
        current_prob = self.american_to_implied_prob(current_odds)
        
        prob_change = current_prob - open_prob
        
        # Determine direction
        if prob_change > 0.01:
            direction = 'steamed'  # Line moved toward this side
        elif prob_change < -0.01:
            direction = 'faded'  # Line moved away from this side
        else:
            direction = 'stable'
        
        return {
            'opening_odds': opening_odds,
            'current_odds': current_odds,
            'opening_implied_prob': open_prob,
            'current_implied_prob': current_prob,
            'prob_change': prob_change,
            'prob_change_pct': prob_change * 100,
            'direction': direction,
            'cents_moved': (current_odds - opening_odds) if opening_odds < 0 else (opening_odds - current_odds),
        }
    
    def detect_sharp_move(self,
                         odds_history: List[Tuple[datetime, float]],
                         threshold_cents: int = 15,
                         time_window_minutes: int = 30) -> bool:
        """
        Detect if there was a sharp move (significant quick movement)
        
        Args:
            odds_history: List of (timestamp, odds) tuples
            threshold_cents: Minimum move to be considered sharp
            time_window_minutes: Time window for the move
        """
        if len(odds_history) < 2:
            return False
        
        # Sort by time
        sorted_history = sorted(odds_history, key=lambda x: x[0])
        
        for i in range(len(sorted_history) - 1):
            time1, odds1 = sorted_history[i]
            
            for j in range(i + 1, len(sorted_history)):
                time2, odds2 = sorted_history[j]
                
                # Check if within time window
                time_diff = (time2 - time1).total_seconds() / 60
                if time_diff > time_window_minutes:
                    break
                
                # Calculate move size
                prob1 = self.american_to_implied_prob(odds1)
                prob2 = self.american_to_implied_prob(odds2)
                move_size = abs(prob2 - prob1) * 100
                
                if move_size >= threshold_cents / 100:
                    return True
        
        return False
    
    # =========================================================================
    # MARKET COMPARISON
    # =========================================================================
    
    def find_best_odds(self, odds_by_book: Dict[str, float]) -> Tuple[str, float]:
        """
        Find the book with best odds
        
        Args:
            odds_by_book: Dict of {bookmaker: american_odds}
        
        Returns:
            (best_book, best_odds)
        """
        if not odds_by_book:
            return None, None
        
        # Convert to implied probs (lower prob = better odds for bettor)
        probs = {book: self.american_to_implied_prob(odds) 
                for book, odds in odds_by_book.items()}
        
        best_book = min(probs, key=probs.get)
        return best_book, odds_by_book[best_book]
    
    def calculate_market_width(self, odds_by_book: Dict[str, float]) -> float:
        """
        Calculate how wide the market is (difference between best and worst odds)
        
        Returns:
            Width in probability percentage points
        """
        if len(odds_by_book) < 2:
            return 0.0
        
        probs = [self.american_to_implied_prob(o) for o in odds_by_book.values()]
        return (max(probs) - min(probs)) * 100
    
    def identify_soft_line(self,
                          odds_by_book: Dict[str, float],
                          threshold_cents: float = 2.0) -> List[Tuple[str, float, float]]:
        """
        Identify books with soft lines (significantly off market)
        
        Returns:
            List of (book, odds, deviation_from_median) for soft lines
        """
        if len(odds_by_book) < 3:
            return []
        
        probs = {book: self.american_to_implied_prob(odds) 
                for book, odds in odds_by_book.items()}
        
        median_prob = np.median(list(probs.values()))
        
        soft_lines = []
        for book, prob in probs.items():
            deviation = (prob - median_prob) * 100  # In percentage points
            if abs(deviation) >= threshold_cents:
                soft_lines.append((book, odds_by_book[book], deviation))
        
        return soft_lines
    
    # =========================================================================
    # PARLAY / COMBO MATH
    # =========================================================================
    
    def calculate_parlay_odds(self, american_odds_list: List[float]) -> float:
        """
        Calculate parlay payout odds from individual leg odds
        
        Returns:
            Combined American odds
        """
        # Convert to decimal, multiply, convert back
        combined_decimal = 1.0
        for odds in american_odds_list:
            combined_decimal *= self.american_to_decimal(odds)
        
        return self.decimal_to_american(combined_decimal)
    
    def calculate_parlay_ev(self,
                           true_probs: List[float],
                           american_odds_list: List[float]) -> float:
        """
        Calculate EV of a parlay bet
        
        Args:
            true_probs: List of true probabilities for each leg
            american_odds_list: List of odds for each leg
        """
        # True joint probability (assuming independence - adjust if correlated)
        true_joint_prob = np.prod(true_probs)
        
        # Parlay odds
        parlay_odds = self.calculate_parlay_odds(american_odds_list)
        
        return self.calculate_ev(true_joint_prob, parlay_odds)
    
    def calculate_correlated_parlay_ev(self,
                                       marginal_probs: List[float],
                                       correlation_adjustment: float,
                                       american_odds_list: List[float]) -> float:
        """
        Calculate EV accounting for correlation between legs
        
        Args:
            marginal_probs: Individual probabilities
            correlation_adjustment: Multiplier for joint probability
                                   >1 = positive correlation
                                   <1 = negative correlation
        """
        # Adjust joint probability for correlation
        independent_joint = np.prod(marginal_probs)
        correlated_joint = independent_joint * correlation_adjustment
        
        # Cap at realistic values
        correlated_joint = min(correlated_joint, min(marginal_probs))
        correlated_joint = max(correlated_joint, 0.001)
        
        parlay_odds = self.calculate_parlay_odds(american_odds_list)
        
        return self.calculate_ev(correlated_joint, parlay_odds)


# Convenience functions
def quick_ev(true_prob: float, american_odds: float) -> float:
    """Quick EV calculation"""
    calc = OddsMathCalculator()
    return calc.calculate_ev_percentage(true_prob, american_odds)


def quick_kelly(true_prob: float, american_odds: float, fraction: float = 0.5) -> float:
    """Quick Kelly calculation"""
    calc = OddsMathCalculator()
    return calc.fractional_kelly(true_prob, american_odds, fraction)


if __name__ == "__main__":
    print("\n🧪 Testing Odds Math Calculator")
    print("=" * 50)
    
    calc = OddsMathCalculator()
    
    # Test odds conversion
    print("\n📊 Odds Conversion Tests:")
    test_odds = [-110, -150, +150, -200, +200]
    for odds in test_odds:
        decimal = calc.american_to_decimal(odds)
        prob = calc.american_to_implied_prob(odds)
        print(f"  {odds:+d} → Decimal: {decimal:.3f}, Implied: {prob:.1%}")
    
    # Test vig calculation
    print("\n💰 Vig Calculations:")
    markets = [
        (-110, -110),  # Standard
        (-105, -115),  # Slight shade
        (-120, +100),  # Significant shade
    ]
    for odds1, odds2 in markets:
        vig = calc.calculate_vig(odds1, odds2)
        nv1, nv2 = calc.calculate_no_vig_prob(odds1, odds2)
        print(f"  {odds1:+d}/{odds2:+d}: Vig={vig:.1f}%, No-vig probs: {nv1:.1%}/{nv2:.1%}")
    
    # Test EV calculation
    print("\n📈 EV Calculations:")
    scenarios = [
        (0.55, -110, "55% at -110"),
        (0.52, -110, "52% at -110"),
        (0.40, +150, "40% at +150"),
        (0.60, -150, "60% at -150"),
    ]
    for prob, odds, desc in scenarios:
        ev = calc.calculate_ev_percentage(prob, odds)
        edge = calc.find_edge(prob, odds) * 100
        print(f"  {desc}: EV={ev:+.2f}%, Edge={edge:+.1f}%")
    
    # Test Kelly
    print("\n🎰 Kelly Criterion:")
    for prob, odds, desc in scenarios:
        kelly = calc.kelly_criterion(prob, odds)
        half_kelly = calc.fractional_kelly(prob, odds, 0.5)
        print(f"  {desc}: Full Kelly={kelly:.1%}, Half Kelly={half_kelly:.1%}")
    
    # Test CLV
    print("\n📉 CLV Calculations:")
    clv_scenarios = [
        (-110, -105, "Bet -110, closed -105"),
        (-110, -115, "Bet -110, closed -115"),
        (+150, +140, "Bet +150, closed +140"),
    ]
    for bet_odds, close_odds, desc in clv_scenarios:
        clv = calc.calculate_clv(bet_odds, close_odds)
        print(f"  {desc}: CLV={clv:+.1f} cents")
    
    # Test soft line detection
    print("\n🎯 Soft Line Detection:")
    test_market = {
        'fanduel': -112,
        'draftkings': -110,
        'betmgm': -108,
        'caesars': -115,
        'pinnacle': -105,  # This is soft (sharp book at different price)
    }
    soft = calc.identify_soft_line(test_market, threshold_cents=2.0)
    print(f"  Market: {test_market}")
    print(f"  Soft lines: {soft}")
    
    # Test parlay math
    print("\n🎲 Parlay Math:")
    legs = [-110, -110, -110]
    parlay_odds = calc.calculate_parlay_odds(legs)
    print(f"  3-leg parlay at -110 each: {parlay_odds:+.0f}")
    
    true_probs = [0.55, 0.55, 0.55]
    parlay_ev = calc.calculate_parlay_ev(true_probs, legs)
    print(f"  EV if each leg is 55% true: ${parlay_ev:+.2f} per $100")
