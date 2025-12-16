"""
SB-ALGO AI Agent Layer
Google Gemini 2.0 Flash with Function Calling
"""

import os
import json
import time
import google.generativeai as genai
from google.api_core.exceptions import ResourceExhausted
from sqlalchemy import create_engine, text
from datetime import datetime
import pytz

# --- CONFIGURATION ---
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "")
DATABASE_URL = os.environ.get("DATABASE_URL")

# Team abbreviation mapping (odds API vs standard)
TEAM_MAP = {
    'NY': 'NYK', 'GS': 'GSW', 'SA': 'SAS', 'NO': 'NOP', 
    'PHO': 'PHX', 'UTAH': 'UTA', 'WSH': 'WAS', 'CHA': 'CHO'
}
TEAM_MAP_REVERSE = {v: k for k, v in TEAM_MAP.items()}

def get_db_engine():
    if DATABASE_URL:
        return create_engine(DATABASE_URL)
    return None

# --- TOOL FUNCTIONS ---

def get_algo_status():
    """Check system health and pipeline status"""
    engine = get_db_engine()
    if not engine:
        return json.dumps({"error": "Database not connected"})
    
    eastern = pytz.timezone('US/Eastern')
    now = datetime.now(eastern)
    
    try:
        with engine.connect() as conn:
            odds_result = conn.execute(text("SELECT MAX(updated_at) FROM betting_odds")).fetchone()
            last_odds = odds_result[0] if odds_result and odds_result[0] else None
            
            if last_odds:
                if last_odds.tzinfo is None:
                    last_odds = eastern.localize(last_odds)
                mins_ago = int((now - last_odds).total_seconds() / 60)
                odds_status = f"{mins_ago} minutes ago"
            else:
                mins_ago = 999
                odds_status = "No data"
            
            injury_result = conn.execute(text("SELECT COUNT(*) FROM injuries")).fetchone()
            injury_count = injury_result[0] if injury_result else 0
            
            today = now.strftime('%Y-%m-%d')
            games_result = conn.execute(text("SELECT COUNT(*) FROM games WHERE date = :today"), {"today": today}).fetchone()
            games_today = games_result[0] if games_result else 0
            
            props_result = conn.execute(text("SELECT COUNT(*) FROM player_props WHERE game_date = :today"), {"today": today}).fetchone()
            props_count = props_result[0] if props_result else 0
            
            return json.dumps({
                "odds_api_status": "Online" if mins_ago < 360 else "Stale",
                "last_odds_update": odds_status,
                "active_injuries": injury_count,
                "games_today": games_today,
                "props_available": props_count,
                "database_connection": "Stable",
                "current_time_et": now.strftime('%Y-%m-%d %H:%M:%S ET')
            })
    except Exception as e:
        return json.dumps({"error": str(e)})


def check_injuries(team: str = "ALL"):
    """Check injury report"""
    engine = get_db_engine()
    if not engine:
        return json.dumps({"error": "Database not connected"})
    
    try:
        with engine.connect() as conn:
            if team == "ALL":
                injuries = conn.execute(text("SELECT player_name, status, description FROM injuries LIMIT 15")).fetchall()
            else:
                injuries = conn.execute(text("""
                    SELECT player_name, status, description FROM injuries 
                    WHERE description ILIKE :team LIMIT 10
                """), {"team": f"%{team}%"}).fetchall()
            
            return json.dumps({
                "count": len(injuries),
                "injuries": [{"player": i[0], "status": i[1], "notes": i[2]} for i in injuries]
            })
    except Exception as e:
        return json.dumps({"error": str(e)})


# --- INITIALIZE MODEL ---
AGENT_AVAILABLE = False
chat = None

try:
    if GOOGLE_API_KEY:
        genai.configure(api_key=GOOGLE_API_KEY)
        
        model = genai.GenerativeModel(
            model_name='gemini-2.0-flash',
            system_instruction="""You are SB-ALGO's voice - the mouthpiece for a proprietary NBA Betting Algorithm.

YOUR ROLE:
- You COMMUNICATE what the algorithm has already calculated
- You DO NOT analyze - the algo already did that
- You TRANSLATE the algo's mathematical outputs into clear language
- You REPORT the algo's picks, edges, and confidence levels

YOUR MANNER:
- Direct, confident, no hedging
- Speak as "The Algorithm determined..." or "My analysis shows..."
- Use first person - you ARE the algo speaking

SYSTEM SCHEDULES (this is normal operation):
- Game odds: 3x daily via Tank01 API
- Player props: 2x daily (7 AM & 4 PM ET) via The Odds API  
- Injuries: Hourly
- News: Hourly
- Odds <6 hours old = FRESH

When asked about picks, edges, or recommendations - report what the algo calculated.
When asked about system status - check the data and report."""
        )
        
        chat = model.start_chat()
        AGENT_AVAILABLE = True
        print("Gemini Agent initialized successfully")
except Exception as e:
    print(f"Gemini init error: {e}")


