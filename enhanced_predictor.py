#!/usr/bin/env python3
"""
Enhanced Predictor - Uses NBA.com Advanced Stats
Integrates with existing algo_brain.py
"""

from sqlalchemy import create_engine, text
import os

DATABASE_URL = os.environ.get('DATABASE_URL',
    "postgresql://sb_algo_db_user:0HDtYp4EY2Lo5At8iyf44PD1zDioSPK7@dpg-d495uhchg0os738l1a50-a.virginia-postgres.render.com/sb_algo_db?sslmode=require")

def get_engine():
    return create_engine(DATABASE_URL)

def get_advanced_team_stats(team_name):
    """Get NBA.com advanced stats for a team"""
    engine = get_engine()
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT "TEAM_NAME", "NET_RATING", "OFF_RATING", "DEF_RATING", 
                   "PACE", "EFG_PCT", "TS_PCT", "OREB_PCT", "DREB_PCT",
                   "TM_TOV_PCT", "AST_PCT"
            FROM nba_team_advanced_stats 
            WHERE "TEAM_NAME" ILIKE :team
            LIMIT 1
        """), {"team": f"%{team_name}%"}).fetchone()
        
        if result:
            return {
                'team': result[0],
                'net_rating': float(result[1] or 0),
                'off_rating': float(result[2] or 110),
                'def_rating': float(result[3] or 110),
                'pace': float(result[4] or 100),
                'efg_pct': float(result[5] or 0.5),
                'ts_pct': float(result[6] or 0.5),
                'oreb_pct': float(result[7] or 0.25),
                'dreb_pct': float(result[8] or 0.75),
                'tov_pct': float(result[9] or 0.12),
                'ast_pct': float(result[10] or 0.6),
            }
        return None

def get_four_factors(team_name):
    """Get Four Factors (Dean Oliver) for a team"""
    engine = get_engine()
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT "TEAM_NAME", "EFG_PCT", "FTA_RATE", "TM_TOV_PCT", "OREB_PCT"
            FROM nba_team_four_factors 
            WHERE "TEAM_NAME" ILIKE :team
            LIMIT 1
        """), {"team": f"%{team_name}%"}).fetchone()
        
        if result:
            return {
                'team': result[0],
                'efg_pct': float(result[1] or 0.5),
                'fta_rate': float(result[2] or 0.2),
                'tov_pct': float(result[3] or 0.12),
                'oreb_pct': float(result[4] or 0.25),
            }
        return None

def enhanced_spread_prediction(home_team, away_team):
    """
    Predict spread using NBA.com advanced stats
    More accurate than box score derived stats
    """
    home = get_advanced_team_stats(home_team)
    away = get_advanced_team_stats(away_team)
    
    if not home or not away:
        return None
    
    # Home court advantage (NBA average ~3.0 points)
    HOME_COURT = 3.0
    
    # Net Rating is points per 100 possessions differential
    # This is the BEST single predictor of team quality
    net_diff = home['net_rating'] - away['net_rating']
    
    # Pace interaction - faster pace = more possessions = larger margins
    pace_avg = (home['pace'] + away['pace']) / 2
    pace_factor = (pace_avg - 100) / 100  # Adjust for pace
    
    # Four Factors edge (eFG%, TOV%, OREB%, FTr)
    efg_edge = (home['efg_pct'] - away['efg_pct']) * 100  # Convert to points
    tov_edge = (away['tov_pct'] - home['tov_pct']) * 50   # Lower is better
    oreb_edge = (home['oreb_pct'] - away['oreb_pct']) * 30
    
    # Offensive vs Defensive matchup
    # Home offense vs Away defense
    home_off_edge = home['off_rating'] - away['def_rating']
    # Away offense vs Home defense  
    away_off_edge = away['off_rating'] - home['def_rating']
    matchup_edge = (home_off_edge - away_off_edge) / 2
    
    # Combine factors (weighted)
    # Net Rating is most important (~70% of prediction)
    raw_spread = (
        net_diff * 0.70 +           # Net rating diff
        matchup_edge * 0.15 +       # Matchup specific
        efg_edge * 0.05 +           # Shooting edge
        tov_edge * 0.05 +           # Turnover edge
        oreb_edge * 0.05            # Rebounding edge
    )
    
    # Apply home court and pace adjustment
    predicted_spread = -(raw_spread + HOME_COURT) * (1 + pace_factor * 0.1)
    
    # Confidence based on data quality and matchup clarity
    net_clarity = min(abs(net_diff) / 10, 1.0)  # Bigger diff = more confident
    confidence = 50 + (net_clarity * 40)  # 50-90% range
    
    return {
        'home_team': home_team,
        'away_team': away_team,
        'predicted_spread': round(predicted_spread, 1),
        'confidence': round(confidence, 1),
        'net_diff': round(net_diff, 1),
        'home_net_rating': home['net_rating'],
        'away_net_rating': away['net_rating'],
        'home_off_rating': home['off_rating'],
        'home_def_rating': home['def_rating'],
        'away_off_rating': away['off_rating'],
        'away_def_rating': away['def_rating'],
        'pace_avg': round(pace_avg, 1),
    }

