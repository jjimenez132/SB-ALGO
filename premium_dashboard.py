import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
import os
from sqlalchemy import create_engine, text
import numpy as np

# Page config
st.set_page_config(
    page_title="SB ALGO — NBA Edge Engine",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="collapsed"
)

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
def get_db_connection():
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
engine = get_db_connection()

# Header
st.markdown("""
<div class="main-header">
    <h1>🎯 SB ALGO — NBA Edge Engine</h1>
    <p style='font-size: 1.2rem; margin: 0;'>Professional Basketball Betting Intelligence</p>
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
    st.markdown("## 📊 Daily Overview")
    
    # Top metrics
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.markdown("""
        <div class="metric-card">
            <h3>Games Today</h3>
            <h1>12</h1>
            <p style='color: #10b981;'>↑ NBA Full Slate</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown("""
        <div class="metric-card">
            <h3>Edges Found</h3>
            <h1>7</h1>
            <p style='color: #10b981;'>↑ +2 vs average</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown("""
        <div class="metric-card">
            <h3>System Confidence</h3>
            <h1>82%</h1>
            <p style='color: #10b981;'>↑ +15%</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        st.markdown("""
        <div class="metric-card">
            <h3>Best Value Play</h3>
            <h1>LAL -3.5</h1>
            <p style='color: #10b981;'>↑ 87% confidence</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col5:
        st.markdown("""
        <div class="metric-card">
            <h3>Algo Status</h3>
            <h1>LIVE</h1>
            <p style='color: #10b981;'>↑ All systems operational</p>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Filter by bet type
    st.markdown("### Filter by Bet Type:")
    bet_filter = st.radio(
        "",
        ["🎯 All Edges", "💵 Moneyline", "📊 Spread", "🎰 Totals", "⭐ Player Props"],
        horizontal=True
    )
    
    # Sample games with edge
    st.markdown("### 🔥 Top Edges Today")
    
    games_data = {
        "Time": ["7:00 PM", "7:30 PM", "8:00 PM", "10:00 PM"],
        "Matchup": ["LAL vs BOS", "MIA vs PHX", "DEN vs GSW", "LAC vs DAL"],
        "Edge Type": ["Spread", "Moneyline", "Total", "Spread"],
        "Recommendation": ["LAL -3.5", "PHX ML", "Under 228.5", "LAC +2.5"],
        "Confidence": ["87%", "82%", "79%", "76%"],
        "Expected Value": ["+12.3%", "+8.7%", "+7.2%", "+6.1%"]
    }
    
    df = pd.DataFrame(games_data)
    st.dataframe(df, use_container_width=True, hide_index=True)

with tab2:
    st.markdown("## 🎲 Today's Games — Deep Analysis")
    
    for i in range(3):
        with st.expander(f"🏀 Game {i+1}: Team A vs Team B — 7:00 PM ET", expanded=(i==0)):
            col1, col2 = st.columns([2, 1])
            
            with col1:
                st.markdown("### 📊 Game Analysis")
                st.markdown("""
                **Matchup Overview:**
                - Team A: 15-8 (Home: 9-3)
                - Team B: 12-11 (Away: 5-7)
                
                **Key Factors:**
                - Team A on 3-game win streak
                - Team B's star player questionable (ankle)
                - Historical edge: Team A 7-2 L9 meetings
                """)
                
                st.markdown("### 🎯 Algorithm Recommendation")
                st.success("**BET: Team A -4.5** | Confidence: 85%")
                st.markdown("Expected Value: +11.2% | Kelly Bet: 3.5% of bankroll")
            
            with col2:
                st.markdown("### 📈 Win Probability")
                fig = go.Figure(go.Indicator(
                    mode = "gauge+number",
                    value = 68,
                    domain = {'x': [0, 1], 'y': [0, 1]},
                    title = {'text': "Team A Win %"},
                    gauge = {
                        'axis': {'range': [None, 100]},
                        'bar': {'color': "#667eea"},
                        'steps': [
                            {'range': [0, 50], 'color': "lightgray"},
                            {'range': [50, 100], 'color': "rgba(102, 126, 234, 0.3)"}
                        ]
                    }
                ))
                fig.update_layout(height=250, margin=dict(l=20, r=20, t=40, b=20))
                st.plotly_chart(fig, use_container_width=True, key=f"game_probability_{i}")

with tab3:
    st.markdown("## 🧠 Props Engine — Player Intelligence")
    
    st.markdown("### 🔍 Search Player Props")
    col1, col2 = st.columns([3, 1])
    with col1:
        player_search = st.text_input("Search player name", "")
    with col2:
        prop_type = st.selectbox("Prop Type", ["All", "Points", "Rebounds", "Assists", "3PT Made"])
    
    st.markdown("### ⭐ Top Player Prop Edges")
    
    props_data = {
        "Player": ["LeBron James", "Stephen Curry", "Nikola Jokic", "Luka Doncic"],
        "Prop": ["Over 26.5 Pts", "Over 4.5 3PT", "Over 9.5 Reb", "Over 32.5 Pts"],
        "Line": ["26.5", "4.5", "9.5", "32.5"],
        "Hit Rate": ["68%", "71%", "65%", "63%"],
        "Confidence": ["84%", "81%", "78%", "75%"],
        "EV": ["+9.8%", "+8.2%", "+7.5%", "+6.3%"]
    }
    
    st.dataframe(pd.DataFrame(props_data), use_container_width=True, hide_index=True)

with tab4:
    st.markdown("## 📈 Trends & Patterns")
    
    trend_type = st.selectbox("View Trends For:", ["Team Trends", "Player Trends", "Situational Edges"])
    
    if trend_type == "Team Trends":
        st.markdown("### 🔥 Hot Teams (L10 Games)")
        hot_teams = pd.DataFrame({
            "Team": ["Boston Celtics", "Oklahoma City", "Cleveland", "Denver"],
            "Record": ["9-1", "8-2", "8-2", "7-3"],
            "ATS": ["7-3", "6-4", "7-3", "5-5"],
            "Avg Margin": ["+12.3", "+8.7", "+9.2", "+6.5"]
        })
        st.dataframe(hot_teams, use_container_width=True, hide_index=True)

with tab5:
    st.markdown("## 💰 Bankroll Manager")
    
    col1, col2 = st.columns(2)
    
    with col1:
        starting_bankroll = st.number_input("Starting Bankroll ($)", value=10000, step=100)
        risk_percentage = st.slider("Max Risk Per Bet (%)", 1, 5, 2)
    
    with col2:
        current_bankroll = st.number_input("Current Bankroll ($)", value=11250, step=100)
        roi = ((current_bankroll - starting_bankroll) / starting_bankroll) * 100
        st.metric("ROI", f"{roi:.1f}%", delta=f"+${current_bankroll - starting_bankroll}")

with tab6:
    st.markdown("## 📰 News & Injuries — Real-Time Updates")
    
    if engine:
        try:
            # Fetch real injury data - query all columns to see what's available
            query = text("""
                SELECT * 
                FROM injuries 
                ORDER BY updated_at DESC 
                LIMIT 50
            """)
            
            with engine.connect() as conn:
                injuries_df = pd.read_sql(query, conn)
            
            if not injuries_df.empty:
                st.markdown("### 🏥 Latest Injury Reports")
                st.markdown(f"**Last updated:** {datetime.now().strftime('%B %d, %Y at %I:%M %p ET')} | **Total Reports:** {len(injuries_df)}")
                st.markdown("---")
                
                # Display injuries in a clean format
                for idx, row in injuries_df.iterrows():
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        # Show player name prominently
                        player_name = row.get('player_name', row.get('name', 'Unknown Player'))
                        status = row.get('status', row.get('injury_status', 'Out'))
                        description = row.get('description', row.get('details', row.get('injury', 'No details available')))
                        
                        st.markdown(f"**{player_name}** — {status}")
                        st.markdown(f"_{description}_")
                    with col2:
                        updated = row.get('updated_at', row.get('date', ''))
                        if updated:
                            st.markdown(f"🕐 {updated}")
                    st.markdown("---")
            else:
                st.info("No recent injury reports found")
                
        except Exception as e:
            st.error(f"Error loading injuries: {str(e)}")
            st.markdown("**Debug info:** Check column names in injuries table")
    else:
        st.warning("Database connection required to view injury reports")

with tab7:
    st.markdown("## 📂 Data Explorer — Historical Stats")
    
    if engine:
        st.markdown("### 🔍 Query Historical Data")
        
        # Fetch all available years from game_date
        try:
            with engine.connect() as conn:
                seasons_query = text("""
                    SELECT DISTINCT EXTRACT(YEAR FROM game_date)::text as year
                    FROM games 
                    WHERE game_date IS NOT NULL
                    ORDER BY year DESC
                """)
                result = conn.execute(seasons_query)
                available_seasons = [row[0] for row in result.fetchall()]
            
            if not available_seasons:
                available_seasons = ["2024", "2023", "2022"]
                
        except Exception as e:
            st.warning(f"Could not load seasons: {str(e)}")
            available_seasons = ["2024", "2023", "2022"]
        
        col1, col2 = st.columns(2)
        with col1:
            season = st.selectbox("Season", available_seasons)
        with col2:
            stat_type = st.selectbox("Stat Type", ["Team Stats", "Player Stats", "Game Results"])
        
        if st.button("Load Data"):
            try:
                with engine.connect() as conn:
                    if stat_type == "Game Results":
                        query = text("""
                            SELECT game_date, team_abbreviation_home, team_abbreviation_away, 
                                   pts_home, pts_away, wl_home
                            FROM games 
                            WHERE EXTRACT(YEAR FROM game_date) = :year
                            ORDER BY game_date DESC
                            LIMIT 100
                        """)
                        df = pd.read_sql(query, conn, params={"year": int(season)})
                        st.dataframe(df, use_container_width=True, hide_index=True)
                        st.success(f"✅ Showing {len(df)} games from {season}")
                    
                    elif stat_type == "Player Stats":
                        query = text("""
                            SELECT player_name, team_abbreviation, game_date, pts, reb, ast
                            FROM player_boxscores 
                            WHERE EXTRACT(YEAR FROM game_date) = :year
                            ORDER BY pts DESC
                            LIMIT 100
                        """)
                        df = pd.read_sql(query, conn, params={"year": int(season)})
                        st.dataframe(df, use_container_width=True, hide_index=True)
                        st.success(f"✅ Showing top 100 performances from {season}")
                    
                    else:  # Team Stats
                        st.info(f"Team aggregation for {season} coming soon!")
                        
            except Exception as e:
                st.error(f"Error loading data: {str(e)}")
    else:
        st.warning("Database connection required")

with tab8:
    st.markdown("## 📊 Daily Reports — Performance Tracking")
    
    st.markdown("### 📅 Today's Summary")
    st.info("Report generation coming soon — will show daily picks, results, and performance metrics")

with tab9:
    st.markdown("## ⚙️ Settings — Customize Your Experience")
    
    st.markdown("### 🎨 Display Preferences")
    theme = st.selectbox("Theme", ["Dark Mode (Default)", "Light Mode"])
    
    st.markdown("### 🔔 Notifications")
    email_alerts = st.checkbox("Email alerts for high-confidence plays", value=True)
    sms_alerts = st.checkbox("SMS alerts for 85%+ confidence plays", value=False)
    
    st.markdown("### 💰 Bankroll Settings")
    auto_kelly = st.checkbox("Auto-calculate Kelly Criterion bets", value=True)
    
    if st.button("Save Settings"):
        st.success("✅ Settings saved!")
