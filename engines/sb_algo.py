#!/usr/bin/env python3
"""
================================================================================
███████╗██████╗       █████╗ ██╗      ██████╗  ██████╗ 
██╔════╝██╔══██╗     ██╔══██╗██║     ██╔════╝ ██╔═══██╗
███████╗██████╔╝     ███████║██║     ██║  ███╗██║   ██║
╚════██║██╔══██╗     ██╔══██║██║     ██║   ██║██║   ██║
███████║██████╔╝     ██║  ██║███████╗╚██████╔╝╚██████╔╝
╚══════╝╚═════╝      ╚═╝  ╚═╝╚══════╝ ╚═════╝  ╚═════╝ 
                                                        
                    MASTER CONTROLLER v1.0
================================================================================

The final embodiment of all SB-ALGO math and algorithms.

WHAT IT DOES:
- Pulls live odds from database (no API calls)
- Analyzes ALL game lines (spread, total, moneyline)
- Analyzes ALL player props with professional filters
- Applies Kelly criterion bankroll management
- Combines everything into unified picks
- Outputs to console, Discord, CSV, JSON

ENGINES INTEGRATED:
├── live_odds_connector.py     - Live odds from DB
├── spread_engine_v2.py        - Spread analysis
├── total_engine.py            - Total analysis  
├── moneyline_engine.py        - Moneyline analysis
├── prop_analyzer_pro.py       - Professional prop analysis
├── historical_patterns.py     - Historical data
├── correlation_engine.py      - Correlation detection
├── kelly_engine.py            - Bankroll management
├── clv_engine.py              - Closing line value
├── injury_engine.py           - Injury adjustments
├── calibration_engine.py      - Probability calibration
├── uncertainty_engine.py      - Regime detection
└── meta_merge_engine_v4.py    - Final pick merging

USAGE:
    python3 sb_algo.py                      # Default run
    python3 sb_algo.py --bankroll 5000      # Custom bankroll
    python3 sb_algo.py --output discord     # Discord format
    python3 sb_algo.py --props-only         # Only player props
    python3 sb_algo.py --games-only         # Only game lines
    python3 sb_algo.py --save               # Save to files
    python3 sb_algo.py --all                # Everything

================================================================================
"""

import sys
import os
import argparse
from datetime import date, datetime
from typing import List, Dict, Optional
import json

# Add engines directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# =============================================================================
# CONFIGURATION
# =============================================================================

DEFAULT_BANKROLL = 10000
MAX_DAILY_RISK = 0.30           # Max 30% of bankroll per day
MAX_SINGLE_BET = 0.05           # Max 5% on single bet
MAX_GAME_PICKS = 10             # Max game line picks
MAX_PROP_PICKS = 5              # Max prop picks
MIN_EDGE_GAMES = 5.0            # Minimum edge for games
MIN_EDGE_PROPS = 8.0            # Minimum edge for props


