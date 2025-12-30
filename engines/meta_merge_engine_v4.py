#!/usr/bin/env python3
"""
================================================================================
META-MERGE ENGINE v4.0 - ULTIMATE EDITION
================================================================================
The Master Orchestrator - Now with Injury, Calibration, and Uncertainty!

ARCHITECTURE v4.0:
------------------
┌─────────────────────────────────────────────────────────────────────────────┐
│                         META-MERGE ENGINE v4.0                               │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                    UNCERTAINTY ENGINE                                │    │
│  │   Detects: HIGH_VARIANCE / UNSTABLE / AVOID regimes                 │    │
│  │   Output: Kelly multiplier, confidence adjustments                   │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                    │                                         │
│                                    ▼                                         │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                      INJURY ENGINE                                   │    │
│  │   Parses: injuries from news, manual input                          │    │
│  │   Output: spread adjustment, prop boosts, confidence penalty        │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                    │                                         │
│                                    ▼                                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────────┐       │
│  │   SPREAD     │  │    TOTAL     │  │      PLAYER PROP             │       │
│  │   ENGINE     │  │    ENGINE    │  │       ENGINE                 │       │
│  └──────┬───────┘  └──────┬───────┘  └───────────┬──────────────────┘       │
│         │                 │                       │                          │
│         └─────────────────┼───────────────────────┘                          │
│                           ▼                                                  │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                 HISTORICAL PATTERNS ENGINE                           │    │
│  │   L5/L10/L15 Averages, Matchup History, Trends, H2H                 │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                           │                                                  │
│                           ▼                                                  │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                   CALIBRATION ENGINE                                 │    │
│  │   Adjusts: raw probabilities → calibrated probabilities             │    │
│  │   Output: Kelly-safe probabilities, reliability metrics             │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                           │                                                  │
│                           ▼                                                  │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                     KELLY ENGINE                                     │    │
│  │   Calculates: optimal bet sizing with calibrated probabilities      │    │
│  │   Output: stake amounts, grades, risk analysis                      │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                           │                                                  │
│                           ▼                                                  │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                       CLV ENGINE                                     │    │
│  │   Tracks: line movement, sharp action, optimal timing              │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                           │                                                  │
│                           ▼                                                  │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                      FINAL OUTPUT                                    │    │
│  │   • Unified predictions with injury adjustments                     │    │
│  │   • Calibrated confidence scores                                    │    │
│  │   • Regime-adjusted Kelly stakes                                    │    │
│  │   • Optimized bet slip                                              │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘

================================================================================
"""

import numpy as np
from scipy import stats
from datetime import datetime
from sqlalchemy import create_engine, text
from typing import List, Dict, Optional, Tuple
import warnings
warnings.filterwarnings('ignore')

# Import engines
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

ENGINES_AVAILABLE = {
    'historical': False,
    'correlation': False,
    'kelly': False,
    'clv': False,
    'injury': False,
    'calibration': False,
    'uncertainty': False,
}

try:
    from historical_patterns_engine import HistoricalPatternsEngine
    ENGINES_AVAILABLE['historical'] = True
except ImportError:
    pass

try:
    from correlation_engine import CorrelationEngine
    ENGINES_AVAILABLE['correlation'] = True
except ImportError:
    pass

try:
    from kelly_engine import KellyEngine
    ENGINES_AVAILABLE['kelly'] = True
except ImportError:
    pass

try:
    from clv_engine import CLVEngine
    ENGINES_AVAILABLE['clv'] = True
except ImportError:
    pass

try:
    from injury_engine import InjuryEngine
    ENGINES_AVAILABLE['injury'] = True
except ImportError:
    pass

try:
    from calibration_engine import CalibrationEngine
    ENGINES_AVAILABLE['calibration'] = True
except ImportError:
    pass

try:
    from uncertainty_engine import UncertaintyEngine
    ENGINES_AVAILABLE['uncertainty'] = True
except ImportError:
    pass

# ==============================================================================
# CONFIGURATION
# ==============================================================================
DATABASE_URL = "postgresql://sb_algo_db_user:0HDtYp4EY2Lo5At8iyf44PD1zDioSPK7@dpg-d495uhchg0os738l1a50-a.virginia-postgres.render.com/sb_algo_db"

