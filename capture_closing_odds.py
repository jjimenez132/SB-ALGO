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
    
    # Get today's date in Eastern Time (not UTC)
    today_et = get_eastern_time().date()
    
    with engine.connect() as conn:
        # Get today's pending picks that need closing odds
        picks = conn.execute(text("""
            SELECT id, pick_id, pick_name, pick_type, odds, line
            FROM algo_picks_tracking 
            WHERE pick_date = :today 
            AND (closing_odds IS NULL OR clv_cents IS NULL)
        """), {'today': today_et}).fetchall()
        
        if not picks:
            print("   ℹ️ No pending picks need closing odds")
            return
        
        print(f"   📋 Found {len(picks)} picks needing closing odds")
        
        # Get sent picks for full pick info (has stat type and side)
        sent_picks = conn.execute(text("""
            SELECT pick_key FROM discord_sent_picks 
            WHERE sent_date = :today
        """), {'today': today_et}).fetchall()
        sent_keys = [row[0] for row in sent_picks]
        
        updated = 0
        
        for pick in picks:
            pick_id, pick_code, pick_name, pick_type, opening_odds, line = pick
            closing_odds = None
            
            if pick_type == 'prop':
                player_name = pick_name.strip()
                stat = None
                side = None
                
                # First try to find in sent_picks
                for key in sent_keys:
                    if key.startswith('PROP_') and player_name in key:
                        parts = key.split('_')
                        if len(parts) >= 4:
                            stat = parts[-2]  # PTS, REB, AST
                            side = parts[-1]  # OVER, UNDER
                        break
                
                # If not found in sent_picks, default to PTS and check both sides
                if not stat:
                    stat = 'PTS'
                    # We'll try to figure out side from opening odds vs current odds
                
                stat_map = {'PTS': 'player_points', 'REB': 'player_rebounds', 'AST': 'player_assists'}
                market = stat_map.get(stat, 'player_points')
                
                # Get latest odds for this player/market
                # Only require the side we need to have odds
                result = conn.execute(text("""
                    SELECT over_odds, under_odds, line
                    FROM player_props 
                    WHERE game_date = :today 
                    AND LOWER(player_name) LIKE :player
                    AND market = :market
                    ORDER BY updated_at DESC 
                    LIMIT 1
                """), {
                    'today': today_et,
                    'player': f'%{player_name.lower()}%',
                    'market': market
                }).fetchone()
                
                if result:
                    over_close, under_close, prop_line = result
                    
                    if side == 'OVER' and over_close:
                        closing_odds = over_close
                    elif side == 'UNDER' and under_close:
                        closing_odds = under_close
                    elif over_close:
                        closing_odds = over_close
                    elif under_close:
                        closing_odds = under_close
                    
                    if closing_odds:
                        print(f"   ✅ {player_name} {stat} {side or '?'}: {opening_odds} → {closing_odds}")
                    else:
                        print(f"   ⚠️ {player_name}: Odds for {side} not available")
                else:
                    print(f"   ⚠️ {player_name}: No odds data found")
            
            elif pick_type == 'game':
                parts = pick_name.split()
                
                if '@' in pick_name:
                    at_idx = parts.index('@')
                    visitor_team = parts[at_idx - 1] if at_idx > 0 else None
                    home_team = parts[at_idx + 1] if at_idx + 1 < len(parts) else None
                    
                    # Normalize team names for database lookup
                    team_map = {'GSW': 'GS', 'PHX': 'PHO', 'NOP': 'NO', 'NYK': 'NY', 'SAS': 'SA', 'BKN': 'BK'}
                    visitor_team = team_map.get(visitor_team, visitor_team)
                    home_team = team_map.get(home_team, home_team)
                    
                    if 'UNDER' in pick_name.upper():
                        result = conn.execute(text("""
                            SELECT under_odds FROM games_with_odds 
                            WHERE game_date = :today 
                            AND home_team = :home AND visitor_team = :visitor
                            LIMIT 1
                        """), {'today': today_et, 'home': home_team, 'visitor': visitor_team}).fetchone()
                        if result and result[0]:
                            closing_odds = result[0]
                    
                    elif 'ML' in pick_name.upper():
                        # Figure out which team
                        team = None
                        for p in parts:
                            if p in [home_team, visitor_team]:
                                team = p
                                break
                        if not team:
                            team = visitor_team  # Default
                        
                        result = conn.execute(text("""
                            SELECT home_ml, away_ml FROM games_with_odds 
                            WHERE game_date = :today 
                            AND home_team = :home AND visitor_team = :visitor
                            LIMIT 1
                        """), {'today': today_et, 'home': home_team, 'visitor': visitor_team}).fetchone()
                        if result:
                            closing_odds = result[0] if team == home_team else result[1]
                    
                    elif '+' in pick_name or '-' in pick_name.split()[-1]:
                        # Spread bet - use betting_odds table
                        result = conn.execute(text("""
                            SELECT home_spread_odds, away_spread_odds FROM betting_odds 
                            WHERE game_date = :today 
                            AND home_team = :home AND away_team = :visitor
                            ORDER BY updated_at DESC
                            LIMIT 1
                        """), {'today': today_et, 'home': home_team, 'visitor': visitor_team}).fetchone()
                        if result:
                            # Check if picked team is visitor (getting points) or home
                            if f"{visitor_team} +" in pick_name:
                                closing_odds = result[1]  # away_spread_odds
                            else:
                                closing_odds = result[0]  # home_spread_odds
                    
                    if closing_odds:
                        print(f"   ✅ {pick_name[:40]}: {opening_odds} → {closing_odds}")
                    else:
                        print(f"   ⚠️ {pick_name[:40]}: No closing odds found")
            
            # Update database if we got closing odds
            if closing_odds:
                # Calculate CLV
                def calc_clv(open_odds, close_odds):
                    def to_implied(odds):
                        if odds < 0:
                            return abs(odds) / (abs(odds) + 100)
                        return 100 / (odds + 100)
                    open_imp = to_implied(open_odds)
                    close_imp = to_implied(close_odds)
                    return round((close_imp - open_imp) * 100, 2)
                
                clv = calc_clv(opening_odds, closing_odds)
                
                conn.execute(text("""
                    UPDATE algo_picks_tracking 
                    SET closing_odds = :close, clv_cents = :clv
                    WHERE id = :id
                """), {'close': closing_odds, 'clv': clv, 'id': pick_id})
                conn.commit()
                updated += 1
        
        print(f"\n   ✅ Updated {updated}/{len(picks)} picks with closing odds")


if __name__ == "__main__":
    capture_closing_odds()
