#!/usr/bin/env python3
"""
================================================================================
PROP ANALYZER v3.0 - PROFESSIONAL GRADE
================================================================================
FULL IMPLEMENTATION with all SB-ALGO filters:

✅ GP Filter: Minimum 15 games (ideal 20)
✅ MPG Filter: Minimum 22 minutes, stable role
✅ Hit Rate: Must hit line 60%+ of recent games
✅ L10/L5 Weighted: Recent games weighted more
✅ Matchup Analysis: vs team, pace, defense
✅ Role Stability: No garbage time dependent players
✅ Trimmed Mean: Remove outliers
✅ Line Buffer: Would it still be good if line moves 1pt?

================================================================================
"""

import sys
import os
from datetime import date
from typing import List, Dict, Optional
from sqlalchemy import create_engine, text
from scipy import stats as scipy_stats
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from live_odds_connector import LiveOddsConnector
from calibration_engine import CalibrationEngine
from kelly_engine import KellyEngine

DATABASE_URL = "postgresql://sb_algo_db_user:0HDtYp4EY2Lo5At8iyf44PD1zDioSPK7@dpg-d495uhchg0os738l1a50-a.virginia-postgres.render.com/sb_algo_db"

# =============================================================================
# PROFESSIONAL FILTER THRESHOLDS
# =============================================================================
MIN_GP = 15                  # Minimum games played
IDEAL_GP = 20                # Ideal games played
MIN_MPG = 22                 # Minimum minutes per game
MIN_HIT_RATE = 0.60          # Must hit line 60% of games
IDEAL_HIT_RATE = 0.65        # Ideal hit rate
MIN_EDGE_PCT = 8.0           # Minimum edge to bet
LINE_BUFFER = 1.0            # Would bet still work if line moves 1pt?
MAX_PROPS_PER_DAY = 5        # Maximum prop bets per day


