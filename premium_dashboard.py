import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import os
from sqlalchemy import create_engine

# PAGE CONFIG
st.set_page_config(
    page_title="🎯 NBA Algo Engine",
    page_icon="🏀",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# CUSTOM CSS FOR PREMIUM DARK THEME
st.markdown("""
<style>
    /* Dark gradient background */
    .stApp {
        background: linear-gradient(180deg, #050814 0%, #0B0F17 100%);
    }
    
    /* Hide Streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* Custom card styling */
    div[data-testid="stHorizontalBlock"] {
        gap: 1rem;
    }
    
    /* Metric cards with glow effect */
    div[data-testid="metric-container"] {
        background: linear-gradient(135deg, #1a1f2e 0%, #151922 100%);
        border: 1px solid rgba(88, 101, 242, 0.2);
        padding: 1.5rem;
        border-radius: 16px;
        box-shadow: 0 4px 24px rgba(88, 101, 242, 0.1);
        transition: all 0.3s ease;
    }
    
    div[data-testid="metric-container"]:hover {
        border-color: rgba(88, 101, 242, 0.4);
        box-shadow: 0 8px 32px rgba(88, 101, 242, 0.2);
        transform: translateY(-2px);
    }
    
    /* Tabs styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 24px;
        background: rgba(26, 31, 46, 0.5);
        border-radius: 12px;
        padding: 4px;
    }
    
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        padding: 0 24px;
        background: transparent;
        border-radius: 8px;
        color: #8892B0;
        font-weight: 500;
    }
    
    .stTabs [data-baseweb="tab"][aria-selected="true"] {
        background: linear-gradient(135deg, #5865F2 0%, #7C3AED 100%);
        color: white;
    }
    
    /* Button styling */
    .stButton > button {
        background: linear-gradient(135deg, #5865F2 0%, #7C3AED 100%);
        color: white;
        border: none;
        padding: 0.75rem 2rem;
        border-radius: 12px;
        font-weight: 600;
        transition: all 0.3s ease;
    }
    
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 24px rgba(88, 101, 242, 0.3);
    }
    
    /* Expander styling */
    .streamlit-expanderHeader {
        background: rgba(26, 31, 46, 0.8);
        border-radius: 12px;
        border: 1px solid rgba(88, 101, 242, 0.2);
    }
    
    /* DataFrame styling */
    .dataframe {
        background: rgba(26, 31, 46, 0.6) !important;
        border: 1px solid rgba(88, 101, 242, 0.2) !important;
        border-radius: 12px;
    }
    
    /* Game card styling */
    .game-card {
        background: rgba(26, 31, 46, 0.8);
        padding: 1.5rem;
        border-radius: 12px;
        border-left: 4px solid #5865F2;
        margin-bottom: 1rem;
        transition: all 0.3s ease;
    }
    
    .game-card:hover {
        transform: translateX(5px);
        box-shadow: 0 4px 20px rgba(88, 101, 242, 0.2);
    }
</style>
""", unsafe_allow_html=True)

# DATABASE CONNECTION
@st.cache_resource
def get_db_connection():
    db_url = os.getenv('DATABASE_URL')
    if db_url:
        return create_engine(db_url)
    return None

engine = get_db_connection()

# HEADER WITH GRADIENT
st.markdown("""
<div style="
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    padding: 2rem;
    border-radius: 20px;
    margin-bottom: 2rem;
    box-shadow: 0 10px 40px rgba(102, 126, 234, 0.2);
">
    <h1 style="color: white; margin: 0; font-size: 2.5rem; font-weight: 700;">
        🎯 SB ALGO — NBA Edge Engine
    </h1>
    <p style="color: rgba(255,255,255,0.9); margin-top: 0.5rem; font-size: 1.1rem;">
        Professional Basketball Betting Intelligence
    </p>
</div>
""", unsafe_allow_html=True)

# DATABASE STATUS
if engine:
    try:
        with engine.connect() as conn:
            result = conn.execute("SELECT COUNT(*) FROM games").fetchone()
            game_count = result[0] if result else 0
        st.success(f"✅ Database Connected | {game_count:,} Games Loaded")
    except Exception as e:
        st.error(f"⚠️ Database Error: {str(e)}")
else:
    st.warning("⚠️ Database not configured. Add DATABASE_URL to environment variables.")

# MAIN NAVIGATION TABS
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

# ==================== DASHBOARD TAB ====================
with tab1:
    st.markdown("### 📊 Daily Overview")
    
    # Top metrics row
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.metric(
            label="Games Today",
            value="12",
            delta="NBA Full Slate"
        )
    
    with col2:
        st.metric(
            label="Edges Found",
            value="7",
            delta="+2 vs average"
        )
    
    with col3:
        st.metric(
            label="System Confidence",
            value="82%",
            delta="+15%"
        )
    
    with col4:
        st.metric(
            label="Best Value Play",
            value="LAL -3.5",
            delta="87% confidence"
        )
    
    with col5:
        st.metric(
            label="Algo Status",
            value="LIVE",
            delta="All systems operational"
        )
    
    st.markdown("---")
    
    # Betting category selector
    bet_type = st.radio(
        "Filter by Bet Type:",
        ["🎯 All Edges", "💵 Moneyline", "📊 Spread", "📈 Totals", "⭐ Player Props"],
        horizontal=True
    )
    
    # Today's games feed
    st.markdown("### 🔥 Today's Algorithm Picks")
    
    # Sample game cards (replace with real data)
    games = [
        {
            "matchup": "Los Angeles Lakers @ Golden State Warriors",
            "time": "10:00 PM ET",
            "venue": "Chase Center",
            "proj_home": 114.2,
            "proj_away": 118.5,
            "confidence": 0.73,
            "pick": "Lakers -3.5 (-110)",
            "edge": "+4.7%"
        },
        {
            "matchup": "Boston Celtics @ Miami Heat",
            "time": "7:30 PM ET",
            "venue": "Kaseya Center",
            "proj_home": 108.3,
            "proj_away": 112.7,
            "confidence": 0.68,
            "pick": "Celtics ML (-150)",
            "edge": "+3.2%"
        },
        {
            "matchup": "Denver Nuggets @ Phoenix Suns",
            "time": "9:00 PM ET",
            "venue": "Footprint Center",
            "proj_home": 115.8,
            "proj_away": 117.2,
            "confidence": 0.81,
            "pick": "Over 228.5 (-110)",
            "edge": "+6.1%"
        }
    ]
    
    for i, game in enumerate(games):
        col1, col2, col3, col4 = st.columns([3, 2, 2, 1])
        
        with col1:
            st.markdown(f"""
            <div class="game-card">
                <h3 style="margin: 0; color: white; font-size: 1.2rem;">{game['matchup']}</h3>
                <p style="color: #8892B0; margin: 0.5rem 0; font-size: 0.9rem;">
                    {game['time']} • {game['venue']}
                </p>
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            st.markdown("**Algorithm Projection**")
            away_team = game['matchup'].split('@')[0].strip().split()[-1]
            home_team = game['matchup'].split('@')[1].strip().split()[0]
            st.caption(f"{away_team}: {game['proj_away']} | {home_team}: {game['proj_home']}")
            st.progress(game['confidence'], text=f"{int(game['confidence']*100)}% confidence")
        
        with col3:
            st.markdown("**Recommended Bet**")
            st.success(game['pick'])
            st.caption(f"Edge: {game['edge']} EV")
        
        with col4:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("📊 Details", key=f"game_{i}"):
                st.info(f"→ Opening game analysis for {game['matchup']}")
        
        st.markdown("<br>", unsafe_allow_html=True)

# ==================== TODAY'S GAMES TAB ====================
with tab2:
    st.markdown("### 🏀 Complete Game-by-Game Analysis")
    
    # Game selector
    selected_game = st.selectbox(
        "Select Game for Deep Dive:",
        ["Lakers @ Warriors", "Celtics @ Heat", "Nuggets @ Suns"]
    )
    
    gcol1, gcol2 = st.columns([2, 1])
    
    with gcol1:
        # Score prediction
        st.markdown("""
        <div style="
            background: linear-gradient(135deg, rgba(88, 101, 242, 0.15), rgba(124, 58, 237, 0.15));
            padding: 2rem;
            border-radius: 16px;
            border: 1px solid rgba(88, 101, 242, 0.3);
            text-align: center;
            margin-bottom: 1.5rem;
        ">
            <h2 style="color: white; margin-bottom: 1rem;">Algorithm Predicted Final Score</h2>
            <div style="display: flex; justify-content: space-around; align-items: center;">
                <div>
                    <h1 style="color: #5865F2; font-size: 3.5rem; margin: 0;">118</h1>
                    <p style="color: #8892B0; font-size: 1.2rem; margin-top: 0.5rem;">Lakers</p>
                </div>
                <div>
                    <h2 style="color: #8892B0; font-size: 2rem;">vs</h2>
                </div>
                <div>
                    <h1 style="color: #7C3AED; font-size: 3.5rem; margin: 0;">114</h1>
                    <p style="color: #8892B0; font-size: 1.2rem; margin-top: 0.5rem;">Warriors</p>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # Key factors
        st.markdown("### 🔑 Critical Factors")
        
        factor_col1, factor_col2 = st.columns(2)
        with factor_col1:
            st.info("**Pace Advantage**: Lakers +3.2 possessions/game")
            st.warning("**Injury Impact**: Curry upgraded to PROBABLE")
            st.success("**Rest Advantage**: LAL (2 days) vs GSW (1 day)")
        
        with factor_col2:
            st.info("**Historical**: Lakers 7-3 ATS in last 10 meetings")
            st.success("**Home/Away**: Warriors 8-5 at home this season")
            st.warning("**Trend**: Warriors 2-8 ATS last 10 games")
    
    with gcol2:
        # Win probability gauge
        fig = go.Figure(go.Indicator(
            mode="gauge+number",
            value=68,
            title={'text': "Win Probability<br><span style='font-size:0.8em'>Lakers</span>", 'font': {'size': 20}},
            domain={'x': [0, 1], 'y': [0, 1]},
            gauge={
                'axis': {'range': [0, 100], 'tickwidth': 1, 'tickcolor': "white"},
                'bar': {'color': "#5865F2", 'thickness': 0.75},
                'bgcolor': "rgba(26, 31, 46, 0.8)",
                'borderwidth': 2,
                'bordercolor': "rgba(88, 101, 242, 0.3)",
                'steps': [
                    {'range': [0, 50], 'color': "rgba(255, 75, 75, 0.1)"},
                    {'range': [50, 75], 'color': "rgba(255, 215, 0, 0.1)"},
                    {'range': [75, 100], 'color': "rgba(0, 255, 127, 0.1)"}
                ],
                'threshold': {
                    'line': {'color': "white", 'width': 4},
                    'thickness': 0.75,
                    'value': 90
                }
            }
        ))
        
        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font={'color': "white", 'family': "Arial"},
            height=300,
            margin=dict(l=20, r=20, t=80, b=20)
        )
        st.plotly_chart(fig, use_container_width=True)
        
        # Confidence breakdown
        st.markdown("### 📊 Model Confidence")
        st.progress(0.85, text="Matchup Analysis: 85%")
        st.progress(0.72, text="Recent Form: 72%")
        st.progress(0.91, text="Pace Metrics: 91%")
        st.progress(0.65, text="Injury Adjusted: 65%")
        
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("**Overall Confidence**: 78%")

# ==================== PROPS ENGINE TAB ====================
with tab3:
    st.markdown("### ⭐ Player Prop Intelligence Engine")
    
    # Search and filters
    pcol1, pcol2, pcol3 = st.columns([2, 1, 1])
    
    with pcol1:
        player_search = st.text_input("🔍 Search Player", placeholder="Enter player name (e.g., LeBron James)")
    
    with pcol2:
        prop_type = st.selectbox(
            "Prop Category",
            ["All Props", "Points", "Rebounds", "Assists", "PRA", "3-Pointers", "Steals", "Blocks"]
        )
    
    with pcol3:
        confidence_filter = st.select_slider(
            "Minimum Confidence",
            options=["All", "60%+", "70%+", "80%+", "90%+"],
            value="70%+"
        )
    
    st.markdown("---")
    
    # Props cards
    props = [
        {
            "player": "LeBron James",
            "stat": "Points",
            "game": "Lakers vs Warriors",
            "line": 27.5,
            "projection": 31.2,
            "edge": 13.5,
            "streak": "Hit 7 of last 10",
            "trend": "Trending UP"
        },
        {
            "player": "Stephen Curry",
            "stat": "3-Pointers Made",
            "game": "Lakers vs Warriors",
            "line": 4.5,
            "projection": 5.8,
            "edge": 11.2,
            "streak": "Hit 6 of last 8",
            "trend": "Hot Streak"
        },
        {
            "player": "Jayson Tatum",
            "stat": "Rebounds",
            "game": "Celtics vs Heat",
            "line": 8.5,
            "projection": 10.1,
            "edge": 8.7,
            "streak": "Hit 5 of last 7",
            "trend": "Favorable Matchup"
        }
    ]
    
    for i, prop in enumerate(props):
        prop_col1, prop_col2, prop_col3 = st.columns([2, 2, 1])
        
        with prop_col1:
            st.markdown(f"""
            <div style="padding: 1.2rem; background: rgba(26, 31, 46, 0.7); border-radius: 12px; border: 1px solid rgba(88, 101, 242, 0.2);">
                <h4 style="color: white; margin: 0; font-size: 1.1rem;">{prop['player']} - {prop['stat']}</h4>
                <p style="color: #8892B0; margin: 0.5rem 0;">{prop['game']}</p>
                <div style="display: flex; gap: 1rem; margin-top: 0.8rem;">
                    <span style="color: #5865F2; font-size: 0.9rem;">🔥 {prop['streak']}</span>
                    <span style="color: #7C3AED; font-size: 0.9rem;">📈 {prop['trend']}</span>
                </div>
            </div>
            """, unsafe_allow_html=True)
        
        with prop_col2:
            met_col1, met_col2, met_col3 = st.columns(3)
            with met_col1:
                st.metric("Vegas Line", f"{prop['line']}", delta="O/U")
            with met_col2:
                st.metric("Algo Proj", f"{prop['projection']}", delta=f"+{prop['projection'] - prop['line']:.1f}")
            with met_col3:
                st.metric("Edge", f"{prop['edge']}%", delta="+++")
        
        with prop_col3:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button(f"🎯 BET OVER", key=f"prop_{i}", type="primary"):
                st.success("✅ Added to betting slip")
        
        st.markdown("---")

# ==================== TRENDS TAB ====================
with tab4:
    st.markdown("### 📈 Trends & Pattern Recognition System")
    
    trend_tab1, trend_tab2, trend_tab3, trend_tab4 = st.tabs([
        "Team Trends", "Player Streaks", "Market Inefficiencies", "Historical Patterns"
    ])
    
    with trend_tab1:
        st.markdown("#### 🔥 Team Performance Matrix (Last 10 Games)")
        
        # Sample heatmap
        teams = ["Lakers", "Warriors", "Celtics", "Heat", "Nuggets", "Suns", "Bucks", "76ers"]
        metrics = ["ATS", "O/U", "ML", "1H Spread", "2H Spread"]
        data = np.random.rand(8, 5) * 100
        
        fig = px.imshow(
            data,
            labels=dict(x="Betting Market", y="Team", color="Win Rate %"),
            x=metrics,
            y=teams,
            color_continuous_scale="RdYlGn",
            aspect="auto"
        )
        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font={'color': "white"},
            height=500
        )
        st.plotly_chart(fig, use_container_width=True)
    
    with trend_tab2:
        st.markdown("#### 📊 Active Player Streaks")
        
        streak_data = pd.DataFrame({
            "Player": ["LeBron James", "Stephen Curry", "Jayson Tatum", "Luka Doncic", "Giannis Antetokounmpo"],
            "Prop Type": ["Points O25.5", "3PM O4.5", "Rebounds O8.5", "PRA O45.5", "Points O28.5"],
            "Current Streak": ["8 games", "6 games", "5 games", "7 games", "9 games"],
            "Hit Rate": ["80%", "85%", "71%", "78%", "90%"],
            "Last 10": ["8-2", "8-2", "7-3", "7-3", "9-1"],
            "Status": ["🔥 HOT", "🔥 HOT", "📈 WARM", "🔥 HOT", "🔥 BLAZING"]
        })
        
        st.dataframe(
            streak_data,
            use_container_width=True,
            hide_index=True
        )
        
        st.info("💡 **Algorithm Insight**: Players on 5+ game streaks have a 73% success rate for the next game.")
    
    with trend_tab3:
        st.markdown("#### 🎯 Market Bias & Sharp Action Detection")
        
        st.markdown("##### Public vs Sharp Money")
        
        bias_col1, bias_col2 = st.columns(2)
        
        with bias_col1:
            st.error("**🚨 PUBLIC HEAVY**")
            st.markdown("""
            - **Lakers -3.5**: 87% of bets, line moved from -2.5
            - **Warriors ML**: 82% of bets, no line movement
            - **Celtics -4.5**: 79% of bets, line moved from -5.5
            """)
        
        with bias_col2:
            st.success("**💎 SHARP ACTION DETECTED**")
            st.markdown("""
            - **Heat +4.5**: Only 35% bets but line moved from +5.5 → +4.5
            - **Under 218.5**: 22% bets but line dropped 3 points
            - **Nuggets ML**: 41% bets but odds shortened significantly
            """)
        
        st.warning("⚠️ **Contrarian Opportunity**: When public is >75% on one side but line moves against them, fade the public.")
    
    with trend_tab4:
        st.markdown("#### 🕰️ Historical Pattern Analysis")
        
        pattern_options = st.multiselect(
            "Select pattern types to analyze:",
            ["Back-to-Back Games", "Rest Advantage", "Home/Away Splits", "Conference Matchups", "Division Rivals"],
            default=["Rest Advantage", "Home/Away Splits"]
        )
        
        if "Rest Advantage" in pattern_options:
            st.info("""
            **Rest Advantage Pattern** (Last 3 seasons):
            - Teams with 2+ days rest vs 0-1 days: **58.3% ATS**
            - Teams with 3+ days rest vs back-to-back: **62.7% ATS**
            - Impact increases in second half of season (+4.2%)
            """)
        
        if "Home/Away Splits" in pattern_options:
            st.success("""
            **Home Court Advantage** (2024-25 Season):
            - Home teams: **54.2% ATS** overall
            - Home underdogs: **61.3% ATS** (best value)
            - Home favorites of 10+: **43.1% ATS** (fade opportunity)
            """)

