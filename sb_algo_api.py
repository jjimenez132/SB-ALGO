#!/usr/bin/env python3
"""
================================================================================
SB-ALGO PICKS API v2.0 - STRICT FILTERS
================================================================================
This module provides the interface between the Streamlit dashboard and the
SB-ALGO engine. Import this to get real picks from the algorithm.

FILTER LOGIC (v2.0):
--------------------
Output: TOP 2 GAMES + TOP 2 PROPS = 4 PICKS MAX

GAMES Filter:
  - Edge % >= 30%
  - EV % > 0
  - Confidence >= 70%
  - Rank by: Edge % (highest first)
  - Select: Top 2

PROPS Filter:
  - Edge % >= 30%
  - Hit Rate >= 60%
  - EV % > 0
  - GP >= 15
  - Score = (0.5 * Edge) + (0.3 * Hit Rate) + (0.2 * EV)
  - Select: Top 2 by Score

Usage in app.py:
    from sb_algo_api import get_todays_picks, get_game_picks, get_prop_picks

================================================================================
"""

import os
import sys
from datetime import date, datetime
from typing import Dict, List, Optional
import json

# Add engines directory to path
ENGINES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'engines')
sys.path.insert(0, ENGINES_DIR)

# =============================================================================
# STRICT FILTER THRESHOLDS
# =============================================================================
MIN_EDGE_PCT = 30.0          # Minimum edge to consider
MIN_CONFIDENCE = 70          # Minimum model confidence
MIN_HIT_RATE = 0.60          # Minimum hit rate for props
MIN_EV = 0                   # EV must be positive

MAX_GAME_PICKS = 2           # Top 2 games only
MAX_PROP_PICKS = 2           # Top 2 props only
MAX_TOTAL_PICKS = 4          # Never more than 4 picks