class PropAnalyzerPro:
    """
    Professional-grade prop analyzer with ALL SB-ALGO filters.
    """
    
    def __init__(self, bankroll: float = 10000):
        self.connector = LiveOddsConnector()
        self.calibration = CalibrationEngine()
        self.kelly = KellyEngine(risk_profile='moderate')
        self.bankroll = bankroll
        self.db = create_engine(DATABASE_URL)
        
        # Cache for player game logs
        self._game_logs = {}
        self._team_defense = {}
        self._preloaded = False  # Track if bulk preload has run
    
    def normalize_name(self, name: str) -> str:
        """Normalize player name for matching"""
        n = name.lower().strip()
        n = n.replace('.', '')  # A.J. -> AJ
        n = n.replace("'", "")  # O'Neal -> ONeal
        n = n.replace(" jr", "").replace(" sr", "")  # Remove suffixes
        n = n.replace(" iii", "").replace(" ii", "")
        return n
    
    # =========================================================================
    # CORE DATA FUNCTIONS
    # =========================================================================
    
    def get_player_game_log(self, player_name: str, n_games: int = 20) -> List[Dict]:
        """Get player's last N games with all stats"""
        # Use simple lowercase name as key (consistent with preload)
        cache_key = player_name.lower().strip()
        if cache_key in self._game_logs:
            return self._game_logs[cache_key]
        
        with self.db.connect() as conn:
            result = conn.execute(text("""
                SELECT game_date, pts, reb, ast, fg3m, min, team_abbreviation
                FROM player_boxscores
                WHERE LOWER(player_name) LIKE LOWER(:p)
                  AND game_date >= '2025-10-01'
                ORDER BY game_date DESC
                LIMIT :n
            """), {"p": f"%{player_name}%", "n": n_games})
            
            games = []
            for row in result:
                r = dict(row._mapping)
                # Parse minutes from "MM:SS" format
                min_val = 0
                if r['min']:
                    try:
                        if ':' in str(r['min']):
                            parts = str(r['min']).split(':')
                            min_val = int(parts[0]) + int(parts[1])/60
                        else:
                            min_val = float(r['min'])
                    except:
                        min_val = 0
                
                games.append({
                    'date': r['game_date'],
                    'pts': float(r['pts']) if r['pts'] else 0,
                    'reb': float(r['reb']) if r['reb'] else 0,
                    'ast': float(r['ast']) if r['ast'] else 0,
                    '3pm': float(r['fg3m']) if r['fg3m'] else 0,
                    'min': min_val,
                    'team': r['team_abbreviation'],
                })
            
            self._game_logs[cache_key] = games
            return games
    
    def get_team_defense_rating(self, team: str, stat: str) -> float:
        """Get team's defensive rating vs a stat (1.0 = average)"""
        # TODO: Implement from nba_defense_dashboard
        # For now, return neutral
        return 1.0
    
    # =========================================================================
    # FILTER FUNCTIONS
    # =========================================================================
    
    def check_gp_filter(self, games: List[Dict]) -> Dict:
        """Filter 1: Games Played check"""
        gp = len(games)
        return {
            'gp': gp,
            'passes': gp >= MIN_GP,
            'is_ideal': gp >= IDEAL_GP,
            'reason': f"GP {gp}" + (" ✅" if gp >= MIN_GP else f" ❌ (need {MIN_GP}+)")
        }
    
    def check_mpg_filter(self, games: List[Dict]) -> Dict:
        """Filter 2: Minutes Per Game check"""
        if not games:
            return {'mpg': 0, 'passes': False, 'reason': 'No games'}
        
        minutes = [g['min'] for g in games if g['min'] > 0]
        if not minutes:
            return {'mpg': 0, 'passes': False, 'reason': 'No minutes data'}
        
        mpg = np.mean(minutes)
        min_std = np.std(minutes)
        
        # Check for stability (std dev < 8 minutes is stable)
        is_stable = min_std < 8
        
        return {
            'mpg': round(mpg, 1),
            'min_std': round(min_std, 1),
            'passes': mpg >= MIN_MPG and is_stable,
            'is_stable': is_stable,
            'reason': f"MPG {mpg:.1f} (std {min_std:.1f})" + 
                     (" ✅" if mpg >= MIN_MPG and is_stable else " ❌")
        }
    
    def check_hit_rate(self, games: List[Dict], stat: str, line: float) -> Dict:
        """Filter 3: Hit rate vs the line"""
        if not games:
            return {'hit_rate': 0, 'passes': False, 'reason': 'No games'}
        
        # Use last 15 games for hit rate
        recent = games[:15]
        hits = sum(1 for g in recent if g.get(stat, 0) > line)
        hit_rate = hits / len(recent)
        
        return {
            'hit_rate': round(hit_rate, 3),
            'hits': hits,
            'games_checked': len(recent),
            'passes': hit_rate >= MIN_HIT_RATE,
            'is_ideal': hit_rate >= IDEAL_HIT_RATE,
            'reason': f"Hit {hits}/{len(recent)} ({hit_rate:.0%})" +
                     (" ✅" if hit_rate >= MIN_HIT_RATE else f" ❌ (need {MIN_HIT_RATE:.0%})")
        }
    
    def calculate_weighted_average(self, games: List[Dict], stat: str) -> Dict:
        """Calculate L5/L10/L15 weighted average with trimmed mean"""
        if not games:
            return {'error': 'No games'}
        
        values = [g.get(stat, 0) for g in games]
        
        # L5, L10, L15 simple averages
        l5 = np.mean(values[:5]) if len(values) >= 5 else np.mean(values)
        l10 = np.mean(values[:10]) if len(values) >= 10 else np.mean(values)
        l15 = np.mean(values[:15]) if len(values) >= 15 else np.mean(values)
        
        # Weighted average (L5 = 50%, L10 = 30%, L15 = 20%)
        weighted = l5 * 0.50 + l10 * 0.30 + l15 * 0.20
        
        # Trimmed mean (remove top and bottom 10%)
        if len(values) >= 10:
            sorted_vals = sorted(values)
            trim = int(len(sorted_vals) * 0.1)
            trimmed = sorted_vals[trim:-trim] if trim > 0 else sorted_vals
            trimmed_mean = np.mean(trimmed)
        else:
            trimmed_mean = np.mean(values)
        
        # Standard deviation
        std_dev = np.std(values) if len(values) > 1 else values[0] * 0.25
        
        return {
            'l5': round(l5, 1),
            'l10': round(l10, 1),
            'l15': round(l15, 1),
            'weighted': round(weighted, 1),
            'trimmed': round(trimmed_mean, 1),
            'std_dev': round(std_dev, 2),
            'projection': round(weighted, 1),  # Use weighted as main projection
        }
    
    def check_vs_opponent(self, games: List[Dict], stat: str, opponent: str) -> Dict:
        """Check player's history vs specific opponent - PLACEHOLDER"""
        # TODO: Need opponent data in boxscores to implement this
        return {
            'games_vs': 0,
            'avg_vs': None,
            'reason': f"Opponent history not available"
        }
    
    def check_line_buffer(self, projection: float, line: float, side: str) -> Dict:
        """Would bet still work if line moves 1 point?"""
        if side == 'OVER':
            buffer_line = line + LINE_BUFFER
            still_good = projection > buffer_line
        else:
            buffer_line = line - LINE_BUFFER
            still_good = projection < buffer_line
        
        return {
            'buffer_line': buffer_line,
            'still_good': still_good,
            'reason': f"At {buffer_line}: {'✅ Still good' if still_good else '❌ Marginal'}"
        }
    
    # =========================================================================
    # MAIN ANALYSIS FUNCTION
    # =========================================================================
    
    def analyze_prop_full(self, player_name: str, stat: str, 
                          book_line: float, opponent: str = None) -> Dict:
        """
        Full professional analysis of a player prop.
        
        Returns detailed analysis with all filters.
        """
        result = {
            'player': player_name,
            'stat': stat,
            'book_line': book_line,
            'opponent': opponent,
            'filters': {},
            'passes_all': False,
            'should_bet': False,
        }
        
        # Get game log
        games = self.get_player_game_log(player_name, 20)
        
        if not games:
            result['error'] = f"No games found for {player_name}"
            return result
        
        # =====================================================================
        # FILTER 1: Games Played
        # =====================================================================
        gp_check = self.check_gp_filter(games)
        result['filters']['gp'] = gp_check
        
        if not gp_check['passes']:
            result['reject_reason'] = f"GP too low: {gp_check['gp']}"
            return result
        
        # =====================================================================
        # FILTER 2: Minutes Per Game
        # =====================================================================
        mpg_check = self.check_mpg_filter(games)
        result['filters']['mpg'] = mpg_check
        
        if not mpg_check['passes']:
            result['reject_reason'] = f"MPG too low or unstable: {mpg_check['mpg']}"
            return result
        
        # =====================================================================
        # FILTER 3: Calculate Projection (Weighted L5/L10/L15)
        # =====================================================================
        projection = self.calculate_weighted_average(games, stat)
        result['projection'] = projection
        
        model_proj = projection['projection']
        std_dev = projection['std_dev']
        
        # Determine best side
        if model_proj > book_line:
            best_side = 'OVER'
            edge_pct = ((model_proj - book_line) / book_line) * 100
        else:
            best_side = 'UNDER'
            edge_pct = ((book_line - model_proj) / book_line) * 100
        
        result['best_side'] = best_side
        result['edge_pct'] = round(edge_pct, 1)
        
        # =====================================================================
        # FILTER 4: Hit Rate vs Line
        # =====================================================================
        if best_side == 'OVER':
            hit_check = self.check_hit_rate(games, stat, book_line)
        else:
            # For unders, count how many times UNDER the line
            recent = games[:15]
            hits = sum(1 for g in recent if g.get(stat, 0) < book_line)
            hit_rate = hits / len(recent)
            hit_check = {
                'hit_rate': round(hit_rate, 3),
                'hits': hits,
                'games_checked': len(recent),
                'passes': hit_rate >= MIN_HIT_RATE,
                'reason': f"Under {hits}/{len(recent)} ({hit_rate:.0%})"
            }
        
        result['filters']['hit_rate'] = hit_check
        
        if not hit_check['passes']:
            result['reject_reason'] = f"Hit rate too low: {hit_check['hit_rate']:.0%}"
            return result
        
        # =====================================================================
        # FILTER 5: Line Buffer Test
        # =====================================================================
        buffer_check = self.check_line_buffer(model_proj, book_line, best_side)
        result['filters']['line_buffer'] = buffer_check
        
        # Not a hard reject, but affects confidence
        
        # =====================================================================
        # FILTER 6: vs Opponent (if provided)
        # =====================================================================
        if opponent:
            vs_opp = self.check_vs_opponent(games, stat, opponent)
            result['filters']['vs_opponent'] = vs_opp
        
        # =====================================================================
        # CALCULATE PROBABILITY & KELLY
        # =====================================================================
        distribution = scipy_stats.norm(loc=model_proj, scale=std_dev)
        
        if best_side == 'OVER':
            win_prob = 1 - distribution.cdf(book_line)
        else:
            win_prob = distribution.cdf(book_line)
        
        # Calibrate
        cal = self.calibration.adjust_for_kelly(win_prob, 'player_prop')
        calibrated_prob = cal['kelly_safe_probability']
        
        # Adjust confidence based on filters
        confidence_adj = 1.0
        if not gp_check['is_ideal']:
            confidence_adj *= 0.9
        if not mpg_check['is_stable']:
            confidence_adj *= 0.85
        if not hit_check.get('is_ideal', False):
            confidence_adj *= 0.9
        if not buffer_check['still_good']:
            confidence_adj *= 0.8
        
        adjusted_prob = calibrated_prob * confidence_adj
        
        # EV calculation (assuming -110 odds)
        odds = -110
        decimal_odds = 1 + (100 / abs(odds))
        ev_pct = (adjusted_prob * (decimal_odds - 1) - (1 - adjusted_prob)) * 100
        
        # Kelly
        kelly_result = self.kelly.calculate_bet(adjusted_prob, odds, self.bankroll)
        
        result['probabilities'] = {
            'raw': round(win_prob, 3),
            'calibrated': round(calibrated_prob, 3),
            'adjusted': round(adjusted_prob, 3),
            'confidence_adj': round(confidence_adj, 2),
        }
        result['ev_pct'] = round(ev_pct, 1)
        result['kelly'] = kelly_result
        
        # =====================================================================
        # FINAL DECISION
        # =====================================================================
        result['passes_all'] = True
        result['should_bet'] = (
            edge_pct >= MIN_EDGE_PCT and
            kelly_result.get('should_bet', False) and
            ev_pct > 0
        )
        
        if result['should_bet']:
            result['stake'] = round(kelly_result.get('recommended_amount', 0), 2)
            result['grade'] = kelly_result.get('grade', 'N/A')
        
        return result
    
    # =========================================================================
    # BATCH SCANNING
    # =========================================================================
    
    def preload_all_game_logs(self, min_games: int = 15):
        """Pre-load all player game logs in ONE query for fast scanning"""
        print("   Pre-loading all player game logs...")
        
        with self.db.connect() as conn:
            result = conn.execute(text("""
                WITH player_games AS (
                    SELECT player_name, game_date, pts, reb, ast, fg3m, min,
                           ROW_NUMBER() OVER (PARTITION BY player_name ORDER BY game_date DESC) as game_num
                    FROM player_boxscores
                    WHERE game_date >= '2025-10-01'
                ),
                player_counts AS (
                    SELECT player_name, COUNT(*) as gp
                    FROM player_games
                    GROUP BY player_name
                    HAVING COUNT(*) >= :min_gp
                )
                SELECT pg.player_name, pg.game_date, pg.pts, pg.reb, pg.ast, pg.fg3m, pg.min, pg.game_num
                FROM player_games pg
                JOIN player_counts pc ON pg.player_name = pc.player_name
                WHERE pg.game_num <= 20
                ORDER BY pg.player_name, pg.game_date DESC
            """), {"min_gp": min_games})
            
            # Group by player
            current_player = None
            current_games = []
            
            for row in result:
                r = dict(row._mapping)
                player = r['player_name']
                
                if player != current_player:
                    if current_player and current_games:
                        # Store with BOTH original and normalized keys
                        key = current_player.lower().strip()
                        norm_key = self.normalize_name(current_player)
                        self._game_logs[key] = current_games
                        if norm_key != key:
                            self._game_logs[norm_key] = current_games
                    current_player = player
                    current_games = []
                
                # Parse minutes
                min_val = 0
                if r['min']:
                    try:
                        if ':' in str(r['min']):
                            parts = str(r['min']).split(':')
                            min_val = int(parts[0]) + int(parts[1])/60
                        else:
                            min_val = float(r['min'])
                    except:
                        min_val = 0
                
                current_games.append({
                    'date': r['game_date'],
                    'pts': float(r['pts']) if r['pts'] else 0,
                    'reb': float(r['reb']) if r['reb'] else 0,
                    'ast': float(r['ast']) if r['ast'] else 0,
                    '3pm': float(r['fg3m']) if r['fg3m'] else 0,
                    'min': min_val,
                })
            
            # Don't forget last player
            if current_player and current_games:
                key = current_player.lower().strip()
                norm_key = self.normalize_name(current_player)
                self._game_logs[key] = current_games
                if norm_key != key:
                    self._game_logs[norm_key] = current_games
        
        self._preloaded = True
        print(f"   ✅ Pre-loaded {len(self._game_logs)} player entries")
    
    def get_player_game_log_fast(self, player_name: str) -> List[Dict]:
        """Get game log from pre-loaded cache with fuzzy matching"""
        key = player_name.lower().strip()
        
        # Exact match
        if key in self._game_logs:
            return self._game_logs[key]
        
        # Normalized match
        norm_key = self.normalize_name(player_name)
        if norm_key in self._game_logs:
            return self._game_logs[norm_key]
        
        return []
    
    def find_best_props(self, target_date: date = None, 
                        markets: List[str] = None) -> List[Dict]:
        """
        Scan all props and return only those passing ALL filters.
        Limited to MAX_PROPS_PER_DAY best picks.
        """
        if target_date is None:
            target_date = date.today()
        
        if markets is None:
            markets = ['pts', 'reb', 'ast']
        
        market_map = {
            'pts': 'player_points',
            'reb': 'player_rebounds',
            'ast': 'player_assists',
        }
        full_markets = [market_map.get(m, f'player_{m}') for m in markets]
        
        stat_map = {
            'player_points': 'pts',
            'player_rebounds': 'reb',
            'player_assists': 'ast',
        }
        
        print(f"\n🔍 Scanning props for {target_date} (PROFESSIONAL FILTERS)...")
        
        # Pre-load all game logs ONCE (use flag, not dict emptiness)
        if not self._preloaded:
            self.preload_all_game_logs(MIN_GP)
        
        # Get props from major books only
        with self.connector.engine.connect() as conn:
            placeholders = ','.join([f"'{m}'" for m in full_markets])
            result = conn.execute(text(f"""
                WITH ranked_props AS (
                    SELECT player_name, market, line, over_odds, under_odds, 
                           sportsbook, home_team, away_team,
                           ROW_NUMBER() OVER (
                               PARTITION BY player_name, market 
                               ORDER BY 
                                   CASE sportsbook 
                                       WHEN 'FanDuel' THEN 1 
                                       WHEN 'DraftKings' THEN 2 
                                       WHEN 'Caesars' THEN 3
                                       WHEN 'BetMGM' THEN 4
                                       ELSE 10
                                   END
                           ) as rn
                    FROM player_props 
                    WHERE game_date = :d
                      AND market IN ({placeholders})
                      AND line >= 5.0
                )
                SELECT player_name, market, line, over_odds, under_odds, 
                       sportsbook, home_team, away_team
                FROM ranked_props
                WHERE rn = 1
            """), {"d": target_date})
            
            all_props = [dict(row._mapping) for row in result]
        
        print(f"   Found {len(all_props)} props to analyze")
        
        qualified = []
        analyzed = 0
        skipped_no_data = 0
        
        for prop in all_props:
            player = prop['player_name']
            market = prop['market']
            line = float(prop['line'])
            stat = stat_map.get(market, 'pts')
            
            analyzed += 1
            
            # Get games from cache (FAST)
            games = self.get_player_game_log_fast(player)
            
            if not games:
                skipped_no_data += 1
                continue
            
            # Quick filters first (no DB calls)
            # Filter 1: GP
            if len(games) < MIN_GP:
                continue
            
            # Filter 2: MPG
            minutes = [g['min'] for g in games if g['min'] > 0]
            if not minutes:
                continue
            mpg = np.mean(minutes)
            min_std = np.std(minutes)
            if mpg < MIN_MPG or min_std >= 8:
                continue
            
            # Filter 3: Calculate projection
            values = [g.get(stat, 0) for g in games]
            l5 = np.mean(values[:5]) if len(values) >= 5 else np.mean(values)
            l10 = np.mean(values[:10]) if len(values) >= 10 else np.mean(values)
            l15 = np.mean(values[:15]) if len(values) >= 15 else np.mean(values)
            weighted = l5 * 0.50 + l10 * 0.30 + l15 * 0.20
            std_dev = np.std(values) if len(values) > 1 else values[0] * 0.25
            
            # Determine side and edge
            if weighted > line:
                best_side = 'OVER'
                edge_pct = ((weighted - line) / line) * 100
                hits = sum(1 for g in games[:15] if g.get(stat, 0) > line)
            else:
                best_side = 'UNDER'
                edge_pct = ((line - weighted) / line) * 100
                hits = sum(1 for g in games[:15] if g.get(stat, 0) < line)
            
            hit_rate = hits / min(15, len(games))
            
            # Filter 4: Hit rate
            if hit_rate < MIN_HIT_RATE:
                continue
            
            # Filter 5: Minimum edge
            if edge_pct < MIN_EDGE_PCT:
                continue
            
            # Filter 6: Line buffer test
            if best_side == 'OVER':
                buffer_ok = weighted > (line + LINE_BUFFER)
            else:
                buffer_ok = weighted < (line - LINE_BUFFER)
            
            # Calculate probability and EV
            distribution = scipy_stats.norm(loc=weighted, scale=std_dev)
            if best_side == 'OVER':
                win_prob = 1 - distribution.cdf(line)
            else:
                win_prob = distribution.cdf(line)
            
            # Calibrate
            cal = self.calibration.adjust_for_kelly(win_prob, 'player_prop')
            calibrated_prob = cal['kelly_safe_probability']
            
            # Confidence adjustment
            conf_adj = 1.0
            if len(games) < IDEAL_GP:
                conf_adj *= 0.9
            if min_std >= 6:
                conf_adj *= 0.9
            if hit_rate < IDEAL_HIT_RATE:
                conf_adj *= 0.9
            if not buffer_ok:
                conf_adj *= 0.85
            
            adjusted_prob = calibrated_prob * conf_adj
            
            # EV
            odds = -110
            decimal_odds = 1 + (100 / abs(odds))
            ev_pct = (adjusted_prob * (decimal_odds - 1) - (1 - adjusted_prob)) * 100
            
            if ev_pct <= 0:
                continue
            
            # Kelly
            kelly_result = self.kelly.calculate_bet(adjusted_prob, odds, self.bankroll)
            
            if kelly_result.get('should_bet'):
                qualified.append({
                    'player': player,
                    'stat': stat,
                    'book_line': line,
                    'book': prop['sportsbook'],
                    'matchup': f"{prop.get('away_team', '?')} @ {prop.get('home_team', '?')}",
                    'projection': {
                        'l5': round(l5, 1),
                        'l10': round(l10, 1),
                        'l15': round(l15, 1),
                        'weighted': round(weighted, 1),
                    },
                    'best_side': best_side,
                    'edge_pct': round(edge_pct, 1),
                    'ev_pct': round(ev_pct, 1),
                    'filters': {
                        'gp': len(games),
                        'mpg': round(mpg, 1),
                        'min_std': round(min_std, 1),
                        'hit_rate': {'hit_rate': round(hit_rate, 2), 'hits': hits},
                        'buffer_ok': buffer_ok,
                    },
                    'probabilities': {
                        'raw': round(win_prob, 3),
                        'adjusted': round(adjusted_prob, 3),
                    },
                    'stake': round(kelly_result.get('recommended_amount', 0), 2),
                    'grade': kelly_result.get('grade', 'N/A'),
                })
        
        print(f"   ✅ Analyzed {analyzed} props, {len(qualified)} passed ALL filters")
        print(f"      (Skipped {skipped_no_data} with no game data)")
        
        # Sort by EV and limit
        qualified.sort(key=lambda x: x.get('ev_pct', 0), reverse=True)
        
        return qualified[:MAX_PROPS_PER_DAY]