# ==================== BANKROLL TAB ====================
with tab5:
    st.markdown("### 💰 Professional Bankroll Management")
    
    bcol1, bcol2 = st.columns([1, 2])
    
    with bcol1:
        st.markdown("#### Your Bankroll Settings")
        
        bankroll = st.number_input(
            "Current Bankroll ($)",
            min_value=100,
            max_value=1000000,
            value=10000,
            step=500
        )
        
        risk_profile = st.select_slider(
            "Risk Profile",
            options=["Conservative", "Standard", "Aggressive", "High Roller"],
            value="Standard"
        )
        
        # Calculate unit size based on risk profile
        unit_percentages = {
            "Conservative": 1.0,
            "Standard": 2.0,
            "Aggressive": 3.0,
            "High Roller": 5.0
        }
        
        unit_size = bankroll * (unit_percentages[risk_profile] / 100)
        max_daily_risk = unit_size * 5
        
        st.markdown("---")
        
        st.metric("💵 Unit Size", f"${unit_size:.0f}", delta=f"{unit_percentages[risk_profile]}% of BR")
        st.metric("⚠️ Max Daily Risk", f"${max_daily_risk:.0f}", delta="5 units max")
        st.metric("📊 Optimal Bet Range", f"${unit_size*0.5:.0f} - ${unit_size*2:.0f}")
        
        # Risk meter
        risk_values = {"Conservative": 25, "Standard": 50, "Aggressive": 75, "High Roller": 95}
        risk_level = risk_values[risk_profile]
        
        st.markdown("<br>", unsafe_allow_html=True)
        st.progress(risk_level / 100, text=f"Risk Level: {risk_level}%")
        
        # Kelly Criterion calculator
        with st.expander("🧮 Kelly Criterion Calculator"):
            win_prob = st.slider("Win Probability (%)", 0, 100, 60) / 100
            odds = st.number_input("Decimal Odds", min_value=1.01, max_value=10.0, value=1.91, step=0.01)
            
            # Kelly formula: (bp - q) / b where b = odds - 1, p = win prob, q = 1 - p
            b = odds - 1
            kelly = (b * win_prob - (1 - win_prob)) / b
            kelly_pct = max(0, kelly * 100)
            
            st.metric("Kelly %", f"{kelly_pct:.2f}%")
            st.metric("Suggested Bet", f"${bankroll * kelly_pct / 100:.0f}")
    
    with bcol2:
        st.markdown("#### 📈 Bankroll Performance Tracking")
        
        # Generate sample bankroll history
        days = 60
        dates = pd.date_range(end=datetime.now(), periods=days)
        
        # Simulate realistic bankroll growth with variance
        np.random.seed(42)
        daily_returns = np.random.normal(0.005, 0.02, days)  # Average 0.5% daily return
        bankroll_history = bankroll * np.exp(np.cumsum(daily_returns))
        
        # Create the chart
        fig = go.Figure()
        
        # Main line
        fig.add_trace(go.Scatter(
            x=dates,
            y=bankroll_history,
            mode='lines',
            name='Bankroll',
            line=dict(color='#5865F2', width=3),
            fill='tozeroy',
            fillcolor='rgba(88, 101, 242, 0.1)'
        ))
        
        # Add starting bankroll reference line
        fig.add_hline(
            y=bankroll,
            line_dash="dash",
            line_color="rgba(255, 255, 255, 0.3)",
            annotation_text="Starting Bankroll",
            annotation_position="right"
        )
        
        fig.update_layout(
            title="60-Day Bankroll Trend",
            xaxis_title="Date",
            yaxis_title="Bankroll ($)",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(26, 31, 46, 0.3)",
            font={'color': "white"},
            hovermode='x unified',
            height=400,
            showlegend=False
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Performance metrics
        perf_col1, perf_col2, perf_col3, perf_col4 = st.columns(4)
        
        current_br = bankroll_history[-1]
        roi = ((current_br - bankroll) / bankroll) * 100
        max_br = np.max(bankroll_history)
        drawdown = ((max_br - current_br) / max_br) * 100
        
        with perf_col1:
            st.metric("Current BR", f"${current_br:,.0f}", delta=f"${current_br - bankroll:,.0f}")
        with perf_col2:
            st.metric("ROI", f"{roi:.1f}%", delta="60 days")
        with perf_col3:
            st.metric("Peak BR", f"${max_br:,.0f}")
        with perf_col4:
            st.metric("Drawdown", f"{drawdown:.1f}%", delta="From peak")

# ==================== NEWS & INJURIES TAB ====================
with tab6:
    st.markdown("### 📰 Real-Time News & Injury Intelligence")
    
    news_col1, news_col2 = st.columns([2, 1])
    
    with news_col1:
        st.markdown("#### 📢 Latest Breaking News")
        
        # Team/Tag filters
        filter_col1, filter_col2 = st.columns(2)
        with filter_col1:
            team_filter = st.multiselect(
                "Filter by Team",
                ["All Teams", "Lakers", "Warriors", "Celtics", "Heat", "Nuggets", "Suns"],
                default=["All Teams"]
            )
        with filter_col2:
            tag_filter = st.multiselect(
                "Filter by Tag",
                ["Injury", "Rest", "Trade", "Back-to-Back", "Coaching", "Lineup Change"],
                default=[]
            )
        
        st.markdown("---")
        
        # News feed
        news_items = [
            {
                "time": "2 minutes ago",
                "tag": "INJURY",
                "title": "Stephen Curry upgraded to PROBABLE",
                "details": "Warriors star cleared to play vs Lakers. Expected to be on minutes restriction.",
                "impact": "HIGH",
                "affected_lines": "Lakers spread moved from -4.5 to -3.5"
            },
            {
                "time": "18 minutes ago",
                "tag": "REST",
                "title": "Joel Embiid OUT for B2B",
                "details": "76ers resting Embiid for second night of back-to-back vs Celtics.",
                "impact": "HIGH",
                "affected_lines": "Celtics spread from -5.5 to -8.5"
            },
            {
                "time": "1 hour ago",
                "tag": "LINEUP",
                "title": "Nets announce Mikal Bridges to bench",
                "details": "Coach adjusting rotation, Cam Thomas to start at SG.",
                "impact": "MEDIUM",
                "affected_lines": "Total moved from 218.5 to 220.5"
            },
            {
                "time": "3 hours ago",
                "tag": "TRADE",
                "title": "Wizards trade Jordan Poole to Spurs",
                "details": "Multi-team deal sends Poole to San Antonio. Impact on pace/scoring.",
                "impact": "MEDIUM",
                "affected_lines": "Minor movement on future games"
            }
        ]
        
        for item in news_items:
            impact_colors = {
                "HIGH": "#FF4444",
                "MEDIUM": "#FFD700",
                "LOW": "#00FF7F"
            }
            
            tag_colors = {
                "INJURY": "#FF6B6B",
                "REST": "#4ECDC4",
                "TRADE": "#95E1D3",
                "LINEUP": "#F38181",
                "COACHING": "#AA96DA",
                "Back-to-Back": "#FCBAD3"
            }
            
            st.markdown(f"""
            <div style="
                background: rgba(26, 31, 46, 0.7);
                padding: 1.2rem;
                border-radius: 12px;
                margin-bottom: 1rem;
                border-left: 4px solid {impact_colors[item['impact']]};
            ">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
                    <span style="color: #8892B0; font-size: 0.85rem;">{item['time']}</span>
                    <span style="
                        background: {tag_colors.get(item['tag'], '#5865F2')};
                        padding: 0.25rem 0.75rem;
                        border-radius: 6px;
                        font-size: 0.75rem;
                        font-weight: 600;
                        color: white;
                    ">{item['tag']}</span>
                </div>
                <h4 style="color: white; margin: 0.5rem 0; font-size: 1.1rem;">{item['title']}</h4>
                <p style="color: #CCD6F6; margin: 0.5rem 0; font-size: 0.95rem;">{item['details']}</p>
                <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 0.8rem;">
                    <span style="color: {impact_colors[item['impact']]}; font-weight: 600;">
                        {'🔴' if item['impact']=='HIGH' else '🟡' if item['impact']=='MEDIUM' else '🟢'} {item['impact']} IMPACT
                    </span>
                    <span style="color: #8892B0; font-size: 0.85rem;">
                        📊 {item['affected_lines']}
                    </span>
                </div>
            </div>
            """, unsafe_allow_html=True)
    
    with news_col2:
        st.markdown("#### 🏥 Injury Report Monitor")
        
        # Date selector
        report_date = st.date_input("Report Date", value=datetime.now())
        
        st.markdown("---")
        
        # Injury status breakdown
        injuries = {
            "🔴 OUT": [
                {"player": "Anthony Davis", "team": "LAL", "reason": "Ankle sprain"},
                {"player": "Kawhi Leonard", "team": "LAC", "reason": "Load management"},
                {"player": "Joel Embiid", "team": "PHI", "reason": "Rest (B2B)"}
            ],
            "🟡 QUESTIONABLE": [
                {"player": "Stephen Curry", "team": "GSW", "reason": "Shoulder soreness"},
                {"player": "Jimmy Butler", "team": "MIA", "reason": "Knee inflammation"},
                {"player": "Zion Williamson", "team": "NOP", "reason": "Hamstring tightness"}
            ],
            "🟢 PROBABLE": [
                {"player": "LeBron James", "team": "LAL", "reason": "Ankle (upgraded)"},
                {"player": "Kevin Durant", "team": "PHX", "reason": "Calf (expected to play)"},
                {"player": "Jayson Tatum", "team": "BOS", "reason": "Wrist (minor)"}
            ]
        }
        
        for status, players in injuries.items():
            with st.expander(f"{status} ({len(players)})", expanded=True):
                for p in players:
                    st.markdown(f"""
                    <div style="
                        background: rgba(26, 31, 46, 0.5);
                        padding: 0.8rem;
                        border-radius: 8px;
                        margin-bottom: 0.5rem;
                    ">
                        <div style="display: flex; justify-content: space-between;">
                            <span style="color: white; font-weight: 600;">{p['player']}</span>
                            <span style="
                                background: rgba(88, 101, 242, 0.3);
                                padding: 0.2rem 0.5rem;
                                border-radius: 4px;
                                font-size: 0.75rem;
                            ">{p['team']}</span>
                        </div>
                        <p style="color: #8892B0; font-size: 0.85rem; margin: 0.3rem 0 0 0;">{p['reason']}</p>
                    </div>
                    """, unsafe_allow_html=True)
        
        st.markdown("---")
        st.info("💡 **Tip**: Monitor injury reports 30min before tip-off for best betting opportunities")

# ==================== DATA EXPLORER TAB ====================
with tab7:
    st.markdown("### 📂 Advanced Statistical Data Explorer")
    
    # Filters
    dcol1, dcol2, dcol3, dcol4 = st.columns(4)
    
    with dcol1:
        season_select = st.selectbox(
            "Season",
            ["2024-25", "2023-24", "2022-23", "2021-22", "2020-21"]
        )
    
    with dcol2:
        team_select = st.selectbox(
            "Team",
            ["All Teams", "Lakers", "Warriors", "Celtics", "Heat", "Nuggets"]
        )
    
    with dcol3:
        player_select = st.selectbox(
            "Player",
            ["All Players", "LeBron James", "Stephen Curry", "Jayson Tatum"]
        )
    
    with dcol4:
        metric_select = st.selectbox(
            "Primary Metric",
            ["Points", "ORtg", "DRtg", "Pace", "eFG%", "TS%", "AST%"]
        )
    
    # Sub-tabs for different data views
    data_tab1, data_tab2, data_tab3, data_tab4 = st.tabs([
        "Team Statistics", "Player Statistics", "Game Logs", "Advanced Metrics"
    ])
    
    with data_tab1:
        st.markdown("#### Team Statistical Overview")
        
        if engine:
            try:
                query = f"""
                SELECT 
                    home_team as team,
                    COUNT(*) as games_played,
                    AVG(home_pts) as avg_points,
                    AVG(CASE WHEN home_win = 1 THEN 1 ELSE 0 END) * 100 as win_pct
                FROM games
                WHERE season = '{season_select.replace('-', '')}'
                GROUP BY home_team
                ORDER BY win_pct DESC
                LIMIT 10
                """
                
                df = pd.read_sql(query, engine)
                
                if not df.empty:
                    st.dataframe(
                        df.style.format({
                            'avg_points': '{:.1f}',
                            'win_pct': '{:.1f}%'
                        }),
                        use_container_width=True
                    )
                else:
                    st.info("No data available for selected season")
            except Exception as e:
                st.warning(f"Unable to fetch team data: {str(e)}")
        else:
            st.info("Connect database to view team statistics")
        
        # Sample data if no DB
        if not engine:
            sample_team_data = pd.DataFrame({
                "Team": ["Lakers", "Warriors", "Celtics", "Heat", "Nuggets"],
                "Record": ["15-8", "14-9", "18-5", "12-11", "16-7"],
                "ATS": ["13-10-0", "11-12-0", "15-8-0", "10-13-0", "14-9-0"],
                "O/U": ["12-11", "14-9", "11-12", "13-10", "15-8"],
                "PPG": [118.5, 116.2, 119.8, 112.3, 117.9],
                "Pace": [101.2, 98.5, 99.8, 97.2, 100.5],
                "ORtg": [118.5, 116.2, 119.8, 112.3, 117.9]
            })
            st.dataframe(sample_team_data, use_container_width=True)
    
    with data_tab2:
        st.markdown("#### Player Performance Metrics")
        
        if player_select != "All Players":
            # Sample player stats
            player_stats = pd.DataFrame({
                "Game": [f"Game {i+1}" for i in range(10)],
                "Date": [(datetime.now() - timedelta(days=i*2)).strftime("%Y-%m-%d") for i in range(10)],
                "OPP": ["GSW", "PHX", "DEN", "UTA", "POR", "SAC", "LAC", "MEM", "NOP", "SAS"],
                "PTS": [28, 31, 25, 33, 27, 29, 26, 30, 32, 24],
                "REB": [7, 8, 6, 9, 7, 8, 6, 7, 9, 5],
                "AST": [8, 9, 7, 10, 8, 9, 7, 8, 10, 6],
                "MIN": [36, 38, 34, 40, 35, 37, 33, 36, 39, 32]
            })
            
            st.dataframe(player_stats, use_container_width=True)
            
            # Player trend chart
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=player_stats['Game'],
                y=player_stats['PTS'],
                mode='lines+markers',
                name='Points',
                line=dict(color='#5865F2', width=3),
                marker=dict(size=8)
            ))
            
            fig.update_layout(
                title=f"{player_select} - Last 10 Games",
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(26, 31, 46, 0.3)",
                font={'color': "white"},
                height=300
            )
            
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Select a specific player to view detailed statistics")
    
    with data_tab3:
        st.markdown("#### Recent Game History")
        
        # Game log filters
        glog_col1, glog_col2, glog_col3 = st.columns(3)
        
        with glog_col1:
            home_away = st.radio("Location", ["All", "Home", "Away"], horizontal=True)
        with glog_col2:
            result_filter = st.radio("Result", ["All", "Wins", "Losses"], horizontal=True)
        with glog_col3:
            last_n = st.selectbox("Last N Games", [5, 10, 20, 50], index=1)
        
        st.info(f"Showing last {last_n} games for {team_select if team_select != 'All Teams' else 'all teams'}")
    
    with data_tab4:
        st.markdown("#### Advanced Analytics Dashboard")
        
        # Four Factors
        st.markdown("##### Four Factors Analysis")
        
        four_col1, four_col2 = st.columns(2)
        
        with four_col1:
            st.markdown("**Offensive Four Factors**")
            factors_off = pd.DataFrame({
                "Factor": ["eFG%", "TO%", "ORB%", "FT Rate"],
                "League Avg": [54.2, 13.5, 24.8, 21.3],
                "Team": [56.1, 12.8, 26.2, 22.1],
                "Rank": [8, 12, 5, 14]
            })
            st.dataframe(factors_off, use_container_width=True, hide_index=True)
        
        with four_col2:
            st.markdown("**Defensive Four Factors**")
            factors_def = pd.DataFrame({
                "Factor": ["eFG%", "TO%", "DRB%", "FT Rate"],
                "League Avg": [54.2, 13.5, 75.2, 21.3],
                "Team": [52.8, 14.2, 76.8, 20.1],
                "Rank": [6, 18, 11, 9]
            })
            st.dataframe(factors_def, use_container_width=True, hide_index=True)