def enhanced_total_prediction(home_team, away_team):
    """
    Predict total using pace and efficiency
    """
    home = get_advanced_team_stats(home_team)
    away = get_advanced_team_stats(away_team)
    
    if not home or not away:
        return None
    
    # Pace determines possessions
    # Average NBA game is ~100 possessions per team
    pace_avg = (home['pace'] + away['pace']) / 2
    estimated_possessions = pace_avg
    
    # Points = Possessions * Offensive Rating / 100
    home_pts = estimated_possessions * home['off_rating'] / 100
    away_pts = estimated_possessions * away['off_rating'] / 100
    
    # Defensive adjustment
    # If facing good defense, reduce expected points
    home_pts_adj = home_pts * (away['def_rating'] / 110)  # 110 is league avg
    away_pts_adj = away_pts * (home['def_rating'] / 110)
    
    predicted_total = home_pts_adj + away_pts_adj
    
    # Confidence based on pace consistency
    pace_diff = abs(home['pace'] - away['pace'])
    confidence = max(50, 85 - pace_diff)  # More similar pace = more confident
    
    return {
        'home_team': home_team,
        'away_team': away_team,
        'predicted_total': round(predicted_total, 1),
        'confidence': round(confidence, 1),
        'home_projected_pts': round(home_pts_adj, 1),
        'away_projected_pts': round(away_pts_adj, 1),
        'pace_avg': round(pace_avg, 1),
        'home_pace': home['pace'],
        'away_pace': away['pace'],
    }

def find_edge(home_team, away_team, book_spread=None, book_total=None):
    """
    Find edges by comparing predictions to book lines
    """
    spread_pred = enhanced_spread_prediction(home_team, away_team)
    total_pred = enhanced_total_prediction(home_team, away_team)
    
    edges = []
    
    if spread_pred and book_spread is not None:
        spread_edge = book_spread - spread_pred['predicted_spread']
        # Positive edge = value on home team
        # Negative edge = value on away team
        if abs(spread_edge) >= 2.0:  # 2+ point edge
            pick = home_team if spread_edge > 0 else away_team
            edges.append({
                'type': 'SPREAD',
                'pick': f"{pick} {'+' if book_spread > 0 else ''}{book_spread}",
                'edge': round(abs(spread_edge), 1),
                'predicted': spread_pred['predicted_spread'],
                'book_line': book_spread,
                'confidence': spread_pred['confidence'],
            })
    
    if total_pred and book_total is not None:
        total_edge = total_pred['predicted_total'] - book_total
        if abs(total_edge) >= 4.0:  # 4+ point edge
            pick = "OVER" if total_edge > 0 else "UNDER"
            edges.append({
                'type': 'TOTAL',
                'pick': f"{pick} {book_total}",
                'edge': round(abs(total_edge), 1),
                'predicted': total_pred['predicted_total'],
                'book_line': book_total,
                'confidence': total_pred['confidence'],
            })
    
    return {
        'spread_prediction': spread_pred,
        'total_prediction': total_pred,
        'edges': edges,
    }


# Test
if __name__ == "__main__":
    print("=" * 60)
    print("ENHANCED PREDICTOR TEST")
    print("=" * 60)
    
    # Test with today's games or sample matchup
    matchups = [
        ("Celtics", "Lakers"),
        ("Thunder", "Timberwolves"),
        ("Cavaliers", "Knicks"),
    ]
    
    for home, away in matchups:
        print(f"\n{away} @ {home}")
        print("-" * 40)
        
        spread = enhanced_spread_prediction(home, away)
        total = enhanced_total_prediction(home, away)
        
        if spread:
            print(f"  Spread: {spread['predicted_spread']:+.1f}")
            print(f"  Net Rating: {home} {spread['home_net_rating']:+.1f} vs {away} {spread['away_net_rating']:+.1f}")
        
        if total:
            print(f"  Total: {total['predicted_total']:.1f}")
            print(f"  Pace: {total['pace_avg']:.1f}")
        
        # Simulate book line to find edge
        if spread and total:
            result = find_edge(home, away, book_spread=-5.0, book_total=220.0)
            if result['edges']:
                print(f"  🎯 EDGES FOUND:")
                for e in result['edges']:
                    print(f"     {e['type']}: {e['pick']} (+{e['edge']} pts edge)")
    
    print("\n✅ Enhanced Predictor Ready!")
