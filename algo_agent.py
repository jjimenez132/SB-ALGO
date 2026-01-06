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
    """Get today's algo picks from sb_algo_api"""
    try:
        from sb_algo_api import get_todays_picks as get_picks
        data = get_picks()
        game_picks = data.get('game_picks', [])
        
        if not game_picks:
            return "No game picks meet the strict criteria today (Edge >= 30%)."
        
        picks_text = [f"**{len(game_picks)} picks** passed filters (Edge ≥ 30%)\n"]
        for p in game_picks:
            picks_text.append(f"🔥 **[{p['id']}]** {p['matchup']} → {p['pick']}")
            picks_text.append(f"   Edge: {p['edge']} | EV: {p['ev']} | Conf: {p['confidence']}\n")
        
        return "\n".join(picks_text)
    except Exception as e:
        return f"Error loading picks: {str(e)}"

def get_top_props():
    """Get today's top prop edges from sb_algo_api"""
    try:
        from sb_algo_api import get_todays_picks as get_picks
        data = get_picks()
        prop_picks = data.get('prop_picks', [])
        
        if not prop_picks:
            return "No prop picks meet the strict criteria today (Edge >= 30%, Hit Rate >= 60%)."
        
        props_text = [f"**{len(prop_picks)} props** passed filters\n"]
        for p in prop_picks:
            props_text.append(f"🎯 **[{p['id']}]** {p['player']} {p['prop']}")
            props_text.append(f"   Edge: {p['edge']} | Hit Rate: {p['hit_rate']} | EV: {p['ev']}\n")
        
        return "\n".join(props_text)
    except Exception as e:
        return f"Error loading props: {str(e)}"

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


def get_algo_full_context():
    """Get comprehensive algo context for AI responses"""
    engine = get_engine()
    today = get_eastern_date()
    context = {}
    
    with engine.connect() as conn:
        # 1. TODAY'S PICKS PERFORMANCE
        try:
            from sb_algo_api import get_todays_picks as get_picks
            picks_data = get_picks()
            context['todays_picks'] = {
                'game_picks': picks_data.get('game_picks', []),
                'prop_picks': picks_data.get('prop_picks', []),
                'total_picks': picks_data.get('total_picks', 0),
                'avg_ev': picks_data.get('avg_ev', '0%'),
                'total_stake': picks_data.get('total_stake', '$0')
            }
        except:
            context['todays_picks'] = {'error': 'Could not load picks'}
        
        # 2. HISTORICAL PERFORMANCE (Last 30 days)
        try:
            result = conn.execute(text("""
                SELECT 
                    COUNT(*) as total_picks,
                    SUM(CASE WHEN status = 'win' THEN 1 ELSE 0 END) as wins,
                    SUM(CASE WHEN status = 'loss' THEN 1 ELSE 0 END) as losses,
                    SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending
                FROM algo_picks_tracking 
                WHERE pick_date >= CURRENT_DATE - INTERVAL '30 days'
            """)).fetchone()
            
            if result and result[0] > 0:
                total = result[0]
                wins = result[1] or 0
                losses = result[2] or 0
                pending = result[3] or 0
                decided = wins + losses
                win_rate = (wins / decided * 100) if decided > 0 else 0
                
                context['historical_30d'] = {
                    'total_picks': total,
                    'wins': wins,
                    'losses': losses,
                    'pending': pending,
                    'win_rate': f"{win_rate:.1f}%"
                }
            else:
                context['historical_30d'] = {'message': 'No historical data yet'}
        except Exception as e:
            context['historical_30d'] = {'error': str(e)}
        
        # 3. BANKROLL STATUS
        try:
            result = conn.execute(text("""
                SELECT current_bankroll, starting_bankroll 
                FROM bankroll_settings 
                LIMIT 1
            """)).fetchone()
            
            if result:
                current = float(result[0]) if result[0] else 10000
                starting = float(result[1]) if result[1] else 10000
                pnl = current - starting
                roi = ((current - starting) / starting * 100) if starting > 0 else 0
                
                context['bankroll'] = {
                    'current': f"${current:,.0f}",
                    'starting': f"${starting:,.0f}",
                    'pnl': f"${pnl:+,.0f}",
                    'roi': f"{roi:+.1f}%"
                }
            else:
                context['bankroll'] = {'current': '$10,000', 'starting': '$10,000', 'pnl': '$0', 'roi': '0%'}
        except:
            context['bankroll'] = {'current': '$10,000', 'message': 'Default bankroll'}
        
        # 4. RECENT RESULTS (Last 7 days with details)
        try:
            result = conn.execute(text("""
                SELECT pick_id, pick_name, pick_type, units, status, pick_date
                FROM algo_picks_tracking 
                WHERE status IN ('win', 'loss')
                ORDER BY pick_date DESC, created_at DESC
                LIMIT 10
            """)).fetchall()
            
            recent = []
            for r in result:
                recent.append({
                    'id': r[0],
                    'name': r[1],
                    'type': r[2],
                    'units': float(r[3]) if r[3] else 0,
                    'result': r[4],
                    'date': str(r[5])
                })
            context['recent_results'] = recent
        except:
            context['recent_results'] = []
        
        # 5. TODAY'S GAMES
        try:
            result = conn.execute(text("""
                SELECT away_team, home_team, commence_time
                FROM games 
                WHERE DATE(commence_time) = :today
                ORDER BY commence_time
            """), {"today": today}).fetchall()
            
            games = []
            for r in result:
                games.append(f"{r[0]} @ {r[1]}")
            context['todays_games'] = games
        except:
            context['todays_games'] = []
        
        # 6. MAJOR INJURIES
        try:
            result = conn.execute(text("""
                SELECT player_name, team_name, status 
                FROM injuries 
                WHERE status IN ('Out', 'Doubtful')
                ORDER BY updated_at DESC
                LIMIT 15
            """)).fetchall()
            
            injuries = []
            for r in result:
                injuries.append(f"{r[0]} ({r[1]}) - {r[2]}")
            context['major_injuries'] = injuries
        except:
            context['major_injuries'] = []
        
        # 7. ALGO HEALTH METRICS
        try:
            # Check data freshness
            result = conn.execute(text("""
                SELECT table_name, MAX(updated_at) as last_update
                FROM (
                    SELECT 'betting_odds' as table_name, MAX(last_update) as updated_at FROM betting_odds
                    UNION ALL
                    SELECT 'player_props', MAX(updated_at) FROM player_props
                    UNION ALL
                    SELECT 'injuries', MAX(updated_at) FROM injuries
                ) t
                GROUP BY table_name
            """)).fetchall()
            
            health = {}
            for r in result:
                health[r[0]] = str(r[1]) if r[1] else 'Unknown'
            context['data_health'] = health
        except:
            context['data_health'] = {'status': 'Unable to check'}
    
    return context


