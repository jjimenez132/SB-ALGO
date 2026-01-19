#!/usr/bin/env python3
"""
CAPTURE CLOSING ODDS
Runs ~30 min before games to capture closing lines for CLV calculation
"""

from sqlalchemy import create_engine, text
from datetime import datetime
import pytz
import os

DATABASE_URL = os.environ.get('DATABASE_URL',
    "postgresql://sb_algo_db_user:0HDtYp4EY2Lo5At8iyf44PD1zDioSPK7@dpg-d495uhchg0os738l1a50-a.virginia-postgres.render.com/sb_algo_db")

def get_eastern_time():
    return datetime.now(pytz.timezone('US/Eastern'))

def capture_closing_odds():
    """Capture current odds as closing odds for today's picks"""
    
    print(f"\n{'='*60}")
    print(f"📊 CAPTURING CLOSING ODDS - {get_eastern_time().strftime('%I:%M %p ET')}")
    print(f"{'='*60}")
    
    engine = create_engine(DATABASE_URL)
    
    with engine.connect() as conn:
        # Get today's pending picks
        picks = conn.execute(text("""
            SELECT id, pick_id, pick_name, pick_type, odds, line
            FROM algo_picks_tracking 
            WHERE pick_date = CURRENT_DATE 
            AND status = 'pending'
            AND closing_odds IS NULL
        """)).fetchall()
        
        if not picks:
            print("   ℹ️ No pending picks need closing odds")
            return
        
        print(f"   📋 Found {len(picks)} picks needing closing odds")
        
        updated = 0
        
        for pick in picks:
            pick_id, pick_code, pick_name, pick_type, opening_odds, line = pick
            closing_odds = None
            
            if pick_type == 'prop':
                # Get closing odds from player_props table
                # Parse player name from pick_name (e.g., "James Harden REB UNDER 5.5")
                parts = pick_name.split()
                
                # Find stat type
                stat_map = {'PTS': 'player_points', 'REB': 'player_rebounds', 'AST': 'player_assists'}
                market = None
                player_name = None
                side = None
                
                for i, p in enumerate(parts):
                    if p.upper() in stat_map:
                        player_name = ' '.join(parts[:i])
                        market = stat_map[p.upper()]
                        side = parts[i+1].upper() if i+1 < len(parts) else 'OVER'
                        break
                
                if player_name and market:
                    result = conn.execute(text("""
                        SELECT over_odds, under_odds, line
                        FROM player_props 
                        WHERE game_date = CURRENT_DATE 
                        AND LOWER(player_name) LIKE :player
                        AND market = :market
                        ORDER BY updated_at DESC 
                        LIMIT 1
                    """), {
                        'player': f'%{player_name.lower()}%',
                        'market': market
                    }).fetchone()
                    
                    if result:
                        closing_odds = result[0] if side == 'OVER' else result[1]
                        print(f"   ✅ {player_name}: {opening_odds} → {closing_odds}")
            
            elif pick_type == 'game':
                # Get closing odds from betting_odds table
                # Parse game from pick_name (e.g., "OKC @ CLE UNDER 234.5")
                parts = pick_name.split()
                
                if '@' in pick_name:
                    # Find the teams
                    at_idx = parts.index('@')
                    away_team = parts[at_idx - 1] if at_idx > 0 else None
                    home_team = parts[at_idx + 1] if at_idx + 1 < len(parts) else None
                    
                    # Determine bet type
                    if 'UNDER' in pick_name.upper():
                        side = 'under'
                    elif 'OVER' in pick_name.upper():
                        side = 'over'
                    else:
                        # Spread bet
                        side = 'spread'
                    
                    if away_team and home_team:
                        result = conn.execute(text("""
                            SELECT over_odds, under_odds, home_spread_odds, away_spread_odds
                            FROM betting_odds 
                            WHERE game_date = CURRENT_DATE 
                            AND (home_team LIKE :home OR away_team LIKE :away)
                            ORDER BY updated_at DESC 
                            LIMIT 1
                        """), {
                            'home': f'%{home_team}%',
                            'away': f'%{away_team}%'
                        }).fetchone()
                        
                        if result:
                            if side == 'under':
                                closing_odds = result[1]
                            elif side == 'over':
                                closing_odds = result[0]
                            else:
                                # Spread - determine which team
                                closing_odds = result[2]  # home spread odds
                            
                            print(f"   ✅ {away_team}@{home_team}: {opening_odds} → {closing_odds}")
            
            # Update closing odds in DB
            if closing_odds:
                conn.execute(text("""
                    UPDATE algo_picks_tracking 
                    SET closing_odds = :closing
                    WHERE id = :id
                """), {'closing': closing_odds, 'id': pick_id})
                updated += 1
        
        conn.commit()
        print(f"\n   ✅ Updated closing odds for {updated}/{len(picks)} picks")


def calculate_clv_for_graded():
    """Calculate CLV for picks that have closing odds but no CLV yet"""
    
    print(f"\n{'='*60}")
    print(f"📈 CALCULATING CLV")
    print(f"{'='*60}")
    
    engine = create_engine(DATABASE_URL)
    
    with engine.connect() as conn:
        # Get picks with closing odds but no CLV
        picks = conn.execute(text("""
            SELECT id, pick_name, odds, closing_odds
            FROM algo_picks_tracking 
            WHERE closing_odds IS NOT NULL 
            AND clv_cents IS NULL
            AND odds IS NOT NULL
        """)).fetchall()
        
        if not picks:
            print("   ℹ️ No picks need CLV calculation")
            return
        
        print(f"   📋 Calculating CLV for {len(picks)} picks")
        
        from engines.clv_engine import CLVEngine
        clv_engine = CLVEngine()
        
        for pick in picks:
            pick_id, pick_name, opening_odds, closing_odds = pick
            
            clv_cents = clv_engine.calculate_clv_cents(opening_odds, closing_odds)
            
            conn.execute(text("""
                UPDATE algo_picks_tracking 
                SET clv_cents = :clv
                WHERE id = :id
            """), {'clv': clv_cents, 'id': pick_id})
            
            direction = "✅" if clv_cents > 0 else "❌"
            print(f"   {direction} {pick_name[:40]}: {clv_cents:+.1f} cents CLV")
        
        conn.commit()
        print(f"\n   ✅ CLV calculated for {len(picks)} picks")


if __name__ == "__main__":
    capture_closing_odds()
    calculate_clv_for_graded()
    print("\n✅ CLOSING ODDS CAPTURE COMPLETE")
