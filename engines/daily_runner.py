#!/usr/bin/env python3
"""
================================================================================
DAILY RUNNER v2.0 - SB-ALGO NBA BETTING SYSTEM
================================================================================
Automated daily prediction generator using LIVE ODDS from your database.

USAGE:
------
python3 daily_runner.py              # Run with defaults
python3 daily_runner.py --bankroll 5000
python3 daily_runner.py --output discord   # Format for Discord
python3 daily_runner.py --save             # Save to JSON

================================================================================
"""

import argparse
from datetime import datetime, date
from sqlalchemy import create_engine, text
import json
import os
import sys

# Add engines directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from meta_merge_engine_v4 import MetaMergeEngine
from live_odds_connector import LiveOddsConnector

DATABASE_URL = "postgresql://sb_algo_db_user:0HDtYp4EY2Lo5At8iyf44PD1zDioSPK7@dpg-d495uhchg0os738l1a50-a.virginia-postgres.render.com/sb_algo_db"


def get_todays_games_live() -> list:
    """
    Fetch today's games from LIVE ODDS in database.
    NO API CALLS - uses your existing twice-daily pulls.
    """
    connector = LiveOddsConnector()
    games = connector.get_games_for_daily_runner()
    
    # Filter out games without spreads
    valid_games = [g for g in games if g.get('spread') is not None]
    
    return valid_games


def format_for_discord(analysis: dict) -> str:
    """Format analysis for Discord posting"""
    lines = []
    
    lines.append("```")
    lines.append("🏀 SB-ALGO DAILY PICKS 🏀")
    lines.append(f"📅 {datetime.now().strftime('%A, %B %d, %Y')}")
    lines.append("=" * 40)
    
    bet_slip = analysis['bet_slip']
    
    if bet_slip['total_picks'] == 0:
        lines.append("\n❌ No value picks found today")
        lines.append("Market is efficient - passing on today's slate")
    else:
        lines.append(f"\n💰 BANKROLL: ${bet_slip['bankroll']:,}")
        lines.append(f"📊 GAMES ANALYZED: {bet_slip['games_analyzed']}")
        lines.append(f"🎯 PICKS: {bet_slip['total_picks']}")
        lines.append(f"💵 TOTAL STAKE: ${bet_slip['total_stake']:.0f}")
        lines.append(f"📈 AVG EV: {bet_slip['avg_ev']:.1f}%")
        
        lines.append("\n" + "-" * 40)
        lines.append("📋 TODAY'S PICKS:")
        lines.append("-" * 40)
        
        for i, pick in enumerate(bet_slip['picks'], 1):
            lines.append(f"\n{i}. {pick['game']}")
            lines.append(f"   🎯 {pick['pick']}")
            lines.append(f"   💵 ${pick['stake']:.0f} | Grade: {pick['grade']}")
            lines.append(f"   📊 EV: {pick['ev_pct']:.1f}% | Prob: {pick['calibrated_prob']:.0%}")
    
    # Add game-by-game breakdown
    lines.append("\n" + "=" * 40)
    lines.append("📊 GAME ANALYSIS:")
    lines.append("=" * 40)
    
    for game in analysis['game_results']:
        lines.append(f"\n🏀 {game['matchup']}")
        
        if 'regime' in game:
            regime = game['regime']
            if regime['status'] == 'NORMAL':
                emoji = '🟢'
            elif regime['status'] == 'HIGH_VARIANCE':
                emoji = '🟡'
            elif regime['status'] == 'UNSTABLE':
                emoji = '🟠'
            else:
                emoji = '🔴'
            lines.append(f"   {emoji} {regime['status']} ({regime['confidence']}% conf)")
        
        if 'predictions' in game:
            pred = game['predictions']
            lines.append(f"   📈 Pred Spread: {pred['spread']} | Total: {pred['total']}")
        
        lines.append(f"   📋 {game['recommendation']}")
    
    lines.append("\n" + "=" * 40)
    lines.append("⚠️ Bet responsibly. Past results ≠ future.")
    lines.append("```")
    
    return "\n".join(lines)