# Edge thresholds for betting
EDGE_THRESHOLDS = {
    'spread': 2.0,
    'total': 3.0,
    'moneyline': 5.0,
    'prop': 8.0,
}


class MetaMergeEngine:
    """
    ============================================================================
    META-MERGE ENGINE v4.0 - The Ultimate Orchestrator
    ============================================================================
    """
    
    def __init__(self, bankroll: float = 10000, risk_profile: str = 'moderate'):
        self.db = create_engine(DATABASE_URL)
        self.bankroll = bankroll
        self.risk_profile = risk_profile
        
        # Initialize all engines
        self.historical = HistoricalPatternsEngine() if ENGINES_AVAILABLE['historical'] else None
        self.correlation = CorrelationEngine() if ENGINES_AVAILABLE['correlation'] else None
        self.kelly = KellyEngine(risk_profile=risk_profile) if ENGINES_AVAILABLE['kelly'] else None
        self.clv = CLVEngine() if ENGINES_AVAILABLE['clv'] else None
        self.injury = InjuryEngine() if ENGINES_AVAILABLE['injury'] else None
        self.calibration = CalibrationEngine() if ENGINES_AVAILABLE['calibration'] else None
        self.uncertainty = UncertaintyEngine() if ENGINES_AVAILABLE['uncertainty'] else None
        
        print(f"🔧 Meta-Merge Engine v4.0 initialized")
        print(f"   Engines loaded: {sum(ENGINES_AVAILABLE.values())}/7")
        for name, loaded in ENGINES_AVAILABLE.items():
            status = "✅" if loaded else "❌"
            print(f"   {status} {name}")
    
    # ==========================================================================
    # TEAM DATA
    # ==========================================================================
    
    def get_team_stats(self, team_name: str) -> Dict:
        """Get comprehensive team stats with team name normalization"""
        # Team abbreviation to full name mapping
        TEAM_MAP = {
            'ATL': 'Atlanta Hawks', 'BOS': 'Boston Celtics', 'BKN': 'Brooklyn Nets',
            'CHA': 'Charlotte Hornets', 'CHI': 'Chicago Bulls', 'CLE': 'Cleveland Cavaliers',
            'DAL': 'Dallas Mavericks', 'DEN': 'Denver Nuggets', 'DET': 'Detroit Pistons',
            'GS': 'Golden State Warriors', 'GSW': 'Golden State Warriors',
            'HOU': 'Houston Rockets', 'IND': 'Indiana Pacers',
            'LAC': 'LA Clippers', 'LAL': 'Los Angeles Lakers',
            'MEM': 'Memphis Grizzlies', 'MIA': 'Miami Heat', 'MIL': 'Milwaukee Bucks',
            'MIN': 'Minnesota Timberwolves', 'NO': 'New Orleans Pelicans', 
            'NOP': 'New Orleans Pelicans', 'NY': 'New York Knicks', 'NYK': 'New York Knicks',
            'OKC': 'Oklahoma City Thunder', 'ORL': 'Orlando Magic',
            'PHI': 'Philadelphia 76ers', 'PHX': 'Phoenix Suns',
            'POR': 'Portland Trail Blazers', 'SAC': 'Sacramento Kings',
            'SA': 'San Antonio Spurs', 'SAS': 'San Antonio Spurs',
            'TOR': 'Toronto Raptors', 'UTA': 'Utah Jazz', 'WAS': 'Washington Wizards',
        }
        
        # Normalize team name
        full_name = TEAM_MAP.get(team_name.upper(), team_name)
        
        with self.db.connect() as conn:
            adv = conn.execute(text("""
                SELECT * FROM nba_team_advanced_stats
                WHERE "TEAM_NAME" ILIKE :team LIMIT 1
            """), {"team": f"%{full_name}%"}).fetchone()
            
            if not adv:
                return None
            
            return {'advanced': dict(adv._mapping)}

    # ==========================================================================
    # FULL GAME PREDICTION v4.0
    # ==========================================================================
    
    def predict_game(self, home_team: str, away_team: str,
                     book_spread: float = None,
                     book_total: float = None,
                     home_ml: int = None,
                     away_ml: int = None,
                     injuries_home: List[Dict] = None,
                     injuries_away: List[Dict] = None,
                     b2b_home: bool = False,
                     b2b_away: bool = False) -> Dict:
        """
        Complete game prediction with all engines integrated.
        
        This is the MAIN function that orchestrates everything.
        """
        result = {
            'matchup': f"{away_team} @ {home_team}",
            'timestamp': datetime.now().isoformat(),
            'engines_used': [],
        }
        
        # =====================================================================
        # STEP 1: UNCERTAINTY/REGIME CHECK
        # =====================================================================
        regime_data = None
        kelly_multiplier = 1.0
        
        if self.uncertainty:
            regime_data = self.uncertainty.detect_regime(
                home_team, away_team,
                injuries_home=len(injuries_home) if injuries_home else 0,
                injuries_away=len(injuries_away) if injuries_away else 0,
                b2b_home=b2b_home,
                b2b_away=b2b_away,
            )
            kelly_multiplier = regime_data['kelly_multiplier']
            result['regime'] = {
                'status': regime_data['regime'],
                'confidence': regime_data['confidence_pct'],
                'kelly_multiplier': kelly_multiplier,
                'warnings': regime_data['warnings'],
            }
            result['engines_used'].append('uncertainty')
        
        # =====================================================================
        # STEP 2: INJURY ANALYSIS
        # =====================================================================
        injury_spread_adj = 0
        injury_total_adj = 0
        injury_confidence_penalty = 0
        
        if self.injury:
            injury_analysis = self.injury.analyze_game_injuries(home_team, away_team)
            injury_spread_adj = injury_analysis['net_spread_adjustment']
            injury_total_adj = injury_analysis['net_total_adjustment']
            injury_confidence_penalty = injury_analysis['combined_confidence_penalty']
            
            result['injuries'] = {
                'spread_adjustment': injury_spread_adj,
                'total_adjustment': injury_total_adj,
                'confidence_penalty': injury_confidence_penalty,
                'edge_for': injury_analysis['edge_for'],
            }
            result['engines_used'].append('injury')
        
        # =====================================================================
        # STEP 3: BASE PREDICTIONS
        # =====================================================================
        home_stats = self.get_team_stats(home_team)
        away_stats = self.get_team_stats(away_team)
        
        if not home_stats or not away_stats:
            result['error'] = f"Team data not found"
            return result
        
        # Net rating based spread
        home_net = home_stats['advanced'].get('NET_RATING', 0) or 0
        away_net = away_stats['advanced'].get('NET_RATING', 0) or 0
        
        # Base prediction
        home_court = 2.8
        base_margin = (home_net - away_net) + home_court
        
        # Apply injury adjustment
        predicted_margin = base_margin + injury_spread_adj
        predicted_spread = -predicted_margin
        
        # Pace for total
        home_pace = home_stats['advanced'].get('PACE', 100) or 100
        away_pace = away_stats['advanced'].get('PACE', 100) or 100
        game_pace = 0.48 * max(home_pace, away_pace) + 0.52 * min(home_pace, away_pace)
        
        # Efficiency
        home_off = home_stats['advanced'].get('OFF_RATING', 110) or 110
        home_def = home_stats['advanced'].get('DEF_RATING', 110) or 110
        away_off = away_stats['advanced'].get('OFF_RATING', 110) or 110
        away_def = away_stats['advanced'].get('DEF_RATING', 110) or 110
        
        expected_possessions = game_pace * 0.96
        home_pts = expected_possessions * (home_off + (220 - away_def)) / 200
        away_pts = expected_possessions * (away_off + (220 - home_def)) / 200
        
        predicted_total = home_pts + away_pts + injury_total_adj
        
        # Standard deviations
        spread_std = 11.5
        total_std = 10.0
        
        result['predictions'] = {
            'margin': round(predicted_margin, 2),
            'spread': round(predicted_spread, 1),
            'total': round(predicted_total, 1),
            'home_pts': round(home_pts, 1),
            'away_pts': round(away_pts, 1),
            'pace': round(game_pace, 1),
        }
        
        # =====================================================================
        # STEP 4: EDGE CALCULATION vs BOOK
        # =====================================================================
        picks = []
        
        # Spread analysis
        if book_spread is not None:
            distribution = stats.t(df=7, loc=predicted_margin, scale=spread_std)
            cover_prob = 1 - distribution.cdf(-book_spread)
            
            if cover_prob > 0.5:
                best_side = 'HOME'
                best_bet = f"{home_team} {book_spread:+.1f}"
                win_prob = cover_prob
            else:
                best_side = 'AWAY'
                best_bet = f"{away_team} {-book_spread:+.1f}"
                win_prob = 1 - cover_prob
            
            edge = abs(book_spread - predicted_spread)
            
            # Calibrate probability
            calibrated_prob = win_prob
            if self.calibration:
                cal_result = self.calibration.adjust_for_kelly(win_prob, 'spread', 
                    100 - injury_confidence_penalty)
                calibrated_prob = cal_result['kelly_safe_probability']
                result['engines_used'].append('calibration')
            
            # Calculate EV and Kelly
            ev_pct = (calibrated_prob * 0.909) - ((1 - calibrated_prob) * 1)
            ev_pct *= 100
            
            kelly_stake = 0
            grade = 'N/A'
            should_bet = False
            
            if self.kelly and calibrated_prob > 0.52 and edge >= EDGE_THRESHOLDS['spread']:
                kelly_result = self.kelly.calculate_bet(calibrated_prob, -110, self.bankroll)
                if kelly_result.get('should_bet'):
                    # Apply regime multiplier
                    kelly_stake = kelly_result['recommended_amount'] * kelly_multiplier
                    grade = kelly_result['grade']
                    should_bet = True
                    result['engines_used'].append('kelly')
            
            spread_pick = {
                'type': 'SPREAD',
                'pick': best_bet,
                'raw_prob': round(win_prob, 4),
                'calibrated_prob': round(calibrated_prob, 4),
                'edge': round(edge, 1),
                'ev_pct': round(ev_pct, 2),
                'grade': grade,
                'stake': round(kelly_stake, 2),
                'should_bet': should_bet,
            }
            
            if should_bet:
                picks.append(spread_pick)
            
            result['spread_analysis'] = spread_pick
        
        # Total analysis
        if book_total is not None:
            distribution = stats.norm(loc=predicted_total, scale=total_std)
            over_prob = 1 - distribution.cdf(book_total)
            
            if over_prob > 0.5:
                best_bet = f"OVER {book_total}"
                win_prob = over_prob
            else:
                best_bet = f"UNDER {book_total}"
                win_prob = 1 - over_prob
            
            edge = abs(predicted_total - book_total)
            
            # Calibrate
            calibrated_prob = win_prob
            if self.calibration:
                cal_result = self.calibration.adjust_for_kelly(win_prob, 'total',
                    100 - injury_confidence_penalty)
                calibrated_prob = cal_result['kelly_safe_probability']
            
            ev_pct = (calibrated_prob * 0.909) - ((1 - calibrated_prob) * 1)
            ev_pct *= 100
            
            kelly_stake = 0
            grade = 'N/A'
            should_bet = False
            
            if self.kelly and calibrated_prob > 0.52 and edge >= EDGE_THRESHOLDS['total']:
                kelly_result = self.kelly.calculate_bet(calibrated_prob, -110, self.bankroll)
                if kelly_result.get('should_bet'):
                    kelly_stake = kelly_result['recommended_amount'] * kelly_multiplier
                    grade = kelly_result['grade']
                    should_bet = True
            
            total_pick = {
                'type': 'TOTAL',
                'pick': best_bet,
                'raw_prob': round(win_prob, 4),
                'calibrated_prob': round(calibrated_prob, 4),
                'edge': round(edge, 1),
                'ev_pct': round(ev_pct, 2),
                'grade': grade,
                'stake': round(kelly_stake, 2),
                'should_bet': should_bet,
            }
            
            if should_bet:
                picks.append(total_pick)
            
            result['total_analysis'] = total_pick
        
        # =====================================================================
        # STEP 5: MONEYLINE ANALYSIS
        # =====================================================================
        if home_ml and away_ml:
            distribution = stats.t(df=7, loc=predicted_margin, scale=spread_std)
            home_win_prob = 1 - distribution.cdf(0)
            
            # Book implied
            if home_ml > 0:
                home_implied = 100 / (home_ml + 100)
            else:
                home_implied = abs(home_ml) / (abs(home_ml) + 100)
            
            ml_edge = (home_win_prob - home_implied) * 100
            
            result['moneyline_analysis'] = {
                'home_win_prob': round(home_win_prob, 4),
                'away_win_prob': round(1 - home_win_prob, 4),
                'home_implied': round(home_implied, 4),
                'edge_pct': round(ml_edge, 2),
                'best_bet': f"{home_team} ML" if ml_edge > 0 else f"{away_team} ML",
            }
        
        # =====================================================================
        # STEP 6: COMPILE FINAL OUTPUT
        # =====================================================================
        result['picks'] = picks
        result['total_picks'] = len(picks)
        result['total_stake'] = sum(p['stake'] for p in picks)
        result['has_value'] = len(picks) > 0
        
        # Final recommendation
        if regime_data and regime_data['regime'] == 'AVOID':
            result['recommendation'] = '🔴 AVOID - High uncertainty, do not bet'
        elif not picks:
            result['recommendation'] = '⚪ NO VALUE - No edges found'
        elif regime_data and regime_data['regime'] == 'HIGH_VARIANCE':
            result['recommendation'] = f'🟡 REDUCED SIZE - {len(picks)} picks, ${result["total_stake"]:.0f} total'
        else:
            result['recommendation'] = f'🟢 PROCEED - {len(picks)} picks, ${result["total_stake"]:.0f} total'
        
        return result
    
    # ==========================================================================
    # PLAYER PROP PREDICTION v4.0
    # ==========================================================================
    
    def predict_prop(self, player_name: str, stat: str, book_line: float,
                     opponent: str = None, player_out: str = None) -> Dict:
        """
        Player prop prediction with injury and calibration adjustments.
        
        Args:
            player_name: Player name
            stat: Stat type (pts, reb, ast, etc.)
            book_line: Book's line
            opponent: Opponent team
            player_out: If a key teammate is out, boost this player
        """
        if not self.historical:
            return {'error': 'Historical engine not available'}
        
        result = {
            'player': player_name,
            'stat': stat,
            'book_line': book_line,
            'opponent': opponent,
        }
        
        # Get base projection
        projection = self.historical.get_weighted_projection(player_name, stat)
        
        if 'error' in projection:
            return projection
        
        base_proj = projection['projection']
        std_dev = projection['std_dev'] or base_proj * 0.25
        
        # Matchup adjustment
        matchup_adj = 0
        if opponent:
            try:
                matchup = self.historical.get_player_vs_team_comparison(player_name, opponent)
                if 'adjustments' in matchup and stat in matchup['adjustments']:
                    matchup_adj = matchup['adjustments'][stat]['difference']
            except:
                pass
        
        # Teammate out boost
        boost = 0
        if player_out and self.injury:
            try:
                realloc = self.injury.calculate_usage_reallocation(
                    self.historical._player_cache.get(player_name.lower(), {}).get('team', ''),
                    player_out
                )
                if 'reallocation' in realloc:
                    for r in realloc['reallocation']:
                        if r['player'].lower() == player_name.lower():
                            boost = r.get(f'{stat}_boost', 0)
                            break
            except:
                pass
        
        # Final projection
        final_proj = base_proj + matchup_adj + boost
        
        # Probability
        distribution = stats.norm(loc=final_proj, scale=std_dev)
        over_prob = 1 - distribution.cdf(book_line)
        
        if over_prob > 0.5:
            best_bet = f"OVER {book_line}"
            win_prob = over_prob
        else:
            best_bet = f"UNDER {book_line}"
            win_prob = 1 - over_prob
        
        edge_pct = ((final_proj - book_line) / book_line) * 100
        
        # Calibrate
        calibrated_prob = win_prob
        if self.calibration:
            cal = self.calibration.adjust_for_kelly(win_prob, 'player_prop')
            calibrated_prob = cal['kelly_safe_probability']
        
        # EV and Kelly
        ev_pct = (calibrated_prob * 0.909) - ((1 - calibrated_prob) * 1)
        ev_pct *= 100
        
        kelly_stake = 0
        grade = 'N/A'
        should_bet = False
        
        if self.kelly and calibrated_prob > 0.52 and abs(edge_pct) >= EDGE_THRESHOLDS['prop']:
            kelly_result = self.kelly.calculate_bet(calibrated_prob, -110, self.bankroll)
            if kelly_result.get('should_bet'):
                kelly_stake = kelly_result['recommended_amount']
                grade = kelly_result['grade']
                should_bet = True
        
        result.update({
            'base_projection': round(base_proj, 2),
            'matchup_adjustment': round(matchup_adj, 2),
            'teammate_out_boost': round(boost, 2),
            'final_projection': round(final_proj, 2),
            'std_dev': round(std_dev, 2),
            
            'over_prob': round(over_prob, 4),
            'calibrated_prob': round(calibrated_prob, 4),
            'edge_pct': round(edge_pct, 2),
            'ev_pct': round(ev_pct, 2),
            
            'best_bet': best_bet,
            'grade': grade,
            'stake': round(kelly_stake, 2),
            'should_bet': should_bet,
        })
        
        return result
    
    # ==========================================================================
    # DAILY SLATE ANALYSIS
    # ==========================================================================
    
    def analyze_slate(self, games: List[Dict]) -> Dict:
        """
        Analyze a full slate of games.
        
        Args:
            games: List of game dicts with keys:
                   home_team, away_team, spread, total, home_ml, away_ml
        
        Returns:
            Complete slate analysis with bet slip
        """
        print(f"\n{'='*70}")
        print(f"📊 ANALYZING {len(games)} GAMES")
        print(f"{'='*70}")
        
        all_picks = []
        game_results = []
        
        for game in games:
            print(f"\n  Analyzing: {game.get('away_team', '?')} @ {game.get('home_team', '?')}...")
            
            result = self.predict_game(
                home_team=game.get('home_team'),
                away_team=game.get('away_team'),
                book_spread=game.get('spread'),
                book_total=game.get('total'),
                home_ml=game.get('home_ml'),
                away_ml=game.get('away_ml'),
                b2b_home=game.get('b2b_home', False),
                b2b_away=game.get('b2b_away', False),
            )
            
            game_results.append(result)
            
            # Collect picks
            for pick in result.get('picks', []):
                pick['game'] = result['matchup']
                all_picks.append(pick)
        
        # Sort by EV
        all_picks.sort(key=lambda x: x.get('ev_pct', 0), reverse=True)
        
        # Build bet slip
        bet_slip = {
            'generated_at': datetime.now().isoformat(),
            'bankroll': self.bankroll,
            'games_analyzed': len(games),
            'total_picks': len(all_picks),
            'total_stake': sum(p['stake'] for p in all_picks),
            'avg_ev': round(np.mean([p['ev_pct'] for p in all_picks]), 2) if all_picks else 0,
            'picks': all_picks,
        }
        
        return {
            'game_results': game_results,
            'bet_slip': bet_slip,
        }