def format_context_for_ai():
    """Format the full context as a string for the AI"""
    ctx = get_algo_full_context()
    
    lines = ["=== SB-ALGO CURRENT STATUS ===\n"]
    
    # Today's picks
    picks = ctx.get('todays_picks', {})
    lines.append(f"📊 TODAY'S PICKS: {picks.get('total_picks', 0)} total")
    lines.append(f"   Avg EV: {picks.get('avg_ev', 'N/A')} | Stake: {picks.get('total_stake', 'N/A')}")
    
    for p in picks.get('game_picks', [])[:3]:
        lines.append(f"   🏀 [{p.get('id')}] {p.get('matchup')} → {p.get('pick')} ({p.get('edge')})")
    for p in picks.get('prop_picks', [])[:3]:
        lines.append(f"   🎯 [{p.get('id')}] {p.get('player')} {p.get('prop')} ({p.get('edge')})")
    
    # Historical
    hist = ctx.get('historical_30d', {})
    if hist.get('total_picks'):
        lines.append(f"\n📈 LAST 30 DAYS: {hist.get('wins', 0)}W - {hist.get('losses', 0)}L ({hist.get('win_rate', 'N/A')})")
    
    # Bankroll
    bank = ctx.get('bankroll', {})
    lines.append(f"\n💰 BANKROLL: {bank.get('current', 'N/A')} | P/L: {bank.get('pnl', 'N/A')} | ROI: {bank.get('roi', 'N/A')}")
    
    # Recent results
    recent = ctx.get('recent_results', [])[:5]
    if recent:
        lines.append("\n📋 RECENT RESULTS:")
        for r in recent:
            emoji = "✅" if r.get('result') == 'win' else "❌"
            lines.append(f"   {emoji} [{r.get('id')}] {r.get('name')} ({r.get('date')})")
    
    # Games today
    games = ctx.get('todays_games', [])
    if games:
        lines.append(f"\n🏀 TODAY'S GAMES ({len(games)}):")
        for g in games[:6]:
            lines.append(f"   • {g}")
    
    # Major injuries
    injuries = ctx.get('major_injuries', [])[:5]
    if injuries:
        lines.append("\n🏥 KEY INJURIES:")
        for inj in injuries:
            lines.append(f"   • {inj}")
    
    return "\n".join(lines)


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
        
        system_prompt = """You are SB-ALGO, a professional NBA betting algorithm assistant.

You have FULL access to:
- Real-time picks from Meta-Merge Engine v4.0 (15 sub-engines)
- Strict filters: Edge ≥30%, Hit Rate ≥60%, Confidence ≥70%
- Historical performance data (wins, losses, ROI)
- Bankroll tracking and Kelly staking
- Live injuries, odds, and game data

Pick IDs: Games are G01, G02... Props are P01, P02...

When answering:
- Reference actual data and pick IDs
- Be confident but remind users betting has risk
- Be concise and professional
- If asked about performance, cite real numbers"""

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
    
    # For performance/status questions, include full context
    if any(word in prompt_lower for word in ['how', 'performance', 'doing', 'status', 'health', 'roi', 'record', 'bankroll', 'results']):
        context = format_context_for_ai()
        prompt = f"{context}\n\nUser question: {prompt}"
    
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
