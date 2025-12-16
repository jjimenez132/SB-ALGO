import os
import google.generativeai as genai
from google.api_core.exceptions import ResourceExhausted
from sqlalchemy import create_engine, text
import time

# --- CONFIGURATION ---
api_key = os.environ.get("GOOGLE_API_KEY")
if api_key:
    genai.configure(api_key=api_key)

def get_db_engine():
    try:
        db_url = os.environ.get("DATABASE_URL")
        if not db_url: return None
        return create_engine(db_url)
    except: return None

# --- INITIALIZE MODEL ---
system_prompt = """You are SB-ALGO's voice. You speak directly to Javier.

YOUR ROLE:
- Report what the algorithm calculated
- Be direct and confident
- Use the data provided in the prompt

When given game data, explain the edge in 2-3 sentences.
When given prop data, explain why the pick has value.
Never say you can't analyze - you have the data, just explain it."""

try:
    model = genai.GenerativeModel('gemini-2.0-flash', system_instruction=system_prompt)
    chat_session = model.start_chat()
    AGENT_AVAILABLE = True
except Exception as e:
    print(f"Model Init Error: {e}")
    chat_session = None
    AGENT_AVAILABLE = False

def query_algo_agent(prompt, retries=3):
    if not chat_session: return "AI Offline"
    for i in range(retries):
        try:
            return chat_session.send_message(prompt).text
        except ResourceExhausted:
            time.sleep(2 ** i)
        except Exception as e:
            return f"Error: {str(e)}"
    return "Rate limited, try again"

# --- WRAPPER FOR DASHBOARD ---
class AlgoAgentWrapper:
    def analyze_game(self, game_data):
        home = game_data.get('home_team', 'Home')
        away = game_data.get('away_team', 'Away')
        pick = game_data.get('algo_pick', 'N/A')
        conf = game_data.get('confidence', 0)
        ev = game_data.get('ev', 0)
        factors = game_data.get('key_factors', '')
        
        prompt = f"""Game: {away} @ {home}
Algo Pick: {pick}
Confidence: {conf}%
Edge: {ev}%
Factors: {factors}

Explain why this pick has value in 2-3 sentences. Be specific."""
        return query_algo_agent(prompt)
    
    def analyze_player_prop(self, prop_data):
        player = prop_data.get('player', 'Player')
        prop_type = prop_data.get('prop_type', 'points')
        line = prop_data.get('line', 'N/A')
        pick = prop_data.get('pick', 'N/A')
        edge = prop_data.get('hit_rate', 0)
        
        prompt = f"""Player: {player}
Prop: {prop_type} {line}
Pick: {pick}
Edge: {edge}%

Explain why this prop has value in 2 sentences."""
        return query_algo_agent(prompt)
    
    def chat(self, msg, context=None):
        if context:
            return query_algo_agent(f"{context}\n\nQuestion: {msg}")
        return query_algo_agent(msg)

def get_algo_ai():
    if AGENT_AVAILABLE:
        return AlgoAgentWrapper()
    return None
