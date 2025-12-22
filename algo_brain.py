#!/usr/bin/env python3
"""
ALGO BRAIN - Always thinking, always analyzing
Called after every data update to find edges in real-time
"""

import os
from sqlalchemy import create_engine, text
from datetime import datetime
import pytz

DATABASE_URL = os.environ.get('DATABASE_URL',
    "postgresql://sb_algo_db_user:0HDtYp4EY2Lo5At8iyf44PD1zDioSPK7@dpg-d495uhchg0os738l1a50-a.virginia-postgres.render.com/sb_algo_db?sslmode=require")

# Edge thresholds - algo only alerts if edge exceeds these
GAME_SPREAD_THRESHOLD = 2.0    # 2+ points edge on spread
GAME_TOTAL_THRESHOLD = 4.0     # 4+ points edge on total
GAME_ML_THRESHOLD = 6.0        # 6%+ edge on moneyline
PROP_EDGE_THRESHOLD = 15.0     # 15%+ edge on props (higher to filter noise)
PROP_MIN_LINE = 1.5            # Ignore props with line < 1.5 (blocks/steals noise)

def get_engine():
    return create_engine(DATABASE_URL)

def analyze_games():
    """Analyze all upcoming games for edges"""
    from math_engine import GamePredictor, GameBettingMemory, PropsMemory
    
    engine = get_engine()
    predictor = GamePredictor(engine)
    memory = GameBettingMemory(engine)
    
    eastern = pytz.timezone('US/Eastern')
    now = datetime.now(eastern)
    today = now.date()
    
    edges_found = []
    
    with engine.connect() as conn:
        # Get today's unplayed games with odds
        games = conn.execute(text("""
            SELECT DISTINCT ON (g.home_team)
                g.home_team, g.visitor_team, g.start_time, g.date,
                bo.home_spread, bo.total, bo.home_ml, bo.away_ml, bo.sportsbook
            FROM games g
            LEFT JOIN LATERAL (
                SELECT home_spread, total, home_ml, away_ml, sportsbook
                FROM betting_odds 
                WHERE game_date = g.date AND home_team = g.home_team
                ORDER BY updated_at DESC LIMIT 1
            ) bo ON true
            WHERE g.date >= :today
            AND (g.home_pts IS NULL OR g.home_pts = 0)
            ORDER BY g.home_team, g.start_time
        """), {"today": today}).fetchall()
    
    for game in games:
        home, away = game[0], game[1]
        start_time, game_date = game[2], game[3]
        spread_line = float(game[4]) if game[4] else None
        total_line = float(game[5]) if game[5] else None
        home_ml = int(game[6]) if game[6] else None
        away_ml = int(game[7]) if game[7] else None
        sportsbook = game[8]
        
        # Run analysis
        analysis = predictor.analyze_game(home, away, spread_line, total_line, home_ml, away_ml)
        spread_pred = analysis['spread']
        total_pred = analysis['total']
        
        # Check for edges
        for pick in analysis.get('picks', []):
            edge = pick['edge']
            pick_type = pick['type']
            
            # Check if edge exceeds threshold
            threshold_met = False
            if pick_type == 'SPREAD' and edge >= GAME_SPREAD_THRESHOLD:
                threshold_met = True
            elif pick_type == 'TOTAL' and edge >= GAME_TOTAL_THRESHOLD:
                threshold_met = True
            elif pick_type == 'MONEYLINE' and edge >= GAME_ML_THRESHOLD:
                threshold_met = True
            
            if threshold_met:
                edge_data = {
                    'type': 'GAME',
                    'subtype': pick_type,
                    'game': f"{away} @ {home}",
                    'pick': pick['pick'],
                    'edge': edge,
                    'confidence': pick['confidence'],
                    'start_time': start_time,
                    'game_date': game_date,
                    'home_team': home,
                    'away_team': away,
                    'line': spread_line if pick_type == 'SPREAD' else total_line,
                    'predicted': spread_pred['predicted_spread'] if pick_type == 'SPREAD' else total_pred['predicted_total'],
                    'sportsbook': sportsbook
                }
                edges_found.append(edge_data)
                
                # Save to memory for tracking
                if pick_type == 'SPREAD':
                    pred_val = spread_pred['predicted_spread']
                    line_val = spread_line
                elif pick_type == 'TOTAL':
                    pred_val = total_pred['predicted_total']
                    line_val = total_line
                else:
                    pred_val = analysis.get('moneyline', {}).get('home_win_prob', 50)
                    line_val = home_ml if home in pick['pick'] else away_ml
                
                memory.save_prediction(
                    game_date=game_date,
                    home_team=home,
                    away_team=away,
                    pred_type=pick_type,
                    pick=pick['pick'],
                    predicted_value=pred_val,
                    line_value=line_val,
                    edge=edge,
                    confidence=pick['confidence'],
                    home_net=spread_pred.get('home_net'),
                    away_net=spread_pred.get('away_net'),
                    home_form=spread_pred.get('home_form'),
                    away_form=spread_pred.get('away_form'),
                    sportsbook=sportsbook,
                    units_bet=2.0 if edge >= 7 else 1.0 if edge >= 4 else 0.5
                )
    
    return edges_found

