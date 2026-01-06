#!/usr/bin/env python3
"""
Grade Predictions - Daily job to grade yesterday's picks
Runs at 6 AM ET after all games are final
Compares algo predictions vs actual results to track performance
"""

import os
import requests
from sqlalchemy import create_engine, text
from datetime import datetime, timedelta
import pytz

DATABASE_URL = os.environ.get('DATABASE_URL',
    "postgresql://sb_algo_db_user:0HDtYp4EY2Lo5At8iyf44PD1zDioSPK7@dpg-d495uhchg0os738l1a50-a.virginia-postgres.render.com/sb_algo_db?sslmode=require")

def main():
    eastern = pytz.timezone('US/Eastern')
    now = datetime.now(eastern)
    yesterday = (now - timedelta(days=1)).date()
    
    print(f"{'='*60}")
    print(f"📊 GRADING PREDICTIONS")
    print(f"⏰ {now.strftime('%Y-%m-%d %H:%M:%S')} ET")
    print(f"📅 Grading: {yesterday}")
    print(f"{'='*60}")
    
    engine = create_engine(DATABASE_URL)
    
    # Import memory classes
    from math_engine import GameBettingMemory, PropsMemory
    
    # ========== GRADE GAME PREDICTIONS ==========
    print("\n🏀 Grading Game Predictions...")
    game_memory = GameBettingMemory(engine)
    game_graded = game_memory.grade_predictions(yesterday)
    print(f"   ✅ Graded {game_graded} game predictions")
    
    # Get game performance stats
    game_stats = game_memory.get_performance_stats(days=30)
    if game_stats.get('by_type'):
        print("\n   📈 Game Betting Performance (L30 days):")
        for pred_type, data in game_stats['by_type'].items():
            print(f"      {pred_type}: {data['win_rate']}% ({data['wins']}-{data['losses']}) {data['units_profit']:+.1f}u")
    
    # ========== GRADE PROP PREDICTIONS ==========
    print("\n🎯 Grading Prop Predictions...")
    props_memory = PropsMemory(engine)
    props_graded = props_memory.grade_prop_predictions(yesterday)
    print(f"   ✅ Graded {props_graded} prop predictions")
    
    # Get props performance stats
    props_stats = props_memory.get_performance_stats(days=30)
    if props_stats.get('overall'):
        overall = props_stats['overall']
        print(f"\n   📈 Props Betting Performance (L30 days):")
        print(f"      Overall: {overall['win_rate']}% ({overall['wins']}-{overall['losses']}) {overall['units_profit']:+.1f}u")
        print(f"      ROI: {overall['roi']}%")
    
    # ========== GENERATE INSIGHTS ==========
    print("\n💡 INSIGHTS:")
    
    game_insights = game_memory.get_insights()
    for insight in game_insights[:5]:
        print(f"   {insight}")
    
    prop_insights = props_memory.get_insights()
    for insight in prop_insights[:5]:
        print(f"   {insight}")
    
    # ========== GET RECOMMENDED FILTERS ==========
    print("\n🎚️ RECOMMENDED THRESHOLDS:")
    
    game_filters = game_memory.get_recommended_filters()
    print("   Game Bets:")
    for pred_type, thresholds in game_filters.items():
        print(f"      {pred_type}: min_edge={thresholds['min_edge']}, min_conf={thresholds['min_confidence']}")
    
    prop_filters = props_memory.get_recommended_filters()
    print(f"   Props:")
    print(f"      min_edge={prop_filters.get('min_edge', 10)}%")
    if prop_filters.get('preferred_markets'):
        print(f"      preferred: {', '.join(prop_filters['preferred_markets'][:3])}")
    if prop_filters.get('avoid_markets'):
        print(f"      avoid: {', '.join(prop_filters['avoid_markets'][:3])}")
    
    print(f"\n{'='*60}")
    # Post to Discord
    post_grading_results_to_discord(yesterday, game_graded, props_graded, game_stats, props_stats)
    
    print(f"✅ GRADING COMPLETE")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()

# ============================================================
# DISCORD RESULTS POSTING
# ============================================================

def post_grading_results_to_discord(yesterday, game_graded, props_graded, game_stats, props_stats):
    """Post grading results to Discord #results channel"""
    import requests
    
    WEBHOOK_URL = os.environ.get('DISCORD_WEBHOOK_RESULTS', 
        'https://discord.com/api/webhooks/1453117355327750185/SIakCtSyVdXBzyhguN_2NWsYjAw6Xg6sTOMcdudnp9L9WDO5Mj7k0pk1o51qFyfX7EJb')
    
    if not WEBHOOK_URL:
        print("   ⚠️ No results webhook configured")
        return
    
    # Build embed
    embed = {
        "title": f"📊 DAILY GRADING RESULTS",
        "description": f"**{yesterday}** - All picks graded",
        "color": 0x667eea,
        "fields": [
            {"name": "🏀 Games Graded", "value": str(game_graded), "inline": True},
            {"name": "🎯 Props Graded", "value": str(props_graded), "inline": True},
            {"name": "📈 Total", "value": str(game_graded + props_graded), "inline": True},
        ]
    }
    
    # Add game stats if available
    if game_stats and game_stats.get('by_type'):
        game_summary = []
        for pred_type, data in game_stats['by_type'].items():
            game_summary.append(f"{pred_type}: {data['win_rate']}% ({data['wins']}-{data['losses']})")
        if game_summary:
            embed["fields"].append({
                "name": "🏀 L30 Game Performance",
                "value": "\n".join(game_summary[:3]),
                "inline": False
            })
    
    # Add props stats if available
    if props_stats and props_stats.get('overall'):
        overall = props_stats['overall']
        embed["fields"].append({
            "name": "🎯 L30 Props Performance",
            "value": f"Win Rate: {overall['win_rate']}% ({overall['wins']}-{overall['losses']})\nROI: {overall['roi']}% | P/L: {overall['units_profit']:+.1f}u",
            "inline": False
        })
    
    embed["footer"] = {"text": f"SB-ALGO • Auto-graded at 6:00 AM ET"}
    
    # Send to Discord
    try:
        response = requests.post(WEBHOOK_URL, json={"embeds": [embed]}, timeout=10)
        if response.status_code in [200, 204]:
            print("   ✅ Posted grading results to Discord")
        else:
            print(f"   ⚠️ Discord error: {response.status_code}")
    except Exception as e:
        print(f"   ⚠️ Discord post failed: {e}")