def query_algo_agent(user_input: str) -> str:
    """Main query function for the agent"""
    if not AGENT_AVAILABLE or not chat:
        return "ALGO AGENT OFFLINE: Check API key configuration."
    
    max_retries = 5
    base_wait = 4
    
    for attempt in range(max_retries):
        try:
            lower_input = user_input.lower()
            
            if any(word in lower_input for word in ['status', 'health', 'pulling', 'working', 'online', 'running']):
                status = get_algo_status()
                context = f"System Status Data: {status}\n\nUser asked: {user_input}\n\nReport this status as the algo's voice."
                response = chat.send_message(context)
                return response.text
            
            elif any(word in lower_input for word in ['injury', 'injuries', 'hurt', 'out']):
                teams = ['LAL', 'BOS', 'GSW', 'MIA', 'DEN', 'PHX', 'MIL', 'PHI', 'CLE', 'NYK', 'BKN', 'CHI', 'ATL', 'DAL', 'HOU', 'MEM', 'MIN', 'NOP', 'OKC', 'ORL', 'POR', 'SAC', 'SAS', 'TOR', 'UTA', 'WAS', 'CHA', 'DET', 'IND', 'LAC']
                team = "ALL"
                for t in teams:
                    if t.lower() in lower_input:
                        team = t
                        break
                injuries = check_injuries(team)
                context = f"Injury Data: {injuries}\n\nUser asked: {user_input}\n\nReport injuries as the algo's voice."
                response = chat.send_message(context)
                return response.text
            
            elif any(word in lower_input for word in ['game', 'matchup', 'spread', 'bet', 'pick', 'edge', 'best', 'top', 'today', 'knicks', 'lakers', 'celtics', 'warriors', 'heat', 'nuggets', 'suns', 'bucks', 'sixers', 'cavs', 'nets', 'bulls', 'hawks', 'mavs', 'rockets', 'grizzlies', 'wolves', 'pelicans', 'thunder', 'magic', 'blazers', 'kings', 'spurs', 'raptors', 'jazz', 'wizards', 'hornets', 'pistons', 'pacers', 'clippers']):
                engine = get_db_engine()
                eastern = pytz.timezone('US/Eastern')
                today = datetime.now(eastern).strftime('%Y-%m-%d')
                
                all_picks = []
                try:
                    with engine.connect() as conn:
                        games_raw = conn.execute(text("""
                            SELECT home_team, visitor_team FROM games 
                            WHERE date = :today AND (home_pts IS NULL OR home_pts = 0)
                        """), {"today": today}).fetchall()
                        
                        games = []
                        for g in games_raw:
                            home, away = g[0], g[1]
                            odds_home = TEAM_MAP_REVERSE.get(home, home)
                            odds_row = conn.execute(text("""
                                SELECT home_spread, total FROM betting_odds 
                                WHERE game_date = :today AND home_team = :home LIMIT 1
                            """), {"today": today, "home": odds_home}).fetchone()
                            spread = float(odds_row[0]) if odds_row and odds_row[0] else None
                            total = float(odds_row[1]) if odds_row and odds_row[1] else None
                            games.append((home, away, spread, total))
                        
                        if games:
                            from math_engine import GamePredictor
                            predictor = GamePredictor(engine)
                            
                            for home, away, spread, total in games:
                                analysis = predictor.analyze_game(home, away, spread, total)
                                for pick in analysis.get('picks', []):
                                    all_picks.append({
                                        "game": f"{away} @ {home}",
                                        "pick": pick['pick'],
                                        "edge": pick['edge'],
                                        "confidence": pick['confidence'],
                                        "type": pick['type']
                                    })
                            
                            all_picks.sort(key=lambda x: -x['edge'])
                except Exception as e:
                    all_picks = [{"error": str(e)}]
                
                if all_picks and "error" not in all_picks[0]:
                    context = f"TODAY'S ALGO PICKS (sorted by edge):\n{json.dumps(all_picks[:10], indent=2)}\n\nUser asked: {user_input}\n\nReport these picks as the algo's voice. Only mention picks from the data above."
                else:
                    context = f"No picks available. Games: {len(games_raw) if 'games_raw' in dir() else 0}. User asked: {user_input}\n\nExplain that picks are being calculated or no games today."
                
                response = chat.send_message(context)
                return response.text
            
            else:
                response = chat.send_message(user_input)
                return response.text
                
        except ResourceExhausted:
            wait_time = base_wait * (2 ** attempt)
            print(f"Rate limit hit. Waiting {wait_time}s...")
            time.sleep(wait_time)
            continue
        except Exception as e:
            return f"AGENT ERROR: {str(e)}"
    
    return "AGENT ERROR: Rate limit exceeded. Try again in a minute."


def get_algo_ai():
    """Returns agent interface for UI compatibility"""
    if AGENT_AVAILABLE:
        class AgentWrapper:
            def analyze_game(self, data):
                return query_algo_agent(f"Analyze: {data}")
            def analyze_player_prop(self, data):
                return query_algo_agent(f"Prop analysis: {data}")
            def chat(self, msg, ctx=None):
                return query_algo_agent(msg)
        return AgentWrapper()
    return None


if __name__ == "__main__":
    print("User: What do you have on the Knicks game?")
    response = query_algo_agent("What do you have on the Knicks game?")
    print(f"Agent: {response}")
