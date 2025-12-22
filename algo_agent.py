import os
import time

# --- CONFIGURATION ---
AGENT_AVAILABLE = False
_model = None
_chat_session = None
_initialized = False

def _ensure_initialized():
    """Lazy initialization - only runs when actually needed"""
    global _model, _chat_session, AGENT_AVAILABLE, _initialized
    
    if _initialized:
        return
    
    _initialized = True
    
    try:
        import google.generativeai as genai
        from google.api_core.exceptions import ResourceExhausted
        
        api_key = os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            print("No GOOGLE_API_KEY found")
            return
        
        genai.configure(api_key=api_key)
        
        system_prompt = """You are SB-ALGO's voice. You speak directly to Javier.

YOUR ROLE:
- Report what the algorithm calculated
- Be direct and confident
- Use the data provided in the prompt

When given game data, explain the edge in 2-3 sentences.
When given prop data, explain why the pick has value.
Never say you can't analyze - you have the data, just explain it."""

        _model = genai.GenerativeModel('gemini-2.0-flash', system_instruction=system_prompt)
        _chat_session = _model.start_chat()
        AGENT_AVAILABLE = True
        print("✅ Gemini AI initialized successfully")
    except Exception as e:
        print(f"Model Init Error: {e}")
        AGENT_AVAILABLE = False

def get_db_engine():
    try:
        from sqlalchemy import create_engine
        db_url = os.environ.get("DATABASE_URL")
        if not db_url: return None
        return create_engine(db_url)
    except: 
        return None

def query_algo_agent(prompt, retries=3):
    """Query the AI - initializes on first call"""
    _ensure_initialized()
    
    if not _chat_session: 
        return "AI Offline"
    
    from google.api_core.exceptions import ResourceExhausted
    
    for i in range(retries):
        try:
            return _chat_session.send_message(prompt).text
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
    """Get AI wrapper - does NOT initialize until actually used"""
    return AlgoAgentWrapper()
