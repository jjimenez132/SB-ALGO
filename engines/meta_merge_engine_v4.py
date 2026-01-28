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
# CLV Intelligence for confidence adjustments
try:
    from engines.clv_intelligence import get_clv_intelligence
    CLV_INTEL_ENABLED = True
except ImportError:
    CLV_INTEL_ENABLED = False
    print("⚠️ CLV Intelligence not available")

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

# VEGAS-CALIBRATED PROFITABLE FILTERS v2.0
# Backtested Dec 1 - Jan 21, 2026 (Date-Aware, No Lookahead)
# GAME BETS: 58-17 (77.3%) | +47.7% ROI
# PLAYER PROPS: 62-21 (74.7%) | +42.7% ROI
# COMBINED: 120-38 (75.9%) | +45.1% ROI | ~3.0 picks/day

# =============================================================================
# VEGAS FILTERS v3.0 - TIERED SYSTEM (Jan 2026)
# =============================================================================
# BACKTEST: Dec 1, 2025 - Jan 25, 2026 (56 days)
# HEADLINE (T1+Games): 108-27 (80.0%) | 2.41/day
# FULL VOLUME (All): 135-42 (76.3%) | 3.16/day
# =============================================================================

# =============================================================================
# VEGAS FILTERS v3.0 - TIERED SYSTEM (Jan 2026)
# =============================================================================
# BACKTEST: Dec 1, 2025 - Jan 25, 2026 (56 days)
# HEADLINE (T1+Games): 108-27 (80.0%) | 2.41/day
# FULL VOLUME (All): 135-42 (76.3%) | 3.16/day
# =============================================================================