def analyze_props():
    """Analyze player props for edges - OPTIMIZED VERSION"""
    engine = get_engine()
    
    eastern = pytz.timezone('US/Eastern')
    today = datetime.now(eastern).date()
    
    edges_found = []
    
    # Single optimized query - get props with player averages in one shot
    with engine.connect() as conn:
        results = conn.execute(text("""
            WITH player_avgs AS (
                SELECT 
                    player_name,
                    AVG(pts) as avg_pts,
                    AVG(reb) as avg_reb,
                    AVG(ast) as avg_ast,
                    AVG(fg3m) as avg_fg3m,
                    AVG(stl) as avg_stl,
                    AVG(blk) as avg_blk,
                    COUNT(*) as games
                FROM player_boxscores
                WHERE game_date >= CURRENT_DATE - INTERVAL '20 days'
                GROUP BY player_name
                HAVING COUNT(*) >= 3
            )
            SELECT 
                pp.player_name,
                pp.market,
                pp.line,
                pp.over_odds,
                pp.under_odds,
                pp.sportsbook,
                pp.home_team,
                pp.away_team,
                pa.avg_pts,
                pa.avg_reb,
                pa.avg_ast,
                pa.avg_fg3m,
                pa.avg_stl,
                pa.avg_blk
            FROM player_props pp
            JOIN player_avgs pa ON LOWER(pp.player_name) = LOWER(pa.player_name)
            WHERE pp.game_date = :today
            AND pp.market IN ('player_points', 'player_rebounds', 'player_assists', 
                              'player_threes', 'player_steals', 'player_blocks')
        """), {"today": today}).fetchall()
    
    market_to_col = {
        'player_points': 8,      # avg_pts index
        'player_rebounds': 9,    # avg_reb
        'player_assists': 10,    # avg_ast
        'player_threes': 11,     # avg_fg3m
        'player_steals': 12,     # avg_stl
        'player_blocks': 13      # avg_blk
    }
    
    # Get today's actual games to filter props
    with engine.connect() as conn:
        todays_games = conn.execute(text("""
            SELECT home_team, visitor_team FROM games WHERE date = :today
        """), {"today": today}).fetchall()
    
    # Build list of team abbreviations playing today
    teams_today = set()
    for g in todays_games:
        teams_today.add(g[0])  # home
        teams_today.add(g[1])  # visitor
    
    # Team name mapping
    TEAM_NAMES = {
        'NYK': ['Knicks', 'New York'], 'SAS': ['Spurs', 'San Antonio'],
        'LAL': ['Lakers', 'Los Angeles Lakers'], 'BOS': ['Celtics', 'Boston'],
        'GSW': ['Warriors', 'Golden State'], 'MIA': ['Heat', 'Miami'],
        'CHI': ['Bulls', 'Chicago'], 'CLE': ['Cavaliers', 'Cleveland'],
        'MEM': ['Grizzlies', 'Memphis'], 'MIN': ['Timberwolves', 'Minnesota'],
        'DEN': ['Nuggets', 'Denver'], 'PHX': ['Suns', 'Phoenix'],
        'MIL': ['Bucks', 'Milwaukee'], 'PHI': ['76ers', 'Philadelphia'],
        'DAL': ['Mavericks', 'Dallas'], 'HOU': ['Rockets', 'Houston'],
        'ATL': ['Hawks', 'Atlanta'], 'SAC': ['Kings', 'Sacramento'],
        'OKC': ['Thunder', 'Oklahoma'], 'ORL': ['Magic', 'Orlando'],
        'IND': ['Pacers', 'Indiana'], 'TOR': ['Raptors', 'Toronto'],
        'BKN': ['Nets', 'Brooklyn'], 'DET': ['Pistons', 'Detroit'],
        'CHA': ['Hornets', 'Charlotte'], 'WAS': ['Wizards', 'Washington'],
        'POR': ['Blazers', 'Portland'], 'UTA': ['Jazz', 'Utah'],
        'NOP': ['Pelicans', 'New Orleans'], 'LAC': ['Clippers', 'LA Clippers']
    }
    
    def is_team_playing(home_team_str, away_team_str):
        """Check if the prop's teams are in today's games"""
        for abbr in teams_today:
            names = TEAM_NAMES.get(abbr, [])
            for name in names:
                if name.lower() in home_team_str.lower() or name.lower() in away_team_str.lower():
                    return True
        return False
    
    seen = set()  # Avoid duplicates
    
    for row in results:
        player = row[0]
        market = row[1]
        line = float(row[2]) if row[2] else 0
        over_odds = row[3]
        under_odds = row[4]
        sportsbook = row[5]
        home_team = row[6] or ""
        away_team = row[7] or ""
        
        # Skip if teams not playing today
        if teams_today and not is_team_playing(home_team, away_team):
            continue
        
        if line < PROP_MIN_LINE:
            continue  # Skip low lines like 0.5 blocks - causes inflated edges
        
        # Get projected value from averages
        col_idx = market_to_col.get(market)
        if not col_idx:
            continue
        
        projected = float(row[col_idx]) if row[col_idx] else 0
        if projected <= 0:
            continue
        
        # Calculate edge
        edge_over = ((projected - line) / line * 100)
        edge_under = ((line - projected) / line * 100)
        
        # Only track significant edges
        if edge_over >= PROP_EDGE_THRESHOLD:
            key = f"{player}_{market}_OVER"
            if key not in seen:
                seen.add(key)
                edges_found.append({
                    'type': 'PROP',
                    'subtype': market,
                    'player': player,
                    'pick': f"OVER {line}",
                    'edge': round(edge_over, 1),
                    'projected': round(projected, 1),
                    'line': line,
                    'odds': over_odds,
                    'sportsbook': sportsbook,
                    'game_date': today,
                    'home_team': home_team,
                    'away_team': away_team
                })
        
        elif edge_under >= PROP_EDGE_THRESHOLD:
            key = f"{player}_{market}_UNDER"
            if key not in seen:
                seen.add(key)
                edges_found.append({
                    'type': 'PROP',
                    'subtype': market,
                    'player': player,
                    'pick': f"UNDER {line}",
                    'edge': round(edge_under, 1),
                    'projected': round(projected, 1),
                    'line': line,
                    'odds': under_odds,
                    'sportsbook': sportsbook,
                    'game_date': today,
                    'home_team': home_team,
                    'away_team': away_team
                })
    
    # Save props to database
    try:
        props_memory = PropsMemory(engine)
        for prop in edges_found:
            pick_direction = "OVER" if "OVER" in prop['pick'] else "UNDER"
            units = 1.5 if prop['edge'] >= 25 else 1.0 if prop['edge'] >= 18 else 0.5
            props_memory.save_prop_prediction(
                game_date=today,
                player_name=prop['player'],
                team=prop.get('home_team', ''),
                opponent=prop.get('away_team', ''),
                market=prop['subtype'],
                pick=pick_direction,
                line=prop['line'],
                projected_value=prop['projected'],
                edge=prop['edge'],
                confidence=min(90, 50 + prop['edge']),
                hit_rate_l5=0,
                hit_rate_l10=0,
                sportsbook=prop.get('sportsbook', ''),
                odds=prop.get('odds', 0),
                units_bet=units
            )
        print(f"✅ Saved {len(edges_found)} props to database")
    except Exception as e:
        print(f"⚠️ Could not save props: {e}")
    
    return edges_found

