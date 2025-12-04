#!/usr/bin/env python3
"""
Generate Picks - Daily job to analyze games and generate picks
Runs at 9 AM ET after lines are set
"""

import os
from sqlalchemy import create_engine, text
from datetime import datetime
import pytz

DATABASE_URL = os.environ.get('DATABASE_URL',
    "postgresql://sb_algo_db_user:0HDtYp4EY2Lo5At8iyf44PD1zDioSPK7@dpg-d495uhchg0os738l1a50-a.virginia-postgres.render.com/sb_algo_db?sslmode=require")

def main():
    eastern = pytz.timezone('US/Eastern')
    now = datetime.now(eastern)
    today = now.date()
    
    print(f"{'='*60}")
    print(f"🎯 GENERATING PICKS FOR {today}")
    print(f"⏰ {now.strftime('%Y-%m-%d %H:%M:%S')} ET")
    print(f"{'='*60}")
    
    engine = create_engine(DATABASE_URL)
    
    from math_engine import GamePredictor, GameBettingMemory
    
    predictor = GamePredictor(engine)
    memory = GameBettingMemory(engine)
    
    # Get recommended filters based on past performance
    filters = memory.get_recommended_filters()
    print(f"\n📋 Using filters based on algo performance:")
    for pred_type, thresholds in filters.items():
        print(f"   {pred_type}: min_edge={thresholds['min_edge']}, min_conf={thresholds['min_confidence']}")
    
    # Get today's games with odds
    with engine.connect() as conn:
        games = conn.execute(text("""
            SELECT g.home_team, g.visitor_team, g.start_time,
                   bo.home_spread, bo.total, bo.home_ml, bo.away_ml, bo.sportsbook
            FROM games g
            LEFT JOIN LATERAL (
                SELECT home_spread, total, home_ml, away_ml, sportsbook
                FROM betting_odds 
                WHERE game_date = g.date AND home_team = g.home_team
                ORDER BY updated_at DESC NULLS LAST
                LIMIT 1
            ) bo ON true
            WHERE g.date = :today
            AND g.home_pts IS NULL
            ORDER BY g.start_time
        """), {"today": today}).fetchall()
    
    if not games:
        print("\n⚠️ No games found for today")
        return
    
    print(f"\n🏀 Analyzing {len(games)} games...\n")
    
    all_picks = []
    
    for game in games:
        home, away, start_time = game[0], game[1], game[2]
        spread_line = float(game[3]) if game[3] else None
        total_line = float(game[4]) if game[4] else None
        home_ml = int(game[5]) if game[5] else None
        away_ml = int(game[6]) if game[6] else None
        sportsbook = game[7]
        
        print(f"{'─'*50}")
        print(f"🏀 {away} @ {home} ({start_time})")
        
        # Analyze game
        analysis = predictor.analyze_game(
            home, away, 
            spread_line=spread_line,
            total_line=total_line,
            home_ml=home_ml,
            away_ml=away_ml
        )
        
        # Print predictions
        spread = analysis['spread']
        total = analysis['total']
        
        print(f"   📊 Predicted Spread: {spread['predicted_spread']:+.1f} (Line: {spread_line})")
        print(f"   📊 Predicted Total: {total['predicted_total']:.1f} (Line: {total_line})")
        
        if 'moneyline' in analysis:
            ml = analysis['moneyline']
            print(f"   📊 Win Prob: {home} {ml['home_win_prob']}% | {away} {ml['away_win_prob']}%")
        
        # Check picks against filters
        for pick in analysis['picks']:
            pred_type = pick['type']
            min_edge = filters.get(pred_type, {}).get('min_edge', 2)
            min_conf = filters.get(pred_type, {}).get('min_confidence', 60)
            
            if pick['edge'] >= min_edge and pick['confidence'] >= min_conf:
                print(f"   ✅ PICK: {pick['pick']} (Edge: {pick['edge']:.1f}, Conf: {pick['confidence']:.0f}%)")
                
                # Save to memory
                if pred_type == 'SPREAD':
                    pred_value = spread['predicted_spread']
                    line_value = spread_line
                elif pred_type == 'TOTAL':
                    pred_value = total['predicted_total']
                    line_value = total_line
                else:
                    pred_value = ml['home_win_prob'] if home in pick['pick'] else ml['away_win_prob']
                    line_value = home_ml if home in pick['pick'] else away_ml
                
                memory.save_prediction(
                    game_date=today,
                    home_team=home,
                    away_team=away,
                    pred_type=pred_type,
                    pick=pick['pick'],
                    predicted_value=pred_value,
                    line_value=line_value,
                    edge=pick['edge'],
                    confidence=pick['confidence'],
                    home_net=spread.get('home_net'),
                    away_net=spread.get('away_net'),
                    home_form=spread.get('home_form'),
                    away_form=spread.get('away_form'),
                    sportsbook=sportsbook,
                    odds=-110,
                    units_bet=1.0
                )
                
                all_picks.append({
                    'game': f"{away} @ {home}",
                    **pick
                })
            else:
                print(f"   ⏭️ Skip: {pick['pick']} (Edge: {pick['edge']:.1f} < {min_edge} or Conf: {pick['confidence']:.0f}% < {min_conf})")
    
    # Summary
    print(f"\n{'='*60}")
    print(f"📋 PICKS SUMMARY: {len(all_picks)} total picks")
    print(f"{'='*60}")
    
    for pick in sorted(all_picks, key=lambda x: -x['edge']):
        print(f"   🎯 {pick['game']}: {pick['pick']} (Edge: {pick['edge']:.1f})")
    
    print(f"\n✅ Picks saved to algo_game_predictions table")

if __name__ == "__main__":
    main()
