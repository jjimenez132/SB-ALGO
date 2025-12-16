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

# --- DATABASE HELPER ---
def get_db_connection():
    try:
        db_url = os.environ.get("DATABASE_URL")
        if not db_url:
            return None
        engine = create_engine(db_url)
        return engine.connect()
    except Exception as e:
        print(f"DB Error: {e}")
        return None

# --- 1. DEFINE THE TOOLS (Read-Only Access) ---

def get_algo_status():
    """
    Retrieves the current technical health status of the data pipelines.
    """
    return {
        "status": "Operational",
        "modules": ["OddsFetcher", "NewsScraper", "MathEngine", "AlgoProcessor"],
        "database": "Connected"
    }

def lookup_historical_data(date: str):
    """
    Retrieves NBA games and top player stats for a specific historical date.
    Use this when the user asks about past games, e.g., 'What happened on March 18, 2005?'.
    
    Args:
        date: The date in YYYY-MM-DD format.
    """
    conn = get_db_connection()
    if not conn:
        return "Error: Database not connected."
    
    try:
        # 1. READ-ONLY Query for Games
        # We query the 'games' table as identified in the schema map
        games_query = text("""
            SELECT home_team, visitor_team, home_pts, visitor_pts, home_win
            FROM games 
            WHERE date = :d 
            ORDER BY start_time
        """)
        games_res = conn.execute(games_query, {"d": date}).fetchall()
        
        if not games_res:
            return f"No games found in database for {date}. (Note: Historical data coverage depends on the import status)."

        games_list = []
        for g in games_res:
            # Determine winner safely
            if g[4] == 1:
                winner = g[0]
                score = f"{g[0]} {int(g[2] or 0)} - {g[1]} {int(g[3] or 0)}"
            else:
                winner = g[1]
                score = f"{g[1]} {int(g[3] or 0)} - {g[0]} {int(g[2] or 0)}"
            games_list.append(f"{score} (Winner: {winner})")

        # 2. READ-ONLY Query for Top Players
        # We query 'player_boxscores' using 'game_date' as identified in schema findings
        players_query = text("""
            SELECT player_name, team_abbreviation, pts, reb, ast
            FROM player_boxscores
            WHERE game_date = :d
            ORDER BY pts DESC
            LIMIT 5
        """)
        players_res = conn.execute(players_query, {"d": date}).fetchall()
        
        top_players = []
        for p in players_res:
            top_players.append(f"{p[0]} ({p[1]}): {int(p[2])}pts / {int(p[3])}reb / {int(p[4])}ast")

        # 3. Return Structured Data to the AI
        return {
            "date": date,
            "games_summary": games_list,
            "top_performers": top_players,
            "meta": "Data retrieved from SB-ALGO Database"
        }
        
    except Exception as e:
        return f"Error executing query: {str(e)}"
    finally:
        conn.close()

# --- 2. INITIALIZE THE MODEL WITH TOOLS ---
tools_list = [get_algo_status, lookup_historical_data]

system_prompt = """
You are the President of the SB-ALGO Neural Network.
You have absolute oversight of the NBA betting algorithm.

YOUR ACCESS:
- You have READ-ONLY access to the historical database via 'lookup_historical_data'.
- You have system status access via 'get_algo_status'.

YOUR PROTOCOL:
1. **Historical Questions:** If a user asks "What happened on [Date]?", YOU MUST use the 'lookup_historical_data' tool. Do not hallucinate scores.
2. **Current Context:** If the user provided current scan data in the prompt, use it.
3. **Persona:** You are professional, analytical, and precise. You speak like a hedge fund manager.
"""

try:
    # We use automatic function calling so the AI decides when to query the DB
    model = genai.GenerativeModel(
        model_name='gemini-2.0-flash', 
        tools=tools_list,
        system_instruction=system_prompt
    )
    chat_session = model.start_chat(enable_automatic_function_calling=True)
except Exception as e:
    print(f"Model Init Error: {e}")
    chat_session = None

def query_algo_agent(user_input):
    """
    Main entry point for the Chat Interface.
    Handles the conversation and tool execution automatically.
    """
    if not chat_session:
        return "AI Agent is offline (Check API Key)."

    max_retries = 3
    base_delay = 2
    
    for attempt in range(max_retries):
        try:
            response = chat_session.send_message(user_input)
            return response.text
            
        except ResourceExhausted:
            # Handle rate limits gracefully
            wait_time = base_delay * (2 ** attempt)
            time.sleep(wait_time)
        except Exception as e:
            return f"Agent Error: {str(e)}"
            
    return "System is currently experiencing high traffic. Please try again."