def format_for_console(analysis: dict) -> str:
    """Format analysis for console output"""
    lines = []
    
    lines.append("\n" + "=" * 70)
    lines.append("🏀 SB-ALGO DAILY PICKS")
    lines.append(f"📅 {datetime.now().strftime('%A, %B %d, %Y')}")
    lines.append("=" * 70)
    
    bet_slip = analysis['bet_slip']
    
    lines.append(f"\n💰 Bankroll: ${bet_slip['bankroll']:,}")
    lines.append(f"📊 Games: {bet_slip['games_analyzed']}")
    lines.append(f"🎯 Picks: {bet_slip['total_picks']}")
    lines.append(f"💵 Stake: ${bet_slip['total_stake']:.0f}")
    lines.append(f"📈 Avg EV: {bet_slip['avg_ev']:.1f}%")
    
    if bet_slip['picks']:
        lines.append("\n" + "-" * 70)
        lines.append("📋 PICKS")
        lines.append("-" * 70)
        
        for pick in bet_slip['picks']:
            lines.append(f"\n  {pick['game']}")
            lines.append(f"  → {pick['pick']} | ${pick['stake']:.0f} | {pick['grade']} | EV: {pick['ev_pct']:.1f}%")
    
    lines.append("\n" + "=" * 70)
    
    return "\n".join(lines)


def save_to_file(analysis: dict, filename: str = None):
    """Save analysis to JSON file"""
    if filename is None:
        date_str = datetime.now().strftime('%Y-%m-%d')
        filename = f"picks_{date_str}.json"
    
    output_dir = os.path.join(os.path.dirname(__file__), 'daily_picks')
    os.makedirs(output_dir, exist_ok=True)
    
    filepath = os.path.join(output_dir, filename)
    
    with open(filepath, 'w') as f:
        json.dump(analysis, f, indent=2, default=str)
    
    print(f"📁 Saved to: {filepath}")
    return filepath


def main():
    parser = argparse.ArgumentParser(description='SB-ALGO Daily Runner v2.0')
    parser.add_argument('--bankroll', type=float, default=10000, help='Bankroll amount')
    parser.add_argument('--risk', choices=['conservative', 'moderate', 'aggressive'], 
                        default='moderate', help='Risk profile')
    parser.add_argument('--output', choices=['console', 'discord', 'json', 'all'], 
                        default='console', help='Output format')
    parser.add_argument('--save', action='store_true', help='Save to file')
    
    args = parser.parse_args()
    
    print("\n" + "=" * 70)
    print("🚀 SB-ALGO DAILY RUNNER v2.0 - LIVE ODDS")
    print("=" * 70)
    print(f"📅 Date: {datetime.now().strftime('%Y-%m-%d')}")
    print(f"💰 Bankroll: ${args.bankroll:,}")
    print(f"⚡ Risk Profile: {args.risk}")
    print("=" * 70)
    
    # Initialize engine
    print("\n🔧 Initializing engines...")
    engine = MetaMergeEngine(bankroll=args.bankroll, risk_profile=args.risk)
    
    # Get today's games from LIVE ODDS
    print("\n📅 Fetching today's games from LIVE ODDS...")
    games = get_todays_games_live()
    print(f"   Found {len(games)} games with odds")
    
    if not games:
        print("\n❌ No games with odds found for today.")
        print("   Make sure your odds pull has run (fetch_betting_odds.py)")
        return None
    
    # Analyze
    print("\n🧠 Running analysis...")
    analysis = engine.analyze_slate(games)
    
    # Output
    if args.output in ['console', 'all']:
        print(format_for_console(analysis))
    
    if args.output in ['discord', 'all']:
        discord_output = format_for_discord(analysis)
        print("\n📱 DISCORD FORMAT:")
        print(discord_output)
    
    if args.output == 'json' or args.save:
        save_to_file(analysis)
    
    return analysis


if __name__ == "__main__":
    main()