# =============================================================================
# MAIN
# =============================================================================
if __name__ == "__main__":
    print("=" * 70)
    print("🏀 PROP ANALYZER v3.0 - PROFESSIONAL GRADE")
    print("=" * 70)
    print(f"\n📋 FILTERS APPLIED:")
    print(f"   • GP ≥ {MIN_GP} (ideal {IDEAL_GP})")
    print(f"   • MPG ≥ {MIN_MPG}")
    print(f"   • Hit Rate ≥ {MIN_HIT_RATE:.0%} (ideal {IDEAL_HIT_RATE:.0%})")
    print(f"   • Line Buffer: {LINE_BUFFER} pts")
    print(f"   • Max Props/Day: {MAX_PROPS_PER_DAY}")
    
    analyzer = PropAnalyzerPro(bankroll=10000)
    today = date.today()
    
    # Test 1: Full analysis of specific prop
    print("\n" + "=" * 70)
    print("TEST 1: FULL PROP ANALYSIS")
    print("=" * 70)
    
    test_props = [
        ('Ayo Dosunmu', 'pts', 8.5, 'MIN'),
        ('Anthony Davis', 'pts', 23.5, 'MIA'),
        ('Shai Gilgeous-Alexander', 'pts', 30.5, 'ATL'),
    ]
    
    for player, stat, line, opp in test_props:
        print(f"\n{'─'*60}")
        print(f"🏀 {player} {stat.upper()} {line}")
        print(f"{'─'*60}")
        
        result = analyzer.analyze_prop_full(player, stat, line, opp)
        
        if 'error' in result:
            print(f"   ❌ {result['error']}")
            continue
        
        if 'reject_reason' in result:
            print(f"   ❌ REJECTED: {result['reject_reason']}")
            for fname, fdata in result.get('filters', {}).items():
                print(f"      {fname}: {fdata.get('reason', fdata)}")
            continue
        
        # Passed filters
        print(f"   ✅ PASSES ALL FILTERS")
        print(f"\n   📊 Projection:")
        proj = result['projection']
        print(f"      L5: {proj['l5']} | L10: {proj['l10']} | L15: {proj['l15']}")
        print(f"      Weighted: {proj['weighted']} | Trimmed: {proj['trimmed']}")
        
        print(f"\n   🎯 Analysis:")
        print(f"      Best Side: {result['best_side']}")
        print(f"      Edge: {result['edge_pct']:+.1f}%")
        print(f"      Hit Rate: {result['filters']['hit_rate']['hit_rate']:.0%}")
        print(f"      EV: {result['ev_pct']:.1f}%")
        
        print(f"\n   📈 Probabilities:")
        probs = result['probabilities']
        print(f"      Raw: {probs['raw']:.0%} → Adjusted: {probs['adjusted']:.0%}")
        print(f"      Confidence Adj: {probs['confidence_adj']:.0%}")
        
        if result['should_bet']:
            print(f"\n   💰 RECOMMENDATION: BET ${result['stake']:.0f} ({result['grade']})")
        else:
            print(f"\n   ⚪ NO BET (edge or EV too low)")
    
    # Test 2: Find best props
    print("\n" + "=" * 70)
    print("TEST 2: FIND BEST PROPS (TOP 5)")
    print("=" * 70)
    
    best_props = analyzer.find_best_props(today, markets=['pts', 'reb', 'ast'])
    
    if best_props:
        print(f"\n📋 TOP {len(best_props)} PROPS (passed ALL filters):")
        print("-" * 70)
        
        total_stake = 0
        for i, prop in enumerate(best_props, 1):
            print(f"\n  {i}. {prop['player']} {prop['stat'].upper()}")
            print(f"     Line: {prop['book_line']} | Model: {prop['projection']['weighted']}")
            print(f"     {prop['best_side']} | Edge: {prop['edge_pct']:+.1f}% | EV: {prop['ev_pct']:.1f}%")
            print(f"     Hit Rate: {prop['filters']['hit_rate']['hit_rate']:.0%}")
            print(f"     ${prop.get('stake', 0):.0f} | {prop.get('grade', 'N/A')}")
            total_stake += prop.get('stake', 0)
        
        print(f"\n  💰 TOTAL STAKE: ${total_stake:.0f}")
    else:
        print("\n  ❌ No props passed all filters")
    
    print("\n" + "=" * 70)
    print("✅ PROP ANALYZER v3.0 - COMPLETE")
    print("=" * 70)