class SBAlgoAPI:
    """
    API interface to SB-ALGO engine for the dashboard.
    Caches results to avoid re-running analysis on every page load.
    """
    
    _instance = None
    _cache = {}
    _cache_date = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        self.bankroll = float(os.getenv('SB_ALGO_BANKROLL', 10000))
        self.risk_profile = os.getenv('SB_ALGO_RISK', 'moderate')
    
    def _run_analysis(self, force: bool = False) -> Dict:
        """Run the SB-ALGO analysis (cached per day)"""
        today = date.today()
        
        # Return cached if same day and not forcing refresh
        if not force and self._cache_date == today and self._cache:
            return self._cache
        
        try:
            from sb_algo import SBAlgoMaster
            
            master = SBAlgoMaster(
                bankroll=self.bankroll,
                risk_profile=self.risk_profile
            )
            
            results = master.run(games=True, props=True)
            
            self._cache = {
                'date': str(today),
                'timestamp': datetime.now().isoformat(),
                'bankroll': self.bankroll,
                'game_picks': master.game_picks,
                'prop_picks': master.prop_picks,
                'all_picks': master.all_picks,
                'summary': {
                    'total_picks': len(master.all_picks),
                    'game_picks_count': len(master.game_picks),
                    'prop_picks_count': len(master.prop_picks),
                    'total_stake': sum(p.get('stake', 0) for p in master.all_picks),
                    'avg_ev': sum(p.get('ev', 0) for p in master.all_picks) / len(master.all_picks) if master.all_picks else 0,
                }
            }
            self._cache_date = today
            
            return self._cache
            
        except Exception as e:
            print(f"SB-ALGO API Error: {e}")
            import traceback
            traceback.print_exc()
            return {
                'error': str(e),
                'date': str(today),
                'game_picks': [],
                'prop_picks': [],
                'all_picks': [],
                'summary': {
                    'total_picks': 0,
                    'game_picks_count': 0,
                    'prop_picks_count': 0,
                    'total_stake': 0,
                    'avg_ev': 0,
                }
            }
    
    def _filter_game_picks(self, game_picks: List[Dict]) -> List[Dict]:
        """
        Apply strict filters to game picks.
        Returns TOP 2 games sorted by edge.
        """
        filtered = []
        
        for p in game_picks:
            # Extract edge value
            edge = p.get('edge', 0)
            if isinstance(edge, str):
                edge = float(edge.replace('+', '').replace('%', ''))
            
            # Extract confidence
            confidence = p.get('confidence', 0)
            if isinstance(confidence, str):
                confidence = float(confidence.replace('%', ''))
            
            # Extract EV
            ev = p.get('ev_pct', p.get('ev', 0))
            if isinstance(ev, str):
                ev = float(ev.replace('%', ''))
            
            # Apply filters
            if edge >= MIN_EDGE_PCT and confidence >= MIN_CONFIDENCE and ev > MIN_EV:
                p['_edge_numeric'] = edge
                p['_confidence_numeric'] = confidence
                p['_ev_numeric'] = ev
                filtered.append(p)
        
        # Sort by edge (highest first) and take top 2
        filtered.sort(key=lambda x: x.get('_edge_numeric', 0), reverse=True)
        
        return filtered[:MAX_GAME_PICKS]
    
    def _filter_prop_picks(self, prop_picks: List[Dict]) -> List[Dict]:
        """
        Apply strict filters to prop picks.
        Returns TOP 2 props sorted by composite score.
        Score = (0.5 * Edge) + (0.3 * Hit Rate * 100) + (0.2 * EV)
        """
        filtered = []
        
        for p in prop_picks:
            # Extract edge value
            edge = p.get('edge_pct', p.get('edge', 0))
            if isinstance(edge, str):
                edge = float(edge.replace('+', '').replace('%', ''))
            
            # Extract hit rate (convert to 0-100 scale)
            hit_rate_data = p.get('filters', {}).get('hit_rate', {})
            hit_rate = hit_rate_data.get('hit_rate', 0) if isinstance(hit_rate_data, dict) else 0
            if hit_rate <= 1:  # If it's a decimal like 0.75
                hit_rate = hit_rate * 100
            
            # Extract EV
            ev = p.get('ev_pct', p.get('ev', 0))
            if isinstance(ev, str):
                ev = float(ev.replace('%', ''))
            
            # Extract GP
            gp = p.get('filters', {}).get('gp', 0)
            # gp is a number, already extracted
            
            # Apply filters
            if edge >= MIN_EDGE_PCT and hit_rate >= (MIN_HIT_RATE * 100) and ev > MIN_EV and gp >= 15:
                # Calculate composite score
                score = (0.5 * edge) + (0.3 * hit_rate) + (0.2 * ev)
                
                p['_edge_numeric'] = edge
                p['_hit_rate_numeric'] = hit_rate
                p['_ev_numeric'] = ev
                p['_score'] = score
                filtered.append(p)
        
        # Sort by composite score (highest first) and take top 2
        filtered.sort(key=lambda x: x.get('_score', 0), reverse=True)
        
        return filtered[:MAX_PROP_PICKS]
    
    def get_all_picks(self, force_refresh: bool = False) -> Dict:
        """Get all picks (games + props)"""
        return self._run_analysis(force=force_refresh)
    
    def get_game_picks(self, force_refresh: bool = False) -> List[Dict]:
        """Get only game picks (filtered)"""
        results = self._run_analysis(force=force_refresh)
        return self._filter_game_picks(results.get('game_picks', []))
    
    def get_prop_picks(self, force_refresh: bool = False) -> List[Dict]:
        """Get only prop picks (filtered)"""
        results = self._run_analysis(force=force_refresh)
        return self._filter_prop_picks(results.get('prop_picks', []))
    
    def get_all_picks_unfiltered(self, force_refresh: bool = False) -> Dict:
        """Get ALL picks without strict filters (for dashboard analysis view)"""
        return self._run_analysis(force=force_refresh)
    
    def get_summary(self, force_refresh: bool = False) -> Dict:
        """Get summary stats"""
        results = self._run_analysis(force=force_refresh)
        return results.get('summary', {})
    
    def format_for_dashboard(self, force_refresh: bool = False) -> Dict:
        """
        Format picks for Streamlit dashboard display.
        Returns FILTERED data (Top 2 games + Top 2 props).
        """
        results = self._run_analysis(force=force_refresh)
        
        # Get filtered picks
        filtered_games = self._filter_game_picks(results.get('game_picks', []))
        filtered_props = self._filter_prop_picks(results.get('prop_picks', []))
        
        # Format game picks for display
        game_picks_display = []
        for p in filtered_games:
            edge = p.get('_edge_numeric', p.get('edge', 0))
            if isinstance(edge, str):
                edge = float(edge.replace('+', '').replace('%', ''))
            
            game_picks_display.append({
                'matchup': p.get('game_id', 'Unknown'),
                'pick': p.get('pick', 'Unknown'),
                'type': p.get('type', 'Unknown'),
                'edge': f"+{edge:.1f}%",
                'ev': f"{p.get('_ev_numeric', p.get('ev_pct', 0)):.1f}%",
                'confidence': f"{p.get('_confidence_numeric', p.get('confidence', 0)):.0f}%",
                'grade': p.get('grade', 'A+'),
                'stake': f"${p.get('stake', 0):.0f}",
            })
        
        # Format prop picks for display
        prop_picks_display = []
        for p in filtered_props:
            edge = p.get('_edge_numeric', p.get('edge_pct', 0))
            hit_rate = p.get('_hit_rate_numeric', 0)
            
            prop_picks_display.append({
                'player': p.get('player', 'Unknown'),
                'prop': f"{p.get('stat', '').upper()} {p.get('best_side', '')} {p.get('book_line', '')}",
                'model': p.get('projection', {}).get('weighted', 0),
                'line': p.get('book_line', 0),
                'hit_rate': f"{hit_rate:.0f}%",
                'edge': f"+{edge:.1f}%",
                'ev': f"{p.get('_ev_numeric', p.get('ev_pct', 0)):.1f}%",
                'grade': p.get('grade', 'A+'),
                'stake': f"${p.get('stake', 0):.0f}",
                'score': f"{p.get('_score', 0):.1f}",
            })
        
        # Calculate summary for filtered picks
        all_filtered = filtered_games + filtered_props
        total_stake = sum(
            float(str(p.get('stake', 0)).replace('$', '').replace(',', '')) 
            for p in all_filtered
        )
        
        avg_ev = 0
        if all_filtered:
            evs = []
            for p in filtered_games:
                evs.append(p.get('_ev_numeric', 0))
            for p in filtered_props:
                evs.append(p.get('_ev_numeric', 0))
            avg_ev = sum(evs) / len(evs) if evs else 0
        
        return {
            'date': results.get('date', str(date.today())),
            'timestamp': results.get('timestamp', datetime.now().isoformat()),
            'game_picks': game_picks_display,
            'prop_picks': prop_picks_display,
            'total_picks': len(all_filtered),
            'total_stake': f"${total_stake:,.0f}",
            'avg_ev': f"{avg_ev:.1f}%",
            'edges_found': len(all_filtered),
            # Also include unfiltered counts for reference
            '_unfiltered_games': len(results.get('game_picks', [])),
            '_unfiltered_props': len(results.get('prop_picks', [])),
        }