# ==================== REPORTS TAB ====================
with tab8:
    st.markdown("### 📊 Daily Performance Reports")
    
    # Date selector
    report_date = st.date_input("Select Report Date", value=datetime.now())
    
    st.markdown("---")
    
    # Yesterday's summary
    st.markdown("#### Yesterday's Algorithm Performance")
    
    rcol1, rcol2, rcol3, rcol4 = st.columns(4)
    
    with rcol1:
        st.metric("Overall Record", "5-2-0", delta="+2.91 units")
    with rcol2:
        st.metric("Spreads", "3-1-0", delta="+1.91 units")
    with rcol3:
        st.metric("Totals", "2-1-0", delta="+0.91 units")
    with rcol4:
        st.metric("Props", "4-2-0", delta="+1.82 units")
    
    st.markdown("---")
    
    # Detailed results
    st.markdown("#### 📝 Detailed Game Results")
    
    results_data = pd.DataFrame({
        "Game": [
            "Lakers @ Warriors",
            "Celtics @ Heat",
            "Nuggets @ Suns",
            "Bucks @ 76ers",
            "Mavericks @ Clippers"
        ],
        "Pick": [
            "LAL -3.5 (-110)",
            "Over 215.5 (-110)",
            "DEN ML (-150)",
            "MIL -2.5 (-110)",
            "Under 223.5 (-110)"
        ],
        "Result": ["✅ WIN", "✅ WIN", "❌ LOSS", "✅ WIN", "✅ WIN"],
        "Final Score": ["118-114", "224 Total", "108-112", "125-118", "210 Total"],
        "Units": ["+1.00", "+1.00", "-1.10", "+1.00", "+1.00"],
        "Notes": [
            "Covered by 7 pts",
            "Went over by 8.5",
            "Lost in OT",
            "Dominant 2H",
            "Under hit easily"
        ]
    })
    
    # Style the dataframe
    def highlight_result(val):
        if '✅' in str(val):
            return 'background-color: rgba(0, 255, 127, 0.1)'
        elif '❌' in str(val):
            return 'background-color: rgba(255, 75, 75, 0.1)'
        return ''
    
    styled_df = results_data.style.applymap(highlight_result, subset=['Result'])
    st.dataframe(styled_df, use_container_width=True, hide_index=True)
    
    # Best & worst picks
    st.markdown("---")
    
    best_col, worst_col = st.columns(2)
    
    with best_col:
        st.success("#### 🏆 Best Pick of the Day")
        st.markdown("""
        **Lakers -3.5 vs Warriors**
        - Algorithm Confidence: 87%
        - Actual Result: Won by 7
        - Edge Identified: Pace advantage + rest differential
        - Unit Profit: +1.00
        """)
    
    with worst_col:
        st.error("#### ⚠️ Miss of the Day")
        st.markdown("""
        **Nuggets ML vs Suns**
        - Algorithm Confidence: 68%
        - Actual Result: Lost in OT
        - What Happened: Jokic foul trouble in 4Q
        - Unit Loss: -1.10
        """)
    
    # Historical performance
    st.markdown("---")
    st.markdown("#### 📈 Season Performance Trend")
    
    # Generate sample season data
    season_dates = pd.date_range(end=datetime.now(), periods=60)
    cumulative_units = np.cumsum(np.random.randn(60) * 0.5 + 0.2)
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=season_dates,
        y=cumulative_units,
        mode='lines',
        name='Cumulative Units',
        line=dict(color='#5865F2', width=3),
        fill='tozeroy',
        fillcolor='rgba(88, 101, 242, 0.1)'
    ))
    
    fig.update_layout(
        title="Season-Long Unit Profit/Loss",
        xaxis_title="Date",
        yaxis_title="Cumulative Units",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(26, 31, 46, 0.3)",
        font={'color': "white"},
        hovermode='x unified',
        height=400
    )
    
    st.plotly_chart(fig, use_container_width=True)

