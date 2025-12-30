#!/usr/bin/env python3
"""
================================================================================
SB-ALGO PICKS API
================================================================================
This module provides the interface between the Streamlit dashboard and the
SB-ALGO engine. Import this to get real picks from the algorithm.

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
    
    def get_all_picks(self, force_refresh: bool = False) -> Dict:
        """Get all picks (games + props)"""
        return self._run_analysis(force=force_refresh)
    
    def get_game_picks(self, force_refresh: bool = False) -> List[Dict]:
        """Get only game picks"""
        results = self._run_analysis(force=force_refresh)
        return results.get('game_picks', [])
    
    def get_prop_picks(self, force_refresh: bool = False) -> List[Dict]:
        """Get only prop picks"""
        results = self._run_analysis(force=force_refresh)
        return results.get('prop_picks', [])
    
    def get_summary(self, force_refresh: bool = False) -> Dict:
        """Get summary stats"""
        results = self._run_analysis(force=force_refresh)
        return results.get('summary', {})
    
    def format_for_dashboard(self, force_refresh: bool = False) -> Dict:
        """
        Format picks for Streamlit dashboard display.
        Returns data ready to be displayed in the UI.
        """
        results = self._run_analysis(force=force_refresh)
        
        # Format game picks for display
        game_picks_display = []
        for p in results.get('game_picks', []):
            game_picks_display.append({
                'matchup': p.get('game_id', 'Unknown'),
                'pick': p.get('pick', 'Unknown'),
                'type': p.get('type', 'Unknown'),
                'edge': f"+{p.get('edge', 0):.1f}%",
                'ev': f"{p.get('ev_pct', 0):.1f}%",
                'confidence': f"{p.get('confidence', 0):.0f}%",
                'grade': p.get('grade', 'N/A'),
                'stake': f"${p.get('stake', 0):.0f}",
            })
        
        # Format prop picks for display
        prop_picks_display = []
        for p in results.get('prop_picks', []):
            prop_picks_display.append({
                'player': p.get('player', 'Unknown'),
                'prop': f"{p.get('stat', '').upper()} {p.get('best_side', '')} {p.get('book_line', '')}",
                'model': p.get('projection', {}).get('weighted', 0),
                'line': p.get('book_line', 0),
                'hit_rate': f"{p.get('filters', {}).get('hit_rate', {}).get('hit_rate', 0):.0%}",
                'edge': f"+{p.get('edge_pct', 0):.1f}%",
                'ev': f"{p.get('ev_pct', 0):.1f}%",
                'grade': p.get('grade', 'N/A'),
                'stake': f"${p.get('stake', 0):.0f}",
            })
        
        summary = results.get('summary', {})
        
        return {
            'date': results.get('date', str(date.today())),
            'timestamp': results.get('timestamp', datetime.now().isoformat()),
            'game_picks': game_picks_display,
            'prop_picks': prop_picks_display,
            'total_picks': summary.get('total_picks', 0),
            'total_stake': f"${summary.get('total_stake', 0):,.0f}",
            'avg_ev': f"{summary.get('avg_ev', 0):.1f}%",
            'edges_found': summary.get('total_picks', 0),
        }


# Singleton instance
_api = SBAlgoAPI()


# Convenience functions for easy import
def get_todays_picks(force_refresh: bool = False) -> Dict:
    """Get all of today's picks formatted for dashboard"""
    return _api.format_for_dashboard(force_refresh)


def get_game_picks(force_refresh: bool = False) -> List[Dict]:
    """Get today's game picks"""
    return _api.get_game_picks(force_refresh)


def get_prop_picks(force_refresh: bool = False) -> List[Dict]:
    """Get today's prop picks"""
    return _api.get_prop_picks(force_refresh)


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
    print("🏀 SB-ALGO API TEST")
    print("=" * 70)
    
    picks = get_todays_picks()
    
    print(f"\n📅 Date: {picks['date']}")
    print(f"📊 Total Picks: {picks['total_picks']}")
    print(f"💰 Total Stake: {picks['total_stake']}")
    print(f"📈 Avg EV: {picks['avg_ev']}")
    
    print(f"\n🏀 GAME PICKS ({len(picks['game_picks'])}):")
    for p in picks['game_picks'][:5]:
        print(f"  • {p['matchup']} → {p['pick']} | {p['edge']} | {p['grade']}")
    
    print(f"\n🎯 PROP PICKS ({len(picks['prop_picks'])}):")
    for p in picks['prop_picks'][:5]:
        print(f"  • {p['player']} {p['prop']} | Hit: {p['hit_rate']} | {p['grade']}")
    
    print("\n" + "=" * 70)
    print("✅ API TEST COMPLETE")
    print("=" * 70)
