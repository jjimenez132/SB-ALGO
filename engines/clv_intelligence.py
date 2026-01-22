#!/usr/bin/env python3
"""
================================================================================
CLV INTELLIGENCE MODULE v1.0
================================================================================
Connects CLV historical data to pick selection and confidence scoring.

WHAT IT DOES:
- Loads your historical CLV by market type
- Provides confidence boosts/penalties based on proven edge
- Adjusts edge thresholds dynamically
- Helps the algo focus on markets where YOU are sharp

================================================================================
"""

from sqlalchemy import create_engine, text
from typing import Dict, Optional
from datetime import datetime, timedelta

DATABASE_URL = "postgresql://sb_algo_db_user:0HDtYp4EY2Lo5At8iyf44PD1zDioSPK7@dpg-d495uhchg0os738l1a50-a.virginia-postgres.render.com/sb_algo_db"

# CLV Thresholds for confidence adjustments
CLV_BOOST_THRESHOLDS = {
    'elite': 5.0,      # +5 cents = +15% confidence boost
    'sharp': 3.0,      # +3 cents = +10% confidence boost  
    'good': 1.0,       # +1 cent = +5% confidence boost
    'neutral': 0.0,    # 0 cents = no adjustment
    'square': -2.0,    # -2 cents = -10% confidence penalty
    'avoid': -5.0,     # -5 cents = -20% confidence penalty
}

# Minimum sample size to trust CLV data
MIN_CLV_SAMPLES = 3


