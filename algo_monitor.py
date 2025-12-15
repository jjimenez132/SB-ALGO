#!/usr/bin/env python3
"""ALGO MONITOR - Fast"""
import os
from sqlalchemy import create_engine, text
from datetime import datetime
import pytz

def run_analysis():
    engine = create_engine(os.environ.get('DATABASE_URL'))
    today = datetime.now(pytz.timezone('US/Eastern')).strftime('%Y-%m-%d')
    
    print(f"🧠 MONITOR {today}")
    
    with engine.connect() as conn:
        games = conn.execute(text("""
            SELECT g.home_team, g.visitor_team, b.home_spread, b.total
            FROM games g
            LEFT JOIN betting_odds b ON b.game_date = g.date AND b.home_team = g.home_team
            WHERE g.date = :today AND (g.home_pts IS NULL OR g.home_pts = 0)
            LIMIT 15
        """), {"today": today}).fetchall()
    
    print(f"✅ {len(games)} games")
    
    from math_engine import GamePredictor
    predictor = GamePredictor(engine)
    
    for g in games:
        a = predictor.analyze_game(g[0], g[1], float(g[2]) if g[2] else None, float(g[3]) if g[3] else None)
        for p in a.get('picks', []):
            if p['edge'] >= 5:
                print(f"🔥 {g[1]}@{g[0]}: {p['pick']} ({p['edge']:.1f})")

if __name__ == "__main__":
    run_analysis()