VEGAS_FILTERS = {
    # =========================================================================
    # TIER 1: ELITE PICKS (81.8% backtest) - 1.5 unit stakes
    # V3 Optimizer: 36-8 record, 0.85 picks/day
    # =========================================================================
    
    # PTS UNDER T1: 80.0% (16-4) | edge>=15%, cv<=0.40, proj>=20
    'prop_pts_under_t1': {
        'edge_max': -15,
        'cv_max': 0.40,
        'min_proj': 20,
        'tier': 1,
        'enabled': True,
    },
    
    # REB OVER T1: 80.0% (4-1) | edge>=25%, cv<=0.30, proj>=10
    'prop_reb_over_t1': {
        'edge_min': 25,
        'cv_max': 0.30,
        'min_proj': 10,
        'tier': 1,
        'enabled': True,
    },
    
    # REB UNDER T1: 83.3% (10-2) | edge>=20%, cv<=0.35, proj>=4
    'prop_reb_under_t1': {
        'edge_max': -20,
        'cv_max': 0.35,
        'min_proj': 4,
        'tier': 1,
        'enabled': True,
    },
    
    # AST UNDER T1: 85.7% (6-1) | edge>=15%, cv<=0.35, proj>=6
    'prop_ast_under_t1': {
        'edge_max': -15,
        'cv_max': 0.35,
        'min_proj': 6,
        'tier': 1,
        'enabled': True,
    },
    
    # PTS OVER: DISABLED in T1 (no filter met 80%+ with volume)
    'prop_pts_over_t1': {
        'edge_min': 50,  # Effectively disabled
        'cv_max': 0.20,
        'min_proj': 30,
        'tier': 1,
        'enabled': False,
    },
    
    # AST OVER: DISABLED in T1 (no filter met 80%+ with volume)
    'prop_ast_over_t1': {
        'edge_min': 50,
        'cv_max': 0.20,
        'min_proj': 15,
        'tier': 1,
        'enabled': False,
    },
    
    # 3PM UNDER: Keep existing (78.6%)
    'prop_3pm_under_t1': {
        'edge_max': -22,
        'cv_max': 0.45,
        'min_proj': 0,
        'tier': 1,
        'enabled': True,
    },
    
    # =========================================================================
    # TIER 2: STRONG PICKS (72.3% backtest) - 1.0 unit stakes
    # V3 Optimizer: 60-23 record, 1.60 picks/day
    # =========================================================================
    
    # PTS UNDER T2: 78.6% (11-3) | edge>=15%, cv<=0.35, proj>=20
    'prop_pts_under_t2': {
        'edge_max': -15,
        'cv_max': 0.35,
        'min_proj': 20,
        'tier': 2,
        'enabled': True,  # Disabled - calibrating
    },
    
    # REB UNDER T2: 70.8% (17-7) | edge>=20%, cv<=0.45, proj>=6
    'prop_reb_under_t2': {
        'edge_max': -20,
        'cv_max': 0.45,
        'min_proj': 6,
        'tier': 2,
        'enabled': True,  # Disabled - calibrating
    },
    
    # AST OVER T2: 70.4% (19-8) | edge>=30%, cv<=0.30, proj>=3
    'prop_ast_over_t2': {
        'edge_min': 30,
        'cv_max': 0.30,
        'min_proj': 3,
        'tier': 2,
        'enabled': True,  # Disabled - calibrating
    },
    
    # AST UNDER T2: 72.2% (13-5) | edge>=10%, cv<=0.35, proj>=6
    'prop_ast_under_t2': {
        'edge_max': -10,
        'cv_max': 0.35,
        'min_proj': 6,
        'tier': 2,
        'enabled': True,  # Disabled - calibrating
    },
    
    # PTS OVER T2: DISABLED (best was 69.7% - moved to T3)
    'prop_pts_over_t2': {
        'edge_min': 50,
        'cv_max': 0.20,
        'min_proj': 30,
        'tier': 2,
        'enabled': False,
    },
    
    # REB OVER T2: DISABLED (best was 65.5% - moved to T3)
    'prop_reb_over_t2': {
        'edge_min': 50,
        'cv_max': 0.20,
        'min_proj': 15,
        'tier': 2,
        'enabled': False,
    },
    
    # =========================================================================
    # TIER 3: VOLUME PICKS (65.9% backtest) - 0.5 unit stakes
    # V3 Optimizer: Additional volume for 4+ picks/day target
    # Only enable if you want more action at slightly lower win rate
    # =========================================================================
    
    # PTS OVER T3: 65.3% (203-108) | edge>=25%, cv<=0.55, proj>=12
    'prop_pts_over_t3': {
        'edge_min': 25,
        'cv_max': 0.55,
        'min_proj': 12,
        'tier': 3,
        'enabled': False,  # Enable for more volume
    },
    
    # PTS UNDER T3: 68.6% (35-16) | edge>=10%, cv<=0.40, proj>=20
    'prop_pts_under_t3': {
        'edge_max': -10,
        'cv_max': 0.40,
        'min_proj': 20,
        'tier': 3,
        'enabled': True,  # Disabled - calibrating
    },
    
    # REB OVER T3: 65.5% (19-10) | edge>=25%, cv<=0.30, proj>=8
    'prop_reb_over_t3': {
        'edge_min': 25,
        'cv_max': 0.30,
        'min_proj': 8,
        'tier': 3,
        'enabled': False,  # Enable for more volume
    },
    
    # REB UNDER T3: 71.4% (20-8) | edge>=20%, cv<=0.45, proj>=5
    'prop_reb_under_t3': {
        'edge_max': -20,
        'cv_max': 0.45,
        'min_proj': 5,
        'tier': 3,
        'enabled': True,  # Disabled - calibrating
    },
    
    # AST OVER T3: 66.0% (33-17) | edge>=30%, cv<=0.55, proj>=6
    'prop_ast_over_t3': {
        'edge_min': 30,
        'cv_max': 0.55,
        'min_proj': 6,
        'tier': 3,
        'enabled': False,  # Enable for more volume
    },
    
    # AST UNDER T3: 69.0% (20-9) | edge>=10%, cv<=0.45, proj>=6
    'prop_ast_under_t3': {
        'edge_max': -10,
        'cv_max': 0.45,
        'min_proj': 5,
        'tier': 3,
        'enabled': True,  # Disabled - calibrating
    },
    
    # =========================================================================
    # GAME FILTERS (Tier 1 only - 78.8% win rate)
    # =========================================================================
    'game_moneyline': {
        'net_diff_min': 5,
        'opp_def_rating_min': 114,
        'opp_off_rating_max': 112,
        'tier': 1,
        'enabled': True,
    },
    'game_under': {
        'combined_def_max': 226,
        'combined_pace_max': 198,
        'book_total_min': 225,
        'book_total_max': 232,
        'tier': 1,
        'enabled': True,
    },
    'game_home_dog': {
        'spread_min': 7,
        'opp_net_max': 5,
        'tier': 1,
        'enabled': True,
    },
    
    # =========================================================================
    # DISABLED FILTERS
    # =========================================================================
    'prop_pra': {
        'edge_min': 15,
        'cv_max': 0.25,
        'min_proj': 35,
        'tier': 0,
        'enabled': False,
    },
    'prop_ra': {
        'edge_min': 18,
        'cv_max': 0.38,
        'min_proj': 11,
        'tier': 0,
        'enabled': False,
    },
}


def get_prop_tier(stat, is_over, edge_pct, cv, proj):
    """
    Determine which tier a prop bet belongs to.
    Returns: (tier, filter_key) where tier is 1, 2, or 0 (no bet)
    
    IMPORTANT: Check Tier 1 FIRST. If it qualifies for T1, don't check T2.
    """
    direction = 'over' if is_over else 'under'
    
    # Map stat names
    stat_map = {'pts': 'pts', 'reb': 'reb', 'ast': 'ast', '3pm': '3pm', 'fg3m': '3pm'}
    stat_key = stat_map.get(stat, stat)
    
    # Build filter keys
    t1_key = f'prop_{stat_key}_{direction}_t1'
    t2_key = f'prop_{stat_key}_{direction}_t2'
    
    # Check Tier 1 first
    if t1_key in VEGAS_FILTERS:
        f = VEGAS_FILTERS[t1_key]
        if f.get('enabled', False):
            cv_ok = cv <= f.get('cv_max', 1.0)
            proj_ok = proj >= f.get('min_proj', 0)
            
            if is_over:
                edge_ok = edge_pct >= f.get('edge_min', 100)
            else:
                edge_ok = edge_pct <= f.get('edge_max', -100)
            
            if cv_ok and proj_ok and edge_ok:
                return 1, t1_key
    
    # Check Tier 2 only if NOT Tier 1
    if t2_key in VEGAS_FILTERS:
        f = VEGAS_FILTERS[t2_key]
        if f.get('enabled', False):
            cv_ok = cv <= f.get('cv_max', 1.0)
            proj_ok = proj >= f.get('min_proj', 0)
            
            if is_over:
                edge_ok = edge_pct >= f.get('edge_min', 100)
            else:
                edge_ok = edge_pct <= f.get('edge_max', -100)
            
            if cv_ok and proj_ok and edge_ok:
                return 2, t2_key
    
    return 0, None


