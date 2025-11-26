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
    st.markdown("## 📁 Data Explorer — Historical Stats")
    st.markdown("### 🔍 Query Historical Data")
    
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
    
    # Get teams list dynamically
    teams_list = ["All Teams"]
    if engine:
        try:
            with engine.connect() as conn:
                # First check what columns exist in games table
                cols_query = text("""
                    SELECT column_name FROM information_schema.columns 
                    WHERE table_name = 'games'
                """)
                cols_result = conn.execute(cols_query).fetchall()
                games_columns = [row[0] for row in cols_result]
                
                # Find the home team column
                home_team_col = None
                for col in games_columns:
                    if 'home' in col.lower() and ('team' in col.lower() or 'abbreviation' in col.lower()):
                        home_team_col = col
                        break
                
                if home_team_col:
                    teams_query = text(f"""
                        SELECT DISTINCT "{home_team_col}" as team 
                        FROM games 
                        WHERE "{home_team_col}" IS NOT NULL
                        ORDER BY "{home_team_col}"
                    """)
                    result = conn.execute(teams_query)
                    teams_list = ["All Teams"] + [row[0] for row in result.fetchall()]
        except Exception as e:
            st.warning(f"Could not load teams: {e}")
    
    if stat_type == "Game Results":
        selected_team = st.selectbox("🏀 Select Team", teams_list, key="explorer_team")
    else:
        player_search_input = st.text_input("🔎 Search Player Name", "", key="explorer_player_search")
    
    if st.button("Load Data", key="explorer_load_btn"):
        start_date, end_date = get_season_dates(selected_season)
        
        if not engine:
            st.error("Database connection not available")
        else:
            try:
                with engine.connect() as conn:
                    if stat_type == "Game Results":
                        # First, get actual column names from games table
                        cols_query = text("""
                            SELECT column_name FROM information_schema.columns 
                            WHERE table_name = 'games'
                        """)
                        cols_result = conn.execute(cols_query).fetchall()
                        games_columns = [row[0] for row in cols_result]
                        
                        # Find the right column names (case-insensitive matching)
                        date_col = None
                        home_team_col = None
                        away_team_col = None
                        pts_home_col = None
                        pts_away_col = None
                        wl_home_col = None
                        
                        for col in games_columns:
                            col_lower = col.lower()
                            if 'date' in col_lower and date_col is None:
                                date_col = col
                            if 'home' in col_lower and 'abbreviation' in col_lower:
                                home_team_col = col
                            if 'away' in col_lower and 'abbreviation' in col_lower:
                                away_team_col = col
                            if col_lower == 'pts_home' or (col_lower.startswith('pts') and 'home' in col_lower):
                                pts_home_col = col
                            if col_lower == 'pts_away' or (col_lower.startswith('pts') and 'away' in col_lower):
                                pts_away_col = col
                            if 'wl' in col_lower and 'home' in col_lower:
                                wl_home_col = col
                        
                        # Debug: show found columns
                        if not all([date_col, home_team_col, away_team_col]):
                            st.warning(f"Available columns: {games_columns}")
                            st.stop()
                        
                        # Build query with actual column names
                        if selected_team == "All Teams":
                            query = text(f"""
                                SELECT 
                                    "{date_col}" AS game_date,
                                    "{home_team_col}" AS home_team,
                                    "{away_team_col}" AS away_team,
                                    "{pts_home_col}" AS home_pts,
                                    "{pts_away_col}" AS away_pts,
                                    "{wl_home_col}" AS home_result
                                FROM games
                                WHERE "{date_col}" >= :start_date AND "{date_col}" <= :end_date
                                ORDER BY "{date_col}" DESC
                                LIMIT 500
                            """)
                            df = pd.read_sql(query, conn, params={"start_date": start_date, "end_date": end_date})
                        else:
                            query = text(f"""
                                SELECT 
                                    "{date_col}" AS game_date,
                                    "{home_team_col}" AS home_team,
                                    "{away_team_col}" AS away_team,
                                    "{pts_home_col}" AS home_pts,
                                    "{pts_away_col}" AS away_pts,
                                    "{wl_home_col}" AS home_result
                                FROM games
                                WHERE "{date_col}" >= :start_date AND "{date_col}" <= :end_date
                                AND ("{home_team_col}" = :team OR "{away_team_col}" = :team)
                                ORDER BY "{date_col}" DESC
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
                            c3.metric("Avg Away Pts", f"{df['away_pts'].mean():.1f}")
                            st.dataframe(df, use_container_width=True, height=400)
                    
                    else:  # Player Stats
                        # First, get actual column names from player_boxscores table
                        cols_query = text("""
                            SELECT column_name FROM information_schema.columns 
                            WHERE table_name = 'player_boxscores'
                        """)
                        cols_result = conn.execute(cols_query).fetchall()
                        player_columns = [row[0] for row in cols_result]
                        
                        # Find the right column names
                        date_col = None
                        player_col = None
                        team_col = None
                        pts_col = None
                        reb_col = None
                        ast_col = None
                        min_col = None
                        
                        for col in player_columns:
                            col_lower = col.lower()
                            if 'date' in col_lower and date_col is None:
                                date_col = col
                            if 'player' in col_lower and 'name' in col_lower:
                                player_col = col
                            if 'team' in col_lower and 'abbreviation' in col_lower:
                                team_col = col
                            if col_lower == 'pts':
                                pts_col = col
                            if col_lower == 'reb':
                                reb_col = col
                            if col_lower == 'ast':
                                ast_col = col
                            if col_lower == 'min':
                                min_col = col
                        
                        if not all([date_col, player_col]):
                            st.warning(f"Available columns: {player_columns}")
                            st.stop()
                        
                        if player_search_input and player_search_input.strip():
                            query = text(f"""
                                SELECT 
                                    "{player_col}" AS player_name,
                                    "{team_col}" AS team,
                                    "{date_col}" AS game_date,
                                    "{pts_col}" AS pts, 
                                    "{reb_col}" AS reb, 
                                    "{ast_col}" AS ast, 
                                    "{min_col}" AS min
                                FROM player_boxscores
                                WHERE "{date_col}" >= :start_date AND "{date_col}" <= :end_date
                                AND LOWER("{player_col}") LIKE LOWER(:player_search)
                                ORDER BY "{date_col}" DESC
                                LIMIT 500
                            """)
                            search_param = f"%{player_search_input.strip()}%"
                            df = pd.read_sql(query, conn, params={"start_date": start_date, "end_date": end_date, "player_search": search_param})
                        else:
                            query = text(f"""
                                SELECT 
                                    "{player_col}" AS player_name,
                                    "{team_col}" AS team,
                                    "{date_col}" AS game_date,
                                    "{pts_col}" AS pts, 
                                    "{reb_col}" AS reb, 
                                    "{ast_col}" AS ast, 
                                    "{min_col}" AS min
                                FROM player_boxscores
                                WHERE "{date_col}" >= :start_date AND "{date_col}" <= :end_date
                                ORDER BY "{date_col}" DESC
                                LIMIT 500
                            """)
                            df = pd.read_sql(query, conn, params={"start_date": start_date, "end_date": end_date})
                        
                        if df.empty:
                            st.warning(f"No player data found for {selected_season}.")
                        else:
                            df['game_date'] = pd.to_datetime(df['game_date']).dt.strftime('%Y-%m-%d')
                            st.success(f"✅ Found {len(df)} records for {selected_season}")
                            c1, c2, c3, c4 = st.columns(4)
                            c1.metric("Records", len(df))
                            c2.metric("Avg PTS", f"{df['pts'].mean():.1f}")
                            c3.metric("Avg REB", f"{df['reb'].mean():.1f}")
                            c4.metric("Avg AST", f"{df['ast'].mean():.1f}")
                            st.dataframe(df, use_container_width=True, height=400)
            
            except Exception as e:
                st.error(f"❌ Error loading data: {str(e)}")

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