def think():
    """Main brain function - analyzes everything and returns all edges found"""
    eastern = pytz.timezone('US/Eastern')
    now = datetime.now(eastern)
    
    print(f"\n{'='*60}")
    print(f"🧠 ALGO BRAIN ACTIVATED")
    print(f"⏰ {now.strftime('%Y-%m-%d %H:%M:%S')} ET")
    print(f"{'='*60}")
    
    all_edges = []
    
    # Analyze games
    print("\n📊 Analyzing games...")
    try:
        game_edges = analyze_games()
        all_edges.extend(game_edges)
        print(f"   Found {len(game_edges)} game edges")
    except Exception as e:
        print(f"   ❌ Error analyzing games: {e}")
    
    # Analyze props
    print("\n🎯 Analyzing props...")
    try:
        prop_edges = analyze_props()
        all_edges.extend(prop_edges)
        print(f"   Found {len(prop_edges)} prop edges")
    except Exception as e:
        print(f"   ❌ Error analyzing props: {e}")
    
    # Separate game and prop edges
    game_edges = [e for e in all_edges if e['type'] == 'GAME']
    prop_edges = [e for e in all_edges if e['type'] == 'PROP']
    
    game_edges.sort(key=lambda x: -x['edge'])
    prop_edges.sort(key=lambda x: -x['edge'])
    
    # Print game edges
    if game_edges:
        print(f"\n🏀 TOP GAME BETS ({len(game_edges)} total):")
        print(f"{'─'*60}")
        for edge in game_edges[:8]:
            units = "2u" if edge['edge'] >= 7 else "1u" if edge['edge'] >= 4 else "0.5u"
            print(f"   {edge['game']}: {edge['pick']} ({edge['edge']:.1f} pts edge) [{units}]")
    
    # Print prop edges  
    if prop_edges:
        print(f"\n🎯 TOP PROP BETS ({len(prop_edges)} total):")
        print(f"{'─'*60}")
        for edge in prop_edges[:8]:
            units = "1.5u" if edge['edge'] >= 25 else "1u" if edge['edge'] >= 15 else "0.5u"
            print(f"   {edge['player']}: {edge['pick']} ({edge['edge']:.1f}% edge) [{units}]")
    
    if not game_edges and not prop_edges:
        print("\n😴 No significant edges found right now")
    
    print(f"\n{'='*60}")
    print(f"🧠 BRAIN CYCLE COMPLETE")
    print(f"{'='*60}\n")
    
    return all_edges

def alert(edges):
    """Send alerts for edges found (placeholder for Discord/SMS/Email)"""
    # TODO: Implement Discord webhook, SMS, or email alerts
    # For now just prints
    if not edges:
        return
    
    print("\n🚨 ALERTS WOULD BE SENT FOR:")
    for edge in edges[:5]:
        if edge['type'] == 'GAME':
            print(f"   {edge['game']}: {edge['pick']} ({edge['edge']:.1f} pts edge)")
        else:
            print(f"   {edge['player']}: {edge['pick']} ({edge['edge']:.1f}% edge)")

# Main entry point - call this after any data update
def analyze_and_alert():
    """Main function to call after any data update"""
    edges = think()
    if edges:
        alert(edges)
    return edges

if __name__ == "__main__":
    analyze_and_alert()
