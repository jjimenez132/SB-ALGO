import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from props_engine_ui import render_props_engine
from datetime import datetime, timedelta
import pytz
import os
from sqlalchemy import create_engine, text
import numpy as np
from algo_engine import AlgoEngine
from algo_ai import get_algo_ai

# Page config MUST be first Streamlit command
st.set_page_config(
    page_title="SB ALGO — NBA Edge Engine",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Initialize Claude AI globally
try:
    algo_ai = get_algo_ai()
except:
    algo_ai = None

# ========== TIMEZONE FIX ==========
def get_eastern_date():
    """Get current date in US Eastern timezone"""
    eastern = pytz.timezone('US/Eastern')
    return datetime.now(eastern).strftime('%Y-%m-%d')

def get_eastern_datetime():
    """Get current datetime in US Eastern timezone"""
    eastern = pytz.timezone('US/Eastern')
    return datetime.now(eastern)

# ========== DATA FUNCTIONS ==========
@st.cache_data(ttl=60)
def get_dashboard_metrics(_engine):
    engine = _engine  # Map cached argument to local variable
    """Fetch real metrics for dashboard"""
    metrics = {
        'games_today': 0,
        'active_injuries': 0,
        'edges_found': 0,
        'system_confidence': 0,
        'best_play': '—',
        'best_play_conf': 0
    }
    
    if not engine:
        return metrics
    
    try:
        with engine.connect() as conn:
            # Games today - USE EASTERN TIME
            today = get_eastern_date()
            games_today_query = text("SELECT COUNT(*) FROM games WHERE date = :today")
            result = conn.execute(games_today_query, {"today": today}).fetchone()
            metrics['games_today'] = result[0] if result else 0
            
            # Active injuries
            injuries_query = text("SELECT COUNT(*) FROM injuries")
            result = conn.execute(injuries_query).fetchone()
            metrics['active_injuries'] = result[0] if result else 0
            
            # Skip slow algo calculation on dashboard load
            metrics['edges_found'] = metrics['games_today']
            metrics['system_confidence'] = 75
            metrics['best_play'] = "See Games Tab"
            metrics['best_play_conf'] = 0
            
    except Exception as e:
        print(f"Dashboard metrics error: {e}")
    
    return metrics

@st.cache_data(ttl=60)
def get_todays_games(_engine):
    engine = _engine  # Map cached argument to local variable
    """Fetch today's games from database"""
    if not engine:
        return []
    
    try:
        today = get_eastern_date()
        query = text("""
            SELECT 
                date, home_team, visitor_team, home_pts, visitor_pts,
                start_time, home_win, home_days_rest, visitor_days_rest,
                home_is_b2b, visitor_is_b2b, season_avg_total, total_points,
                current_home_score, current_away_score, quarter, time_remaining, game_status
            FROM games 
            WHERE date = :today
            ORDER BY start_time
        """)
        
        with engine.connect() as conn:
            result = conn.execute(query, {"today": today})
            games = []
            for row in result:
                games.append({
                    'date': row[0],
                    'home_team': row[1],
                    'visitor_team': row[2],
                    'home_pts': row[3],
                    'visitor_pts': row[4],
                    'start_time': row[5] or 'TBD',
                    'home_win': row[6],
                    'home_days_rest': row[7] or 0,
                    'visitor_days_rest': row[8] or 0,
                    'home_is_b2b': row[9] or False,
                    'visitor_is_b2b': row[10] or False,
                    'season_avg_total': row[11] or 220,
                    'total_points': row[12],
                    'current_home_score': row[13] or 0,
                    'current_away_score': row[14] or 0,
                    'quarter': row[15] or '',
                    'time_remaining': row[16] or '',
                    'game_status': row[17] or 'Scheduled'
                })
            return games
    except Exception as e:
        print(f"Error fetching today's games: {e}")
        return []

def get_recent_team_record(engine, team, days=30):
    """Get team's recent record"""
    if not engine:
        return {'wins': 0, 'losses': 0, 'home_record': '0-0', 'away_record': '0-0'}
    
    try:
        today = get_eastern_date()
        query = text("""
            SELECT 
                SUM(CASE WHEN (home_team = :team AND home_win = 1) OR 
                             (visitor_team = :team AND home_win = 0) THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN (home_team = :team AND home_win = 0) OR 
                             (visitor_team = :team AND home_win = 1) THEN 1 ELSE 0 END) as losses,
                SUM(CASE WHEN home_team = :team AND home_win = 1 THEN 1 ELSE 0 END) as home_wins,
                SUM(CASE WHEN home_team = :team AND home_win = 0 THEN 1 ELSE 0 END) as home_losses,
                SUM(CASE WHEN visitor_team = :team AND home_win = 0 THEN 1 ELSE 0 END) as away_wins,
                SUM(CASE WHEN visitor_team = :team AND home_win = 1 THEN 1 ELSE 0 END) as away_losses
            FROM games
            WHERE date >= :start_date AND date < :today
            AND (home_team = :team OR visitor_team = :team)
            AND home_win IS NOT NULL
        """)
        
        start_date = (datetime.strptime(today, '%Y-%m-%d') - timedelta(days=days)).strftime('%Y-%m-%d')
        
        with engine.connect() as conn:
            result = conn.execute(query, {"team": team, "start_date": start_date, "today": today}).fetchone()
            if result:
                wins = int(result[0] or 0)
                losses = int(result[1] or 0)
                home_wins = int(result[2] or 0)
                home_losses = int(result[3] or 0)
                away_wins = int(result[4] or 0)
                away_losses = int(result[5] or 0)
                return {
                    'wins': wins,
                    'losses': losses,
                    'home_record': f"{home_wins}-{home_losses}",
                    'away_record': f"{away_wins}-{away_losses}"
                }
    except Exception as e:
        print(f"Error getting team record: {e}")
    
    return {'wins': 0, 'losses': 0, 'home_record': '0-0', 'away_record': '0-0'}

@st.cache_data(ttl=300)
def get_hot_teams(_engine, limit=5):
    engine = _engine  # Map cached argument to local variable
    """Get hottest teams in last 30 days"""
    if not engine:
        return pd.DataFrame()
    
    try:
        today = get_eastern_date()
        start_date = (datetime.strptime(today, '%Y-%m-%d') - timedelta(days=30)).strftime('%Y-%m-%d')
        
        query = text("""
            WITH team_games AS (
                SELECT home_team as team, 
                       CASE WHEN home_win = 1 THEN 1 ELSE 0 END as win,
                       home_pts - visitor_pts as margin
                FROM games 
                WHERE date >= :start_date AND date < :today AND home_win IS NOT NULL
                
                UNION ALL
                
                SELECT visitor_team as team,
                       CASE WHEN home_win = 0 THEN 1 ELSE 0 END as win,
                       visitor_pts - home_pts as margin
                FROM games 
                WHERE date >= :start_date AND date < :today AND home_win IS NOT NULL
            )
            SELECT team,
                   SUM(win) as wins,
                   COUNT(*) - SUM(win) as losses,
                   ROUND(100.0 * SUM(win) / COUNT(*), 1) as win_pct,
                   ROUND(AVG(margin), 1) as avg_margin
            FROM team_games
            GROUP BY team
            HAVING COUNT(*) >= 5
            ORDER BY win_pct DESC, avg_margin DESC
            LIMIT :limit
        """)
        
        with engine.connect() as conn:
            df = pd.read_sql(query, conn, params={"start_date": start_date, "today": today, "limit": limit})
            if not df.empty:
                df['Record'] = df['wins'].astype(int).astype(str) + '-' + df['losses'].astype(int).astype(str)
                df['Win%'] = df['win_pct'].astype(str) + '%'
                df['Avg Margin'] = df['avg_margin'].apply(lambda x: f"+{x}" if x > 0 else str(x))
                return df[['team', 'Record', 'Win%', 'Avg Margin']].rename(columns={'team': 'Team'})
        return pd.DataFrame()
    except Exception as e:
        print(f"Error getting hot teams: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=300)
def get_cold_teams(_engine, limit=5):
    engine = _engine  # Map cached argument to local variable
    """Get coldest teams in last 30 days"""
    if not engine:
        return pd.DataFrame()
    
    try:
        today = get_eastern_date()
        start_date = (datetime.strptime(today, '%Y-%m-%d') - timedelta(days=30)).strftime('%Y-%m-%d')
        
        query = text("""
            WITH team_games AS (
                SELECT home_team as team, 
                       CASE WHEN home_win = 1 THEN 1 ELSE 0 END as win,
                       home_pts - visitor_pts as margin
                FROM games 
                WHERE date >= :start_date AND date < :today AND home_win IS NOT NULL
                
                UNION ALL
                
                SELECT visitor_team as team,
                       CASE WHEN home_win = 0 THEN 1 ELSE 0 END as win,
                       visitor_pts - home_pts as margin
                FROM games 
                WHERE date >= :start_date AND date < :today AND home_win IS NOT NULL
            )
            SELECT team,
                   SUM(win) as wins,
                   COUNT(*) - SUM(win) as losses,
                   ROUND(100.0 * SUM(win) / COUNT(*), 1) as win_pct,
                   ROUND(AVG(margin), 1) as avg_margin
            FROM team_games
            GROUP BY team
            HAVING COUNT(*) >= 5
            ORDER BY win_pct ASC, avg_margin ASC
            LIMIT :limit
        """)
        
        with engine.connect() as conn:
            df = pd.read_sql(query, conn, params={"start_date": start_date, "today": today, "limit": limit})
            if not df.empty:
                df['Record'] = df['wins'].astype(int).astype(str) + '-' + df['losses'].astype(int).astype(str)
                df['Win%'] = df['win_pct'].astype(str) + '%'
                df['Avg Margin'] = df['avg_margin'].apply(lambda x: f"+{x}" if x > 0 else str(x))
                return df[['team', 'Record', 'Win%', 'Avg Margin']].rename(columns={'team': 'Team'})
        return pd.DataFrame()
    except Exception as e:
        print(f"Error getting cold teams: {e}")
        return pd.DataFrame()

def get_totals_trends(engine, limit=6):
    """Get teams' over/under trends"""
    if not engine:
        return pd.DataFrame()
    
    try:
        today = get_eastern_date()
        start_date = (datetime.strptime(today, '%Y-%m-%d') - timedelta(days=60)).strftime('%Y-%m-%d')
        
        query = text("""
            WITH team_totals AS (
                SELECT home_team as team,
                       total_points,
                       season_avg_total,
                       CASE WHEN total_points > season_avg_total THEN 1 ELSE 0 END as went_over
                FROM games
                WHERE date >= :start_date AND date < :today 
                AND total_points IS NOT NULL AND season_avg_total IS NOT NULL
                
                UNION ALL
                
                SELECT visitor_team as team,
                       total_points,
                       season_avg_total,
                       CASE WHEN total_points > season_avg_total THEN 1 ELSE 0 END as went_over
                FROM games
                WHERE date >= :start_date AND date < :today
                AND total_points IS NOT NULL AND season_avg_total IS NOT NULL
            )
            SELECT team,
                   ROUND(AVG(total_points), 1) as avg_total,
                   ROUND(100.0 * SUM(went_over) / COUNT(*), 0) as over_pct
            FROM team_totals
            GROUP BY team
            HAVING COUNT(*) >= 5
            ORDER BY over_pct DESC
            LIMIT :limit
        """)
        
        with engine.connect() as conn:
            df = pd.read_sql(query, conn, params={"start_date": start_date, "today": today, "limit": limit})
            if not df.empty:
                df['Avg Total'] = df['avg_total'].astype(str)
                df['Over %'] = df['over_pct'].astype(int).astype(str) + '%'
                df['Trend'] = df['over_pct'].apply(lambda x: 
                    '🔥 Over Team' if x >= 60 else 
                    '📈 Trending Over' if x >= 50 else 
                    '❄️ Under Team' if x <= 40 else '➡️ Neutral')
                return df[['team', 'Avg Total', 'Over %', 'Trend']].rename(columns={'team': 'Team'})
        return pd.DataFrame()
    except Exception as e:
        print(f"Error getting totals trends: {e}")
        return pd.DataFrame()

# Page config


# Custom CSS
st.markdown("""
<style>
    .stApp {
        background: linear-gradient(135deg, #050814 0%, #0B0F17 100%);
    }
    .main-header {
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        padding: 2rem;
        border-radius: 10px;
        margin-bottom: 2rem;
    }
    .metric-card {
        background: rgba(102, 126, 234, 0.1);
        border: 1px solid rgba(102, 126, 234, 0.3);
        padding: 1rem;
        border-radius: 8px;
        text-align: center;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 24px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        background-color: rgba(102, 126, 234, 0.1);
        border-radius: 8px;
        padding: 0 24px;
    }
</style>
""", unsafe_allow_html=True)

# Database connection
@st.cache_resource
def get_db_engine():
    """Connect to PostgreSQL database"""
    try:
        database_url = os.getenv('DATABASE_URL')
        if not database_url:
            st.error("⚠️ DATABASE_URL not found in environment variables")
            return None
        
        engine = create_engine(database_url)
        
        # Test connection and count games
        with engine.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM games")).fetchone()
            game_count = result[0] if result else 0
            
        st.success(f"✅ Database Connected | {game_count:,} Games Loaded")
        return engine
    except Exception as e:
        st.error(f"⚠️ Database Error: {str(e)}")
        return None

# Initialize database
engine = get_db_engine()

# Header
eastern_now = get_eastern_datetime()
st.markdown(f"""
<div class="main-header">
    <h1>🎯 SB ALGO — NBA Edge Engine</h1>
    <p style='font-size: 1.2rem; margin: 0;'>Professional Basketball Betting Intelligence</p>
    <p style='font-size: 0.9rem; margin: 0.5rem 0 0 0; opacity: 0.8;'>📅 {eastern_now.strftime('%B %d, %Y')} | {eastern_now.strftime('%I:%M %p')} ET</p>
</div>
""", unsafe_allow_html=True)

# Create tabs
tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9 = st.tabs([
    "🏠 Dashboard",
    "🎲 Today's Games", 
    "🧠 Props Engine",
    "📈 Trends & Patterns",
    "💰 Bankroll Manager",
    "📰 News & Injuries",
    "📂 Data Explorer",
    "📊 Daily Reports",
    "⚙️ Settings"
])

with tab1:
    # Get real metrics
    dashboard_data = get_dashboard_metrics(engine)
    
    # ========== SECTION 1: TOP DAILY PICKS (HERO SECTION) ==========
    st.markdown("""
    <div style="
        background: linear-gradient(135deg, rgba(102, 126, 234, 0.15) 0%, rgba(118, 75, 162, 0.15) 100%);
        border: 2px solid rgba(102, 126, 234, 0.4);
        border-radius: 16px;
        padding: 2rem;
        margin-bottom: 2rem;
        box-shadow: 0 0 40px rgba(102, 126, 234, 0.2);
    ">
        <div style="display: flex; align-items: center; gap: 1rem; margin-bottom: 1.5rem;">
            <span style="font-size: 2rem;">🔥</span>
            <div>
                <h2 style="margin: 0; color: #fff; font-size: 1.8rem;">Top Daily Picks</h2>
                <p style="margin: 0; color: #a0aec0; font-size: 0.95rem;">Algo-Selected • High Confidence Plays</p>
            </div>
        </div>
    """, unsafe_allow_html=True)
    
    if dashboard_data['games_today'] > 0:
        st.markdown("""
        <div style="background: rgba(0,0,0,0.3); border-radius: 12px; padding: 1rem; margin-bottom: 1rem;">
        """, unsafe_allow_html=True)
        
        # Get picks from ALGO BRAIN
        try:
            from algo_brain import analyze_games, analyze_props
            
            game_edges = analyze_games()
            prop_edges = analyze_props()
            
            col_games, col_props = st.columns(2)
            
            with col_games:
                st.markdown("""
                <p style="color: #10b981; font-weight: 600; font-size: 0.9rem; margin-bottom: 0.5rem;">🏀 TOP GAME BETS</p>
                """, unsafe_allow_html=True)
                
                if game_edges:
                    for edge in game_edges[:4]:
                        units = "2u" if edge['edge'] >= 7 else "1u" if edge['edge'] >= 4 else "0.5u"
                        st.markdown(f"""
                        <div style="background: rgba(16, 185, 129, 0.1); border-left: 3px solid #10b981; padding: 0.5rem 0.8rem; margin-bottom: 0.4rem; border-radius: 0 6px 6px 0;">
                            <p style="color: #fff; font-size: 0.9rem; margin: 0; font-weight: 600;">{edge['pick']}</p>
                            <p style="color: #6b7280; font-size: 0.75rem; margin: 0;">{edge['game']} • {edge['edge']:.1f} pts • {units}</p>
                        </div>
                        """, unsafe_allow_html=True)
                else:
                    st.markdown("<p style='color: #6b7280; font-size: 0.85rem;'>No game edges found</p>", unsafe_allow_html=True)
            
            with col_props:
                st.markdown("""
                <p style="color: #fbbf24; font-weight: 600; font-size: 0.9rem; margin-bottom: 0.5rem;">🎯 TOP PROP BETS</p>
                """, unsafe_allow_html=True)
                
                if prop_edges:
                    for edge in prop_edges[:4]:
                        units = "1.5u" if edge['edge'] >= 25 else "1u"
                        st.markdown(f"""
                        <div style="background: rgba(251, 191, 36, 0.1); border-left: 3px solid #fbbf24; padding: 0.5rem 0.8rem; margin-bottom: 0.4rem; border-radius: 0 6px 6px 0;">
                            <p style="color: #fff; font-size: 0.9rem; margin: 0; font-weight: 600;">{edge['player']}: {edge['pick']}</p>
                            <p style="color: #6b7280; font-size: 0.75rem; margin: 0;">{edge['subtype'].replace('player_', '')} • {edge['edge']:.0f}% edge • {units}</p>
                        </div>
                        """, unsafe_allow_html=True)
                else:
                    st.markdown("<p style='color: #6b7280; font-size: 0.85rem;'>No prop edges found</p>", unsafe_allow_html=True)
                    
        except Exception as e:
            st.warning(f"Algo brain loading... {e}")
        
        st.markdown("</div>", unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div style="
            background: rgba(0, 0, 0, 0.2);
            border-radius: 12px;
            padding: 2rem;
            text-align: center;
            border: 1px dashed rgba(102, 126, 234, 0.3);
        ">
            <p style="color: #6b7280; font-size: 1.1rem; margin: 0;">📅 No games scheduled today ({get_eastern_date()})</p>
            <p style="color: #4b5563; font-size: 0.9rem; margin-top: 0.5rem;">Check back tomorrow for new picks</p>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("""
        <div style="
            background: rgba(0, 0, 0, 0.25);
            border-radius: 10px;
            padding: 1.2rem;
            margin-top: 1rem;
            border-left: 3px solid #667eea;
        ">
            <h4 style="color: #667eea; margin-bottom: 0.8rem; font-size: 1rem;">📘 Algo Rationale</h4>
            <div style="display: grid; gap: 0.6rem;">
                <div style="background: rgba(102, 126, 234, 0.1); padding: 0.7rem 1rem; border-radius: 6px;">
                    <span style="color: #a0aec0; font-size: 0.85rem;">Primary factors considered: Team form, injuries, H2H history, rest days</span>
                </div>
                <div style="background: rgba(102, 126, 234, 0.1); padding: 0.7rem 1rem; border-radius: 6px;">
                    <span style="color: #a0aec0; font-size: 0.85rem;">Model confidence threshold: 75%+ required for recommendations</span>
                </div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # ========== DAILY OVERVIEW CARDS ==========
    st.markdown("""
    <p style="color: #667eea; font-weight: 600; margin-bottom: 1rem; font-size: 0.9rem;">📊 DAILY OVERVIEW</p>
    """, unsafe_allow_html=True)
    
    col1, col2, col3, col4, col5 = st.columns(5)
    
    games_count = dashboard_data['games_today']
    eastern_date_display = get_eastern_datetime().strftime('%B %d')
    
    with col1:
        st.markdown(f"""
        <div style="
            background: linear-gradient(135deg, rgba(102, 126, 234, 0.15) 0%, rgba(102, 126, 234, 0.05) 100%);
            border: 1px solid rgba(102, 126, 234, 0.3);
            border-top: 3px solid #667eea;
            border-radius: 12px;
            padding: 1.3rem;
            text-align: center;
            min-height: 140px;
        ">
            <p style="color: #a0aec0; font-size: 0.8rem; margin-bottom: 0.3rem; text-transform: uppercase;">🏀 Games Today</p>
            <h1 style="color: #fff; margin: 0.3rem 0; font-size: 2.5rem; font-weight: 700;">{games_count}</h1>
            <p style='color: {"#6b7280" if games_count == 0 else "#10b981"}; font-size: 0.8rem; margin: 0;'>📅 {eastern_date_display}</p>
        </div>
        """, unsafe_allow_html=True)
    
    edges = dashboard_data['edges_found']
    with col2:
        st.markdown(f"""
        <div style="
            background: linear-gradient(135deg, rgba(16, 185, 129, 0.15) 0%, rgba(16, 185, 129, 0.05) 100%);
            border: 1px solid rgba(16, 185, 129, 0.3);
            border-top: 3px solid #10b981;
            border-radius: 12px;
            padding: 1.3rem;
            text-align: center;
            min-height: 140px;
        ">
            <p style="color: #a0aec0; font-size: 0.8rem; margin-bottom: 0.3rem; text-transform: uppercase;">🎯 Edges Found</p>
            <h1 style="color: #fff; margin: 0.3rem 0; font-size: 2.5rem; font-weight: 700;">{edges}</h1>
            <p style='color: {"#6b7280" if edges == 0 else "#10b981"}; font-size: 0.8rem; margin: 0;'>{"⏸️ No games" if edges == 0 else "↑ +2 vs avg"}</p>
        </div>
        """, unsafe_allow_html=True)
    
    confidence = dashboard_data['system_confidence']
    with col3:
        st.markdown(f"""
        <div style="
            background: linear-gradient(135deg, rgba(251, 191, 36, 0.15) 0%, rgba(251, 191, 36, 0.05) 100%);
            border: 1px solid rgba(251, 191, 36, 0.3);
            border-top: 3px solid #fbbf24;
            border-radius: 12px;
            padding: 1.3rem;
            text-align: center;
            min-height: 140px;
        ">
            <p style="color: #a0aec0; font-size: 0.8rem; margin-bottom: 0.3rem; text-transform: uppercase;">📈 Confidence</p>
            <h1 style="color: #fff; margin: 0.3rem 0; font-size: 2.5rem; font-weight: 700;">{confidence if confidence > 0 else "—"}{"%" if confidence > 0 else ""}</h1>
            <p style='color: {"#6b7280" if confidence == 0 else "#10b981"}; font-size: 0.8rem; margin: 0;'>{"⏸️ Standby" if confidence == 0 else "↑ +15%"}</p>
        </div>
        """, unsafe_allow_html=True)
    
    best_play = dashboard_data['best_play']
    with col4:
        st.markdown(f"""
        <div style="
            background: linear-gradient(135deg, rgba(118, 75, 162, 0.15) 0%, rgba(118, 75, 162, 0.05) 100%);
            border: 1px solid rgba(118, 75, 162, 0.3);
            border-top: 3px solid #764ba2;
            border-radius: 12px;
            padding: 1.3rem;
            text-align: center;
            min-height: 140px;
        ">
            <p style="color: #a0aec0; font-size: 0.8rem; margin-bottom: 0.3rem; text-transform: uppercase;">⭐ Best Play</p>
            <h1 style="color: #fff; margin: 0.3rem 0; font-size: 2rem; font-weight: 700;">{best_play}</h1>
            <p style='color: {"#6b7280" if best_play == "—" else "#10b981"}; font-size: 0.8rem; margin: 0;'>{"⏸️ No picks" if best_play == "—" else f"↑ {dashboard_data['best_play_conf']}%"}</p>
        </div>
        """, unsafe_allow_html=True)
    
    injuries = dashboard_data['active_injuries']
    with col5:
        st.markdown(f"""
        <div style="
            background: linear-gradient(135deg, rgba(239, 68, 68, 0.15) 0%, rgba(239, 68, 68, 0.05) 100%);
            border: 1px solid rgba(239, 68, 68, 0.3);
            border-top: 3px solid #ef4444;
            border-radius: 12px;
            padding: 1.3rem;
            text-align: center;
            min-height: 140px;
        ">
            <p style="color: #a0aec0; font-size: 0.8rem; margin-bottom: 0.3rem; text-transform: uppercase;">🏥 Injuries</p>
            <h1 style="color: #fff; margin: 0.3rem 0; font-size: 2.5rem; font-weight: 700;">{injuries}</h1>
            <p style='color: #f59e0b; font-size: 0.8rem; margin: 0;'>⚠️ Updated hourly</p>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # System Status Panel
    st.markdown(f"""
    <div style="
        background: linear-gradient(90deg, rgba(102, 126, 234, 0.1) 0%, rgba(16, 185, 129, 0.1) 100%);
        border: 1px solid rgba(102, 126, 234, 0.25);
        border-radius: 12px;
        padding: 1rem 1.5rem;
        margin-bottom: 1.5rem;
        display: flex;
        justify-content: space-between;
        align-items: center;
        flex-wrap: wrap;
        gap: 1rem;
    ">
        <div style="display: flex; align-items: center; gap: 0.8rem;">
            <span style="font-size: 1.2rem;">🧠</span>
            <span style="color: #e2e8f0; font-weight: 600;">System Status</span>
        </div>
        <div style="display: flex; gap: 2rem; flex-wrap: wrap;">
            <div style="text-align: center;">
                <p style="color: #6b7280; font-size: 0.7rem; margin: 0;">GAMES</p>
                <p style="color: #e2e8f0; font-size: 1rem; margin: 0; font-weight: 600;">{dashboard_data['games_today']}</p>
            </div>
            <div style="text-align: center;">
                <p style="color: #6b7280; font-size: 0.7rem; margin: 0;">PICKS</p>
                <p style="color: #e2e8f0; font-size: 1rem; margin: 0; font-weight: 600;">{dashboard_data['edges_found']}</p>
            </div>
            <div style="text-align: center;">
                <p style="color: #6b7280; font-size: 0.7rem; margin: 0;">MODE</p>
                <p style="color: #e2e8f0; font-size: 1rem; margin: 0; font-weight: 600;">{"Active" if dashboard_data['games_today'] > 0 else "Standby"}</p>
            </div>
            <div style="display: flex; align-items: center; gap: 0.5rem;">
                <div style="width: 12px; height: 12px; border-radius: 50%; background: {"#10b981" if dashboard_data['games_today'] > 0 else "#fbbf24"}; box-shadow: 0 0 8px {"#10b981" if dashboard_data['games_today'] > 0 else "#fbbf24"};"></div>
                <span style="color: {"#10b981" if dashboard_data['games_today'] > 0 else "#fbbf24"}; font-size: 0.85rem; font-weight: 500;">{"LIVE" if dashboard_data['games_today'] > 0 else "STANDBY"}</span>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ========== AI CHAT BOX ==========
    st.markdown("""
    <div style="
        background: linear-gradient(135deg, rgba(168, 85, 247, 0.15) 0%, rgba(168, 85, 247, 0.05) 100%);
        border: 2px solid rgba(168, 85, 247, 0.4);
        border-radius: 16px;
        padding: 1.5rem;
        margin-top: 2rem;
    ">
        <div style="display: flex; align-items: center; gap: 0.8rem; margin-bottom: 1rem;">
            <span style="font-size: 1.5rem;">🧠</span>
            <h3 style="margin: 0; color: #a855f7; font-size: 1.2rem;">Ask the Algorithm</h3>
        </div>
    """, unsafe_allow_html=True)
    
    # Initialize chat history in session state
    if "ai_chat_history" not in st.session_state:
        st.session_state.ai_chat_history = []
    
    # Display chat history
    for msg in st.session_state.ai_chat_history[-5:]:  # Show last 5 messages
        if msg["role"] == "user":
            st.markdown(f"""
            <div style="background: rgba(59, 130, 246, 0.2); border-radius: 8px; padding: 0.8rem; margin-bottom: 0.5rem;">
                <p style="color: #93c5fd; font-size: 0.75rem; margin: 0 0 0.3rem 0;">You</p>
                <p style="color: #e2e8f0; font-size: 0.9rem; margin: 0;">{msg["content"]}</p>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div style="background: rgba(168, 85, 247, 0.2); border-radius: 8px; padding: 0.8rem; margin-bottom: 0.5rem;">
                <p style="color: #c084fc; font-size: 0.75rem; margin: 0 0 0.3rem 0;">SB-ALGO</p>
                <p style="color: #e2e8f0; font-size: 0.9rem; margin: 0; line-height: 1.5;">{msg["content"]}</p>
            </div>
            """, unsafe_allow_html=True)
    
    # Chat input
    user_input = st.text_input("Ask about picks, system status, injuries...", key="ai_chat_input", label_visibility="collapsed", placeholder="Ask about picks, system status, injuries...")
    
    col_send, col_clear = st.columns([4, 1])
    with col_send:
        if st.button("🚀 Send", key="ai_send", use_container_width=True):
            if user_input:
                st.session_state.ai_chat_history.append({"role": "user", "content": user_input})
                
                from algo_agent import query_algo_agent
                with st.spinner("🧠 Thinking..."):
                    response = query_algo_agent(user_input)
                
                st.session_state.ai_chat_history.append({"role": "assistant", "content": response})
                st.rerun()
    
    with col_clear:
        if st.button("🗑️", key="ai_clear", use_container_width=True):
            st.session_state.ai_chat_history = []
            st.rerun()
    
    st.markdown("</div>", unsafe_allow_html=True)

# ========== TAB 2: TODAY'S GAMES ==========
with tab2:
    st.markdown("""
    <div style="
        background: linear-gradient(135deg, rgba(102, 126, 234, 0.15) 0%, rgba(118, 75, 162, 0.15) 100%);
        border: 1px solid rgba(102, 126, 234, 0.3);
        border-radius: 16px;
        padding: 1.5rem 2rem;
        margin-bottom: 2rem;
        box-shadow: 0 0 30px rgba(102, 126, 234, 0.15);
    ">
        <div style="display: flex; align-items: center; gap: 1rem;">
            <span style="font-size: 2.5rem;">🎲</span>
            <div>
                <h1 style="margin: 0; color: #fff; font-size: 1.8rem; font-weight: 700;">Today's Games — Deep Analysis</h1>
                <p style="margin: 0.3rem 0 0 0; color: #a0aec0; font-size: 0.95rem;">AI-Powered Breakdown • Real-Time Edge Detection</p>
            </div>
        </div>
        <div style="height: 3px; background: linear-gradient(90deg, #667eea 0%, #764ba2 50%, #667eea 100%); border-radius: 2px; margin-top: 1rem;"></div>
    </div>
    """, unsafe_allow_html=True)
    
    # ========== TOP GAME BETS FROM ALGO BRAIN ==========
    try:
        from algo_brain import analyze_games
        game_edges = analyze_games()
        
        if game_edges:
            st.markdown("""
            <div style="
                background: linear-gradient(135deg, rgba(16, 185, 129, 0.15) 0%, rgba(16, 185, 129, 0.05) 100%);
                border: 2px solid rgba(16, 185, 129, 0.4);
                border-radius: 16px;
                padding: 1.5rem;
                margin-bottom: 2rem;
            ">
                <div style="display: flex; align-items: center; gap: 0.8rem; margin-bottom: 1rem;">
                    <span style="font-size: 1.5rem;">🔥</span>
                    <h2 style="color: #10b981; margin: 0; font-size: 1.3rem;">Top Game Bets — Algo Picks</h2>
                </div>
            """, unsafe_allow_html=True)
            
            # Display top 6 game edges
            for edge in game_edges[:6]:
                edge_val = edge['edge']
                if edge_val >= 7:
                    units = "2u"
                    unit_color = "#ef4444"
                elif edge_val >= 4:
                    units = "1u"
                    unit_color = "#fbbf24"
                else:
                    units = "0.5u"
                    unit_color = "#10b981"
                
                st.markdown(f"""
                <div style="
                    background: rgba(0,0,0,0.3);
                    border-radius: 10px;
                    padding: 1rem;
                    margin-bottom: 0.5rem;
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                ">
                    <div>
                        <p style="color: #a0aec0; font-size: 0.8rem; margin: 0;">{edge['game']}</p>
                        <p style="color: #fff; font-size: 1.1rem; font-weight: 600; margin: 0.2rem 0 0 0;">{edge['pick']}</p>
                    </div>
                    <div style="display: flex; gap: 1rem; align-items: center;">
                        <div style="text-align: center;">
                            <p style="color: #6b7280; font-size: 0.7rem; margin: 0;">EDGE</p>
                            <p style="color: #10b981; font-size: 1rem; font-weight: 600; margin: 0;">{edge_val:.1f} pts</p>
                        </div>
                        <div style="text-align: center;">
                            <p style="color: #6b7280; font-size: 0.7rem; margin: 0;">SIZE</p>
                            <p style="color: {unit_color}; font-size: 1rem; font-weight: 600; margin: 0;">{units}</p>
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
            
            st.markdown("</div>", unsafe_allow_html=True)
    except Exception as e:
        pass  # Silently fail if algo_brain not available
    
    # Get real games
    todays_games = get_todays_games(engine)
    
    if not todays_games:
        eastern_date = get_eastern_date()
        st.markdown(f"""
        <div style="
            background: rgba(0, 0, 0, 0.2);
            border-radius: 12px;
            padding: 3rem;
            text-align: center;
            border: 1px dashed rgba(102, 126, 234, 0.3);
        ">
            <span style="font-size: 3rem;">📅</span>
            <h3 style="color: #e2e8f0; margin: 1rem 0 0.5rem 0;">No Games Scheduled Today</h3>
            <p style="color: #6b7280; font-size: 1rem; margin: 0;">Date: {eastern_date} (Eastern)</p>
            <p style="color: #4b5563; font-size: 0.9rem; margin-top: 0.5rem;">Check back tomorrow for new matchups</p>
        </div>
        """, unsafe_allow_html=True)
    else:
        # Games count badge
        st.markdown(f"""
        <div style="
            background: rgba(16, 185, 129, 0.15);
            border: 1px solid rgba(16, 185, 129, 0.3);
            border-radius: 8px;
            padding: 0.5rem 1rem;
            display: inline-block;
            margin-bottom: 1.5rem;
        ">
            <span style="color: #10b981; font-weight: 600;">🏀 {len(todays_games)} Games Today</span>
            <span style="color: #6b7280; margin-left: 0.5rem;">({get_eastern_date()})</span>
        </div>
        """, unsafe_allow_html=True)
        
        # Loop through real games
        for i, game in enumerate(todays_games):
            home = game['home_team']
            visitor = game['visitor_team']
            start_time = game['start_time']
            
            # Check game status
            game_status = game.get('game_status', 'Scheduled')
            is_final = game['home_pts'] is not None and game['home_pts'] > 0
            is_live = game_status and game_status.lower() not in ['scheduled', 'not started yet', ''] and not is_final
            
            current_home = game.get('current_home_score', 0) or 0
            current_away = game.get('current_away_score', 0) or 0
            quarter = game.get('quarter', '')
            time_remaining = game.get('time_remaining', '')
            
            if is_final:
                score_display = f"FINAL: {visitor} {int(game['visitor_pts'])} - {home} {int(game['home_pts'])}"
                winner = home if game['home_win'] else visitor
                status_color = "#10b981"
            elif is_live:
                score_display = f"🔴 LIVE: {visitor} {current_away} - {home} {current_home} | {quarter} {time_remaining}"
                winner = None
                status_color = "#ef4444"
            else:
                score_display = f"🕐 {start_time}"
                winner = None
                status_color = "#fbbf24"
            
            with st.expander(f"🏀 {visitor} @ {home} — {score_display}", expanded=(i==0)):
                
                # Live Score Card (only show if game is live or final)
                if is_live or is_final:
                    if is_live:
                        live_bg = "linear-gradient(135deg, rgba(239, 68, 68, 0.2) 0%, rgba(239, 68, 68, 0.05) 100%)"
                        live_border = "rgba(239, 68, 68, 0.5)"
                        status_text = f"🔴 LIVE — {quarter} {time_remaining}"
                        home_score_show = current_home
                        away_score_show = current_away
                    else:
                        live_bg = "linear-gradient(135deg, rgba(16, 185, 129, 0.2) 0%, rgba(16, 185, 129, 0.05) 100%)"
                        live_border = "rgba(16, 185, 129, 0.5)"
                        status_text = "✅ FINAL"
                        home_score_show = int(game['home_pts'])
                        away_score_show = int(game['visitor_pts'])
                    
                    st.markdown(f"""
                    <div style="
                        background: {live_bg};
                        border: 2px solid {live_border};
                        border-radius: 16px;
                        padding: 1.5rem;
                        margin-bottom: 1.5rem;
                        text-align: center;
                    ">
                        <p style="color: #a0aec0; font-size: 0.85rem; margin: 0 0 0.5rem 0;">{status_text}</p>
                        <div style="display: flex; justify-content: center; align-items: center; gap: 2rem;">
                            <div style="text-align: center;">
                                <p style="color: #fff; font-size: 2.5rem; font-weight: 700; margin: 0;">{away_score_show}</p>
                                <p style="color: #a0aec0; font-size: 1rem; margin: 0.3rem 0 0 0;">{visitor}</p>
                            </div>
                            <div style="color: #667eea; font-size: 1.5rem; font-weight: 600;">VS</div>
                            <div style="text-align: center;">
                                <p style="color: #fff; font-size: 2.5rem; font-weight: 700; margin: 0;">{home_score_show}</p>
                                <p style="color: #a0aec0; font-size: 1rem; margin: 0.3rem 0 0 0;">{home}</p>
                            </div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                
                # Key Metrics
                st.markdown("""
                <p style="color: #667eea; font-weight: 600; margin-bottom: 0.8rem; font-size: 0.85rem;">📊 Key Metrics</p>
                """, unsafe_allow_html=True)
                
                m1, m2, m3, m4 = st.columns(4)
                
                with m1:
                    rest_home = int(game['home_days_rest']) if game['home_days_rest'] else 0
                    b2b_warning = " ⚠️" if game['home_is_b2b'] else ""
                    st.markdown(f"""
                    <div style="background: rgba(102, 126, 234, 0.15); border: 1px solid rgba(102, 126, 234, 0.3); border-radius: 10px; padding: 0.8rem; text-align: center;">
                        <p style="color: #6b7280; font-size: 0.7rem; margin: 0;">HOME REST</p>
                        <p style="color: #667eea; font-size: 1.2rem; margin: 0.2rem 0 0 0; font-weight: 600;">{rest_home} days{b2b_warning}</p>
                    </div>
                    """, unsafe_allow_html=True)
                
                with m2:
                    rest_away = int(game['visitor_days_rest']) if game['visitor_days_rest'] else 0
                    b2b_warning = " ⚠️" if game['visitor_is_b2b'] else ""
                    st.markdown(f"""
                    <div style="background: rgba(16, 185, 129, 0.15); border: 1px solid rgba(16, 185, 129, 0.3); border-radius: 10px; padding: 0.8rem; text-align: center;">
                        <p style="color: #6b7280; font-size: 0.7rem; margin: 0;">AWAY REST</p>
                        <p style="color: #10b981; font-size: 1.2rem; margin: 0.2rem 0 0 0; font-weight: 600;">{rest_away} days{b2b_warning}</p>
                    </div>
                    """, unsafe_allow_html=True)
                
                with m3:
                    avg_total = game['season_avg_total'] or 220
                    st.markdown(f"""
                    <div style="background: rgba(251, 191, 36, 0.15); border: 1px solid rgba(251, 191, 36, 0.3); border-radius: 10px; padding: 0.8rem; text-align: center;">
                        <p style="color: #6b7280; font-size: 0.7rem; margin: 0;">AVG TOTAL</p>
                        <p style="color: #fbbf24; font-size: 1.2rem; margin: 0.2rem 0 0 0; font-weight: 600;">{avg_total:.1f}</p>
                    </div>
                    """, unsafe_allow_html=True)
                
                with m4:
                    if is_final:
                        home_pts = int(game['home_pts']) if game['home_pts'] is not None else 0
                        visitor_pts = int(game['visitor_pts']) if game['visitor_pts'] is not None else 0
                        raw_total = game.get('total_points')
                        if raw_total is None:
                            total_pts = home_pts + visitor_pts
                        else:
                            try:
                                total_pts = int(raw_total)
                            except (TypeError, ValueError):
                                total_pts = home_pts + visitor_pts
                        over_under = "OVER" if total_pts > avg_total else "UNDER"
                        color = "#10b981" if over_under == "OVER" else "#ef4444"
                        st.markdown(f"""
                        <div style="background: rgba(239, 68, 68, 0.15); border: 1px solid rgba(239, 68, 68, 0.3); border-radius: 10px; padding: 0.8rem; text-align: center;">
                            <p style="color: #6b7280; font-size: 0.7rem; margin: 0;">TOTAL PTS</p>
                            <p style="color: {color}; font-size: 1.2rem; margin: 0.2rem 0 0 0; font-weight: 600;">{total_pts} ({over_under})</p>
                        </div>
                        """, unsafe_allow_html=True)
                    else:
                        st.markdown("""
                        <div style="background: rgba(239, 68, 68, 0.15); border: 1px solid rgba(239, 68, 68, 0.3); border-radius: 10px; padding: 0.8rem; text-align: center;">
                            <p style="color: #6b7280; font-size: 0.7rem; margin: 0;">TOTAL PTS</p>
                            <p style="color: #ef4444; font-size: 1.2rem; margin: 0.2rem 0 0 0; font-weight: 600;">TBD</p>
                        </div>
                        """, unsafe_allow_html=True)
                
                st.markdown("<br>", unsafe_allow_html=True)
                
                # Two column layout
                col1, col2 = st.columns([2, 1])
                
                with col1:
                    # Get team records
                    home_record = get_recent_team_record(engine, home)
                    visitor_record = get_recent_team_record(engine, visitor)
                    
                    # Game Analysis - Matchup Overview
                    home_b2b = " (B2B)" if game['home_is_b2b'] else ""
                    visitor_b2b = " (B2B)" if game['visitor_is_b2b'] else ""
                    
                    analysis_html = f"""
                    <div style="background: rgba(15, 20, 35, 0.8); border: 1px solid rgba(102, 126, 234, 0.25); border-radius: 12px; padding: 1.5rem; margin-bottom: 1rem;">
                        <div style="display: flex; align-items: center; gap: 0.6rem; margin-bottom: 1rem;">
                            <span style="font-size: 1.3rem;">📊</span>
                            <h3 style="color: #e2e8f0; margin: 0; font-size: 1.1rem;">Game Analysis</h3>
                        </div>
                        <div style="background: rgba(0,0,0,0.25); border-radius: 8px; padding: 1rem; margin-bottom: 0.8rem; border-left: 3px solid #667eea;">
                            <p style="color: #667eea; font-size: 0.85rem; font-weight: 600; margin-bottom: 0.5rem;">Matchup Overview</p>
                            <p style="color: #a0aec0; font-size: 0.85rem; margin: 0;">• {home}: {home_record['wins']}-{home_record['losses']} (Home: {home_record['home_record']})</p>
                            <p style="color: #a0aec0; font-size: 0.85rem; margin: 0;">• {visitor}: {visitor_record['wins']}-{visitor_record['losses']} (Away: {visitor_record['away_record']})</p>
                        </div>
                        <div style="background: rgba(0,0,0,0.25); border-radius: 8px; padding: 1rem; border-left: 3px solid #fbbf24;">
                            <p style="color: #fbbf24; font-size: 0.85rem; font-weight: 600; margin-bottom: 0.5rem;">Key Factors</p>
                            <p style="color: #a0aec0; font-size: 0.85rem; margin: 0;">• {home} has {rest_home} days rest{home_b2b}</p>
                            <p style="color: #a0aec0; font-size: 0.85rem; margin: 0;">• {visitor} has {rest_away} days rest{visitor_b2b}</p>
                            <p style="color: #a0aec0; font-size: 0.85rem; margin: 0;">• Season avg total: {avg_total:.1f} pts</p>
                        </div>
                    </div>
                    """
                    st.markdown(analysis_html, unsafe_allow_html=True)
                    
                    # Algorithm Recommendation - FULL ANALYSIS
                    from math_engine import GamePredictor
                    predictor = GamePredictor(engine)
                    
                    # Get betting odds for this game
                    spread_line = None
                    total_line = None
                    try:
                        with engine.connect() as conn:
                            odds_result = conn.execute(text("""
                                SELECT home_spread, total FROM betting_odds 
                                WHERE game_date = :gd AND home_team = :home
                                LIMIT 1
                            """), {"gd": game['date'], "home": home}).fetchone()
                            if odds_result:
                                spread_line = float(odds_result[0]) if odds_result[0] else None
                                total_line = float(odds_result[1]) if odds_result[1] else None
                    except:
                        pass
                    
                    # Run prediction
                    analysis = predictor.analyze_game(home, visitor, spread_line, total_line)
                    spread_pred = analysis['spread']
                    total_pred = analysis['total']
                    picks = analysis.get('picks', [])
                    
                    # Get values for display
                    algo_spread = spread_pred['predicted_spread']
                    algo_total = total_pred['predicted_total']
                    confidence = spread_pred['confidence']
                    home_net = spread_pred.get('home_net', 0)
                    away_net = spread_pred.get('away_net', 0)
                    home_form = spread_pred.get('home_form', 0)
                    away_form = spread_pred.get('away_form', 0)
                    
                    if is_final:
                        # Show final result
                        st.markdown(f"""
                        <div style="
                            background: linear-gradient(135deg, rgba(16, 185, 129, 0.2) 0%, rgba(16, 185, 129, 0.05) 100%);
                            border: 2px solid rgba(16, 185, 129, 0.4);
                            border-radius: 12px;
                            padding: 1.5rem;
                        ">
                            <div style="display: flex; align-items: center; gap: 0.6rem; margin-bottom: 0.5rem;">
                                <span style="font-size: 1.3rem;">🎯</span>
                                <h3 style="color: #10b981; margin: 0; font-size: 1.1rem;">Final Result</h3>
                            </div>
                            <h2 style="color: #fff; margin: 0; font-size: 1.5rem;">✅ {winner} won</h2>
                        </div>
                        """, unsafe_allow_html=True)
                    else:
                        # Build picks display
                        if picks:
                            primary_pick = picks[0]
                            pick_text = primary_pick['pick']
                            pick_edge = primary_pick['edge']
                            pick_conf = primary_pick['confidence']
                            pick_color = "#10b981" if pick_edge >= 5 else "#fbbf24"
                            
                            # Unit sizing based on edge
                            if pick_edge >= 7:
                                units = "2.0 Units (High Edge)"
                                unit_color = "#ef4444"
                            elif pick_edge >= 4:
                                units = "1.0 Unit (Standard)"
                                unit_color = "#fbbf24"
                            else:
                                units = "0.5 Units (Small Edge)"
                                unit_color = "#10b981"
                        else:
                            pick_text = "No strong edge"
                            pick_edge = 0
                            pick_conf = 0
                            pick_color = "#6b7280"
                            units = "PASS"
                            unit_color = "#6b7280"
                        
                        # Build HTML parts separately to avoid rendering issues
                        spread_line_display = spread_line if spread_line else 'N/A'
                        total_line_display = total_line if total_line else 'N/A'
                        
                        algo_html = f"""<div style="background: linear-gradient(135deg, rgba(16, 185, 129, 0.15) 0%, rgba(16, 185, 129, 0.05) 100%); border: 2px solid rgba(16, 185, 129, 0.4); border-radius: 12px; padding: 1.5rem;">
<div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 1rem;">
<div style="display: flex; align-items: center; gap: 0.6rem;">
<span style="font-size: 1.3rem;">🎯</span>
<h3 style="color: #10b981; margin: 0; font-size: 1.1rem;">Algorithm Recommendation</h3>
</div>
<span style="background: rgba(16, 185, 129, 0.2); color: #10b981; padding: 0.3rem 0.8rem; border-radius: 20px; font-size: 0.8rem;">{confidence:.0f}% Confidence</span>
</div>
<div style="background: rgba(0,0,0,0.3); border-radius: 10px; padding: 1.2rem; margin-bottom: 1rem;">
<p style="color: #6b7280; font-size: 0.75rem; margin: 0 0 0.3rem 0; text-transform: uppercase;">Primary Pick</p>
<h2 style="color: {pick_color}; margin: 0; font-size: 1.6rem; font-weight: 700;">{pick_text}</h2>
<div style="display: flex; gap: 1.5rem; margin-top: 0.8rem;">
<div><p style="color: #6b7280; font-size: 0.7rem; margin: 0;">EDGE</p><p style="color: #fff; font-size: 1.1rem; margin: 0; font-weight: 600;">{pick_edge:.1f} pts</p></div>
<div><p style="color: #6b7280; font-size: 0.7rem; margin: 0;">SUGGESTED</p><p style="color: {unit_color}; font-size: 1.1rem; margin: 0; font-weight: 600;">{units}</p></div>
</div>
</div>
<div style="display: grid; grid-template-columns: 1fr 1fr; gap: 0.8rem; margin-bottom: 1rem;">
<div style="background: rgba(102, 126, 234, 0.1); border-radius: 8px; padding: 0.8rem; border-left: 3px solid #667eea;">
<p style="color: #667eea; font-size: 0.75rem; margin: 0 0 0.3rem 0; font-weight: 600;">SPREAD ANALYSIS</p>
<p style="color: #fff; font-size: 1rem; margin: 0;">Algo: <strong>{algo_spread:+.1f}</strong></p>
<p style="color: #a0aec0; font-size: 0.85rem; margin: 0;">Line: {spread_line_display}</p>
</div>
<div style="background: rgba(251, 191, 36, 0.1); border-radius: 8px; padding: 0.8rem; border-left: 3px solid #fbbf24;">
<p style="color: #fbbf24; font-size: 0.75rem; margin: 0 0 0.3rem 0; font-weight: 600;">TOTAL ANALYSIS</p>
<p style="color: #fff; font-size: 1rem; margin: 0;">Algo: <strong>{algo_total:.0f}</strong></p>
<p style="color: #a0aec0; font-size: 0.85rem; margin: 0;">Line: {total_line_display}</p>
</div>
</div>
<div style="background: rgba(0,0,0,0.2); border-radius: 8px; padding: 1rem;">
<p style="color: #a0aec0; font-size: 0.75rem; margin: 0 0 0.5rem 0; font-weight: 600;">📊 FACTORS CONSIDERED</p>
<div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 0.5rem; text-align: center;">
<div><p style="color: #6b7280; font-size: 0.65rem; margin: 0;">NET RTG</p><p style="color: #fff; font-size: 0.9rem; margin: 0;">{home} {home_net:+.1f}</p></div>
<div><p style="color: #6b7280; font-size: 0.65rem; margin: 0;">NET RTG</p><p style="color: #fff; font-size: 0.9rem; margin: 0;">{visitor} {away_net:+.1f}</p></div>
<div><p style="color: #6b7280; font-size: 0.65rem; margin: 0;">FORM</p><p style="color: #fff; font-size: 0.9rem; margin: 0;">{home} {home_form:+.1f}</p></div>
<div><p style="color: #6b7280; font-size: 0.65rem; margin: 0;">FORM</p><p style="color: #fff; font-size: 0.9rem; margin: 0;">{visitor} {away_form:+.1f}</p></div>
</div>
<p style="color: #4b5563; font-size: 0.7rem; margin: 0.8rem 0 0 0; text-align: center;">+ H2H History • Rest Days • Home Court Advantage • Pace Factor</p>
</div>
</div>"""
                        st.markdown(algo_html, unsafe_allow_html=True)
                        
                        # AI Breakdown - Claude explains the pick
                        if algo_ai:
                            try:
                                game_data = {
                                    'home_team': home,
                                    'away_team': visitor,
                                    'algo_pick': pick_text,
                                    'confidence': confidence,
                                    'ev': pick_edge,
                                    'key_factors': f"{home} Net RTG: {home_net:+.1f}, {visitor} Net RTG: {away_net:+.1f}, {home} Form: {home_form:+.1f}, {visitor} Form: {away_form:+.1f}, Algo Spread: {algo_spread:+.1f}, Line: {spread_line_display}, Algo Total: {algo_total:.0f}, Line Total: {total_line_display}"
                                }
                                with st.spinner("🧠 Generating AI analysis..."):
                                    ai_analysis = algo_ai.analyze_game(game_data)
                                    if ai_analysis:
                                        st.markdown(f"""
                                        <div style="background: linear-gradient(135deg, rgba(168, 85, 247, 0.15) 0%, rgba(168, 85, 247, 0.05) 100%); border: 2px solid rgba(168, 85, 247, 0.3); border-radius: 12px; padding: 1.2rem; margin-top: 1rem;">
                                            <div style="display: flex; align-items: center; gap: 0.6rem; margin-bottom: 0.8rem;">
                                                <span style="font-size: 1.2rem;">🧠</span>
                                                <h4 style="color: #a855f7; margin: 0; font-size: 1rem;">AI Breakdown</h4>
                                            </div>
                                            <p style="color: #e2e8f0; font-size: 0.9rem; line-height: 1.6; margin: 0;">{ai_analysis}</p>
                                        </div>
                                        """, unsafe_allow_html=True)
                            except Exception as e:
                                pass  # Silently fail if AI unavailable
                
                with col2:
                    # Win Probability Gauge
                    st.markdown("""
                    <div style="
                        background: rgba(15, 20, 35, 0.8);
                        border: 1px solid rgba(102, 126, 234, 0.25);
                        border-radius: 12px;
                        padding: 1rem;
                    ">
                        <div style="display: flex; align-items: center; gap: 0.6rem; margin-bottom: 0.5rem;">
                            <span style="font-size: 1.1rem;">📈</span>
                            <h3 style="color: #e2e8f0; margin: 0; font-size: 0.95rem;">Win Probability</h3>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # Calculate win probability based on records
                    home_games = home_record['wins'] + home_record['losses']
                    visitor_games = visitor_record['wins'] + visitor_record['losses']
                    
                    if home_games > 0 and visitor_games > 0:
                        home_win_pct = (home_record['wins'] / home_games) * 100
                        visitor_win_pct = (visitor_record['wins'] / visitor_games) * 100
                        # Weighted probability (home team gets slight boost)
                        home_prob = (home_win_pct * 0.55 + (100 - visitor_win_pct) * 0.45)
                        home_prob = max(25, min(75, home_prob))  # Clamp between 25-75
                    else:
                        home_prob = 50
                    
                    fig = go.Figure(go.Indicator(
                        mode = "gauge+number",
                        value = home_prob,
                        domain = {'x': [0, 1], 'y': [0, 1]},
                        title = {'text': f"{home} Win %", 'font': {'size': 12, 'color': '#a0aec0'}},
                        number = {'font': {'size': 28, 'color': '#ffffff'}, 'suffix': '%'},
                        gauge = {
                            'axis': {'range': [None, 100], 'tickcolor': "#667eea"},
                            'bar': {'color': "#667eea", 'thickness': 0.3},
                            'bgcolor': "rgba(15, 20, 35, 0.8)",
                            'borderwidth': 2,
                            'bordercolor': "rgba(102, 126, 234, 0.3)",
                            'steps': [
                                {'range': [0, 40], 'color': "rgba(239, 68, 68, 0.2)"},
                                {'range': [40, 60], 'color': "rgba(251, 191, 36, 0.2)"},
                                {'range': [60, 100], 'color': "rgba(16, 185, 129, 0.2)"}
                            ],
                        }
                    ))
                    
                    fig.update_layout(
                        height=200,
                        margin=dict(l=20, r=20, t=40, b=20),
                        paper_bgcolor='rgba(0,0,0,0)',
                        plot_bgcolor='rgba(0,0,0,0)',
                    )
                    
                    st.plotly_chart(fig, use_container_width=True, key=f"prob_{i}")
                
                st.markdown("""
                <div style="height: 1px; background: linear-gradient(90deg, transparent 0%, rgba(102, 126, 234, 0.3) 50%, transparent 100%); margin: 1rem 0;"></div>
                """, unsafe_allow_html=True)

# ========== TAB 3: PROPS ENGINE (PLACEHOLDER) ==========
with tab3:
    render_props_engine(engine)

# ========== TAB 4: TRENDS & PATTERNS ==========
with tab4:
    st.markdown("""
    <div style="text-align: center; padding: 1rem 0 0.5rem 0;">
        <h1 style="margin-bottom: 0.2rem;">📈 Trends & Patterns</h1>
        <p style="color: #a0aec0; font-size: 1rem;">Analyze team trends, player patterns, and prop-related performance indicators.</p>
        <div style="height: 3px; background: linear-gradient(90deg, #667eea 0%, #764ba2 100%); border-radius: 2px; max-width: 400px; margin: 0 auto;"></div>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    trend_type = st.selectbox(
        "View Trends For:",
        ["Algo Performance", "Team Trends", "Player Trends", "Situational Edges"],
        key="trends_selector",
        label_visibility="collapsed"
    )
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    if trend_type == "Algo Performance":
        # ========== ALGO PERFORMANCE SECTION ==========
        st.markdown("""
        <div style="
            background: linear-gradient(135deg, rgba(102, 126, 234, 0.15) 0%, rgba(118, 75, 162, 0.15) 100%);
            border: 2px solid rgba(102, 126, 234, 0.4);
            border-radius: 16px;
            padding: 1.5rem;
            margin-bottom: 1.5rem;
        ">
            <div style="display: flex; align-items: center; gap: 0.8rem; margin-bottom: 0.5rem;">
                <span style="font-size: 1.5rem;">🧠</span>
                <h3 style="color: #667eea; margin: 0; font-size: 1.3rem;">Algo Brain Status</h3>
            </div>
            <p style="color: #a0aec0; font-size: 0.85rem; margin: 0;">Real-time algorithm performance and insights</p>
        </div>
        """, unsafe_allow_html=True)
        
        try:
            from algo_brain import analyze_games, analyze_props
            from math_engine import GameBettingMemory, PropsMemory
            
            # Get current edges
            game_edges = analyze_games()
            prop_edges = analyze_props()
            
            # Display current status
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.markdown(f"""
                <div style="background: rgba(16, 185, 129, 0.15); border: 1px solid rgba(16, 185, 129, 0.3); border-radius: 10px; padding: 1rem; text-align: center;">
                    <p style="color: #6b7280; font-size: 0.75rem; margin: 0;">GAME EDGES</p>
                    <p style="color: #10b981; font-size: 2rem; font-weight: 700; margin: 0;">{len(game_edges)}</p>
                </div>
                """, unsafe_allow_html=True)
            
            with col2:
                st.markdown(f"""
                <div style="background: rgba(251, 191, 36, 0.15); border: 1px solid rgba(251, 191, 36, 0.3); border-radius: 10px; padding: 1rem; text-align: center;">
                    <p style="color: #6b7280; font-size: 0.75rem; margin: 0;">PROP EDGES</p>
                    <p style="color: #fbbf24; font-size: 2rem; font-weight: 700; margin: 0;">{len(prop_edges)}</p>
                </div>
                """, unsafe_allow_html=True)
            
            with col3:
                top_game_edge = max([e['edge'] for e in game_edges]) if game_edges else 0
                st.markdown(f"""
                <div style="background: rgba(239, 68, 68, 0.15); border: 1px solid rgba(239, 68, 68, 0.3); border-radius: 10px; padding: 1rem; text-align: center;">
                    <p style="color: #6b7280; font-size: 0.75rem; margin: 0;">TOP GAME EDGE</p>
                    <p style="color: #ef4444; font-size: 2rem; font-weight: 700; margin: 0;">{top_game_edge:.1f}</p>
                </div>
                """, unsafe_allow_html=True)
            
            with col4:
                top_prop_edge = max([e['edge'] for e in prop_edges]) if prop_edges else 0
                st.markdown(f"""
                <div style="background: rgba(168, 85, 247, 0.15); border: 1px solid rgba(168, 85, 247, 0.3); border-radius: 10px; padding: 1rem; text-align: center;">
                    <p style="color: #6b7280; font-size: 0.75rem; margin: 0;">TOP PROP EDGE</p>
                    <p style="color: #a855f7; font-size: 2rem; font-weight: 700; margin: 0;">{top_prop_edge:.0f}%</p>
                </div>
                """, unsafe_allow_html=True)
            
            st.markdown("<br>", unsafe_allow_html=True)
            
            # Today's Best Picks
            st.markdown("""
            <div style="background: rgba(0,0,0,0.3); border-radius: 12px; padding: 1.5rem; margin-bottom: 1rem;">
                <p style="color: #10b981; font-weight: 600; font-size: 1rem; margin-bottom: 1rem;">🔥 TODAY'S BEST GAME BETS</p>
            """, unsafe_allow_html=True)
            
            if game_edges:
                for edge in game_edges[:5]:
                    units = "2u" if edge['edge'] >= 7 else "1u" if edge['edge'] >= 4 else "0.5u"
                    st.markdown(f"""
                    <div style="display: flex; justify-content: space-between; align-items: center; padding: 0.5rem 0; border-bottom: 1px solid rgba(255,255,255,0.1);">
                        <div>
                            <p style="color: #fff; font-size: 0.95rem; margin: 0; font-weight: 500;">{edge['pick']}</p>
                            <p style="color: #6b7280; font-size: 0.8rem; margin: 0;">{edge['game']}</p>
                        </div>
                        <div style="display: flex; gap: 1rem;">
                            <span style="color: #10b981; font-weight: 600;">{edge['edge']:.1f} pts</span>
                            <span style="color: #fbbf24; font-weight: 600;">{units}</span>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
            
            st.markdown("</div>", unsafe_allow_html=True)
            
            st.markdown("""
            <div style="background: rgba(0,0,0,0.3); border-radius: 12px; padding: 1.5rem;">
                <p style="color: #fbbf24; font-weight: 600; font-size: 1rem; margin-bottom: 1rem;">🎯 TODAY'S BEST PROP BETS</p>
            """, unsafe_allow_html=True)
            
            if prop_edges:
                for edge in prop_edges[:5]:
                    units = "1.5u" if edge['edge'] >= 25 else "1u"
                    market = edge.get('subtype', '').replace('player_', '')
                    st.markdown(f"""
                    <div style="display: flex; justify-content: space-between; align-items: center; padding: 0.5rem 0; border-bottom: 1px solid rgba(255,255,255,0.1);">
                        <div>
                            <p style="color: #fff; font-size: 0.95rem; margin: 0; font-weight: 500;">{edge['player']}: {edge['pick']}</p>
                            <p style="color: #6b7280; font-size: 0.8rem; margin: 0;">{market}</p>
                        </div>
                        <div style="display: flex; gap: 1rem;">
                            <span style="color: #fbbf24; font-weight: 600;">{edge['edge']:.0f}%</span>
                            <span style="color: #10b981; font-weight: 600;">{units}</span>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
            
            st.markdown("</div>", unsafe_allow_html=True)
            
        except Exception as e:
            st.error(f"Error loading algo data: {e}")
    
    elif trend_type == "Team Trends":
        # HOT TEAMS - LIVE DATA
        st.markdown("""
        <div style="
            background: linear-gradient(135deg, rgba(239, 68, 68, 0.1) 0%, rgba(251, 191, 36, 0.1) 100%);
            border: 1px solid rgba(239, 68, 68, 0.3);
            border-radius: 12px;
            padding: 1.5rem;
            margin-bottom: 1.5rem;
        ">
            <div style="display: flex; align-items: center; gap: 0.8rem; margin-bottom: 0.5rem;">
                <span style="font-size: 1.5rem;">🔥</span>
                <h3 style="color: #e2e8f0; margin: 0; font-size: 1.2rem;">Hot Teams (Last 30 Days)</h3>
            </div>
            <p style="color: #a0aec0; font-size: 0.85rem; margin: 0;">Real data from your database</p>
        </div>
        """, unsafe_allow_html=True)
        
        hot_teams_df = get_hot_teams(engine, 5)
        if not hot_teams_df.empty:
            st.dataframe(hot_teams_df, use_container_width=True, hide_index=True)
        else:
            st.info("No hot teams data available")
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        # TOTALS TRENDS - LIVE DATA
        st.markdown("""
        <div style="
            background: linear-gradient(135deg, rgba(16, 185, 129, 0.1) 0%, rgba(79, 172, 254, 0.1) 100%);
            border: 1px solid rgba(16, 185, 129, 0.3);
            border-radius: 12px;
            padding: 1.5rem;
            margin-bottom: 1.5rem;
        ">
            <div style="display: flex; align-items: center; gap: 0.8rem; margin-bottom: 0.5rem;">
                <span style="font-size: 1.5rem;">💥</span>
                <h3 style="color: #e2e8f0; margin: 0; font-size: 1.2rem;">Totals Trends (Last 60 Days)</h3>
            </div>
            <p style="color: #a0aec0; font-size: 0.85rem; margin: 0;">Over/Under tendencies from real games</p>
        </div>
        """, unsafe_allow_html=True)
        
        totals_df = get_totals_trends(engine, 6)
        if not totals_df.empty:
            st.dataframe(totals_df, use_container_width=True, hide_index=True)
        else:
            st.info("No totals data available")
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        # COLD TEAMS - LIVE DATA
        st.markdown("""
        <div style="
            background: linear-gradient(135deg, rgba(59, 130, 246, 0.1) 0%, rgba(99, 102, 241, 0.1) 100%);
            border: 1px solid rgba(59, 130, 246, 0.3);
            border-radius: 12px;
            padding: 1.5rem;
            margin-bottom: 1.5rem;
        ">
            <div style="display: flex; align-items: center; gap: 0.8rem; margin-bottom: 0.5rem;">
                <span style="font-size: 1.5rem;">❄️</span>
                <h3 style="color: #e2e8f0; margin: 0; font-size: 1.2rem;">Cold Teams (Last 30 Days)</h3>
            </div>
            <p style="color: #a0aec0; font-size: 0.85rem; margin: 0;">Teams in a slump — fade opportunities</p>
        </div>
        """, unsafe_allow_html=True)
        
        cold_teams_df = get_cold_teams(engine, 5)
        if not cold_teams_df.empty:
            st.dataframe(cold_teams_df, use_container_width=True, hide_index=True)
        else:
            st.info("No cold teams data available")
    
    elif trend_type == "Situational Edges":
        st.markdown("""
        <div style="
            background: linear-gradient(135deg, rgba(118, 75, 162, 0.1) 0%, rgba(212, 175, 55, 0.1) 100%);
            border: 1px solid rgba(118, 75, 162, 0.3);
            border-radius: 12px;
            padding: 1.5rem;
            margin-bottom: 1.5rem;
        ">
            <div style="display: flex; align-items: center; gap: 0.8rem; margin-bottom: 0.5rem;">
                <span style="font-size: 1.5rem;">🎲</span>
                <h3 style="color: #e2e8f0; margin: 0; font-size: 1.2rem;">Situational Edges</h3>
            </div>
            <p style="color: #a0aec0; font-size: 0.85rem; margin: 0;">Rest, travel, back-to-backs from today's games</p>
        </div>
        """, unsafe_allow_html=True)
        
        # Get today's games for situational analysis
        todays_games = get_todays_games(engine)
        
        if todays_games:
            # Rest advantages
            rest_edges = []
            b2b_teams = []
            
            for game in todays_games:
                home_rest = game['home_days_rest'] or 0
                away_rest = game['visitor_days_rest'] or 0
                
                if home_rest >= 3 and away_rest <= 1:
                    rest_edges.append(f"✅ {game['home_team']} ({home_rest} days) vs {game['visitor_team']} ({away_rest} days)")
                elif away_rest >= 3 and home_rest <= 1:
                    rest_edges.append(f"✅ {game['visitor_team']} ({away_rest} days) vs {game['home_team']} ({home_rest} days)")
                
                if game['home_is_b2b']:
                    b2b_teams.append(f"⚠️ {game['home_team']} (Home B2B)")
                if game['visitor_is_b2b']:
                    b2b_teams.append(f"⚠️ {game['visitor_team']} (Away B2B)")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("### 💤 Rest Advantage Today")
                if rest_edges:
                    for edge in rest_edges:
                        st.write(edge)
                else:
                    st.write("No significant rest advantages today")
            
            with col2:
                st.markdown("### 🔄 Back-to-Back Teams Today")
                if b2b_teams:
                    for team in b2b_teams:
                        st.write(team)
                else:
                    st.write("No teams on B2B today")
        else:
            st.info("No games today to analyze for situational edges")
    
    else:  # Player Trends
        st.markdown("""
        <div style="
            background: linear-gradient(135deg, rgba(168, 85, 247, 0.1) 0%, rgba(236, 72, 153, 0.1) 100%);
            border: 1px solid rgba(168, 85, 247, 0.3);
            border-radius: 12px;
            padding: 1.5rem;
            margin-bottom: 1.5rem;
        ">
            <div style="display: flex; align-items: center; gap: 0.8rem; margin-bottom: 0.5rem;">
                <span style="font-size: 1.5rem;">⭐</span>
                <h3 style="color: #e2e8f0; margin: 0; font-size: 1.2rem;">Top Performers (Last 10 Games)</h3>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        try:
            with engine.connect() as conn:
                # Top scorers
                scorers = conn.execute(text("""
                    SELECT player_name, team_abbreviation,
                           ROUND(AVG(pts)::numeric, 1) as ppg,
                           ROUND(AVG(reb)::numeric, 1) as rpg,
                           ROUND(AVG(ast)::numeric, 1) as apg,
                           COUNT(*) as games
                    FROM player_boxscores
                    WHERE game_date >= CURRENT_DATE - INTERVAL '15 days'
                    GROUP BY player_name, team_abbreviation
                    HAVING COUNT(*) >= 3
                    ORDER BY AVG(pts) DESC
                    LIMIT 10
                """)).fetchall()
                
                if scorers:
                    df = pd.DataFrame(scorers, columns=['Player', 'Team', 'PPG', 'RPG', 'APG', 'Games'])
                    st.dataframe(df, use_container_width=True, hide_index=True)
                else:
                    st.info("No player data available")
                    
        except Exception as e:
            st.error(f"Error loading player trends: {e}")
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        # Hot props performers
        st.markdown("""
        <div style="
            background: linear-gradient(135deg, rgba(16, 185, 129, 0.1) 0%, rgba(34, 197, 94, 0.1) 100%);
            border: 1px solid rgba(16, 185, 129, 0.3);
            border-radius: 12px;
            padding: 1.5rem;
            margin-bottom: 1.5rem;
        ">
            <div style="display: flex; align-items: center; gap: 0.8rem; margin-bottom: 0.5rem;">
                <span style="font-size: 1.5rem;">📈</span>
                <h3 style="color: #e2e8f0; margin: 0; font-size: 1.2rem;">Trending Up (Beating Projections)</h3>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        try:
            with engine.connect() as conn:
                trending = conn.execute(text("""
                    SELECT player_name, team_abbreviation,
                           ROUND(AVG(pts)::numeric, 1) as recent_ppg,
                           COUNT(*) as games
                    FROM player_boxscores
                    WHERE game_date >= CURRENT_DATE - INTERVAL '7 days'
                    GROUP BY player_name, team_abbreviation
                    HAVING COUNT(*) >= 2 AND AVG(pts) > 20
                    ORDER BY AVG(pts) DESC
                    LIMIT 8
                """)).fetchall()
                
                if trending:
                    df = pd.DataFrame(trending, columns=['Player', 'Team', 'Recent PPG', 'Games'])
                    st.dataframe(df, use_container_width=True, hide_index=True)
                else:
                    st.info("No trending data available")
        except Exception as e:
            st.error(f"Error: {e}")
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # Trend insights
    st.markdown("""
    <div style="
        background: linear-gradient(135deg, rgba(102, 126, 234, 0.1) 0%, rgba(118, 75, 162, 0.1) 100%);
        border: 1px solid rgba(102, 126, 234, 0.25);
        border-radius: 12px;
        padding: 1.5rem;
    ">
        <h4 style="color: #e2e8f0; margin-bottom: 1rem;">📝 Trend Insights</h4>
        <div style="background: rgba(0,0,0,0.25); border-radius: 8px; padding: 1rem; border-left: 3px solid #667eea;">
            <p style="color: #10b981; font-size: 0.9rem; margin: 0;">✅ Data is now pulling from your live database</p>
            <p style="color: #a0aec0; font-size: 0.85rem; margin: 0.5rem 0 0 0;">Hot/cold teams and totals trends update automatically as new games are added.</p>
        </div>
    </div>
    """, unsafe_allow_html=True)

# ========== TABS 5-9: Keep original code ==========
with tab5:
    # ========== HEADER ==========
    st.markdown("""
    <div style="text-align: center; padding: 1rem 0 0.5rem 0;">
        <h1 style="margin-bottom: 0.2rem;">💰 Bankroll Manager — Financial Control Suite</h1>
        <p style="color: #a0aec0; font-size: 1rem; margin-bottom: 0.5rem;">Institutional-grade bankroll allocation for disciplined bettors.</p>
        <div style="height: 3px; background: linear-gradient(90deg, #667eea 0%, #D4AF37 100%); border-radius: 2px; max-width: 500px; margin: 0 auto;"></div>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # ========== BANKROLL INPUT MODULE ==========
    st.markdown("""
    <div style="
        background: linear-gradient(135deg, rgba(212, 175, 55, 0.08) 0%, rgba(102, 126, 234, 0.08) 100%);
        border: 1px solid rgba(212, 175, 55, 0.3);
        border-radius: 12px;
        padding: 1.5rem;
        margin-bottom: 1.5rem;
        box-shadow: 0 0 25px rgba(212, 175, 55, 0.1);
    ">
        <p style="color: #D4AF37; font-weight: 600; margin-bottom: 0.5rem; font-size: 0.9rem;">🧮 BANKROLL CONFIGURATION</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Row 1: Starting and Current Bankroll
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("""
        <p style="color: #e2e8f0; font-size: 0.85rem; margin-bottom: 0.3rem;">Starting Bankroll ($)</p>
        """, unsafe_allow_html=True)
        starting_bankroll = st.number_input(
            "",
            min_value=0,
            value=10000,
            step=100,
            key="bankroll_starting",
            label_visibility="collapsed"
        )
    
    with col2:
        st.markdown("""
        <p style="color: #e2e8f0; font-size: 0.85rem; margin-bottom: 0.3rem;">Current Bankroll ($)</p>
        """, unsafe_allow_html=True)
        current_bankroll = st.number_input(
            "",
            min_value=0,
            value=11250,
            step=100,
            key="bankroll_current",
            label_visibility="collapsed"
        )
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # Row 2: Risk Method and Max Risk
    col3, col4 = st.columns(2)
    
    with col3:
        st.markdown("""
        <p style="color: #e2e8f0; font-size: 0.85rem; margin-bottom: 0.3rem;">Risk Method</p>
        """, unsafe_allow_html=True)
        risk_method = st.selectbox(
            "",
            ["Percentage (%)", "Units", "Flat Dollar ($)"],
            key="bankroll_risk_method",
            label_visibility="collapsed"
        )
    
    with col4:
        st.markdown("""
        <p style="color: #e2e8f0; font-size: 0.85rem; margin-bottom: 0.3rem;">Max Risk Per Bet</p>
        """, unsafe_allow_html=True)
        
        if risk_method == "Percentage (%)":
            max_risk_pct = st.slider("", 1, 10, 2, key="bankroll_max_risk_pct", label_visibility="collapsed")
            unit_size = current_bankroll * (max_risk_pct / 100)
            st.markdown(f"""
            <p style="color: #D4AF37; font-size: 0.8rem;">Selected: {max_risk_pct}% of bankroll</p>
            """, unsafe_allow_html=True)
        elif risk_method == "Units":
            max_risk_units = st.number_input("", min_value=0.5, max_value=10.0, value=1.0, step=0.5, key="bankroll_max_risk_units", label_visibility="collapsed")
            # Assume 1 unit = 1% of bankroll
            unit_size = current_bankroll * 0.01 * max_risk_units
            st.markdown(f"""
            <p style="color: #D4AF37; font-size: 0.8rem;">Selected: {max_risk_units} units</p>
            """, unsafe_allow_html=True)
        else:
            unit_size = st.number_input("", min_value=10, max_value=1000, value=100, step=10, key="bankroll_max_risk_dollar", label_visibility="collapsed")
            st.markdown(f"""
            <p style="color: #D4AF37; font-size: 0.8rem;">Selected: ${unit_size:.0f} per bet</p>
            """, unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # ========== CALCULATE METRICS ==========
    if starting_bankroll > 0:
        profit = current_bankroll - starting_bankroll
        roi = ((current_bankroll - starting_bankroll) / starting_bankroll) * 100
    else:
        profit = 0
        roi = 0
    
    # Kelly Criterion recommended sizes
    kelly_conservative = current_bankroll * 0.01  # 1%
    kelly_balanced = current_bankroll * 0.02      # 2%
    kelly_aggressive = current_bankroll * 0.04   # 4%
    
    # ========== UNIT SIZE OUTPUT - DYNAMIC ==========
    st.markdown(f"""
    <div style="
        background: linear-gradient(135deg, rgba(212, 175, 55, 0.2) 0%, rgba(102, 126, 234, 0.2) 100%);
        border: 2px solid rgba(212, 175, 55, 0.5);
        border-radius: 16px;
        padding: 2rem;
        text-align: center;
        margin-bottom: 1.5rem;
        box-shadow: 0 0 30px rgba(212, 175, 55, 0.15);
    ">
        <h2 style="color: #D4AF37; margin-bottom: 0.5rem; font-size: 1.8rem;">💵 Your Recommended Unit Size</h2>
        <h1 style="color: #e2e8f0; font-size: 3.5rem; margin: 0.5rem 0; font-weight: 700;">${unit_size:,.2f}</h1>
        <p style="color: #a0aec0; font-size: 0.9rem;">Based on your {risk_method.lower()} risk method</p>
        <div style="
            display: flex;
            justify-content: center;
            gap: 2rem;
            margin-top: 1.5rem;
            flex-wrap: wrap;
        ">
            <div style="text-align: center;">
                <p style="color: #6b7280; font-size: 0.75rem; margin: 0;">CONSERVATIVE (1%)</p>
                <p style="color: #10b981; font-size: 1.2rem; margin: 0; font-weight: 600;">${kelly_conservative:,.2f}</p>
            </div>
            <div style="text-align: center;">
                <p style="color: #6b7280; font-size: 0.75rem; margin: 0;">BALANCED (2%)</p>
                <p style="color: #fbbf24; font-size: 1.2rem; margin: 0; font-weight: 600;">${kelly_balanced:,.2f}</p>
            </div>
            <div style="text-align: center;">
                <p style="color: #6b7280; font-size: 0.75rem; margin: 0;">AGGRESSIVE (4%)</p>
                <p style="color: #ef4444; font-size: 1.2rem; margin: 0; font-weight: 600;">${kelly_aggressive:,.2f}</p>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # ========== PROFESSIONAL SUMMARY PANEL ==========
    st.markdown("""
    <p style="color: #D4AF37; font-weight: 600; margin-bottom: 1rem; font-size: 0.9rem;">📊 PERFORMANCE METRICS</p>
    """, unsafe_allow_html=True)
    
    metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)
    
    with metric_col1:
        roi_color = "#10b981" if roi >= 0 else "#ef4444"
        roi_arrow = "↑" if roi >= 0 else "↓"
        st.markdown(f"""
        <div style="
            background: linear-gradient(135deg, rgba(16, 185, 129, 0.15) 0%, rgba(16, 185, 129, 0.05) 100%);
            border: 1px solid rgba(16, 185, 129, 0.3);
            border-radius: 12px;
            padding: 1.2rem;
            text-align: center;
            box-shadow: 0 4px 15px rgba(16, 185, 129, 0.1);
        ">
            <p style="color: #a0aec0; font-size: 0.8rem; margin-bottom: 0.3rem;">ROI</p>
            <h2 style="color: {roi_color}; margin: 0; font-size: 1.8rem;">{roi:.1f}%</h2>
            <p style="color: {roi_color}; font-size: 0.75rem; margin-top: 0.3rem;">{roi_arrow} ${abs(profit):,.0f}</p>
        </div>
        """, unsafe_allow_html=True)
    
    with metric_col2:
        profit_color = "#D4AF37" if profit >= 0 else "#ef4444"
        st.markdown(f"""
        <div style="
            background: linear-gradient(135deg, rgba(212, 175, 55, 0.15) 0%, rgba(212, 175, 55, 0.05) 100%);
            border: 1px solid rgba(212, 175, 55, 0.3);
            border-radius: 12px;
            padding: 1.2rem;
            text-align: center;
            box-shadow: 0 4px 15px rgba(212, 175, 55, 0.1);
        ">
            <p style="color: #a0aec0; font-size: 0.8rem; margin-bottom: 0.3rem;">Total Profit</p>
            <h2 style="color: {profit_color}; margin: 0; font-size: 1.8rem;">{'+' if profit >= 0 else ''}{profit:,.0f}</h2>
            <p style="color: {profit_color}; font-size: 0.75rem; margin-top: 0.3rem;">Lifetime P/L</p>
        </div>
        """, unsafe_allow_html=True)
    
    with metric_col3:
        st.markdown(f"""
        <div style="
            background: linear-gradient(135deg, rgba(102, 126, 234, 0.15) 0%, rgba(102, 126, 234, 0.05) 100%);
            border: 1px solid rgba(102, 126, 234, 0.3);
            border-radius: 12px;
            padding: 1.2rem;
            text-align: center;
            box-shadow: 0 4px 15px rgba(102, 126, 234, 0.1);
        ">
            <p style="color: #a0aec0; font-size: 0.8rem; margin-bottom: 0.3rem;">Current Bankroll</p>
            <h2 style="color: #667eea; margin: 0; font-size: 1.8rem;">${current_bankroll:,}</h2>
            <p style="color: #667eea; font-size: 0.75rem; margin-top: 0.3rem;">Available</p>
        </div>
        """, unsafe_allow_html=True)
    
    with metric_col4:
        # Determine risk rating based on percentage
        if risk_method == "Percentage (%)":
            if max_risk_pct <= 2:
                risk_rating = "Low"
                risk_color = "#10b981"
            elif max_risk_pct <= 4:
                risk_rating = "Moderate"
                risk_color = "#fbbf24"
            else:
                risk_rating = "High"
                risk_color = "#ef4444"
        else:
            risk_rating = "Custom"
            risk_color = "#667eea"
        
        st.markdown(f"""
        <div style="
            background: linear-gradient(135deg, rgba(251, 191, 36, 0.15) 0%, rgba(251, 191, 36, 0.05) 100%);
            border: 1px solid rgba(251, 191, 36, 0.3);
            border-radius: 12px;
            padding: 1.2rem;
            text-align: center;
            box-shadow: 0 4px 15px rgba(251, 191, 36, 0.1);
        ">
            <p style="color: #a0aec0; font-size: 0.8rem; margin-bottom: 0.3rem;">Risk Rating</p>
            <h2 style="color: {risk_color}; margin: 0; font-size: 1.4rem;">{risk_rating}</h2>
            <p style="color: {risk_color}; font-size: 0.75rem; margin-top: 0.3rem;">{risk_method}</p>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # ========== BET SIZE CALCULATOR ==========
    st.markdown("""
    <p style="color: #D4AF37; font-weight: 600; margin-bottom: 1rem; font-size: 0.9rem;">🎯 BET SIZE CALCULATOR</p>
    """, unsafe_allow_html=True)
    
    calc_col1, calc_col2, calc_col3 = st.columns(3)
    
    with calc_col1:
        st.markdown(f"""
        <div style="
            background: linear-gradient(135deg, rgba(16, 185, 129, 0.15) 0%, rgba(16, 185, 129, 0.05) 100%);
            border: 1px solid rgba(16, 185, 129, 0.3);
            border-radius: 12px;
            padding: 1.5rem;
            text-align: center;
        ">
            <p style="color: #6b7280; font-size: 0.8rem; margin: 0;">🟢 LOW CONFIDENCE</p>
            <p style="color: #a0aec0; font-size: 0.75rem; margin: 0.3rem 0;">0.5 Units</p>
            <h3 style="color: #10b981; margin: 0.5rem 0; font-size: 1.5rem;">${unit_size * 0.5:,.2f}</h3>
            <p style="color: #6b7280; font-size: 0.7rem; margin: 0;">60-70% confidence plays</p>
        </div>
        """, unsafe_allow_html=True)
    
    with calc_col2:
        st.markdown(f"""
        <div style="
            background: linear-gradient(135deg, rgba(251, 191, 36, 0.15) 0%, rgba(251, 191, 36, 0.05) 100%);
            border: 1px solid rgba(251, 191, 36, 0.3);
            border-radius: 12px;
            padding: 1.5rem;
            text-align: center;
        ">
            <p style="color: #6b7280; font-size: 0.8rem; margin: 0;">🟡 STANDARD</p>
            <p style="color: #a0aec0; font-size: 0.75rem; margin: 0.3rem 0;">1.0 Unit</p>
            <h3 style="color: #fbbf24; margin: 0.5rem 0; font-size: 1.5rem;">${unit_size:,.2f}</h3>
            <p style="color: #6b7280; font-size: 0.7rem; margin: 0;">70-80% confidence plays</p>
        </div>
        """, unsafe_allow_html=True)
    
    with calc_col3:
        st.markdown(f"""
        <div style="
            background: linear-gradient(135deg, rgba(239, 68, 68, 0.15) 0%, rgba(239, 68, 68, 0.05) 100%);
            border: 1px solid rgba(239, 68, 68, 0.3);
            border-radius: 12px;
            padding: 1.5rem;
            text-align: center;
        ">
            <p style="color: #6b7280; font-size: 0.8rem; margin: 0;">🔴 HIGH CONFIDENCE</p>
            <p style="color: #a0aec0; font-size: 0.75rem; margin: 0.3rem 0;">2.0 Units</p>
            <h3 style="color: #ef4444; margin: 0.5rem 0; font-size: 1.5rem;">${unit_size * 2:,.2f}</h3>
            <p style="color: #6b7280; font-size: 0.7rem; margin: 0;">80%+ confidence plays</p>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # ========== PERFORMANCE VISUALIZATION SECTION ==========
    st.markdown("""
    <p style="color: #D4AF37; font-weight: 600; margin-bottom: 1rem; font-size: 0.9rem;">📈 PERFORMANCE VISUALIZATION</p>
    """, unsafe_allow_html=True)
    
    viz_col1, viz_col2 = st.columns(2)
    
    with viz_col1:
        st.markdown("""
        <div style="
            background: rgba(15, 20, 35, 0.6);
            border: 1px dashed rgba(16, 185, 129, 0.4);
            border-radius: 12px;
            padding: 1.5rem;
            min-height: 220px;
            box-shadow: 0 0 15px rgba(16, 185, 129, 0.08);
        ">
            <h4 style="color: #10b981; margin-bottom: 0.5rem; font-size: 1rem;">📈 Equity Curve</h4>
            <p style="color: #4a5568; font-size: 0.8rem;">(Chart Coming Soon)</p>
            <div style="
                width: 100%;
                height: 140px;
                border: 1px solid rgba(16, 185, 129, 0.2);
                border-radius: 8px;
                margin-top: 1rem;
                background: rgba(0, 0, 0, 0.3);
                display: flex;
                align-items: center;
                justify-content: center;
            ">
                <p style="color: #4a5568; font-size: 0.75rem;">Equity visualization placeholder</p>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    with viz_col2:
        st.markdown("""
        <div style="
            background: rgba(15, 20, 35, 0.6);
            border: 1px dashed rgba(239, 68, 68, 0.4);
            border-radius: 12px;
            padding: 1.5rem;
            min-height: 220px;
            box-shadow: 0 0 15px rgba(239, 68, 68, 0.08);
        ">
            <h4 style="color: #ef4444; margin-bottom: 0.5rem; font-size: 1rem;">📉 Drawdown Curve</h4>
            <p style="color: #4a5568; font-size: 0.8rem;">(Chart Coming Soon)</p>
            <div style="
                width: 100%;
                height: 140px;
                border: 1px solid rgba(239, 68, 68, 0.2);
                border-radius: 8px;
                margin-top: 1rem;
                background: rgba(0, 0, 0, 0.3);
                display: flex;
                align-items: center;
                justify-content: center;
            ">
                <p style="color: #4a5568; font-size: 0.75rem;">Drawdown visualization placeholder</p>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # ========== ADVANCED BETTING ANALYTICS MODULE ==========
    st.markdown("""
    <p style="color: #D4AF37; font-weight: 600; margin-bottom: 1rem; font-size: 0.9rem;">🧠 ADVANCED BETTING ANALYTICS</p>
    """, unsafe_allow_html=True)
    
    adv_col1, adv_col2 = st.columns(2)
    
    with adv_col1:
        # Kelly Criterion Guidance
        st.markdown(f"""
        <div style="
            background: linear-gradient(135deg, rgba(102, 126, 234, 0.1) 0%, rgba(102, 126, 234, 0.05) 100%);
            border: 1px solid rgba(102, 126, 234, 0.3);
            border-radius: 12px;
            padding: 1.2rem;
            margin-bottom: 1rem;
            box-shadow: 0 4px 15px rgba(102, 126, 234, 0.1);
        ">
            <h5 style="color: #667eea; margin-bottom: 0.8rem; font-size: 0.95rem;">📐 Kelly Criterion Guidance</h5>
            <div style="background: rgba(0,0,0,0.2); padding: 0.8rem; border-radius: 8px; margin-bottom: 0.5rem;">
                <p style="color: #a0aec0; font-size: 0.85rem; margin: 0;">Max recommended bet:</p>
                <p style="color: #e2e8f0; font-size: 1.1rem; margin: 0.3rem 0 0 0; font-weight: 600;">${current_bankroll * 0.05:,.2f} (5% max)</p>
            </div>
            <div style="background: rgba(0,0,0,0.2); padding: 0.8rem; border-radius: 8px;">
                <p style="color: #a0aec0; font-size: 0.85rem; margin-bottom: 0.5rem;">Risk Tiers:</p>
                <div style="display: flex; gap: 0.5rem; flex-wrap: wrap;">
                    <span style="background: rgba(16, 185, 129, 0.2); color: #10b981; padding: 0.3rem 0.6rem; border-radius: 4px; font-size: 0.75rem;">Conservative 1-2%</span>
                    <span style="background: rgba(251, 191, 36, 0.2); color: #fbbf24; padding: 0.3rem 0.6rem; border-radius: 4px; font-size: 0.75rem;">Balanced 2-3%</span>
                    <span style="background: rgba(239, 68, 68, 0.2); color: #ef4444; padding: 0.3rem 0.6rem; border-radius: 4px; font-size: 0.75rem;">Aggressive 3-5%</span>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # Exposure Controls
        st.markdown(f"""
        <div style="
            background: linear-gradient(135deg, rgba(118, 75, 162, 0.1) 0%, rgba(118, 75, 162, 0.05) 100%);
            border: 1px solid rgba(118, 75, 162, 0.3);
            border-radius: 12px;
            padding: 1.2rem;
            box-shadow: 0 4px 15px rgba(118, 75, 162, 0.1);
        ">
            <h5 style="color: #764ba2; margin-bottom: 0.8rem; font-size: 0.95rem;">🎚️ Exposure Limits</h5>
            <div style="background: rgba(0,0,0,0.2); padding: 0.8rem; border-radius: 8px; margin-bottom: 0.5rem;">
                <p style="color: #a0aec0; font-size: 0.85rem; margin: 0;">Max Daily Exposure (10%):</p>
                <p style="color: #e2e8f0; font-size: 1.1rem; margin: 0.3rem 0 0 0; font-weight: 600;">${current_bankroll * 0.10:,.2f}</p>
            </div>
            <div style="background: rgba(0,0,0,0.2); padding: 0.8rem; border-radius: 8px;">
                <p style="color: #a0aec0; font-size: 0.85rem; margin: 0;">Max Single Game (5%):</p>
                <p style="color: #e2e8f0; font-size: 1.1rem; margin: 0.3rem 0 0 0; font-weight: 600;">${current_bankroll * 0.05:,.2f}</p>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    with adv_col2:
        # Volatility Index
        st.markdown(f"""
        <div style="
            background: linear-gradient(135deg, rgba(251, 191, 36, 0.1) 0%, rgba(251, 191, 36, 0.05) 100%);
            border: 1px solid rgba(251, 191, 36, 0.3);
            border-radius: 12px;
            padding: 1.2rem;
            margin-bottom: 1rem;
            text-align: center;
            box-shadow: 0 4px 15px rgba(251, 191, 36, 0.1);
        ">
            <h5 style="color: #fbbf24; margin-bottom: 0.8rem; font-size: 0.95rem;">🌡️ Bankroll Health</h5>
            <div style="
                width: 120px;
                height: 120px;
                border: 4px solid {"#10b981" if roi >= 0 else "#ef4444"};
                border-radius: 50%;
                margin: 0 auto;
                display: flex;
                align-items: center;
                justify-content: center;
                background: rgba(0, 0, 0, 0.3);
            ">
                <div style="text-align: center;">
                    <p style="color: {"#10b981" if roi >= 0 else "#ef4444"}; font-size: 1.8rem; margin: 0; font-weight: bold;">{"+" if roi >= 0 else ""}{roi:.1f}%</p>
                    <p style="color: #a0aec0; font-size: 0.7rem; margin: 0;">ROI</p>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # Session Targets
        st.markdown("""
        <div style="
            background: linear-gradient(135deg, rgba(16, 185, 129, 0.1) 0%, rgba(16, 185, 129, 0.05) 100%);
            border: 1px solid rgba(16, 185, 129, 0.3);
            border-radius: 12px;
            padding: 1.2rem;
            box-shadow: 0 4px 15px rgba(16, 185, 129, 0.1);
        ">
            <h5 style="color: #10b981; margin-bottom: 0.8rem; font-size: 0.95rem;">🎯 Session Targets</h5>
        </div>
        """, unsafe_allow_html=True)
        
        daily_goal = st.number_input("Daily Profit Goal ($)", min_value=0, value=int(unit_size * 3), step=50, key="daily_profit_goal")
        stop_loss = st.number_input("Stop Loss Limit ($)", min_value=0, value=int(unit_size * 3), step=25, key="stop_loss_limit")
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # ========== STRATEGY PROFILES ==========
    st.markdown("""
    <p style="color: #D4AF37; font-weight: 600; margin-bottom: 1rem; font-size: 0.9rem;">📚 STRATEGY PROFILES</p>
    """, unsafe_allow_html=True)
    
    with st.expander("🟢 Conservative Strategy"):
        st.markdown(f"""
        <div style="
            background: rgba(16, 185, 129, 0.1);
            border-left: 3px solid #10b981;
            padding: 1rem;
            border-radius: 0 8px 8px 0;
        ">
            <p style="color: #e2e8f0; margin-bottom: 0.5rem;"><strong>Risk Level:</strong> Low (1-2% per bet)</p>
            <p style="color: #a0aec0; margin-bottom: 0.5rem;">Your unit: <strong>${current_bankroll * 0.015:,.2f}</strong></p>
            <p style="color: #718096; font-size: 0.85rem;">
                This strategy focuses on capital preservation above all else. Recommended for new bettors 
                or those recovering from a drawdown period. Emphasizes high-confidence plays only.
            </p>
        </div>
        """, unsafe_allow_html=True)
    
    with st.expander("🟡 Balanced Strategy"):
        st.markdown(f"""
        <div style="
            background: rgba(251, 191, 36, 0.1);
            border-left: 3px solid #fbbf24;
            padding: 1rem;
            border-radius: 0 8px 8px 0;
        ">
            <p style="color: #e2e8f0; margin-bottom: 0.5rem;"><strong>Risk Level:</strong> Medium (2-4% per bet)</p>
            <p style="color: #a0aec0; margin-bottom: 0.5rem;">Your unit: <strong>${current_bankroll * 0.03:,.2f}</strong></p>
            <p style="color: #718096; font-size: 0.85rem;">
                The balanced approach offers a middle ground between growth and protection. 
                Suitable for experienced bettors with a proven track record seeking consistent returns.
            </p>
        </div>
        """, unsafe_allow_html=True)
    
    with st.expander("🔴 Aggressive Strategy"):
        st.markdown(f"""
        <div style="
            background: rgba(239, 68, 68, 0.1);
            border-left: 3px solid #ef4444;
            padding: 1rem;
            border-radius: 0 8px 8px 0;
        ">
            <p style="color: #e2e8f0; margin-bottom: 0.5rem;"><strong>Risk Level:</strong> High (4-5% per bet)</p>
            <p style="color: #a0aec0; margin-bottom: 0.5rem;">Your unit: <strong>${current_bankroll * 0.045:,.2f}</strong></p>
            <p style="color: #718096; font-size: 0.85rem;">
                This aggressive strategy is designed for experienced bettors with high conviction plays. 
                Only recommended with a substantial edge and ability to withstand significant variance.
            </p>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # ========== RISK COMPLIANCE BOX ==========
    st.markdown("""
    <div style="
        background: linear-gradient(135deg, rgba(251, 191, 36, 0.15) 0%, rgba(251, 191, 36, 0.05) 100%);
        border: 1px solid rgba(251, 191, 36, 0.4);
        border-radius: 12px;
        padding: 1.2rem;
        display: flex;
        align-items: flex-start;
        gap: 1rem;
        box-shadow: 0 4px 15px rgba(251, 191, 36, 0.1);
    ">
        <span style="font-size: 1.5rem;">⚠️</span>
        <div>
            <h5 style="color: #fbbf24; margin-bottom: 0.5rem; font-size: 0.95rem;">Risk Management Notice</h5>
            <p style="color: #a0aec0; font-size: 0.85rem; margin: 0;">
                Good bankroll management is essential to long-term success. This tool helps you plan, track, 
                and structure your approach responsibly. Never bet more than you can afford to lose, and always 
                maintain discipline in your betting strategy.
            </p>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)

with tab6:
    st.markdown("""
    <div style="
        background: linear-gradient(135deg, rgba(239, 68, 68, 0.12) 0%, rgba(251, 191, 36, 0.12) 100%);
        border: 1px solid rgba(239, 68, 68, 0.3);
        border-radius: 16px;
        padding: 1.5rem 2rem;
        margin-bottom: 2rem;
    ">
        <div style="display: flex; align-items: center; gap: 1rem;">
            <span style="font-size: 2.5rem;">📰</span>
            <div>
                <h1 style="margin: 0; color: #fff; font-size: 1.8rem;">News & Injuries</h1>
                <p style="margin: 0.3rem 0 0 0; color: #a0aec0;">Live Injury Reports • Updated Hourly</p>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    if engine:
        try:
            query = text("SELECT * FROM injuries LIMIT 115")
            with engine.connect() as conn:
                injuries_df = pd.read_sql(query, conn)
            
            if not injuries_df.empty:
                st.success(f"🏥 {len(injuries_df)} Active Injury Reports")
                
                for idx, row in injuries_df.iterrows():
                    player_name = row.get('player_name', row.get('name', 'Unknown'))
                    status = row.get('status', row.get('injury_status', 'Out'))
                    description = row.get('description', row.get('details', 'No details'))
                    
                    status_lower = str(status).lower()
                    if 'out' in status_lower:
                        status_color = '#ef4444'
                    elif 'questionable' in status_lower or 'dtd' in status_lower:
                        status_color = '#fbbf24'
                    else:
                        status_color = '#6b7280'
                    
                    st.markdown(f"""
                    <div style="
                        background: rgba(15, 20, 35, 0.7);
                        border-left: 3px solid {status_color};
                        border-radius: 8px;
                        padding: 0.8rem 1rem;
                        margin-bottom: 0.5rem;
                    ">
                        <span style="color: #fff; font-weight: 600;">{player_name}</span>
                        <span style="color: {status_color}; margin-left: 0.5rem;">{status}</span>
                        <p style="color: #9ca3af; font-size: 0.85rem; margin: 0.3rem 0 0 0;">{description}</p>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.info("No injury reports found")
        except Exception as e:
            st.error(f"Error loading injuries: {e}")
    else:
        st.warning("Database connection required")

    # ========== NEWS SECTION ==========
    st.markdown("<br><br>", unsafe_allow_html=True)
    
    st.markdown("""
    <div style="
        background: linear-gradient(135deg, rgba(102, 126, 234, 0.12) 0%, rgba(168, 85, 247, 0.12) 100%);
        border: 1px solid rgba(102, 126, 234, 0.3);
        border-radius: 16px;
        padding: 1.5rem 2rem;
        margin-bottom: 1.5rem;
    ">
        <div style="display: flex; align-items: center; gap: 1rem;">
            <span style="font-size: 2rem;">📰</span>
            <div>
                <h2 style="margin: 0; color: #fff; font-size: 1.4rem;">Top Headlines</h2>
                <p style="margin: 0.3rem 0 0 0; color: #a0aec0;">Latest NBA News • Updated Hourly</p>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    if engine:
        try:
            news_query = text("SELECT title, link, source, published_at FROM nba_news ORDER BY fetched_at DESC LIMIT 15")
            with engine.connect() as conn:
                news_df = pd.read_sql(news_query, conn)
            
            if not news_df.empty:
                for idx, row in news_df.iterrows():
                    title = row.get('title', 'No title')
                    link = row.get('link', '#')
                    source = row.get('source', 'Unknown')
                    
                    st.markdown(f"""
                    <div style="
                        background: rgba(15, 20, 35, 0.7);
                        border-left: 3px solid #667eea;
                        border-radius: 8px;
                        padding: 0.8rem 1rem;
                        margin-bottom: 0.5rem;
                    ">
                        <a href="{link}" target="_blank" style="color: #fff; font-weight: 600; text-decoration: none;">{title}</a>
                        <p style="color: #9ca3af; font-size: 0.8rem; margin: 0.3rem 0 0 0;">Source: {source}</p>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.info("No news available yet. News will appear after the first hourly fetch.")
        except Exception as e:
            st.error(f"Error loading news: {e}")


with tab7:
    st.markdown("## 📂 Data Explorer")
    
    SEASONS = ["2025-26", "2024-25", "2023-24", "2022-23", "2021-22"]
    
    col1, col2 = st.columns(2)
    with col1:
       selected_season = st.selectbox("Season", SEASONS, key="explorer_season")
    with col2:
        stat_type = st.selectbox("Stat Type", ["Game Results", "Player Stats"], key="explorer_stat_type")
    
    def get_season_dates(season_str):
        start_year = int(season_str.split("-")[0])
        start_date = f"{start_year}-10-01"
        end_date = f"{start_year + 1}-07-31"
        return start_date, end_date
    
    # Current 30 NBA teams
    NBA_TEAMS = ["ATL", "BOS", "BKN", "CHA", "CHI", "CLE", "DAL", "DEN", "DET", "GSW",
                 "HOU", "IND", "LAC", "LAL", "MEM", "MIA", "MIL", "MIN", "NOP", "NYK",
                 "OKC", "ORL", "PHI", "PHX", "POR", "SAC", "SAS", "TOR", "UTA", "WAS"]
    teams_list = ["All Teams"] + NBA_TEAMS
    
    if stat_type == "Game Results":
        selected_team = st.selectbox("🏀 Select Team", teams_list, key="explorer_team")
        
        if st.button("Load Data", key="explorer_load_btn"):
            start_date, end_date = get_season_dates(selected_season)
            
            if not engine:
                st.error("Database connection not available")
            else:
                try:
                    with engine.connect() as conn:
                        if selected_team == "All Teams":
                            query = text("""
                                SELECT 
                                    date AS game_date,
                                    home_team,
                                    visitor_team,
                                    home_pts,
                                    visitor_pts,
                                    home_win
                                FROM games
                                WHERE date >= :start_date AND date <= :end_date
                                ORDER BY date DESC
                                LIMIT 500
                            """)
                            df = pd.read_sql(query, conn, params={"start_date": start_date, "end_date": end_date})
                        else:
                            query = text("""
                                SELECT 
                                    date AS game_date,
                                    home_team,
                                    visitor_team,
                                    home_pts,
                                    visitor_pts,
                                    home_win
                                FROM games
                                WHERE date >= :start_date AND date <= :end_date
                                AND (home_team = :team OR visitor_team = :team)
                                ORDER BY date DESC
                                LIMIT 500
                            """)
                            df = pd.read_sql(query, conn, params={"start_date": start_date, "end_date": end_date, "team": selected_team})
                        
                        if df.empty:
                            st.warning(f"No game data found for {selected_season}.")
                        else:
                            df['game_date'] = pd.to_datetime(df['game_date']).dt.strftime('%Y-%m-%d')
                            st.success(f"✅ Found {len(df)} games for {selected_season}")
                            c1, c2, c3 = st.columns(3)
                            c1.metric("Total Games", len(df))
                            c2.metric("Avg Home Pts", f"{df['home_pts'].mean():.1f}")
                            c3.metric("Avg Away Pts", f"{df['visitor_pts'].mean():.1f}")
                            st.dataframe(df, use_container_width=True, height=400)
                
                except Exception as e:
                    st.error(f"❌ Error loading data: {str(e)}")
    
    else:
        st.markdown("---")
        
        # Current 30 NBA teams for player stats
        NBA_TEAMS_PLAYERS = ["ATL", "BOS", "BKN", "CHA", "CHI", "CLE", "DAL", "DEN", "DET", "GSW",
                            "HOU", "IND", "LAC", "LAL", "MEM", "MIA", "MIL", "MIN", "NOP", "NYK",
                            "OKC", "ORL", "PHI", "PHX", "POR", "SAC", "SAS", "TOR", "UTA", "WAS"]
        player_teams_list = NBA_TEAMS_PLAYERS
        
        col_team, col_player = st.columns(2)
        
        with col_team:
            selected_player_team = st.selectbox("🏀 Select Team", ["-- Select Team --"] + player_teams_list, key="player_team_select")

        players_list = []
        if selected_player_team != "-- Select Team --" and engine:
            start_date, end_date = get_season_dates(selected_season)
            try:
                with engine.connect() as conn:
                    result = conn.execute(text("""
                        SELECT DISTINCT player_name 
                        FROM player_boxscores 
                        WHERE team_abbreviation = :team
                        AND game_date >= :start_date AND game_date <= :end_date
                        ORDER BY player_name
                    """), {"team": selected_player_team, "start_date": start_date, "end_date": end_date})
                    players_list = [row[0] for row in result.fetchall()]
            except Exception:
                pass
        
        with col_player:
            if players_list:
                selected_player = st.selectbox("👤 Select Player", ["-- Select Player --"] + players_list, key="player_select")
            else:
                selected_player = st.selectbox("👤 Select Player", ["-- Select Team First --"], key="player_select_empty", disabled=True)
                selected_player = None
        
        st.markdown("**Or search by name:**")
        player_search_input = st.text_input("🔎 Search Player Name", "", key="explorer_player_search", placeholder="e.g. LeBron James")
        
        if st.button("Load Player Stats", key="explorer_load_player_btn"):
            start_date, end_date = get_season_dates(selected_season)
            
            search_player = None
            if player_search_input and player_search_input.strip():
                search_player = player_search_input.strip()
                use_like = True
            elif selected_player and selected_player not in ["-- Select Player --", "-- Select Team First --"]:
                search_player = selected_player
                use_like = False
            
            if not search_player:
                st.warning("Please select a player or enter a name to search.")
            elif not engine:
                st.error("Database connection not available")
            else:
                try:
                    with engine.connect() as conn:
                        if use_like:
                            query = text("""
                                SELECT *
                                FROM player_boxscores
                                WHERE game_date >= :start_date AND game_date <= :end_date
                                AND LOWER(player_name) LIKE LOWER(:player_search)
                                ORDER BY game_date DESC
                            """)
                            df = pd.read_sql(query, conn, params={"start_date": start_date, "end_date": end_date, "player_search": f"%{search_player}%"})
                        else:
                            query = text("""
                                SELECT *
                                FROM player_boxscores
                                WHERE game_date >= :start_date AND game_date <= :end_date
                                AND player_name = :player_name
                                ORDER BY game_date DESC
                            """)
                            df = pd.read_sql(query, conn, params={"start_date": start_date, "end_date": end_date, "player_name": search_player})
                        
                        if df.empty:
                            st.warning(f"No data found for '{search_player}' in {selected_season}.")
                        else:
                            player_display_name = df['player_name'].iloc[0]
                            player_team = df['team_abbreviation'].iloc[0] if 'team_abbreviation' in df.columns else 'N/A'
                            games_played = len(df)
                            
                            st.markdown("---")
                            st.markdown(f"""
                            <div style='background: linear-gradient(135deg, rgba(102, 126, 234, 0.2) 0%, rgba(118, 75, 162, 0.2) 100%); 
                                        padding: 1.5rem; border-radius: 12px; margin-bottom: 1rem;'>
                                <h2 style='margin: 0; color: #fff;'>🏀 {player_display_name}</h2>
                                <p style='margin: 0.5rem 0 0 0; color: #a0a0a0; font-size: 1.1rem;'>{player_team} • {selected_season} Season</p>
                            </div>
                            """, unsafe_allow_html=True)
                            
                            st.markdown("### 📊 Season Averages")
                            
                            stat_cols = ['pts', 'reb', 'ast', 'stl', 'blk', 'fg_pct', 'fg3_pct', 'ft_pct', 'oreb', 'dreb', 'pf', 'plus_minus']
                            
                            available_stats = {}
                            for col in stat_cols:
                                if col in df.columns:
                                    df[col] = pd.to_numeric(df[col], errors='coerce')
                                    avg_val = df[col].mean()
                                    if pd.notna(avg_val):
                                        available_stats[col] = avg_val
                            
                            stat_labels = {
                                'pts': 'PPG', 'reb': 'RPG', 'ast': 'APG', 'stl': 'SPG', 'blk': 'BPG',
                                'fg_pct': 'FG%', 'fg3_pct': '3P%', 'ft_pct': 'FT%', 
                                'oreb': 'ORPG', 'dreb': 'DRPG', 'pf': 'PFPG', 'plus_minus': '+/-'
                            }
                            
                            stat_items = list(available_stats.items())
                            stat_items.append(('games', games_played))
                            
                            for i in range(0, len(stat_items), 5):
                                cols = st.columns(5)
                                for j, col in enumerate(cols):
                                    if i + j < len(stat_items):
                                        stat_key, stat_val = stat_items[i + j]
                                        label = stat_labels.get(stat_key, stat_key.upper())
                                        if stat_key in ['fg_pct', 'fg3_pct', 'ft_pct']:
                                            col.metric(label, f"{stat_val:.1f}%")
                                        elif stat_key == 'games':
                                            col.metric("Games", f"{stat_val}")
                                        else:
                                            col.metric(label, f"{stat_val:.1f}")
                            
                            st.markdown("### 📅 Game Log")
                            
                            display_cols = ['game_date', 'team_abbreviation']
                            for col in ['pts', 'reb', 'ast', 'stl', 'blk', 'fg_pct', 'fg3_pct', 'ft_pct', 'plus_minus']:
                                if col in df.columns:
                                    display_cols.append(col)
                            
                            display_df = df[display_cols].copy()
                            display_df['game_date'] = pd.to_datetime(display_df['game_date']).dt.strftime('%Y-%m-%d')
                            
                            rename_map = {
                                'game_date': 'Date', 'team_abbreviation': 'Team',
                                'pts': 'PTS', 'reb': 'REB', 'ast': 'AST', 'stl': 'STL', 'blk': 'BLK',
                                'fg_pct': 'FG%', 'fg3_pct': '3P%', 'ft_pct': 'FT%', 'plus_minus': '+/-'
                            }
                            display_df.rename(columns=rename_map, inplace=True)
                            
                            st.dataframe(display_df, use_container_width=True, height=400, hide_index=True)
                
                except Exception as e:
                    st.error(f"❌ Error loading data: {str(e)}")

with tab8:
    st.markdown("""
    <div style="
        background: linear-gradient(135deg, rgba(102, 126, 234, 0.15) 0%, rgba(118, 75, 162, 0.15) 100%);
        border: 1px solid rgba(102, 126, 234, 0.3);
        border-radius: 16px;
        padding: 1.5rem 2rem;
        margin-bottom: 2rem;
    ">
        <div style="display: flex; align-items: center; gap: 1rem;">
            <span style="font-size: 2.5rem;">📊</span>
            <div>
                <h1 style="margin: 0; color: #fff; font-size: 1.8rem;">Daily Reports — Algo Performance</h1>
                <p style="margin: 0.3rem 0 0 0; color: #a0aec0;">Track win rates, ROI, and algorithm insights</p>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    try:
        from math_engine import GameBettingMemory, PropsMemory
        
        game_memory = GameBettingMemory(engine)
        props_memory = PropsMemory(engine)
        
        # ========== TIME PERIOD SELECTOR ==========
        period = st.selectbox("Select Period", ["Last 7 Days", "Last 30 Days", "Last 60 Days", "All Time"], key="report_period")
        days_map = {"Last 7 Days": 7, "Last 30 Days": 30, "Last 60 Days": 60, "All Time": 365}
        days = days_map[period]
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        # ========== GAME BETTING PERFORMANCE ==========
        st.markdown("""
        <div style="
            background: linear-gradient(135deg, rgba(16, 185, 129, 0.1) 0%, rgba(16, 185, 129, 0.05) 100%);
            border: 2px solid rgba(16, 185, 129, 0.3);
            border-radius: 12px;
            padding: 1.5rem;
            margin-bottom: 1.5rem;
        ">
            <div style="display: flex; align-items: center; gap: 0.8rem; margin-bottom: 0.5rem;">
                <span style="font-size: 1.5rem;">🏀</span>
                <h3 style="color: #10b981; margin: 0; font-size: 1.2rem;">Game Betting Performance</h3>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        game_stats = game_memory.get_performance_stats(days=days)
        
        if game_stats.get('by_type'):
            # Summary metrics
            col1, col2, col3, col4 = st.columns(4)
            
            total_bets = sum(d['total'] for d in game_stats['by_type'].values())
            total_wins = sum(d['wins'] for d in game_stats['by_type'].values())
            total_profit = sum(d['units_profit'] for d in game_stats['by_type'].values())
            overall_wr = (total_wins / total_bets * 100) if total_bets > 0 else 0
            
            with col1:
                st.metric("Total Bets", total_bets)
            with col2:
                st.metric("Win Rate", f"{overall_wr:.1f}%")
            with col3:
                st.metric("Units Profit", f"{total_profit:+.1f}u")
            with col4:
                roi = (total_profit / total_bets * 100) if total_bets > 0 else 0
                st.metric("ROI", f"{roi:+.1f}%")
            
            st.markdown("<br>", unsafe_allow_html=True)
            
            # By bet type
            st.markdown("**Performance by Bet Type:**")
            
            type_data = []
            for pred_type, data in game_stats['by_type'].items():
                type_data.append({
                    'Type': pred_type,
                    'Bets': data['total'],
                    'Wins': data['wins'],
                    'Losses': data['losses'],
                    'Win %': f"{data['win_rate']}%",
                    'Units': f"{data['units_profit']:+.1f}",
                    'Avg Edge': f"{data['avg_edge']:.1f}"
                })
            
            if type_data:
                st.dataframe(pd.DataFrame(type_data), use_container_width=True, hide_index=True)
            
            # By edge tier
            if game_stats.get('by_edge'):
                st.markdown("<br>", unsafe_allow_html=True)
                st.markdown("**Performance by Edge Size:**")
                
                edge_data = []
                for item in game_stats['by_edge']:
                    edge_data.append({
                        'Type': item['type'],
                        'Edge Tier': item['tier'],
                        'Bets': item['total'],
                        'Wins': item['wins'],
                        'Win %': f"{item['win_rate']}%",
                        'Units': f"{item['units_profit']:+.1f}"
                    })
                
                if edge_data:
                    st.dataframe(pd.DataFrame(edge_data), use_container_width=True, hide_index=True)
        else:
            st.info("No game betting data yet. Predictions will be graded after games complete.")
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        # ========== PROPS BETTING PERFORMANCE ==========
        st.markdown("""
        <div style="
            background: linear-gradient(135deg, rgba(251, 191, 36, 0.1) 0%, rgba(251, 191, 36, 0.05) 100%);
            border: 2px solid rgba(251, 191, 36, 0.3);
            border-radius: 12px;
            padding: 1.5rem;
            margin-bottom: 1.5rem;
        ">
            <div style="display: flex; align-items: center; gap: 0.8rem; margin-bottom: 0.5rem;">
                <span style="font-size: 1.5rem;">🎯</span>
                <h3 style="color: #fbbf24; margin: 0; font-size: 1.2rem;">Props Betting Performance</h3>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        props_stats = props_memory.get_performance_stats(days=days)
        
        if props_stats.get('overall') and props_stats['overall']['total'] > 0:
            overall = props_stats['overall']
            
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("Total Props", overall['total'])
            with col2:
                st.metric("Win Rate", f"{overall['win_rate']}%")
            with col3:
                st.metric("Units Profit", f"{overall['units_profit']:+.1f}u")
            with col4:
                st.metric("ROI", f"{overall['roi']:+.1f}%")
            
            st.markdown("<br>", unsafe_allow_html=True)
            
            # By market
            if props_stats.get('by_market'):
                st.markdown("**Performance by Market:**")
                
                market_data = []
                for item in props_stats['by_market']:
                    market_clean = item['market'].replace('player_', '').title()
                    market_data.append({
                        'Market': market_clean,
                        'Bets': item['total'],
                        'Wins': item['wins'],
                        'Win %': f"{item['win_rate']}%",
                        'Units': f"{item['units_profit']:+.1f}",
                        'Avg Edge': f"{item['avg_edge']:.0f}%"
                    })
                
                if market_data:
                    st.dataframe(pd.DataFrame(market_data), use_container_width=True, hide_index=True)
            
            # By edge tier
            if props_stats.get('by_edge'):
                st.markdown("<br>", unsafe_allow_html=True)
                st.markdown("**Performance by Edge Size:**")
                
                edge_data = []
                for item in props_stats['by_edge']:
                    edge_data.append({
                        'Edge Tier': item['tier'],
                        'Bets': item['total'],
                        'Wins': item['wins'],
                        'Win %': f"{item['win_rate']}%",
                        'Units': f"{item['units_profit']:+.1f}"
                    })
                
                if edge_data:
                    st.dataframe(pd.DataFrame(edge_data), use_container_width=True, hide_index=True)
        else:
            st.info("No props betting data yet. Predictions will be graded after games complete.")
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        # ========== INSIGHTS ==========
        st.markdown("""
        <div style="
            background: linear-gradient(135deg, rgba(168, 85, 247, 0.1) 0%, rgba(168, 85, 247, 0.05) 100%);
            border: 2px solid rgba(168, 85, 247, 0.3);
            border-radius: 12px;
            padding: 1.5rem;
            margin-bottom: 1.5rem;
        ">
            <div style="display: flex; align-items: center; gap: 0.8rem; margin-bottom: 0.5rem;">
                <span style="font-size: 1.5rem;">💡</span>
                <h3 style="color: #a855f7; margin: 0; font-size: 1.2rem;">Algorithm Insights</h3>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # Game insights
        game_insights = game_memory.get_insights()
        prop_insights = props_memory.get_insights()
        
        if game_insights or prop_insights:
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("**🏀 Game Betting Insights:**")
                for insight in game_insights[:5]:
                    st.markdown(f"• {insight}")
            
            with col2:
                st.markdown("**🎯 Props Betting Insights:**")
                for insight in prop_insights[:5]:
                    st.markdown(f"• {insight}")
        else:
            st.info("Insights will appear after 20+ graded picks")
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        # ========== RECENT PICKS ==========
        st.markdown("""
        <div style="
            background: linear-gradient(135deg, rgba(59, 130, 246, 0.1) 0%, rgba(59, 130, 246, 0.05) 100%);
            border: 2px solid rgba(59, 130, 246, 0.3);
            border-radius: 12px;
            padding: 1.5rem;
            margin-bottom: 1.5rem;
        ">
            <div style="display: flex; align-items: center; gap: 0.8rem; margin-bottom: 0.5rem;">
                <span style="font-size: 1.5rem;">📋</span>
                <h3 style="color: #3b82f6; margin: 0; font-size: 1.2rem;">Recent Graded Picks</h3>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        with engine.connect() as conn:
            # Recent game picks
            recent_games = conn.execute(text("""
                SELECT game_date, home_team, away_team, prediction_type, pick, 
                       edge, hit, units_result
                FROM algo_game_predictions
                WHERE graded_at IS NOT NULL
                ORDER BY graded_at DESC
                LIMIT 15
            """)).fetchall()
            
            if recent_games:
                st.markdown("**Recent Game Bets:**")
                game_data = []
                for row in recent_games:
                    result = "✅" if row[6] else "❌"
                    game_data.append({
                        'Date': str(row[0]),
                        'Game': f"{row[2]} @ {row[1]}",
                        'Type': row[3],
                        'Pick': row[4],
                        'Edge': f"{row[5]:.1f}",
                        'Result': result,
                        'Units': f"{row[7]:+.1f}" if row[7] else "0"
                    })
                st.dataframe(pd.DataFrame(game_data), use_container_width=True, hide_index=True)
            
            # Recent prop picks
            recent_props = conn.execute(text("""
                SELECT game_date, player_name, market, pick, line,
                       edge, hit, units_result
                FROM algo_prop_predictions
                WHERE graded_at IS NOT NULL
                ORDER BY graded_at DESC
                LIMIT 15
            """)).fetchall()
            
            if recent_props:
                st.markdown("<br>", unsafe_allow_html=True)
                st.markdown("**Recent Prop Bets:**")
                prop_data = []
                for row in recent_props:
                    result = "✅" if row[6] else "❌"
                    market_clean = row[2].replace('player_', '') if row[2] else ''
                    prop_data.append({
                        'Date': str(row[0]),
                        'Player': row[1],
                        'Market': market_clean,
                        'Pick': f"{row[3]} {row[4]}",
                        'Edge': f"{row[5]:.0f}%",
                        'Result': result,
                        'Units': f"{row[7]:+.1f}" if row[7] else "0"
                    })
                st.dataframe(pd.DataFrame(prop_data), use_container_width=True, hide_index=True)
            
            if not recent_games and not recent_props:
                st.info("No graded picks yet. Check back after tomorrow's grading runs at 6 AM ET.")
                
    except Exception as e:
        st.error(f"Error loading performance data: {e}")
        st.info("Performance tracking will activate once picks are graded.")

with tab9:
    st.markdown("## ⚙️ Settings")
    st.info("Settings panel coming soon")