# ==============================================================================
# TEST SUITE
# ==============================================================================
if __name__ == "__main__":
    print("=" * 80)
    print("META-MERGE ENGINE v4.0 - ULTIMATE TEST")
    print("=" * 80)
    
    engine = MetaMergeEngine(bankroll=10000, risk_profile='moderate')
    
    # -------------------------------------------------------------------------
    # Test 1: Single game prediction
    # -------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("TEST 1: SINGLE GAME PREDICTION")
    print("=" * 80)
    
    game = engine.predict_game(
        home_team="Celtics",
        away_team="Lakers",
        book_spread=-8.5,
        book_total=224.5,
        home_ml=-350,
        away_ml=280,
        b2b_away=True,
    )
    
    print(f"\n  🏀 {game['matchup']}")
    
    if 'regime' in game:
        print(f"\n  📊 REGIME: {game['regime']['status']} ({game['regime']['confidence']}% confidence)")
        print(f"     Kelly Multiplier: {game['regime']['kelly_multiplier']}")
        if game['regime']['warnings']:
            print(f"     Warnings: {', '.join(game['regime']['warnings'][:2])}")
    
    if 'injuries' in game:
        print(f"\n  🏥 INJURIES:")
        print(f"     Spread Adj: {game['injuries']['spread_adjustment']:+.1f}")
        print(f"     Total Adj: {game['injuries']['total_adjustment']:+.1f}")
    
    if 'predictions' in game:
        print(f"\n  📈 PREDICTIONS:")
        print(f"     Margin: {game['predictions']['margin']:+.1f}")
        print(f"     Spread: {game['predictions']['spread']}")
        print(f"     Total: {game['predictions']['total']}")
    
    if 'spread_analysis' in game:
        sa = game['spread_analysis']
        print(f"\n  🎯 SPREAD ANALYSIS:")
        print(f"     Pick: {sa['pick']}")
        print(f"     Raw Prob: {sa['raw_prob']:.1%} → Calibrated: {sa['calibrated_prob']:.1%}")
        print(f"     Edge: {sa['edge']:.1f} pts | EV: {sa['ev_pct']:.1f}%")
        print(f"     Grade: {sa['grade']} | Stake: ${sa['stake']:.0f}")
    
    print(f"\n  📋 {game['recommendation']}")
    print(f"     Engines used: {', '.join(game['engines_used'])}")
    
    # -------------------------------------------------------------------------
    # Test 2: Player prop with teammate out
    # -------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("TEST 2: PLAYER PROP (TEAMMATE OUT)")
    print("=" * 80)
    
    if ENGINES_AVAILABLE['historical']:
        prop = engine.predict_prop(
            player_name="Austin Reaves",
            stat="pts",
            book_line=20.5,
            opponent="BOS",
            player_out="LeBron James"
        )
        
        if 'error' not in prop:
            print(f"\n  🏀 {prop['player']} {prop['stat'].upper()} vs {prop['opponent']}")
            print(f"\n  📊 PROJECTION:")
            print(f"     Base: {prop['base_projection']}")
            print(f"     Matchup Adj: {prop['matchup_adjustment']:+.1f}")
            print(f"     Teammate Out Boost: {prop['teammate_out_boost']:+.1f}")
            print(f"     Final: {prop['final_projection']}")
            print(f"\n  🎯 ANALYSIS:")
            print(f"     Book: {prop['book_line']} | Edge: {prop['edge_pct']:+.1f}%")
            print(f"     Best Bet: {prop['best_bet']} | EV: {prop['ev_pct']:.1f}%")
            print(f"     Grade: {prop['grade']} | Stake: ${prop['stake']:.0f}")
    
    # -------------------------------------------------------------------------
    # Test 3: Full slate analysis
    # -------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("TEST 3: FULL SLATE ANALYSIS")
    print("=" * 80)
    
    slate = [
        {'home_team': 'Celtics', 'away_team': 'Lakers', 'spread': -8.5, 'total': 224.5},
        {'home_team': 'Thunder', 'away_team': 'Cavaliers', 'spread': -2.5, 'total': 228.0},
        {'home_team': 'Knicks', 'away_team': 'Heat', 'spread': -4.0, 'total': 212.5},
    ]
    
    analysis = engine.analyze_slate(slate)
    
    print(f"\n  💰 BET SLIP")
    print(f"     Bankroll: ${analysis['bet_slip']['bankroll']:,}")
    print(f"     Games Analyzed: {analysis['bet_slip']['games_analyzed']}")
    print(f"     Total Picks: {analysis['bet_slip']['total_picks']}")
    print(f"     Total Stake: ${analysis['bet_slip']['total_stake']:.0f}")
    print(f"     Average EV: {analysis['bet_slip']['avg_ev']:.1f}%")
    
    if analysis['bet_slip']['picks']:
        print(f"\n  📋 PICKS:")
        for pick in analysis['bet_slip']['picks'][:5]:
            print(f"     ${pick['stake']:.0f} | {pick['game']} | {pick['pick']} | {pick['grade']}")
    
    # -------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("✅ META-MERGE ENGINE v4.0 - ALL TESTS COMPLETE")
    print("=" * 80)
