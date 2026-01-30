#!/usr/bin/env python3
"""
================================================================================
POISSON ENGINE v1.0 - Discrete Event Modeling
================================================================================
Uses Poisson distribution to model player stat lines and game totals.

Mathematical Framework:
- λ (lambda) = expected rate of occurrence
- P(X = k) = (e^(-λ) × λ^k) / k!
- P(X > line) = 1 - CDF(line)  [for OVER bets]
- P(X < line) = CDF(line - 1)  [for UNDER bets]

Key advantage over Normal distribution:
- Poisson is discrete (stats are integers)
- Better models low-count events (assists, rebounds)
- Natural handling of 0 outcomes

================================================================================
"""

import numpy as np
from scipy.stats import poisson, nbinom
from scipy.special import factorial
from sqlalchemy import create_engine, text
from typing import Dict, Optional, Tuple
import os

DATABASE_URL = os.environ.get('DATABASE_URL',
    "postgresql://sb_algo_db_user:0HDtYp4EY2Lo5At8iyf44PD1zDioSPK7@dpg-d495uhchg0os738l1a50-a.virginia-postgres.render.com/sb_algo_db")


class PoissonEngine:
    """
    Poisson-based probability engine for player props and game totals.
    
    For player stats, we use Negative Binomial when variance > mean (overdispersion),
    otherwise standard Poisson.
    """
    
    def __init__(self):
        self.engine = create_engine(DATABASE_URL)
        self._cache = {}
        
        # League average defensive ratings (1.0 = average)
        self.league_avg_def = {
            'pts': 1.0,
            'reb': 1.0,
            'ast': 1.0,
            '3pm': 1.0,
        }
    
    # =========================================================================
    # LAMBDA CALCULATION
    # =========================================================================
    
    def calculate_player_lambda(self, player_name: str, stat: str, 
                                 opponent: str = None,
                                 minutes_factor: float = 1.0) -> Dict:
        """
        Calculate λ (expected value) for a player's stat.
        
        λ = base_rate × opp_defense_factor × minutes_factor
        
        Args:
            player_name: Player name
            stat: Stat type (pts, reb, ast, 3pm)
            opponent: Opponent team abbreviation (for defense adjustment)
            minutes_factor: Minutes adjustment (1.0 = expected minutes)
            
        Returns:
            Dictionary with lambda and variance info
        """
        # Get player's historical stats
        games = self._get_player_game_log(player_name, stat, n_games=15)
        
        if not games or len(games) < 5:
            return None
        
        # Calculate mean and variance
        values = [g[stat] for g in games if g[stat] is not None]
        if not values:
            return None
            
        mean_val = np.mean(values)
        var_val = np.var(values, ddof=1) if len(values) > 1 else mean_val
        
        # L5, L10, L15 weighted average (recency weighted)
        l5 = np.mean(values[:5]) if len(values) >= 5 else mean_val
        l10 = np.mean(values[:10]) if len(values) >= 10 else mean_val
        l15 = np.mean(values[:15]) if len(values) >= 15 else mean_val
        
        # Weighted: 50% L5, 30% L10, 20% L15
        weighted_mean = 0.50 * l5 + 0.30 * l10 + 0.20 * l15
        
        # Base lambda
        base_lambda = weighted_mean
        
        # Opponent defense adjustment
        opp_factor = 1.0
        if opponent:
            opp_factor = self._get_opponent_defense_factor(opponent, stat)
        
        # Apply adjustments
        adjusted_lambda = base_lambda * opp_factor * minutes_factor
        
        # Check for overdispersion (variance > mean)
        # If overdispersed, use Negative Binomial
        is_overdispersed = var_val > mean_val * 1.2  # 20% threshold
        
        return {
            'player': player_name,
            'stat': stat,
            'base_lambda': round(base_lambda, 2),
            'adjusted_lambda': round(adjusted_lambda, 2),
            'variance': round(var_val, 2),
            'opp_factor': round(opp_factor, 3),
            'minutes_factor': round(minutes_factor, 3),
            'is_overdispersed': is_overdispersed,
            'l5': round(l5, 2),
            'l10': round(l10, 2),
            'l15': round(l15, 2),
            'games_used': len(values),
        }
    
    def _get_player_game_log(self, player_name: str, stat: str, n_games: int = 15) -> list:
        """Get player's last N games with specified stat"""
        cache_key = f"gamelog_{player_name}_{stat}_{n_games}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        stat_col = {'pts': 'pts', 'reb': 'reb', 'ast': 'ast', '3pm': 'fg3m'}.get(stat, stat)
        
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text(f"""
                    SELECT game_date, {stat_col} as stat_val, min as minutes
                    FROM player_boxscores 
                    WHERE player_name ILIKE :player
                    AND {stat_col} IS NOT NULL
                    ORDER BY game_date DESC 
                    LIMIT :n
                """), {'player': f'%{player_name}%', 'n': n_games}).fetchall()
                
                games = [{stat: row[1], 'minutes': row[2]} for row in result]
                self._cache[cache_key] = games
                return games
        except Exception as e:
            print(f"   ⚠️ Poisson gamelog error: {e}")
            return []
    
    def _get_opponent_defense_factor(self, opponent: str, stat: str) -> float:
        """
        Get opponent's defense factor for a stat.
        
        > 1.0 = bad defense (allows more)
        < 1.0 = good defense (allows less)
        """
        cache_key = f"opp_def_{opponent}_{stat}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        # Map stat to defensive column and league average per-game
        # OPP_PTS etc are ALREADY per-game values, don't divide by GP
        stat_map = {
            'pts': ('OPP_PTS', 114.0),    # League avg ~114 PPG allowed
            'reb': ('OPP_REB', 44.0),     # League avg ~44 RPG allowed
            'ast': ('OPP_AST', 26.0),     # League avg ~26 APG allowed
            '3pm': ('OPP_FG3M', 13.0),    # League avg ~13 3PM allowed
        }
        
        col, league_avg = stat_map.get(stat, ('OPP_PTS', 114.0))
        
        try:
            with self.engine.connect() as conn:
                # OPP_PTS is already per-game, don't divide by GP
                result = conn.execute(text(f"""
                    SELECT "{col}"
                    FROM nba_team_opponent_stats 
                    WHERE "TEAM_NAME" ILIKE :team
                    ORDER BY pull_date DESC LIMIT 1
                """), {'team': f'%{opponent}%'}).fetchone()
                
                if result and result[0]:
                    opp_allowed_pg = float(result[0])
                    factor = opp_allowed_pg / league_avg
                    self._cache[cache_key] = factor
                    return factor
        except:
            pass
        
        return 1.0
    
    # =========================================================================
    # HIT PROBABILITY CALCULATION
    # =========================================================================
    
    def hit_probability(self, lambda_val: float, line: float, side: str,
                        variance: float = None) -> float:
        """
        Calculate probability of hitting the line.
        
        For OVER: P(X > line) = 1 - P(X <= floor(line))
        For UNDER: P(X < line) = P(X <= floor(line) - 1)
        
        Note: We use floor(line) because stats are discrete integers.
        If line is 24.5, we need X >= 25 for OVER.
        """
        if lambda_val <= 0:
            return 0.5
        
        # Determine if we should use Negative Binomial (overdispersed)
        use_nbinom = variance and variance > lambda_val * 1.2
        
        # Convert line to integer threshold
        line_int = int(np.floor(line))
        
        if use_nbinom:
            # Negative Binomial parameterization
            # mean = mu, variance = mu + mu^2/size
            # Solving for size: size = mu^2 / (variance - mu)
            if variance > lambda_val:
                size = (lambda_val ** 2) / (variance - lambda_val)
                size = max(0.1, size)  # Ensure positive
                prob = 1 - lambda_val / (lambda_val + size)
                
                if side.upper() == 'OVER':
                    # P(X > line) = 1 - CDF(line)
                    return 1 - nbinom.cdf(line_int, n=size, p=prob)
                else:
                    # P(X < line) = CDF(line - 1)
                    if line_int <= 0:
                        return 0.0
                    return nbinom.cdf(line_int - 1, n=size, p=prob)
        
        # Standard Poisson
        if side.upper() == 'OVER':
            # P(X > line) = 1 - CDF(line)
            return 1 - poisson.cdf(line_int, mu=lambda_val)
        else:
            # P(X < line) = CDF(line - 1)
            if line_int <= 0:
                return 0.0
            return poisson.cdf(line_int - 1, mu=lambda_val)
    
    def exact_probability(self, lambda_val: float, k: int) -> float:
        """
        Calculate P(X = k) using Poisson PMF.
        
        P(X = k) = (e^(-λ) × λ^k) / k!
        """
        if lambda_val <= 0 or k < 0:
            return 0.0
        return poisson.pmf(k, mu=lambda_val)
    
    # =========================================================================
    # FAIR PRICE CALCULATION
    # =========================================================================
    
    def fair_price(self, lambda_val: float, line: float, side: str,
                   variance: float = None) -> int:
        """
        Calculate fair American odds based on Poisson probability.
        
        No-vig fair odds = probability to American odds conversion.
        """
        prob = self.hit_probability(lambda_val, line, side, variance)
        
        if prob <= 0.001:
            return 10000  # Massive underdog
        if prob >= 0.999:
            return -10000  # Massive favorite
        
        return self._prob_to_american(prob)
    
    def _prob_to_american(self, prob: float) -> int:
        """Convert probability to American odds"""
        if prob >= 0.5:
            return int(-100 * prob / (1 - prob))
        else:
            return int(100 * (1 - prob) / prob)
    
    def _american_to_prob(self, odds: int) -> float:
        """Convert American odds to implied probability"""
        if odds < 0:
            return abs(odds) / (abs(odds) + 100)
        else:
            return 100 / (odds + 100)
    
    # =========================================================================
    # EDGE CALCULATION
    # =========================================================================
    
    def calculate_edge(self, lambda_info: Dict, line: float, side: str,
                       market_odds: int) -> Dict:
        """
        Calculate edge between Poisson fair price and market odds.
        
        Edge = Poisson implied prob - Market implied prob
        """
        poisson_prob = self.hit_probability(
            lambda_info['adjusted_lambda'], 
            line, 
            side,
            lambda_info.get('variance')
        )
        
        market_prob = self._american_to_prob(market_odds)
        fair_odds = self.fair_price(
            lambda_info['adjusted_lambda'], 
            line, 
            side,
            lambda_info.get('variance')
        )
        
        edge_prob = poisson_prob - market_prob
        edge_pct = edge_prob * 100
        
        # EV calculation at given odds
        if market_odds < 0:
            potential_profit = 100 / abs(market_odds)
        else:
            potential_profit = market_odds / 100
        
        ev = (poisson_prob * potential_profit) - ((1 - poisson_prob) * 1)
        ev_pct = ev * 100
        
        return {
            'poisson_prob': round(poisson_prob, 4),
            'market_prob': round(market_prob, 4),
            'edge_pct': round(edge_pct, 2),
            'fair_odds': fair_odds,
            'market_odds': market_odds,
            'ev_pct': round(ev_pct, 2),
            'is_value': edge_pct > 3.0,  # 3% minimum edge
        }
    
    # =========================================================================
    # GAME TOTAL POISSON (Convolution)
    # =========================================================================
    
    def game_total_probability(self, home_lambda: float, away_lambda: float,
                                line: float, side: str) -> float:
        """
        Calculate P(total > line) using Poisson convolution.
        
        Total = Home + Away, where both follow Poisson.
        The sum of two Poisson RVs is Poisson with λ = λ1 + λ2.
        """
        total_lambda = home_lambda + away_lambda
        
        # Use standard Poisson for totals
        line_int = int(np.floor(line))
        
        if side.upper() == 'OVER':
            return 1 - poisson.cdf(line_int, mu=total_lambda)
        else:
            return poisson.cdf(line_int - 1, mu=total_lambda)
    
    # =========================================================================
    # FULL ANALYSIS
    # =========================================================================
    
    def analyze_prop(self, player_name: str, stat: str, line: float,
                     side: str, market_odds: int = -110,
                     opponent: str = None) -> Dict:
        """
        Complete Poisson analysis for a player prop.
        
        Returns all metrics needed for decision-making.
        """
        # Get lambda
        lambda_info = self.calculate_player_lambda(player_name, stat, opponent)
        
        if not lambda_info:
            return None
        
        # Get edge
        edge_info = self.calculate_edge(lambda_info, line, side, market_odds)
        
        # Distribution visualization (PMF at key values)
        adj_lambda = lambda_info['adjusted_lambda']
        pmf_values = {}
        for k in range(max(0, int(line) - 10), int(line) + 15):
            pmf_values[k] = round(self.exact_probability(adj_lambda, k), 4)
        
        return {
            'player': player_name,
            'stat': stat,
            'line': line,
            'side': side,
            'market_odds': market_odds,
            'lambda': lambda_info,
            'edge': edge_info,
            'pmf_distribution': pmf_values,
            'recommendation': 'BET' if edge_info['is_value'] else 'PASS',
        }