class SBAlgoMaster:
    """
    Master controller that orchestrates all SB-ALGO engines.
    """
    
    def __init__(self, bankroll: float = DEFAULT_BANKROLL, 
                 risk_profile: str = 'moderate'):
        self.bankroll = bankroll
        self.risk_profile = risk_profile
        self.today = date.today()
        
        # Initialize engines
        self._init_engines()
        
        # Results storage
        self.game_picks = []
        self.prop_picks = []
        self.all_picks = []
    
    def _init_engines(self):
        """Initialize all engines"""
        print("🔧 Initializing SB-ALGO engines...")
        
        try:
            from live_odds_connector import LiveOddsConnector
            self.odds = LiveOddsConnector()
            print("   ✅ Live Odds Connector")
        except Exception as e:
            print(f"   ❌ Live Odds Connector: {e}")
            self.odds = None
        
        try:
            from meta_merge_engine_v4 import MetaMergeEngine
            self.meta = MetaMergeEngine(
                bankroll=self.bankroll,
                risk_profile=self.risk_profile
            )
            print("   ✅ Meta-Merge Engine v4")
        except Exception as e:
            print(f"   ❌ Meta-Merge Engine: {e}")
            self.meta = None
        
        try:
            from prop_analyzer_pro import PropAnalyzerPro
            self.props = PropAnalyzerPro(bankroll=self.bankroll)
            print("   ✅ Prop Analyzer PRO")
        except Exception as e:
            print(f"   ❌ Prop Analyzer: {e}")
            self.props = None
        
        try:
            from kelly_engine import KellyEngine
            self.kelly = KellyEngine(risk_profile=self.risk_profile)
            print("   ✅ Kelly Engine")
        except Exception as e:
            print(f"   ❌ Kelly Engine: {e}")
            self.kelly = None
        
        print(f"   💰 Bankroll: ${self.bankroll:,.0f}")
        print(f"   ⚡ Risk Profile: {self.risk_profile}")
    
    # =========================================================================
    # GAME ANALYSIS
    # =========================================================================
    
    def analyze_games(self) -> List[Dict]:
        """Analyze all game lines for today"""
        print(f"\n{'='*70}")
        print("🏀 ANALYZING GAME LINES")
        print(f"{'='*70}")
        
        if not self.odds or not self.meta:
            print("   ❌ Required engines not available")
            return []
        
        # Get today's games with odds
        games = self.odds.get_todays_games(self.today)
        
        if not games:
            print("   ❌ No games found for today")
            return []
        
        print(f"   Found {len(games)} games")
        
        # Format games for meta engine
        formatted_games = []
        for g in games:
            consensus = g.get('consensus', {})
            spread = consensus.get('spread')
            total = consensus.get('total')
            
            # Get real odds from preferred book (fanduel > draftkings > others)
            books = g.get('books', {})
            book_odds = books.get('fanduel') or books.get('draftkings') or books.get('caesars') or books.get('betmgm') or {}
            
            if spread is not None:
                formatted_games.append({
                    'game_id': f"{g['away_team']}@{g['home_team']}",
                    'home_team': g['home_team'],
                    'away_team': g['away_team'],
                    'spread': spread,
                    'total': total or 220,
                    'home_ml': consensus.get('home_ml', -110),
                    'away_ml': consensus.get('away_ml', -110),
                    # Real odds from book
                    'spread_odds': book_odds.get('spread_odds', -110),
                    'over_odds': book_odds.get('over_odds', -110),
                    'under_odds': book_odds.get('under_odds', -110),
                })
        
        if not formatted_games:
            print("   ❌ No games with valid odds")
            return []
        
        # Run meta-merge analysis
        print(f"   Analyzing {len(formatted_games)} games...")
        results = self.meta.analyze_slate(formatted_games)
        
        # Get picks from bet_slip
        bet_slip = results.get('bet_slip', {})
        picks = bet_slip.get('picks', [])
        
        # Format picks consistently
        formatted_picks = []
        for p in picks:
            formatted_picks.append({
                'game_id': p.get('game', 'Unknown'),
                'pick': p.get('pick', 'Unknown'),
                'type': p.get('type', 'Unknown'),
                'edge': p.get('edge', 0),
                'ev_pct': p.get('ev_pct', 0),
                'confidence': p.get('calibrated_prob', 0) * 100,
                'grade': p.get('grade', 'N/A'),
                'stake': p.get('stake', 0),
                # EXPLANATION DATA - model predictions
                'model_total': p.get('model_total'),
                'model_home_pts': p.get('model_home_pts'),
                'model_away_pts': p.get('model_away_pts'),
                'model_pace': p.get('model_pace'),
                'model_margin': p.get('model_margin'),
                # Regime & injuries
                'regime_status': p.get('regime_status'),
                'regime_confidence': p.get('regime_confidence'),
                'injury_adjustment': p.get('injury_adjustment', 0),
                'injury_edge': p.get('injury_edge', 'NEUTRAL'),
                'odds': p.get('odds', -110),
            })
        
        # Apply daily limits
        formatted_picks = formatted_picks[:MAX_GAME_PICKS]
        
        # Recalculate stakes with daily limit
        max_games_stake = self.bankroll * MAX_DAILY_RISK * 0.6  # 60% of daily risk for games
        total_stake = sum(p.get('stake', 0) for p in formatted_picks)
        
        if total_stake > max_games_stake:
            ratio = max_games_stake / total_stake
            for p in formatted_picks:
                p['stake'] = round(p.get('stake', 0) * ratio, 2)
        
        self.game_picks = formatted_picks
        print(f"   ✅ Found {len(formatted_picks)} game picks")
        
        return formatted_picks
    
    # =========================================================================
    # PROP ANALYSIS
    # =========================================================================
    
    def analyze_props(self) -> List[Dict]:
        """Analyze all player props for today"""
        print(f"\n{'='*70}")
        print("🎯 ANALYZING PLAYER PROPS")
        print(f"{'='*70}")
        
        if not self.props:
            print("   ❌ Prop Analyzer not available")
            return []
        
        # Run professional prop analysis
        picks = self.props.find_best_props(
            target_date=self.today,
            markets=['pts', 'reb', 'ast']
        )
        
        # Apply daily limits
        picks = picks[:MAX_PROP_PICKS]
        
        # Recalculate stakes with daily limit
        max_props_stake = self.bankroll * MAX_DAILY_RISK * 0.4  # 40% of daily risk for props
        total_stake = sum(p.get('stake', 0) for p in picks)
        
        if total_stake > max_props_stake:
            ratio = max_props_stake / total_stake
            for p in picks:
                p['stake'] = round(p.get('stake', 0) * ratio, 2)
        
        self.prop_picks = picks
        print(f"   ✅ Found {len(picks)} prop picks")
        
        return picks
    
    # =========================================================================
    # COMBINE & RANK
    # =========================================================================
    
    def combine_picks(self) -> List[Dict]:
        """Combine game and prop picks into unified list"""
        print(f"\n{'='*70}")
        print("🔀 COMBINING ALL PICKS")
        print(f"{'='*70}")
        
        all_picks = []
        
        # Add game picks
        for p in self.game_picks:
            all_picks.append({
                'type': 'GAME',
                'pick': p.get('pick', 'Unknown'),
                'matchup': p.get('game_id', 'Unknown'),
                'edge': p.get('edge', 0),
                'ev': p.get('ev_pct', 0),
                'confidence': p.get('confidence', 0),
                'grade': p.get('grade', 'N/A'),
                'stake': p.get('stake', 0),
                'bet_type': p.get('type', 'Unknown'),
                'details': p,
            })
        
        # Add prop picks
        for p in self.prop_picks:
            pick_str = f"{p['player']} {p['stat'].upper()} {p['best_side']} {p['book_line']}"
            all_picks.append({
                'type': 'PROP',
                'pick': pick_str,
                'matchup': p.get('matchup', 'Unknown'),
                'edge': p.get('edge_pct', 0),
                'ev': p.get('ev_pct', 0),
                'confidence': p['filters']['hit_rate']['hit_rate'] * 100,
                'grade': p.get('grade', 'N/A'),
                'stake': p.get('stake', 0),
                'details': p,
            })
        
        # Sort by EV
        all_picks.sort(key=lambda x: x['ev'], reverse=True)
        
        # Final stake adjustment to not exceed daily max
        max_daily = self.bankroll * MAX_DAILY_RISK
        total_stake = sum(p['stake'] for p in all_picks)
        
        if total_stake > max_daily:
            ratio = max_daily / total_stake
            for p in all_picks:
                p['stake'] = round(p['stake'] * ratio, 2)
        
        self.all_picks = all_picks
        
        total_stake = sum(p['stake'] for p in all_picks)
        print(f"   📊 Total Picks: {len(all_picks)}")
        print(f"   💰 Total Stake: ${total_stake:,.0f}")
        print(f"   📈 Avg EV: {sum(p['ev'] for p in all_picks)/len(all_picks):.1f}%" if all_picks else "   📈 Avg EV: N/A")
        
        return all_picks
    
    # =========================================================================
    # RUN ALL
    # =========================================================================
    
    def run(self, games: bool = True, props: bool = True) -> Dict:
        """Run full analysis"""
        print("\n" + "="*70)
        print("███████╗██████╗       █████╗ ██╗      ██████╗  ██████╗ ")
        print("██╔════╝██╔══██╗     ██╔══██╗██║     ██╔════╝ ██╔═══██╗")
        print("███████╗██████╔╝     ███████║██║     ██║  ███╗██║   ██║")
        print("╚════██║██╔══██╗     ██╔══██║██║     ██║   ██║██║   ██║")
        print("███████║██████╔╝     ██║  ██║███████╗╚██████╔╝╚██████╔╝")
        print("╚══════╝╚═════╝      ╚═╝  ╚═╝╚══════╝ ╚═════╝  ╚═════╝ ")
        print("="*70)
        print(f"📅 {self.today.strftime('%A, %B %d, %Y')}")
        print(f"💰 Bankroll: ${self.bankroll:,.0f}")
        print("="*70)
        
        # Analyze
        if games:
            self.analyze_games()
        
        if props:
            self.analyze_props()
        
        # Combine
        self.combine_picks()
        
        return {
            'date': str(self.today),
            'bankroll': self.bankroll,
            'game_picks': self.game_picks,
            'prop_picks': self.prop_picks,
            'all_picks': self.all_picks,
        }
    
    # =========================================================================
    # OUTPUT FORMATS
    # =========================================================================
    
    def print_picks(self):
        """Print picks to console"""
        if not self.all_picks:
            print("\n❌ No picks found")
            return
        
        print("\n" + "="*70)
        print("🏀 SB-ALGO DAILY PICKS")
        print(f"📅 {self.today.strftime('%A, %B %d, %Y')}")
        print("="*70)
        
        total_stake = sum(p['stake'] for p in self.all_picks)
        avg_ev = sum(p['ev'] for p in self.all_picks) / len(self.all_picks)
        
        print(f"\n💰 Bankroll: ${self.bankroll:,.0f}")
        print(f"📊 Total Picks: {len(self.all_picks)}")
        print(f"💵 Total Stake: ${total_stake:,.0f} ({total_stake/self.bankroll*100:.1f}%)")
        print(f"📈 Avg EV: {avg_ev:.1f}%")
        
        # Game picks
        game_picks = [p for p in self.all_picks if p['type'] == 'GAME']
        if game_picks:
            print(f"\n{'─'*70}")
            print("🏀 GAME PICKS")
            print(f"{'─'*70}")
            for i, p in enumerate(game_picks, 1):
                print(f"\n  {i}. {p['matchup']}")
                print(f"     → {p['pick']}")
                print(f"     Edge: {p['edge']:+.1f}% | EV: {p['ev']:.1f}%")
                print(f"     💰 ${p['stake']:.0f} | {p['grade']}")
        
        # Prop picks
        prop_picks = [p for p in self.all_picks if p['type'] == 'PROP']
        if prop_picks:
            print(f"\n{'─'*70}")
            print("🎯 PROP PICKS")
            print(f"{'─'*70}")
            for i, p in enumerate(prop_picks, 1):
                details = p['details']
                print(f"\n  {i}. {p['pick']}")
                print(f"     Model: {details['projection']['weighted']} | Line: {details['book_line']}")
                print(f"     Hit Rate: {details['filters']['hit_rate']['hit_rate']:.0%} | EV: {p['ev']:.1f}%")
                print(f"     💰 ${p['stake']:.0f} | {p['grade']}")
        
        print("\n" + "="*70)
        print("✅ SB-ALGO ANALYSIS COMPLETE")
        print("="*70)
    
    def to_discord(self) -> str:
        """Format picks for Discord"""
        if not self.all_picks:
            return "❌ No picks found"
        
        lines = []
        lines.append("```")
        lines.append("🏀 SB-ALGO DAILY PICKS")
        lines.append(f"📅 {self.today.strftime('%A, %B %d, %Y')}")
        lines.append("=" * 40)
        
        total_stake = sum(p['stake'] for p in self.all_picks)
        lines.append(f"💰 Bankroll: ${self.bankroll:,.0f}")
        lines.append(f"💵 Total Stake: ${total_stake:,.0f}")
        lines.append("")
        
        # Game picks
        game_picks = [p for p in self.all_picks if p['type'] == 'GAME']
        if game_picks:
            lines.append("🏀 GAMES:")
            for p in game_picks:
                lines.append(f"  • {p['pick']} | ${p['stake']:.0f} | {p['grade']}")
        
        # Prop picks
        prop_picks = [p for p in self.all_picks if p['type'] == 'PROP']
        if prop_picks:
            lines.append("")
            lines.append("🎯 PROPS:")
            for p in prop_picks:
                d = p['details']
                lines.append(f"  • {d['player']} {d['stat'].upper()} {d['best_side']} {d['book_line']}")
                lines.append(f"    Hit: {d['filters']['hit_rate']['hit_rate']:.0%} | ${p['stake']:.0f} | {p['grade']}")
        
        lines.append("```")
        
        return "\n".join(lines)
    
    def to_json(self) -> str:
        """Export picks to JSON"""
        return json.dumps({
            'date': str(self.today),
            'bankroll': self.bankroll,
            'total_picks': len(self.all_picks),
            'total_stake': sum(p['stake'] for p in self.all_picks),
            'picks': [{
                'type': p['type'],
                'pick': p['pick'],
                'matchup': p['matchup'],
                'edge': p['edge'],
                'ev': p['ev'],
                'grade': p['grade'],
                'stake': p['stake'],
            } for p in self.all_picks]
        }, indent=2)
    
    def save_picks(self, output_dir: str = None):
        """Save picks to files"""
        if output_dir is None:
            output_dir = os.path.dirname(os.path.abspath(__file__))
        
        date_str = self.today.strftime('%Y-%m-%d')
        
        # Save JSON
        json_path = os.path.join(output_dir, f"picks_{date_str}.json")
        with open(json_path, 'w') as f:
            f.write(self.to_json())
        print(f"   💾 Saved: {json_path}")
        
        # Save Discord format
        discord_path = os.path.join(output_dir, f"picks_{date_str}_discord.txt")
        with open(discord_path, 'w') as f:
            f.write(self.to_discord())
        print(f"   💾 Saved: {discord_path}")


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description='SB-ALGO Master Controller')
    parser.add_argument('--bankroll', type=float, default=DEFAULT_BANKROLL,
                        help=f'Bankroll amount (default: ${DEFAULT_BANKROLL:,})')
    parser.add_argument('--risk', choices=['conservative', 'moderate', 'aggressive'],
                        default='moderate', help='Risk profile')
    parser.add_argument('--games-only', action='store_true',
                        help='Only analyze game lines')
    parser.add_argument('--props-only', action='store_true',
                        help='Only analyze player props')
    parser.add_argument('--output', choices=['console', 'discord', 'json', 'all'],
                        default='console', help='Output format')
    parser.add_argument('--save', action='store_true',
                        help='Save picks to files')
    
    args = parser.parse_args()
    
    # Determine what to analyze
    do_games = not args.props_only
    do_props = not args.games_only
    
    # Initialize master
    master = SBAlgoMaster(
        bankroll=args.bankroll,
        risk_profile=args.risk
    )
    
    # Run analysis
    master.run(games=do_games, props=do_props)
    
    # Output
    if args.output in ['console', 'all']:
        master.print_picks()
    
    if args.output in ['discord', 'all']:
        print("\n" + "="*70)
        print("📱 DISCORD FORMAT")
        print("="*70)
        print(master.to_discord())
    
    if args.output in ['json', 'all']:
        print("\n" + "="*70)
        print("📄 JSON FORMAT")
        print("="*70)
        print(master.to_json())
    
    # Save
    if args.save:
        print("\n💾 Saving picks...")
        master.save_picks()


if __name__ == "__main__":
    main()