def get_unit_size(tier):
    """Returns unit size based on tier"""
    if tier == 1:
        return 1.0
    elif tier == 2:
        return 0.5
    return 0



class MetaMergeEngine:
    """
    ============================================================================
    META-MERGE ENGINE v4.0 - The Ultimate Orchestrator
    ============================================================================
    """
    
    def __init__(self, bankroll: float = 10000, risk_profile: str = 'moderate'):
        self.db = create_engine(DATABASE_URL)
        self.bankroll = bankroll
        
        # CLV Intelligence
        self.clv_intel = None
        if CLV_INTEL_ENABLED:
            try:
                self.clv_intel = get_clv_intelligence()
            except:
                pass
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
    

    def passes_vegas_filter(self, bet_type: str, home_stats: Dict, away_stats: Dict, 
                            book_total: float = None, home_ml: int = None, away_ml: int = None, book_spread: float = None) -> Tuple[bool, str]:
        """
        Check if a bet passes our backtested Vegas-style filters.
        These filters achieved 65-70% win rates in backtesting.
        
        Returns: (passes: bool, reason: str)
        """
        if not VEGAS_FILTERS.get(bet_type, {}).get('enabled', False):
            return False, "Filter disabled - bet type not allowed"
        
        # Extract stats
        home_off = home_stats.get('advanced', {}).get('OFF_RATING', 110) or 110
        home_def = home_stats.get('advanced', {}).get('DEF_RATING', 114) or 114
        home_pace = home_stats.get('advanced', {}).get('PACE', 100) or 100
        home_net = home_stats.get('advanced', {}).get('NET_RATING', 0) or 0
        
        away_off = away_stats.get('advanced', {}).get('OFF_RATING', 110) or 110
        away_def = away_stats.get('advanced', {}).get('DEF_RATING', 114) or 114
        away_pace = away_stats.get('advanced', {}).get('PACE', 100) or 100
        away_net = away_stats.get('advanced', {}).get('NET_RATING', 0) or 0
        
        combined_def = home_def + away_def
        combined_pace = home_pace + away_pace
        combined_off = home_off + away_off
        
        # Home court advantage (~3 pts)
        HOME_ADV = 3.0
        
        if bet_type == 'moneyline':
            f = VEGAS_FILTERS['moneyline']
            net_diff_home = (home_net + HOME_ADV) - away_net
            net_diff_away = (away_net) - (home_net + HOME_ADV)
            
            # Check if home team qualifies
            if net_diff_home >= f['net_diff_min']:
                if away_def >= f['opp_def_min'] and away_off <= f['opp_off_max']:
                    if home_ml and home_ml >= f['odds_min']:
                        return True, f"HOME ML passes: NetDiff={net_diff_home:.1f}, OppDef={away_def}, OppOff={away_off}"
            
            # Check if away team qualifies
            if net_diff_away >= f['net_diff_min']:
                if home_def >= f['opp_def_min'] and home_off <= f['opp_off_max']:
                    if away_ml and away_ml >= f['odds_min']:
                        return True, f"AWAY ML passes: NetDiff={net_diff_away:.1f}, OppDef={home_def}, OppOff={home_off}"
            
            return False, f"ML filter failed: NetDiff H={net_diff_home:.1f}/A={net_diff_away:.1f}"
        
        elif bet_type == 'under':
            f = VEGAS_FILTERS['under']
            if book_total is None:
                return False, "No book total"
            
            if (combined_def <= f['combined_def_max'] and 
                combined_pace <= f['combined_pace_max'] and
                f['book_total_min'] <= book_total <= f['book_total_max']):
                return True, f"UNDER passes: CombDef={combined_def}, CombPace={combined_pace:.1f}, Book={book_total}"
            
            return False, f"UNDER filter failed: CombDef={combined_def}, CombPace={combined_pace:.1f}, Book={book_total}"
        
        elif bet_type == 'over':
            f = VEGAS_FILTERS['over']
            if book_total is None:
                return False, "No book total"
            
            if (combined_def >= f['combined_def_min'] and 
                combined_pace >= f['combined_pace_min'] and
                combined_off >= f['combined_off_min']):
                return True, f"OVER passes: CombDef={combined_def}, CombPace={combined_pace:.1f}, CombOff={combined_off}"
            
            return False, f"OVER filter failed: CombDef={combined_def}, CombPace={combined_pace:.1f}, CombOff={combined_off}"
        
        elif bet_type == 'spread_favorite':
            f = VEGAS_FILTERS['spread_favorite']
            if not f.get('enabled', False):
                return False, "Spread favorite filter disabled"
            
            net_diff_home = (home_net + HOME_ADV) - away_net
            net_diff_away = away_net - (home_net + HOME_ADV)
            opp_def_min = f.get('opp_def_min', 0)
            
            if book_spread is not None:
                spread = float(book_spread) if hasattr(book_spread, '__float__') else book_spread
                
                # Home favorite: spread is negative, not too big, opponent has bad defense
                if spread < 0 and abs(spread) <= f['spread_max'] and net_diff_home >= f['net_diff_min']:
                    if away_def >= opp_def_min:
                        return True, f"HOME FAV passes: NetDiff={net_diff_home:.1f}, Spread={spread}, OppDef={away_def}"
                
                # Away favorite: spread is positive, away has edge, home has bad defense
                if spread > 0 and spread <= f['spread_max'] and net_diff_away >= f['net_diff_min']:
                    if home_def >= opp_def_min:
                        return True, f"AWAY FAV passes: NetDiff={net_diff_away:.1f}, Spread={spread}, OppDef={home_def}"
            
            return False, f"Spread favorite filter failed"
        
        elif bet_type == 'spread_home_dog':
            f = VEGAS_FILTERS['spread_home_dog']
            if not f.get('enabled', False):
                return False, "Spread home dog filter disabled"
            
            opp_net_max = f.get('opp_net_max', 999)
            
            if book_spread is not None:
                spread = float(book_spread) if hasattr(book_spread, '__float__') else book_spread
                
                # Home is underdog when spread is positive
                # Away team (opponent) shouldn't be too dominant
                if spread >= f['home_spread_min'] and away_net <= opp_net_max:
                    return True, f"HOME DOG passes: Spread=+{spread}, OppNet={away_net}"
            
            return False, f"Home dog filter failed"
        
        return True, "Unknown bet type"


    def get_team_stats(self, team_name: str) -> Dict:
        """Get COMPREHENSIVE team stats from ALL available tables"""
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
        
        full_name = TEAM_MAP.get(team_name.upper(), team_name)
        result = {}
        
        with self.db.connect() as conn:
            # 1. Advanced Stats (pace, ratings)
            adv = conn.execute(text("""
                SELECT * FROM nba_team_advanced_stats
                WHERE "TEAM_NAME" ILIKE :team ORDER BY pull_date DESC LIMIT 1
            """), {"team": f"%{full_name}%"}).fetchone()
            if adv:
                result['advanced'] = dict(adv._mapping)
            
            # 2. Four Factors (Dean Oliver's keys to winning)
            ff = conn.execute(text("""
                SELECT * FROM nba_team_four_factors
                WHERE "TEAM_NAME" ILIKE :team ORDER BY pull_date DESC LIMIT 1
            """), {"team": f"%{full_name}%"}).fetchone()
            if ff:
                result['four_factors'] = dict(ff._mapping)
            
            # 3. Opponent Stats (defensive performance)
            opp = conn.execute(text("""
                SELECT * FROM nba_team_opponent_stats
                WHERE "TEAM_NAME" ILIKE :team ORDER BY pull_date DESC LIMIT 1
            """), {"team": f"%{full_name}%"}).fetchone()
            if opp:
                result['opponent'] = dict(opp._mapping)
            
            # 4. Clutch Stats (close game performance)
            clutch = conn.execute(text("""
                SELECT * FROM nba_team_clutch
                WHERE "TEAM_NAME" ILIKE :team ORDER BY pull_date DESC LIMIT 1
            """), {"team": f"%{full_name}%"}).fetchone()
            if clutch:
                result['clutch'] = dict(clutch._mapping)
            
            # 5. Hustle Stats (effort metrics)
            hustle = conn.execute(text("""
                SELECT * FROM nba_team_hustle
                WHERE "TEAM_NAME" ILIKE :team ORDER BY pull_date DESC LIMIT 1
            """), {"team": f"%{full_name}%"}).fetchone()
            if hustle:
                result['hustle'] = dict(hustle._mapping)
            
            # 6. Base Stats 
            base = conn.execute(text("""
                SELECT * FROM nba_team_base_stats
                WHERE "TEAM_NAME" ILIKE :team ORDER BY pull_date DESC LIMIT 1
            """), {"team": f"%{full_name}%"}).fetchone()
            if base:
                result['base'] = dict(base._mapping)
            
            # 7. Scoring breakdown
            scoring = conn.execute(text("""
                SELECT * FROM nba_team_scoring
                WHERE "TEAM_NAME" ILIKE :team ORDER BY pull_date DESC LIMIT 1
            """), {"team": f"%{full_name}%"}).fetchone()
            if scoring:
                result['scoring'] = dict(scoring._mapping)

            
            # 9. Derived Team Stats
            derived = conn.execute(text("""
                SELECT * FROM nba_derived_team_stats
                WHERE "TEAM_ABBREVIATION" ILIKE :team ORDER BY pull_date DESC LIMIT 1
            """), {"team": f"%{full_name.split()[-1]}%"}).fetchone()
            if derived:
                result['derived'] = dict(derived._mapping)
        
        return result if result.get('advanced') else None

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
                     b2b_away: bool = False,
                     spread_odds: int = -110,
                     over_odds: int = -110,
                     under_odds: int = -110) -> Dict:
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
        # STEP 3: BASE PREDICTIONS (USING ALL 8 DATA TABLES)
        # =====================================================================
        home_stats = self.get_team_stats(home_team)
        away_stats = self.get_team_stats(away_team)
        
        if not home_stats or not away_stats:
            result['error'] = f"Team data not found"
            return result
        
        # === ADVANCED STATS ===
        home_net = home_stats['advanced'].get('NET_RATING', 0) or 0
        away_net = away_stats['advanced'].get('NET_RATING', 0) or 0
        home_pace = home_stats['advanced'].get('PACE', 100) or 100
        away_pace = away_stats['advanced'].get('PACE', 100) or 100
        home_off = home_stats['advanced'].get('OFF_RATING', 110) or 110
        home_def = home_stats['advanced'].get('DEF_RATING', 110) or 110
        away_off = away_stats['advanced'].get('OFF_RATING', 110) or 110
        away_def = away_stats['advanced'].get('DEF_RATING', 110) or 110
        
        # === FOUR FACTORS (Dean Oliver's Keys) ===
        home_ff = home_stats.get('four_factors', {})
        away_ff = away_stats.get('four_factors', {})
        
        # Effective FG% differential
        home_efg = home_ff.get('EFG_PCT', 0.50) or 0.50
        away_efg = away_ff.get('EFG_PCT', 0.50) or 0.50
        home_opp_efg = home_ff.get('OPP_EFG_PCT', 0.50) or 0.50
        away_opp_efg = away_ff.get('OPP_EFG_PCT', 0.50) or 0.50
        
        # Turnover differential
        home_tov = home_ff.get('TM_TOV_PCT', 0.14) or 0.14
        away_tov = away_ff.get('TM_TOV_PCT', 0.14) or 0.14
        home_opp_tov = home_ff.get('OPP_TOV_PCT', 0.14) or 0.14
        away_opp_tov = away_ff.get('OPP_TOV_PCT', 0.14) or 0.14
        
        # Rebounding
        home_oreb = home_ff.get('OREB_PCT', 0.25) or 0.25
        away_oreb = away_ff.get('OREB_PCT', 0.25) or 0.25
        
        # FT Rate
        home_fta = home_ff.get('FTA_RATE', 0.25) or 0.25
        away_fta = away_ff.get('FTA_RATE', 0.25) or 0.25
        
        # Four Factors Score (weighted by importance)
        # Shooting (40%), Turnovers (25%), Rebounding (20%), FT (15%)
        home_ff_score = (home_efg - away_opp_efg) * 40 + (away_tov - home_tov) * 25 + (home_oreb - 0.25) * 20 + (home_fta - 0.25) * 15
        away_ff_score = (away_efg - home_opp_efg) * 40 + (home_tov - away_tov) * 25 + (away_oreb - 0.25) * 20 + (away_fta - 0.25) * 15
        ff_adjustment = (home_ff_score - away_ff_score) * 0.1  # Scale to points
        
        # === OPPONENT STATS (Defensive Quality) ===
        home_opp = home_stats.get('opponent', {})
        away_opp = away_stats.get('opponent', {})
        
        home_opp_pts = home_opp.get('OPP_PTS', 110) or 110
        away_opp_pts = away_opp.get('OPP_PTS', 110) or 110
        home_opp_fg3 = home_opp.get('OPP_FG3_PCT', 0.36) or 0.36
        away_opp_fg3 = away_opp.get('OPP_FG3_PCT', 0.36) or 0.36
        
        # Defense adjustment (better defense = lower opponent points)
        league_avg_pts = 114
        home_def_factor = home_opp_pts / league_avg_pts
        away_def_factor = away_opp_pts / league_avg_pts
        
        # === CLUTCH STATS ===
        home_clutch = home_stats.get('clutch', {})
        away_clutch = away_stats.get('clutch', {})
        
        home_clutch_wp = home_clutch.get('W_PCT', 0.50) or 0.50
        away_clutch_wp = away_clutch.get('W_PCT', 0.50) or 0.50
        home_clutch_pm = home_clutch.get('PLUS_MINUS', 0) or 0
        away_clutch_pm = away_clutch.get('PLUS_MINUS', 0) or 0
        
        # Clutch adjustment (for close games / spread)
        clutch_adjustment = (home_clutch_wp - away_clutch_wp) * 3  # Up to 1.5 pts
        
        # === HUSTLE STATS ===
        home_hustle = home_stats.get('hustle', {})
        away_hustle = away_stats.get('hustle', {})
        
        home_deflections = home_hustle.get('DEFLECTIONS', 14) or 14
        away_deflections = away_hustle.get('DEFLECTIONS', 14) or 14
        home_contested = home_hustle.get('CONTESTED_SHOTS', 50) or 50
        away_contested = away_hustle.get('CONTESTED_SHOTS', 50) or 50
        home_loose = home_hustle.get('LOOSE_BALLS_RECOVERED', 5) or 5
        away_loose = away_hustle.get('LOOSE_BALLS_RECOVERED', 5) or 5
        
        # Hustle score (effort = extra possessions)
        home_hustle_score = (home_deflections - 14) * 0.3 + (home_contested - 50) * 0.05 + (home_loose - 5) * 0.4
        away_hustle_score = (away_deflections - 14) * 0.3 + (away_contested - 50) * 0.05 + (away_loose - 5) * 0.4
        hustle_adjustment = (home_hustle_score - away_hustle_score) * 0.5
        
        # === SCORING BREAKDOWN ===
        home_scoring = home_stats.get('scoring', {})
        away_scoring = away_stats.get('scoring', {})
        
        # Fast break and paint points indicate pace/style
        home_fb = home_scoring.get('PCT_PTS_FB', 0.12) or 0.12
        away_fb = away_scoring.get('PCT_PTS_FB', 0.12) or 0.12
        home_paint = home_scoring.get('PCT_PTS_PAINT', 0.45) or 0.45
        away_paint = away_scoring.get('PCT_PTS_PAINT', 0.45) or 0.45
        
        # === DERIVED STATS (Rest, Travel, B2B) ===
        home_derived = home_stats.get('derived', {})
        away_derived = away_stats.get('derived', {})
        
        home_rest = home_derived.get('REST_DAYS', 1) or 1
        away_rest = away_derived.get('REST_DAYS', 1) or 1
        home_b2b = home_derived.get('IS_B2B', False) or False
        away_b2b = away_derived.get('IS_B2B', False) or False
        
        # Rest advantage (each rest day = ~1 pt advantage, B2B = -2.5 pts)
        rest_adjustment = (home_rest - away_rest) * 1.0
        if home_b2b:
            rest_adjustment -= 2.5
        if away_b2b:
            rest_adjustment += 2.5
        
        # =====================================================================
        # FINAL CALCULATIONS
        # =====================================================================
        
        # Home court advantage
        home_court = 2.8
        
        # Base margin from net rating
        base_margin = (home_net - away_net) + home_court
        
        # Apply ALL adjustments
        predicted_margin = (
            base_margin 
            + injury_spread_adj 
            + ff_adjustment 
            + clutch_adjustment 
            + hustle_adjustment 
            + rest_adjustment
        )
        predicted_spread = -predicted_margin
        
        # === TOTAL CALCULATION ===
        # Game pace is weighted average of both teams
        game_pace = (home_pace + away_pace) / 2
        
        # Standard NBA points formula:
        # Points = Pace * OffRtg / 100, adjusted for opponent defense
        # League average OffRtg ~114, DefRtg ~114
        LEAGUE_AVG_DEF = 114.0
        
        # Adjust offensive rating based on opponent defense
        # If opponent defense is worse than avg (higher DefRtg), team scores more
        home_pts = game_pace * home_off / 100 * (away_def / LEAGUE_AVG_DEF)
        away_pts = game_pace * away_off / 100 * (home_def / LEAGUE_AVG_DEF)
        
        # Apply defense factors from other calculations
        home_pts *= away_def_factor
        away_pts *= home_def_factor
        
        # Apply injury and pace adjustments
        predicted_total = home_pts + away_pts + injury_total_adj
        
        # Fast break teams in fast-paced games = more points
        if (home_fb > 0.14 or away_fb > 0.14) and game_pace > 100:
            predicted_total += 2.0
        
        # Standard deviations (adjusted by data quality)
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
        
        result['adjustments'] = {
            'base_margin': round(base_margin, 2),
            'injury': round(injury_spread_adj, 2),
            'four_factors': round(ff_adjustment, 2),
            'clutch': round(clutch_adjustment, 2),
            'hustle': round(hustle_adjustment, 2),
            'rest': round(rest_adjustment, 2),
            'home_def_factor': round(home_def_factor, 3),
            'away_def_factor': round(away_def_factor, 3),
        }
        
        result['data_sources'] = {
            'tables_used': list(home_stats.keys()),
            'total_tables': len(home_stats.keys()),
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
            
            # Apply Vegas spread filters FIRST (backtested 65%+ win rate)
            passes_fav, fav_reason = self.passes_vegas_filter(
                'spread_favorite', home_stats, away_stats, book_spread=book_spread
            )
            passes_dog, dog_reason = self.passes_vegas_filter(
                'spread_home_dog', home_stats, away_stats, book_spread=book_spread
            )
            
            # CRITICAL: Match filter to picked side
            # best_side is 'HOME' or 'AWAY' based on model prediction
            # If home_dog filter passes, we should ONLY bet if picking HOME side
            # If favorite filter passes, we should ONLY bet the favorite side
            
            passes_spread_filter = False
            spread_filter_reason = ""
            
            if passes_dog and best_side == 'HOME':
                # Home dog filter passed AND we're picking the home dog - GOOD
                passes_spread_filter = True
                spread_filter_reason = dog_reason
            elif passes_fav:
                # Favorite filter passed - check if we're picking the correct side
                # If spread < 0, home is favorite, best_side should be HOME
                # If spread > 0, away is favorite, best_side should be AWAY
                if book_spread < 0 and best_side == 'HOME':
                    passes_spread_filter = True
                    spread_filter_reason = fav_reason
                elif book_spread > 0 and best_side == 'AWAY':
                    passes_spread_filter = True
                    spread_filter_reason = fav_reason
            
            if passes_spread_filter:
                result['spread_vegas_filter'] = spread_filter_reason
                # Vegas filter passed - now check Kelly for sizing
                if self.kelly:
                    kelly_result = self.kelly.calculate_bet(calibrated_prob, spread_odds, self.bankroll)
                    if kelly_result.get('should_bet'):
                        kelly_stake = kelly_result['recommended_amount'] * kelly_multiplier
                        grade = kelly_result['grade']
                    else:
                        # Kelly says no, but Vegas filter passed - use minimum stake
                        kelly_stake = self.bankroll * 0.01  # 1% of bankroll
                        grade = 'C'
                    should_bet = True
                    result['engines_used'].append('kelly')
            else:
                result['spread_vegas_filter_rejected'] = f"Side mismatch or filter failed: {fav_reason} | {dog_reason}"
            
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
                'odds': spread_odds,
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
                total_odds = over_odds if best_bet.startswith('OVER') else under_odds
                kelly_result = self.kelly.calculate_bet(calibrated_prob, total_odds, self.bankroll)
                if kelly_result.get('should_bet'):
                    # Apply Vegas filter for totals (backtested 69% win rate)
                    filter_type = 'over' if best_bet.startswith('OVER') else 'under'
                    passes_filter, filter_reason = self.passes_vegas_filter(
                        filter_type, home_stats, away_stats, book_total
                    )
                    if passes_filter:
                        kelly_stake = kelly_result['recommended_amount'] * kelly_multiplier
                        grade = kelly_result['grade']
                        should_bet = True
                        result['vegas_filter'] = filter_reason
                    else:
                        result['vegas_filter_rejected'] = filter_reason
            
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
                'odds': total_odds if 'total_odds' in dir() else (over_odds if best_bet.startswith('OVER') else under_odds),
            }
            
            if should_bet:
                picks.append(total_pick)
            
            result['total_analysis'] = total_pick
        
        # =====================================================================
        # STEP 5: MONEYLINE ANALYSIS (with Vegas Filter - 70.6% win rate)
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
            
            # Determine best ML pick
            if ml_edge > 0:
                ml_pick_team = home_team
                ml_pick_odds = home_ml
                ml_win_prob = home_win_prob
            else:
                ml_pick_team = away_team
                ml_pick_odds = away_ml
                ml_win_prob = 1 - home_win_prob
            
            result['moneyline_analysis'] = {
                'home_win_prob': round(home_win_prob, 4),
                'away_win_prob': round(1 - home_win_prob, 4),
                'home_implied': round(home_implied, 4),
                'edge_pct': round(ml_edge, 2),
                'best_bet': f"{ml_pick_team} ML",
            }
            
            # Apply Vegas ML Filter (backtested 70.6% win rate, +28.6% ROI)
            passes_ml_filter, ml_filter_reason = self.passes_vegas_filter(
                'moneyline', home_stats, away_stats, 
                home_ml=home_ml, away_ml=away_ml
            )
            
            ml_should_bet = False
            ml_kelly_stake = 0
            ml_grade = 'N/A'
            
            if passes_ml_filter and abs(ml_edge) >= EDGE_THRESHOLDS['moneyline']:
                # Calculate Kelly for ML
                if self.kelly and ml_win_prob > 0.55:
                    kelly_result = self.kelly.calculate_bet(ml_win_prob, ml_pick_odds, self.bankroll)
                    if kelly_result.get('should_bet'):
                        ml_kelly_stake = kelly_result['recommended_amount'] * kelly_multiplier
                        ml_grade = kelly_result['grade']
                        ml_should_bet = True
                        result['ml_vegas_filter'] = ml_filter_reason
            else:
                result['ml_vegas_filter_rejected'] = ml_filter_reason
            
            ml_pick = {
                'type': 'MONEYLINE',
                'pick': f"{ml_pick_team} ML",
                'raw_prob': round(ml_win_prob, 4),
                'calibrated_prob': round(ml_win_prob, 4),
                'edge': round(abs(ml_edge), 1),
                'ev_pct': round((ml_win_prob * (100/abs(ml_pick_odds) if ml_pick_odds < 0 else ml_pick_odds/100) - (1-ml_win_prob)) * 100, 2),
                'grade': ml_grade,
                'stake': round(ml_kelly_stake, 2),
                'should_bet': ml_should_bet,
                'odds': ml_pick_odds,
                'vegas_filter': ml_filter_reason if passes_ml_filter else f"REJECTED: {ml_filter_reason}",
            }
            
            if ml_should_bet:
                picks.append(ml_pick)
            
            result['moneyline_pick'] = ml_pick
        
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
        
        # CLV Intelligence adjustment
        clv_adjustment = None
        if self.clv_intel:
            clv_adjustment = self.clv_intel.get_confidence_adjustment(stat)
            if clv_adjustment['clv_rating'] != 'UNKNOWN':
                # Adjust probability based on historical CLV performance
                calibrated_prob = min(0.95, calibrated_prob * clv_adjustment['multiplier'])
        
        # EV and Kelly
        ev_pct = (calibrated_prob * 0.909) - ((1 - calibrated_prob) * 1)
        ev_pct *= 100
        
        kelly_stake = 0
        grade = 'N/A'
        should_bet = False
        
        # =====================================================================
        # TIERED PROP FILTERS v3.0 (Jan 2026)
        # =====================================================================
        # BACKTEST: Dec 1, 2025 - Jan 25, 2026 (56 days)
        # 
        # HEADLINE (T1 + Games): 108-27 (80.0%) | 2.41/day | 1.0 units
        # FULL VOLUME (T1 + T2 + Games): 128-34 (79.0%) | 2.89/day
        #
        # TIER 1 Props: 82-20 (80.4%) | 1.82/day | 1.0 units
        # TIER 2 Props (reb_under + ast_under only): 20-7 (74.1%) | 0.48/day | 0.5 units
        # Games: 26-7 (78.8%) | 0.59/day | 1.0 units
        # =====================================================================
        
        cv = (std_dev / final_proj) if final_proj > 0 else 999
        is_over_bet = over_prob > 0.5
        
        # Use the get_prop_tier function to determine tier
        pick_tier, filter_key = get_prop_tier(stat, is_over_bet, edge_pct, cv, final_proj)
        
        passes_prop_filter = pick_tier > 0
        unit_size = get_unit_size(pick_tier)
        
        if pick_tier == 1:
            tier_label = "🔥 TIER 1 (80%)"
            result['prop_filter'] = f"{tier_label}: {filter_key} | Edge {edge_pct:.1f}%, CV {cv:.2f}, Proj {final_proj:.1f}"
            result['pick_tier'] = 1
        elif pick_tier == 2:
            tier_label = "✅ TIER 2 (Volume)"
            result['prop_filter'] = f"{tier_label}: {filter_key} | Edge {edge_pct:.1f}%, CV {cv:.2f}, Proj {final_proj:.1f}"
            result['pick_tier'] = 2
        else:
            result['prop_filter_rejected'] = f"No tier match: {stat} {'OVER' if is_over_bet else 'UNDER'} | Edge {edge_pct:.1f}%, CV {cv:.2f}, Proj {final_proj:.1f}"
            result['pick_tier'] = 0
        
        if passes_prop_filter and self.kelly and calibrated_prob > 0.52:
            kelly_result = self.kelly.calculate_bet(calibrated_prob, -110, self.bankroll)
            if kelly_result.get('should_bet'):
                # Apply tier-based unit sizing (T1 = 1.0, T2 = 0.5)
                kelly_stake = kelly_result['recommended_amount'] * unit_size
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
            
            # CLV Intelligence data
            'clv_rating': clv_adjustment.get('clv_rating', 'N/A') if clv_adjustment else 'N/A',
            'clv_multiplier': clv_adjustment.get('multiplier', 1.0) if clv_adjustment else 1.0,
            'clv_reason': clv_adjustment.get('reason', 'No CLV data') if clv_adjustment else 'No CLV data',
            'clv_avg': clv_adjustment.get('avg_clv', 0) if clv_adjustment else 0,
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
                spread_odds=game.get('spread_odds', -110),
                over_odds=game.get('over_odds', -110),
                under_odds=game.get('under_odds', -110),
            )
            
            game_results.append(result)
            
            # Collect picks with FULL context for explanations
            for pick in result.get('picks', []):
                pick['game'] = result['matchup']
                # Add prediction data for explanation engine
                if 'predictions' in result:
                    pick['model_total'] = result['predictions'].get('total')
                    pick['model_home_pts'] = result['predictions'].get('home_pts')
                    pick['model_away_pts'] = result['predictions'].get('away_pts')
                    pick['model_pace'] = result['predictions'].get('pace')
                    pick['model_margin'] = result['predictions'].get('margin')
                # Add regime data
                if 'regime' in result:
                    pick['regime_status'] = result['regime'].get('status')
                    pick['regime_confidence'] = result['regime'].get('confidence')
                # Add injury data
                if 'injuries' in result:
                    pick['injury_adjustment'] = result['injuries'].get('total_adjustment', 0)
                    pick['injury_edge'] = result['injuries'].get('edge_for', 'NEUTRAL')
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