class CLVIntelligence:
    """
    Provides CLV-based adjustments to pick confidence and edge thresholds.
    """
    
    def __init__(self):
        self.engine = create_engine(DATABASE_URL)
        self._clv_cache = {}
        self._last_refresh = None
        self._refresh_clv_data()
    
    def _refresh_clv_data(self):
        """Load CLV stats by market from database"""
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text("""
                    SELECT 
                        CASE 
                            WHEN pick_name LIKE '%PTS%' THEN 'pts'
                            WHEN pick_name LIKE '%REB%' THEN 'reb'
                            WHEN pick_name LIKE '%AST%' THEN 'ast'
                            WHEN pick_name LIKE '%3PT%' OR pick_name LIKE '%THREE%' THEN '3pt'
                            WHEN pick_name LIKE '%STL%' THEN 'stl'
                            WHEN pick_name LIKE '%BLK%' THEN 'blk'
                            WHEN pick_name LIKE '%PRA%' THEN 'pra'
                            WHEN pick_name LIKE '%UNDER%' AND pick_type = 'game' THEN 'game_total'
                            WHEN pick_name LIKE '%OVER%' AND pick_type = 'game' THEN 'game_total'
                            WHEN pick_name LIKE '% -' OR pick_name LIKE '% +' THEN 'spread'
                            ELSE 'other'
                        END as market,
                        COUNT(*) as sample_size,
                        ROUND(AVG(clv_cents)::numeric, 2) as avg_clv,
                        ROUND(STDDEV(clv_cents)::numeric, 2) as clv_std,
                        COUNT(CASE WHEN status = 'win' THEN 1 END) as wins,
                        COUNT(CASE WHEN status = 'loss' THEN 1 END) as losses,
                        ROUND(AVG(CASE WHEN status = 'win' THEN clv_cents END)::numeric, 2) as win_clv,
                        ROUND(AVG(CASE WHEN status = 'loss' THEN clv_cents END)::numeric, 2) as loss_clv
                    FROM algo_picks_tracking
                    WHERE clv_cents IS NOT NULL
                    GROUP BY 1
                    HAVING COUNT(*) >= 1
                """)).fetchall()
                
                self._clv_cache = {}
                for r in result:
                    market = r[0]
                    self._clv_cache[market] = {
                        'sample_size': r[1],
                        'avg_clv': float(r[2]) if r[2] else 0,
                        'clv_std': float(r[3]) if r[3] else 0,
                        'wins': r[4],
                        'losses': r[5],
                        'win_rate': r[4] / (r[4] + r[5]) if (r[4] + r[5]) > 0 else 0,
                        'win_clv': float(r[6]) if r[6] else 0,
                        'loss_clv': float(r[7]) if r[7] else 0,
                    }
                
                self._last_refresh = datetime.now()
                print(f"✅ CLV Intelligence loaded: {len(self._clv_cache)} markets")
                
        except Exception as e:
            print(f"⚠️ CLV Intelligence load error: {e}")
            self._clv_cache = {}
    
    def get_market_clv_stats(self, stat: str) -> Dict:
        """
        Get CLV stats for a specific market/stat type.
        
        Args:
            stat: Stat type (pts, reb, ast, etc.) or 'game_total', 'spread'
        
        Returns:
            Dict with CLV stats for that market
        """
        # Refresh if stale (>1 hour)
        if self._last_refresh and (datetime.now() - self._last_refresh).seconds > 3600:
            self._refresh_clv_data()
        
        stat_lower = stat.lower()
        return self._clv_cache.get(stat_lower, {
            'sample_size': 0,
            'avg_clv': 0,
            'clv_std': 0,
            'wins': 0,
            'losses': 0,
            'win_rate': 0,
        })
    
    def get_confidence_adjustment(self, stat: str) -> Dict:
        """
        Get confidence adjustment based on historical CLV.
        
        Returns:
            {
                'multiplier': 1.15,  # Multiply confidence by this
                'reason': 'Sharp on AST (+7.3 cents CLV)',
                'clv_rating': 'ELITE'
            }
        """
        stats = self.get_market_clv_stats(stat)
        avg_clv = stats.get('avg_clv', 0)
        sample = stats.get('sample_size', 0)
        
        # Not enough data - no adjustment
        if sample < MIN_CLV_SAMPLES:
            return {
                'multiplier': 1.0,
                'edge_adjustment': 0,
                'reason': f'Insufficient CLV data ({sample} samples)',
                'clv_rating': 'UNKNOWN',
                'should_boost': False,
                'should_penalize': False,
            }
        
        # Determine adjustment based on CLV
        if avg_clv >= CLV_BOOST_THRESHOLDS['elite']:
            multiplier = 1.15
            edge_adj = -5  # Lower edge threshold (easier to qualify)
            rating = 'ELITE'
            reason = f'🔥 ELITE CLV: +{avg_clv:.1f} cents ({sample} picks)'
        elif avg_clv >= CLV_BOOST_THRESHOLDS['sharp']:
            multiplier = 1.10
            edge_adj = -3
            rating = 'SHARP'
            reason = f'✅ Sharp market: +{avg_clv:.1f} cents CLV'
        elif avg_clv >= CLV_BOOST_THRESHOLDS['good']:
            multiplier = 1.05
            edge_adj = -2
            rating = 'GOOD'
            reason = f'👍 Positive CLV: +{avg_clv:.1f} cents'
        elif avg_clv >= CLV_BOOST_THRESHOLDS['neutral']:
            multiplier = 1.0
            edge_adj = 0
            rating = 'NEUTRAL'
            reason = f'Neutral CLV: {avg_clv:.1f} cents'
        elif avg_clv >= CLV_BOOST_THRESHOLDS['square']:
            multiplier = 0.90
            edge_adj = 3  # Raise edge threshold (harder to qualify)
            rating = 'SQUARE'
            reason = f'⚠️ Negative CLV: {avg_clv:.1f} cents - raising bar'
        else:
            multiplier = 0.80
            edge_adj = 5
            rating = 'AVOID'
            reason = f'🚫 Poor CLV: {avg_clv:.1f} cents - consider avoiding'
        
        return {
            'multiplier': multiplier,
            'edge_adjustment': edge_adj,
            'reason': reason,
            'clv_rating': rating,
            'avg_clv': avg_clv,
            'sample_size': sample,
            'win_rate': stats.get('win_rate', 0),
            'should_boost': multiplier > 1.0,
            'should_penalize': multiplier < 1.0,
        }
    
    def adjust_prop_confidence(self, stat: str, base_confidence: float) -> Dict:
        """
        Adjust prop confidence based on CLV history.
        
        Args:
            stat: Stat type (pts, reb, ast)
            base_confidence: Original confidence (0-1)
        
        Returns:
            Adjusted confidence and explanation
        """
        adj = self.get_confidence_adjustment(stat)
        adjusted = min(0.95, base_confidence * adj['multiplier'])
        
        return {
            'original_confidence': base_confidence,
            'adjusted_confidence': round(adjusted, 4),
            'clv_multiplier': adj['multiplier'],
            'clv_rating': adj['clv_rating'],
            'clv_reason': adj['reason'],
        }
    
    def should_bet_market(self, stat: str, edge_pct: float, base_threshold: float) -> Dict:
        """
        Determine if we should bet this market with CLV-adjusted thresholds.
        
        Args:
            stat: Stat type
            edge_pct: Calculated edge percentage
            base_threshold: Normal edge threshold for this market
        
        Returns:
            Whether to bet and why
        """
        adj = self.get_confidence_adjustment(stat)
        adjusted_threshold = base_threshold + adj['edge_adjustment']
        
        passes = abs(edge_pct) >= adjusted_threshold
        
        return {
            'should_bet': passes,
            'base_threshold': base_threshold,
            'adjusted_threshold': adjusted_threshold,
            'edge_pct': edge_pct,
            'clv_adjustment': adj['edge_adjustment'],
            'clv_rating': adj['clv_rating'],
            'reason': adj['reason'],
        }
    
    def get_market_rankings(self) -> list:
        """Get all markets ranked by CLV (best to worst)"""
        rankings = []
        for market, stats in self._clv_cache.items():
            rankings.append({
                'market': market,
                'avg_clv': stats['avg_clv'],
                'sample_size': stats['sample_size'],
                'win_rate': stats['win_rate'],
                'wins': stats['wins'],
                'losses': stats['losses'],
            })
        
        return sorted(rankings, key=lambda x: x['avg_clv'], reverse=True)
    
    def print_clv_report(self):
        """Print CLV intelligence report"""
        print("\n" + "=" * 60)
        print("📊 CLV INTELLIGENCE REPORT")
        print("=" * 60)
        
        rankings = self.get_market_rankings()
        
        print(f"\n{'Market':<15} {'CLV':>10} {'W-L':>10} {'Win%':>8} {'Rating':<10}")
        print("-" * 60)
        
        for r in rankings:
            clv = r['avg_clv']
            if clv >= 5:
                rating = "🔥 ELITE"
            elif clv >= 3:
                rating = "✅ SHARP"
            elif clv >= 1:
                rating = "👍 GOOD"
            elif clv >= 0:
                rating = "➖ NEUTRAL"
            elif clv >= -2:
                rating = "⚠️ SQUARE"
            else:
                rating = "🚫 AVOID"
            
            win_pct = r['win_rate'] * 100
            print(f"{r['market']:<15} {clv:>+8.2f}c  {r['wins']}-{r['losses']:>6} {win_pct:>6.1f}%  {rating}")
        
        print("=" * 60)


# Singleton instance
_clv_intel = None

def get_clv_intelligence() -> CLVIntelligence:
    """Get or create CLV Intelligence singleton"""
    global _clv_intel
    if _clv_intel is None:
        _clv_intel = CLVIntelligence()
    return _clv_intel


# =============================================================================
# TEST
# =============================================================================
if __name__ == "__main__":
    intel = get_clv_intelligence()
    intel.print_clv_report()
    
    print("\n" + "=" * 60)
    print("CONFIDENCE ADJUSTMENTS BY MARKET")
    print("=" * 60)
    
    for stat in ['ast', 'reb', 'pts', 'game_total']:
        adj = intel.get_confidence_adjustment(stat)
        print(f"\n{stat.upper()}:")
        print(f"  Rating: {adj['clv_rating']}")
        print(f"  Confidence multiplier: {adj['multiplier']}x")
        print(f"  Edge threshold adjust: {adj['edge_adjustment']:+d}%")
        print(f"  Reason: {adj['reason']}")
