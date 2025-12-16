import os
import google.generativeai as genai
from google.generativeai.types import FunctionDeclaration, Tool
from google.api_core.exceptions import ResourceExhausted
from sqlalchemy import create_engine, text
import json
import time
import numpy as np

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
    # (Existing code for history - abbreviated for safety)
    try:
        engine = get_db_engine()
        with engine.connect() as conn:
            games = conn.execute(text("SELECT home_team, visitor_team, home_pts, visitor_pts, home_win FROM games WHERE date = :d"), {"d": date}).fetchall()
            return str(games)
    except Exception as e: return str(e)

def check_player_projection(player_name: str, stat_type: str, line: float):
    """
    Runs a LIVE Monte Carlo simulation for a specific player to check a betting line.
    Args:
        player_name: Full name (e.g. 'LeBron James')
        stat_type: 'points', 'rebounds', 'assists', 'threes'
        line: The betting line to test (e.g. 24.5)
    """
    try:
        from math_engine import PlayerSimulator
        engine = get_db_engine()
        if not engine: return "Database Error"
        
        sim = PlayerSimulator(engine)
        result = sim.run_projection(player_name, stat_type, line)
        return result
    except Exception as e:
        return f"Calculation Error: {str(e)}"

# --- INITIALIZE MODEL ---
tools_list = [get_algo_status, lookup_historical_data, check_player_projection]

system_prompt = """
You are the President of the SB-ALGO.
You are "Always Awake". You monitor lines 24/7.

YOUR PROTOCOL:
1. **Specific Line Checks:** If a user asks "Is Wemby 20.5 good?", YOU MUST use 'check_player_projection'.
   - Input: player_name="Victor Wembanyama", stat_type="points", line=20.5.
   - Output: Analyze the EV/Edge returned by the tool.
   
2. **Proactive Tone:** You are Javier's Right Hand Man. Speak directly to him. 
   - "Yo Javier, ran the numbers..."
   - "Stay away from that one."
   - "Green light, heavy edge."

3. **Data Authority:** Never guess. If you don't know, run a simulation.
"""

try:
    model = genai.GenerativeModel('gemini-2.0-flash', tools=tools_list, system_instruction=system_prompt)
    chat_session = model.start_chat(enable_automatic_function_calling=True)
except:
    chat_session = None

def query_algo_agent(user_input):
    if not chat_session: return "Offline."
    try:
        return chat_session.send_message(user_input).text
    except Exception as e:
        return f"Error: {e}"