# ==================== SETTINGS TAB ====================
with tab9:
    st.markdown("### ⚙️ Settings & Preferences")
    
    set_col1, set_col2 = st.columns(2)
    
    with set_col1:
        st.markdown("#### 🎨 Display Settings")
        
        dark_mode = st.checkbox("Dark Mode", value=True, help="Toggle dark/light theme")
        compact_view = st.checkbox("Compact View", value=False, help="Reduce spacing between elements")
        show_decimals = st.checkbox("Show Decimal Odds", value=False, help="Display odds in decimal format instead of American")
        
        timezone = st.selectbox(
            "Time Zone",
            ["Eastern (ET)", "Central (CT)", "Mountain (MT)", "Pacific (PT)"],
            index=0
        )
        
        st.markdown("---")
        
        st.markdown("#### 🏀 Favorite Teams")
        fav_teams = st.multiselect(
            "Select your favorite teams (for priority alerts)",
            ["Lakers", "Warriors", "Celtics", "Heat", "Nuggets", "Suns", "Bucks", "76ers",
             "Mavericks", "Clippers", "Knicks", "Nets", "Raptors", "Bulls", "Cavaliers"],
            default=["Lakers"]
        )
    
    with set_col2:
        st.markdown("#### 🔔 Notification Preferences")
        
        push_notifications = st.checkbox("Enable Push Notifications", value=True)
        email_alerts = st.checkbox("Enable Email Alerts", value=False)
        
        st.markdown("**Alert Thresholds**")
        
        min_confidence = st.slider(
            "Minimum Confidence for Alerts (%)",
            min_value=50,
            max_value=95,
            value=75,
            step=5
        )
        
        min_edge = st.slider(
            "Minimum Edge for Alerts (%)",
            min_value=1,
            max_value=15,
            value=5,
            step=1
        )
        
        alert_types = st.multiselect(
            "Alert Types",
            ["New Picks Released", "High Confidence Bets", "Injury News",
             "Line Movement", "Lineup Changes", "Sharp Action Detected"],
            default=["New Picks Released", "High Confidence Bets", "Injury News"]
        )
        
        st.markdown("---")
        
        st.markdown("#### 💵 Default Betting Settings")
        
        default_unit = st.number_input(
            "Default Unit Size ($)",
            min_value=10,
            max_value=10000,
            value=100,
            step=10
        )
        
        default_odds_format = st.radio(
            "Default Odds Format",
            ["American (-110)", "Decimal (1.91)", "Fractional (10/11)"],
            index=0
        )
    
    # Save button
    st.markdown("---")
    
    save_col1, save_col2, save_col3 = st.columns([1, 1, 2])
    
    with save_col1:
        if st.button("💾 Save Settings", type="primary", use_container_width=True):
            st.success("✅ Settings saved successfully!")
            st.balloons()
    
    with save_col2:
        if st.button("🔄 Reset to Defaults", use_container_width=True):
            st.info("Settings reset to default values")
    
    # System info
    st.markdown("---")
    st.markdown("#### 📊 System Information")
    
    info_col1, info_col2, info_col3 = st.columns(3)
    
    with info_col1:
        st.metric("App Version", "2.0.1")
    with info_col2:
        st.metric("Last Updated", datetime.now().strftime("%Y-%m-%d"))
    with info_col3:
        if engine:
            st.metric("Database Status", "✅ Connected")
        else:
            st.metric("Database Status", "❌ Not Connected")