# =============================================================================
# TEST
# =============================================================================
if __name__ == "__main__":
    print("=" * 70)
    print("POISSON ENGINE v1.0 - TEST")
    print("=" * 70)
    
    engine = PoissonEngine()
    
    # Test cases
    tests = [
        ("Anthony Edwards", "pts", 25.5, "UNDER", -110, "BOS"),
        ("Donovan Mitchell", "pts", 24.5, "UNDER", -112, "LAL"),
        ("Trae Young", "ast", 10.5, "OVER", -115, "MIA"),
    ]
    
    for player, stat, line, side, odds, opp in tests:
        print(f"\n{'='*70}")
        print(f"{player} {stat.upper()} {side} {line}")
        print("=" * 70)
        
        result = engine.analyze_prop(player, stat, line, side, odds, opp)
        
        if result:
            print(f"\n📊 LAMBDA ANALYSIS")
            print(f"   Base λ: {result['lambda']['base_lambda']}")
            print(f"   Adjusted λ: {result['lambda']['adjusted_lambda']}")
            print(f"   Variance: {result['lambda']['variance']}")
            print(f"   Opp Factor ({opp}): {result['lambda']['opp_factor']}")
            print(f"   L5/L10/L15: {result['lambda']['l5']}/{result['lambda']['l10']}/{result['lambda']['l15']}")
            
            print(f"\n🎯 EDGE ANALYSIS")
            print(f"   Poisson Prob: {result['edge']['poisson_prob']*100:.1f}%")
            print(f"   Market Prob: {result['edge']['market_prob']*100:.1f}%")
            print(f"   Edge: {result['edge']['edge_pct']:+.1f}%")
            print(f"   Fair Odds: {result['edge']['fair_odds']}")
            print(f"   EV: {result['edge']['ev_pct']:+.1f}%")
            
            print(f"\n💡 RECOMMENDATION: {result['recommendation']}")
        else:
            print("   ❌ Could not analyze (insufficient data)")
    
    print("\n" + "=" * 70)
    print("✅ POISSON ENGINE v1.0 READY")
    print("=" * 70)
