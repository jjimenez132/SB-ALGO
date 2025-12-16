import os
import google.generativeai as genai
from google.generativeai.types import FunctionDeclaration, Tool
from google.api_core.exceptions import ResourceExhausted
from sqlalchemy import create_engine, text
import json
import time

# --- CONFIGURATION ---
api_key = os.environ.get("GOOGLE_API_KEY")
if not api_key:
    print("⚠️ WARNING: GOOGLE_API_KEY not found.")
else:
    genai.configure(api_key=api_key)

def get_db_engine():
    try:
        db_url = os.environ.get("DATABASE_URL")
        if not db_url: return None
        return create_engine(db_url)
    except: return None

# --- TOOLS ---

def get_algo_status():
    return {"status": "Online", "mode": "Presidential"}

def lookup_historical_data(date: str):
    """Retrieves NBA games and stats for a historical date (YYYY-MM-DD)."""
    try:
        engine = get_db_engine()
        with engine.connect() as conn:
            # Games
            games = conn.execute(text("SELECT home_team, visitor_team, home_pts, visitor_pts, home_win FROM games WHERE date = :d ORDER BY start_time"), {"d": date}).fetchall()
            if not games: return f"No games found for {date}."
            
            games_list = []
            for g in games:
                score = f"{g[0]} {int(g[2] or 0)} - {g[1]} {int(g[3] or 0)}"
                games_list.append(score)

            # Top Players
            players = conn.execute(text("SELECT player_name, pts, reb, ast FROM player_boxscores WHERE game_date = :d ORDER BY pts DESC LIMIT 5"), {"d": date}).fetchall()
            top_players = [f"{p[0]}: {int(p[1])}pts" for p in players]

            return {"date": date, "games": games_list, "leaders": top_players}
    except Exception as e: return f"Error: {str(e)}"

def check_player_projection(player_name: str, stat_type: str, line: float):
    """Runs a LIVE Monte Carlo simulation for a player line (e.g. 'LeBron James', 'points', 24.5)."""
    try:
        # Import inside function to avoid circular import issues
        from math_engine import PlayerSimulator
        engine = get_db_engine()
        if not engine: return "Database Error"
        
        sim = PlayerSimulator(engine)
        return sim.run_projection(player_name, stat_type, line)
    except Exception as e:
        return f"Calculation Error: {str(e)}"

# --- INITIALIZE MODEL ---
tools_list = [get_algo_status, lookup_historical_data, check_player_projection]

system_prompt = """
You are the President of the SB-ALGO.
You are "Always Awake".

YOUR PROTOCOL:
1. **Line Checks:** If user asks "Is Wemby 20.5 good?", use 'check_player_projection'.
2. **History:** If user asks about a past date, use 'lookup_historical_data'.
3. **Tone:** Direct. "Yo Javier, ran the numbers..."
"""

try:
    model = genai.GenerativeModel('gemini-2.0-flash', tools=tools_list, system_instruction=system_prompt)
    chat_session = model.start_chat(enable_automatic_function_calling=True)
except Exception as e:
    print(f"Model Init Error: {e}")
    chat_session = None

def query_algo_agent(user_input):
    if not chat_session: return "Offline (Check API Key)"
    try:
        return chat_session.send_message(user_input).text
    except Exception as e: return f"Error: {str(e)}"

# --- COMPATIBILITY LAYER (THE FIX) ---

# 1. Availability Flag
AGENT_AVAILABLE = True if chat_session else False

# 2. Wrapper Class for Dashboard
class AlgoAgentWrapper:
    def __init__(self, session):
        self.session = session

    def chat(self, user_input, context=""):
        if context:
            full_prompt = f"{context}\n\nUSER QUESTION: {user_input}"
            return query_algo_agent(full_prompt)
        return query_algo_agent(user_input)

    def analyze_game(self, game_data):
        h = game_data.get('home_team', 'Home')
        a = game_data.get('away_team', 'Away')
        return query_algo_agent(f"Analyze matchup {a} vs {h}.")

# 3. Factory Function (Required by Dashboard)
def get_algo_ai():
    if chat_session:
        return AlgoAgentWrapper(chat_session)
    return None