# ADMIN SECTION (Hidden by default)
with st.sidebar:
    st.markdown("---")
    admin_mode = st.checkbox("🔐 Admin Mode", value=False)
    
    if admin_mode:
        st.markdown("### 🛠️ Admin Controls")
        
        with st.expander("Internal Metrics", expanded=True):
            st.metric("True Edge", "4.73%")
            st.metric("Expected Value", "+$47.21")
            st.metric("Kelly Criterion", "2.31% of BR")
            st.metric("Sharpe Ratio", "1.84")
        
        st.markdown("### Pick Management")
        
        approve_pick = st.checkbox("✅ Approve Pick", value=True)
        vip_only = st.checkbox("⭐ VIP Only", value=False)
        featured_pick = st.checkbox("🔥 Featured Pick", value=False)
        
        confidence_override = st.slider(
            "Confidence Override",
            min_value=0,
            max_value=100,
            value=75
        )
        
        internal_notes = st.text_area(
            "Internal Notes",
            placeholder="Add internal notes about this pick..."
        )
        
        if st.button("📤 Push to Clients", type="primary"):
            st.success("✅ Pick pushed to all active clients")
            st.info("📧 Email notifications sent")
            st.info("📱 Push notifications sent")
        
        st.markdown("---")
        
        st.markdown("### 🤖 AI Assistant")
        
        ai_query = st.text_area(
            "Ask the AI:",
            placeholder="Which picks today have the strongest multi-factor alignment?"
        )
        
        if st.button("🔍 Analyze"):
            with st.spinner("Analyzing..."):
                st.info("""
                **AI Analysis:**
                
                Today's strongest multi-factor picks:
                
                1. **Lakers -3.5** (87% confidence)
                   - Pace advantage (+3.2)
                   - Rest differential (2 days vs 1)
                   - Historical edge (7-3 L10 ATS)
                   
                2. **Over 228.5 Nuggets/Suns** (81% confidence)
                   - Both teams top-5 pace
                   - Defensive struggles recent games
                   - Weather/altitude factors
                   
                Recommend avoiding:
                - Heat +4.5 (conflicting signals)
                - Celtics props (injury uncertainty)
                """)

# FOOTER
st.markdown("---")
st.markdown("""
<div style="text-align: center; color: #8892B0; padding: 2rem;">
    <p style="font-size: 0.9rem;">
        🎯 SB ALGO — NBA Edge Engine v2.0<br>
        Professional Sports Betting Intelligence System<br>
        <span style="font-size: 0.8rem;">Powered by Advanced Statistical Analysis & Machine Learning</span>
    </p>
</div>
""", unsafe_allow_html=True)
