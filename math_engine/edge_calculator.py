#!/usr/bin/env python3
"""
Edge Calculator Engine
Calculates expected value and true edge for bets
"""

class EdgeCalculator:
    """
    Calculates betting edges including:
    - Implied probability from odds
    - Expected value (EV)
    - Kelly criterion sizing
    """
    
    def american_to_decimal(self, american_odds):
        """Convert American odds to decimal"""
        if american_odds is None:
            return None
        if american_odds >= 100:
            return (american_odds / 100) + 1
        else:
            return (100 / abs(american_odds)) + 1
    
    def american_to_implied_prob(self, american_odds):
        """Convert American odds to implied probability"""
        if american_odds is None:
            return None
        if american_odds >= 100:
            return 100 / (american_odds + 100)
        else:
            return abs(american_odds) / (abs(american_odds) + 100)
    
    def remove_vig(self, over_odds, under_odds):
        """Remove vig to get fair probabilities"""
        if over_odds is None or under_odds is None:
            return None, None, None
        
        over_implied = self.american_to_implied_prob(over_odds)
        under_implied = self.american_to_implied_prob(under_odds)
        total_implied = over_implied + under_implied
        vig = total_implied - 1
        
        fair_over = over_implied / total_implied
        fair_under = under_implied / total_implied
        
        return round(fair_over, 4), round(fair_under, 4), round(vig, 4)
    
    def calculate_ev(self, win_probability, decimal_odds, stake=100):
        """Calculate Expected Value"""
        if win_probability is None or decimal_odds is None:
            return None
        
        win_amount = stake * (decimal_odds - 1)
        lose_prob = 1 - win_probability
        ev_dollars = (win_probability * win_amount) - (lose_prob * stake)
        ev_percentage = (ev_dollars / stake) * 100
        
        return {
            'ev_dollars': round(ev_dollars, 2),
            'ev_percentage': round(ev_percentage, 2)
        }
    
    def calculate_edge(self, true_probability, implied_probability):
        """Calculate edge as difference between true and implied probability"""
        if true_probability is None or implied_probability is None:
            return None
        return round((true_probability - implied_probability) * 100, 2)
    
    def kelly_criterion(self, win_probability, decimal_odds, fraction=0.25):
        """Calculate Kelly Criterion bet size"""
        if win_probability is None or decimal_odds is None:
            return None
        if win_probability <= 0 or win_probability >= 1:
            return 0
        
        b = decimal_odds - 1
        p = win_probability
        q = 1 - p
        kelly = (b * p - q) / b
        kelly_fractional = kelly * fraction
        
        return round(max(0, min(kelly_fractional, 0.10)), 4)
    
    def calculate_units(self, ev_percentage, confidence, max_units=3):
        """Calculate recommended units based on EV and confidence"""
        if ev_percentage is None or ev_percentage <= 0:
            return 0
        
        if ev_percentage >= 10:
            base_units = 2.0
        elif ev_percentage >= 7:
            base_units = 1.5
        elif ev_percentage >= 4:
            base_units = 1.0
        elif ev_percentage >= 2:
            base_units = 0.5
        else:
            base_units = 0
        
        if confidence >= 85:
            multiplier = 1.25
        elif confidence >= 75:
            multiplier = 1.0
        elif confidence >= 65:
            multiplier = 0.75
        else:
            multiplier = 0.5
        
        return min(round(base_units * multiplier, 1), max_units)
    
    def analyze_bet(self, true_probability, american_odds, confidence=75):
        """Complete bet analysis"""
        decimal_odds = self.american_to_decimal(american_odds)
        implied_prob = self.american_to_implied_prob(american_odds)
        edge = self.calculate_edge(true_probability, implied_prob)
        ev = self.calculate_ev(true_probability, decimal_odds)
        kelly = self.kelly_criterion(true_probability, decimal_odds)
        units = self.calculate_units(ev['ev_percentage'] if ev else 0, confidence)
        
        is_value = edge and edge > 0 and ev and ev['ev_percentage'] > 2
        
        if edge >= 10 and confidence >= 80:
            rating = "A+"
        elif edge >= 7 and confidence >= 75:
            rating = "A"
        elif edge >= 5 and confidence >= 70:
            rating = "B+"
        elif edge >= 3 and confidence >= 65:
            rating = "B"
        else:
            rating = "C"
        
        return {
            'edge_percentage': edge,
            'ev_percentage': ev['ev_percentage'] if ev else 0,
            'kelly_percentage': round(kelly * 100, 2) if kelly else 0,
            'recommended_units': units,
            'is_value_bet': is_value,
            'rating': rating
        }
