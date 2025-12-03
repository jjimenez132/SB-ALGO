#!/usr/bin/env python3
"""
Confidence Engine
Calculates overall confidence scores for picks
"""

from sqlalchemy import create_engine, text
import os

DATABASE_URL = os.environ.get('DATABASE_URL',
    "postgresql://sb_algo_db_user:0HDtYp4EY2Lo5At8iyf44PD1zDioSPK7@dpg-d495uhchg0os738l1a50-a.virginia-postgres.render.com/sb_algo_db?sslmode=require")


class ConfidenceEngine:
    """
    Calculates confidence scores based on:
    - Sample size
    - Consistency
    - Edge size
    - Market agreement
    - Trend alignment
    - Matchup factors
    """
    
    def __init__(self, engine=None):
        self.engine = engine or create_engine(DATABASE_URL)
        
        # Weight factors for confidence calculation
        self.WEIGHTS = {
            'sample_size': 0.15,
            'consistency': 0.20,
            'edge_size': 0.25,
            'market_agreement': 0.15,
            'trend': 0.15,
            'matchup': 0.10
        }
    
    def calculate_sample_confidence(self, games_played):
        """Confidence from sample size"""
        if games_played >= 20:
            return 100
        elif games_played >= 15:
            return 85
        elif games_played >= 10:
            return 70
        elif games_played >= 5:
            return 55
        else:
            return 40
    
    def calculate_consistency_confidence(self, cv):
        """
        Confidence from consistency (coefficient of variation)
        Lower CV = more consistent = higher confidence
        """
        if cv is None:
            return 50
        
        if cv <= 0.15:
            return 100
        elif cv <= 0.25:
            return 85
        elif cv <= 0.35:
            return 70
        elif cv <= 0.50:
            return 55
        else:
            return 40
    
    def calculate_edge_confidence(self, edge, threshold):
        """Confidence from edge size relative to threshold"""
        if edge is None or threshold is None or threshold == 0:
            return 50
        
        ratio = abs(edge) / threshold
        
        if ratio >= 3.0:
            return 100
        elif ratio >= 2.0:
            return 85
        elif ratio >= 1.5:
            return 70
        elif ratio >= 1.0:
            return 55
        else:
            return 40
    
    def calculate_market_confidence(self, spread, num_books):
        """
        Confidence from market agreement
        Lower spread + more books = higher confidence
        """
        # Books factor
        if num_books >= 8:
            books_score = 100
        elif num_books >= 6:
            books_score = 85
        elif num_books >= 4:
            books_score = 70
        else:
            books_score = 55
        
        # Spread factor (lower spread = more agreement)
        if spread <= 0.5:
            spread_score = 100
        elif spread <= 1.0:
            spread_score = 85
        elif spread <= 2.0:
            spread_score = 70
        elif spread <= 3.0:
            spread_score = 55
        else:
            spread_score = 40
        
        return (books_score + spread_score) / 2
    
    def calculate_trend_confidence(self, hit_rate_l5, trend_direction):
        """Confidence from trends"""
        score = 50
        
        if hit_rate_l5 is not None:
            if hit_rate_l5 >= 0.80:
                score += 25
            elif hit_rate_l5 >= 0.60:
                score += 15
            elif hit_rate_l5 <= 0.20:
                score -= 20
            elif hit_rate_l5 <= 0.40:
                score -= 10
        
        if trend_direction in ['STRONG_UP', 'STRONG_DOWN']:
            score += 15
        elif trend_direction in ['UP', 'DOWN']:
            score += 5
        
        return min(100, max(0, score))
    
    def calculate_matchup_confidence(self, rest_advantage, pace_factor, vs_team_history):
        """Confidence from matchup factors"""
        score = 50
        
        # Rest advantage
        if rest_advantage and rest_advantage >= 2:
            score += 15
        elif rest_advantage and rest_advantage <= -2:
            score -= 15
        
        # Pace alignment (high pace = more stats)
        if pace_factor and pace_factor > 0.03:
            score += 10
        
        # Historical vs team
        if vs_team_history and vs_team_history.get('games', 0) >= 3:
            score += 10
        
        return min(100, max(0, score))
    
    def calculate_overall_confidence(self, factors):
        """
        Calculate weighted overall confidence
        
        Args:
            factors: dict with keys matching self.WEIGHTS
        
        Returns:
            Overall confidence score (0-100)
        """
        total_score = 0
        total_weight = 0
        
        for factor, weight in self.WEIGHTS.items():
            if factor in factors and factors[factor] is not None:
                total_score += factors[factor] * weight
                total_weight += weight
        
        if total_weight == 0:
            return 50
        
        raw_confidence = total_score / total_weight
        
        # Apply bounds
        return int(min(95, max(50, raw_confidence)))
    
    def get_confidence_breakdown(self, factors):
        """Get detailed breakdown of confidence score"""
        breakdown = {}
        
        for factor, weight in self.WEIGHTS.items():
            if factor in factors and factors[factor] is not None:
                contribution = factors[factor] * weight
                breakdown[factor] = {
                    'score': factors[factor],
                    'weight': weight,
                    'contribution': round(contribution, 1)
                }
        
        overall = self.calculate_overall_confidence(factors)
        
        return {
            'overall': overall,
            'breakdown': breakdown,
            'rating': self._get_rating(overall)
        }
    
    def _get_rating(self, confidence):
        """Convert confidence to letter rating"""
        if confidence >= 85:
            return 'A'
        elif confidence >= 75:
            return 'B+'
        elif confidence >= 65:
            return 'B'
        elif confidence >= 55:
            return 'C'
        else:
            return 'D'
    
    def quick_confidence(self, edge, games_played, hit_rate_l5, spread):
        """Quick confidence calculation with minimal inputs"""
        factors = {
            'sample_size': self.calculate_sample_confidence(games_played),
            'edge_size': self.calculate_edge_confidence(edge, 1.5),
            'market_agreement': self.calculate_market_confidence(spread, 7),
            'trend': self.calculate_trend_confidence(hit_rate_l5, None)
        }
        
        return self.calculate_overall_confidence(factors)


if __name__ == "__main__":
    engine = ConfidenceEngine()
    
    print("Confidence Engine Test")
    print("=" * 50)
    
    # Test case
    factors = {
        'sample_size': engine.calculate_sample_confidence(15),
        'consistency': engine.calculate_consistency_confidence(0.25),
        'edge_size': engine.calculate_edge_confidence(2.5, 1.5),
        'market_agreement': engine.calculate_market_confidence(1.5, 8),
        'trend': engine.calculate_trend_confidence(0.80, 'UP'),
        'matchup': engine.calculate_matchup_confidence(2, 0.05, {'games': 3})
    }
    
    breakdown = engine.get_confidence_breakdown(factors)
    
    print(f"\nOverall Confidence: {breakdown['overall']}%")
    print(f"Rating: {breakdown['rating']}")
    print("\nBreakdown:")
    for factor, data in breakdown['breakdown'].items():
        print(f"  {factor}: {data['score']} (weight: {data['weight']}, contribution: {data['contribution']})")
