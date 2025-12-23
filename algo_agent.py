"""
algo_agent.py - AI Agent connected to real data
================================================
Queries the database and provides intelligent responses.
"""

import os
import time
from sqlalchemy import create_engine, text
from datetime import datetime
import pytz

DATABASE_URL = os.environ.get('DATABASE_URL',
    "postgresql://sb_algo_db_user:0HDtYp4EY2Lo5At8iyf44PD1zDioSPK7@dpg-d495uhchg0os738l1a50-a.virginia-postgres.render.com/sb_algo_db")

# Lazy loading for Gemini
AGENT_AVAILABLE = False
_model = None
_chat_session = None
_initialized = False

def get_engine():
    return create_engine(DATABASE_URL)

def get_eastern_date():
    return datetime.now(pytz.timezone('US/Eastern')).strftime('%Y-%m-%d')

# ============================================================
# DATABASE QUERIES - Real Data
# ============================================================

def get_injuries(team: str = None):
    """Get real injuries from database"""
    engine = get_engine()
    with engine.connect() as conn:
        if team:
            result = conn.execute(text("""
                SELECT player_name, team_name, status, description 
                FROM injuries 
                WHERE UPPER(team_name) LIKE UPPER(:team)
                ORDER BY status
                LIMIT 20
            """), {"team": f"%{team}%"}).fetchall()
        else:
            result = conn.execute(text("""
                SELECT player_name, team_name, status, description 
                FROM injuries 
                ORDER BY updated_at DESC
                LIMIT 30
            """)).fetchall()
        
        if not result:
            return "No injuries found."
        
        injuries_text = []
        for r in result:
            injuries_text.append(f"• **{r[0]}** ({r[1]}) - {r[2]}: {r[3] or 'No details'}")
        
        return "\n".join(injuries_text)

def get_todays_games():
    """Get today's games from database"""
    engine = get_engine()
    today = get_eastern_date()
    
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT home_team, visitor_team, start_time, game_status
            FROM games 
            WHERE date = :today
            ORDER BY start_time
        """), {"today": today}).fetchall()
        
        if not result:
            return "No games scheduled today."
        
        games_text = []
        for r in result:
            games_text.append(f"• {r[1]} @ {r[0]} - {r[2] or 'TBD'}")
        
        return "\n".join(games_text)

def get_todays_picks():
    """Get today's algo picks"""
    engine = get_engine()
    today = get_eastern_date()
    
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT pick_id, pick_name, units, status
            FROM algo_picks_tracking 
            WHERE pick_date = :today
            ORDER BY created_at DESC
            LIMIT 10
        """), {"today": today}).fetchall()
        
        if not result:
            return "No picks generated yet today."
        
        picks_text = []
        for r in result:
            status_emoji = "⏳" if r[3] == 'pending' else "✅" if r[3] == 'win' else "❌"
            picks_text.append(f"{status_emoji} **[{r[0]}]** {r[1]} - {r[2]}u")
        
        return "\n".join(picks_text)

def get_top_props():
    """Get today's top prop edges"""
    engine = get_engine()
    today = get_eastern_date()
    
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT pick_id, pick_name, units, status
            FROM algo_picks_tracking 
            WHERE pick_date = :today AND pick_type = 'prop'
            ORDER BY units DESC
            LIMIT 5
        """), {"today": today}).fetchall()
        
        if not result:
            # Try to get from analyze_props
            try:
                from algo_brain import analyze_props
                props = analyze_props()
                if props:
                    props_text = []
                    for p in sorted(props, key=lambda x: x['edge'], reverse=True)[:5]:
                        props_text.append(f"🎯 **{p['player']}** {p['pick']} - {p['edge']:.0f}% edge")
                    return "\n".join(props_text)
            except:
                pass
            return "No prop picks yet today. Check back later."
        
        props_text = []
        for r in result:
            status_emoji = "⏳" if r[3] == 'pending' else "✅" if r[3] == 'win' else "❌"
            props_text.append(f"{status_emoji} **[{r[0]}]** {r[1]} - {r[2]}u")
        
        return "\n".join(props_text)

def get_game_analysis(team: str):
    """Get analysis for a specific team's game"""
    engine = get_engine()
    today = get_eastern_date()
    
    with engine.connect() as conn:
        # Find today's game for this team
        result = conn.execute(text("""
            SELECT g.home_team, g.visitor_team, g.start_time,
                   bo.home_spread, bo.total, bo.home_ml, bo.away_ml
            FROM games g
            LEFT JOIN betting_odds bo ON g.home_team = bo.home_team AND g.date = bo.game_date
            WHERE g.date = :today 
            AND (UPPER(g.home_team) LIKE UPPER(:team) OR UPPER(g.visitor_team) LIKE UPPER(:team))
            LIMIT 1
        """), {"today": today, "team": f"%{team}%"}).fetchone()
        
        if not result:
            return f"No game found for {team} today."
        
        home, away, time, spread, total, home_ml, away_ml = result
        
        analysis = f"**{away} @ {home}** - {time or 'TBD'}\n\n"
        if spread:
            analysis += f"📊 **Spread:** {home} {spread:+.1f}\n"
        if total:
            analysis += f"📊 **Total:** {total}\n"
        if home_ml and away_ml:
            analysis += f"📊 **ML:** {home} ({home_ml:+d}) | {away} ({away_ml:+d})\n"
        
        return analysis