# Singleton instance
_api = SBAlgoAPI()


# Convenience functions for easy import
def get_todays_picks(force_refresh: bool = False) -> Dict:
    """Get all of today's picks formatted for dashboard (FILTERED: Top 2 + Top 2)"""
    return _api.format_for_dashboard(force_refresh)


def get_game_picks(force_refresh: bool = False) -> List[Dict]:
    """Get today's game picks (FILTERED: Top 2)"""
    return _api.get_game_picks(force_refresh)


def get_prop_picks(force_refresh: bool = False) -> List[Dict]:
    """Get today's prop picks (FILTERED: Top 2)"""
    return _api.get_prop_picks(force_refresh)


def get_all_picks_unfiltered(force_refresh: bool = False) -> Dict:
    """Get ALL picks without strict filters (for analysis)"""
    return _api.get_all_picks_unfiltered(force_refresh)


def get_picks_summary(force_refresh: bool = False) -> Dict:
    """Get summary of today's picks"""
    return _api.get_summary(force_refresh)


def refresh_picks() -> Dict:
    """Force refresh picks (re-run analysis)"""
    return _api.format_for_dashboard(force_refresh=True)


# =============================================================================
# TEST
# =============================================================================
if __name__ == "__main__":
    print("=" * 70)
    print("🏀 SB-ALGO API v2.0 TEST - STRICT FILTERS")
    print("=" * 70)
    print(f"\n📋 FILTER SETTINGS:")
    print(f"   • Min Edge: {MIN_EDGE_PCT}%")
    print(f"   • Min Hit Rate: {MIN_HIT_RATE*100}%")
    print(f"   • Min Confidence: {MIN_CONFIDENCE}%")
    print(f"   • Max Game Picks: {MAX_GAME_PICKS}")
    print(f"   • Max Prop Picks: {MAX_PROP_PICKS}")
    
    picks = get_todays_picks()
    
    print(f"\n📅 Date: {picks['date']}")
    print(f"📊 Total Picks: {picks['total_picks']} (filtered from {picks.get('_unfiltered_games', '?')} games + {picks.get('_unfiltered_props', '?')} props)")
    print(f"💰 Total Stake: {picks['total_stake']}")
    print(f"📈 Avg EV: {picks['avg_ev']}")
    
    print(f"\n🏀 TOP GAME PICKS ({len(picks['game_picks'])}):")
    for p in picks['game_picks']:
        print(f"  🔥 {p['matchup']} → {p['pick']}")
        print(f"     Edge: {p['edge']} | EV: {p['ev']} | Conf: {p['confidence']} | Grade: {p['grade']}")
    
    print(f"\n🎯 TOP PROP PICKS ({len(picks['prop_picks'])}):")
    for p in picks['prop_picks']:
        print(f"  🔥 {p['player']} {p['prop']}")
        print(f"     Edge: {p['edge']} | Hit Rate: {p['hit_rate']} | EV: {p['ev']} | Score: {p.get('score', 'N/A')}")
    
    print("\n" + "=" * 70)
    print("✅ API TEST COMPLETE")
    print("=" * 70)