# ============================================================
# GEMINI AI (for natural language)
# ============================================================

def _ensure_initialized():
    """Lazy initialization for Gemini"""
    global _model, _chat_session, AGENT_AVAILABLE, _initialized
    
    if _initialized:
        return
    
    _initialized = True
    
    try:
        import google.generativeai as genai
        
        api_key = os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            print("No GOOGLE_API_KEY found")
            return
        
        genai.configure(api_key=api_key)
        
        system_prompt = """You are SB-ALGO's assistant. You help users with sports betting questions.
        Be concise and direct. When given data, summarize it clearly.
        You have access to real NBA data including injuries, games, odds, and picks."""

        _model = genai.GenerativeModel('gemini-2.0-flash', system_instruction=system_prompt)
        _chat_session = _model.start_chat()
        AGENT_AVAILABLE = True
        print("✅ Gemini AI initialized")
    except Exception as e:
        print(f"Gemini init error: {e}")
        AGENT_AVAILABLE = False

# ============================================================
# MAIN QUERY FUNCTION
# ============================================================

def query_algo_agent(prompt: str, retries: int = 2):
    """Smart query handler - uses database first, AI for complex questions"""
    prompt_lower = prompt.lower()
    
    # Direct database queries for common questions
    if any(word in prompt_lower for word in ['injury', 'injuries', 'hurt', 'out']):
        # Extract team if mentioned
        team = None
        teams = ['lakers', 'celtics', 'warriors', 'heat', 'bulls', 'knicks', 'nets', 
                 'sixers', '76ers', 'bucks', 'suns', 'mavs', 'mavericks', 'nuggets',
                 'grizzlies', 'pelicans', 'hawks', 'cavs', 'cavaliers', 'pistons',
                 'pacers', 'hornets', 'wizards', 'magic', 'raptors', 'kings', 
                 'blazers', 'jazz', 'thunder', 'spurs', 'rockets', 'clippers', 'wolves',
                 'timberwolves', 'lal', 'bos', 'gsw', 'mia', 'chi', 'nyk', 'bkn',
                 'phi', 'mil', 'phx', 'dal', 'den', 'mem', 'nop', 'atl', 'cle',
                 'det', 'ind', 'cha', 'was', 'orl', 'tor', 'sac', 'por', 'uta',
                 'okc', 'sas', 'hou', 'lac', 'min']
        for t in teams:
            if t in prompt_lower:
                team = t
                break
        
        injuries = get_injuries(team)
        if team:
            return f"**{team.upper()} Injuries:**\n{injuries}"
        return f"**Current NBA Injuries:**\n{injuries}"
    
    if any(word in prompt_lower for word in ['games today', 'schedule', 'playing today', "today's games"]):
        games = get_todays_games()
        return f"**Today's Games ({get_eastern_date()}):**\n{games}"
    
    if any(word in prompt_lower for word in ['picks', 'pick', 'best bet', 'top bet']):
        picks = get_todays_picks()
        return f"**Today's Picks:**\n{picks}"
    
    if any(word in prompt_lower for word in ['props', 'prop', 'player']):
        props = get_top_props()
        return f"**Top Props:**\n{props}"
    
    if 'game' in prompt_lower and any(word in prompt_lower for word in ['analyze', 'analysis', 'breakdown']):
        # Try to find team name
        for t in teams:
            if t in prompt_lower:
                return get_game_analysis(t)
        return "Please specify a team. Example: `!game Lakers`"
    
    # For other questions, use Gemini if available
    _ensure_initialized()
    
    if not _chat_session:
        return "I can help with injuries (!injuries), games (!picks), props (!props), and game analysis (!game <team>)."
    
    try:
        from google.api_core.exceptions import ResourceExhausted
        
        for i in range(retries):
            try:
                response = _chat_session.send_message(prompt)
                return response.text[:1900]  # Discord limit
            except ResourceExhausted:
                time.sleep(2 ** i)
            except Exception as e:
                return f"Error: {str(e)}"
        
        return "Rate limited. Try again in a moment."
    except Exception as e:
        return f"Error: {str(e)}"

# ============================================================
# WRAPPER CLASS
# ============================================================

class AlgoAgentWrapper:
    def analyze_game(self, game_data):
        return query_algo_agent(f"Analyze: {game_data}")
    
    def analyze_player_prop(self, prop_data):
        return query_algo_agent(f"Analyze prop: {prop_data}")
    
    def chat(self, msg, context=None):
        return query_algo_agent(msg)

def get_algo_ai():
    return AlgoAgentWrapper()
