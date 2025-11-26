import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

# PAGE CONFIG
st.set_page_config(
    page_title="NBA Algo Engine",
    page_icon="🎯",
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
</style>
""", unsafe_allow_html=True)

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
        🎯 NBA ALGO ENGINE
    </h1>
    <p style="color: rgba(255,255,255,0.9); margin-top: 0.5rem; font-size: 1.1rem;">
        Professional Basketball Betting Intelligence
    </p>
</div>
""", unsafe_allow_html=True)

# MAIN NAVIGATION TABS
main_tab1, main_tab2, main_tab3, main_tab4, main_tab5, main_tab6, main_tab7, main_tab8, main_tab9 = st.tabs([
    "🏠 Dashboard",
    "🎲 Today's Games", 
    "🧠 Props Engine",
    "📈 Trends",
    "💰 Bankroll",
    "📰 News & Injuries",
    "📂 Data Explorer",
    "📊 Reports",
    "⚙️ Settings"
])

# ==================== DASHBOARD TAB ====================
with main_tab1:
    # Top metrics row
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.metric(
            label="Games Today",
            value="12",
            delta="NBA Slate"
        )
    
    with col2:
        st.metric(
            label="Edges Found",
            value="7",
            delta="+2 vs avg"
        )
    
    with col3:
        st.metric(
            label="Confidence",
            value="82%",
            delta="+15%"
        )
    
    with col4:
        st.metric(
            label="Best Play",
            value="LAL -3.5",
            delta="87% edge"
        )
    
    with col5:
        st.metric(
            label="System Status",
            value="LIVE",
            delta="All systems go"
        )
    
    st.markdown("---")
    
    # Betting category selector
    bet_type = st.radio(
        "Select Bet Type",
        ["🎯 All Picks", "💵 Moneyline", "📊 Spread", "📈 Totals", "⭐ Player Props"],
        horizontal=True,
        label_visibility="collapsed"
    )
    
    # Today's games feed
    st.subheader("🔥 Today's Algorithm Picks")
    
    # Sample game cards
    for i in range(3):
        with st.container():
            col1, col2, col3, col4 = st.columns([3, 2, 2, 1])
            
            with col1:
                st.markdown(f"""
                <div style="
                    background: rgba(26, 31, 46, 0.8);
                    padding: 1.5rem;
                    border-radius: 12px;
                    border-left: 4px solid #5865F2;
                ">
                    <h3 style="margin: 0; color: white;">Lakers @ Warriors</h3>
                    <p style="color: #8892B0; margin: 0.5rem 0;">10:00 PM ET • Chase Center</p>
                </div>
                """, unsafe_allow_html=True)
            
            with col2:
                st.markdown("**Algo Projection**")
                st.caption("LAL: 118.5 | GSW: 114.2")
                st.progress(0.73, text="73% confidence")
            
            with col3:
                st.markdown("**Recommended Bet**")
                st.success("Lakers -3.5 (-110)")
                st.caption("Edge: +4.7% EV")
            
            with col4:
                if st.button("Full Analysis", key=f"game_{i}"):
                    st.info("→ Game detail page")
        
        st.markdown("---")

# ==================== TODAY'S GAMES TAB ====================
with main_tab2:
    st.subheader("🏀 Complete Game Analysis")
    
    # Game selector
    selected_game = st.selectbox(
        "Select Game",
        ["Lakers @ Warriors", "Celtics @ Heat", "Nuggets @ Suns"],
        label_visibility="collapsed"
    )
    
    # Game detail layout
    gcol1, gcol2 = st.columns([2, 1])
    
    with gcol1:
        # Score prediction box
        st.markdown("""
        <div style="
            background: linear-gradient(135deg, rgba(88, 101, 242, 0.1), rgba(124, 58, 237, 0.1));
            padding: 2rem;
            border-radius: 16px;
            border: 1px solid rgba(88, 101, 242, 0.3);
            text-align: center;
        ">
            <h2 style="color: white;">Predicted Final Score</h2>
            <div style="display: flex; justify-content: space-around; margin-top: 1rem;">
                <div>
                    <h1 style="color: #5865F2; font-size: 3rem;">118</h1>
                    <p style="color: #8892B0;">Lakers</p>
                </div>
                <div style="align-self: center;">
                    <h2 style="color: #8892B0;">vs</h2>
                </div>
                <div>
                    <h1 style="color: #7C3AED; font-size: 3rem;">114</h1>
                    <p style="color: #8892B0;">Warriors</p>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # Key factors
        st.markdown("### 🔑 Key Factors")
        
        factor_col1, factor_col2 = st.columns(2)
        with factor_col1:
            st.info("**Pace Advantage**: Lakers +3.2")
            st.warning("**Injury Impact**: Curry questionable")
        with factor_col2:
            st.success("**Historical Edge**: 7-3 L10 ATS")
            st.info("**Rest Days**: LAL (2) vs GSW (1)")
    
    with gcol2:
        # Win probability gauge
        fig = go.Figure(go.Indicator(
            mode="gauge+number",
            value=68,
            title={'text': "Win Probability"},
            gauge={'axis': {'range': [0, 100]},
                   'bar': {'color': "#5865F2"},
                   'steps': [
                       {'range': [0, 50], 'color': "rgba(255, 255, 255, 0.05)"},
                       {'range': [50, 100], 'color': "rgba(88, 101, 242, 0.1)"}],
                   'threshold': {'line': {'color': "red", 'width': 4},
                                'thickness': 0.75, 'value': 90}}
        ))
        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font={'color': "white"},
            height=250
        )
        st.plotly_chart(fig, use_container_width=True)
        
        # Confidence breakdown
        st.markdown("### 📊 Confidence Factors")
        st.progress(0.85, text="Matchup Model: 85%")
        st.progress(0.72, text="Recent Form: 72%")
        st.progress(0.91, text="Pace Analysis: 91%")
        st.progress(0.65, text="Injury Adjusted: 65%")

# ==================== PROPS ENGINE TAB ====================
with main_tab3:
    st.subheader("⭐ Player Props Intelligence")
    
    # Search and filters
    pcol1, pcol2, pcol3 = st.columns([2, 1, 1])
    
    with pcol1:
        player_search = st.text_input("🔍 Search Player", placeholder="LeBron James...")
    
    with pcol2:
        prop_type = st.selectbox(
            "Prop Type",
            ["All Props", "Points", "Rebounds", "Assists", "PRA", "3-Pointers", "Steals", "Blocks"]
        )
    
    with pcol3:
        confidence_filter = st.select_slider(
            "Min Confidence",
            options=["All", "60%+", "70%+", "80%+", "90%+"],
            value="70%+"
        )
    
    # Props cards
    st.markdown("---")
    
    for i in range(3):
        with st.container():
            prop_col1, prop_col2, prop_col3 = st.columns([2, 2, 1])
            
            with prop_col1:
                st.markdown(f"""
                <div style="padding: 1rem; background: rgba(26, 31, 46, 0.6); border-radius: 12px;">
                    <h4 style="color: white; margin: 0;">LeBron James - Points</h4>
                    <p style="color: #8892B0;">Lakers vs Warriors</p>
                    <div style="display: flex; gap: 1rem; margin-top: 1rem;">
                        <span style="color: #5865F2;">🔥 Hit 7 of last 10</span>
                        <span style="color: #7C3AED;">📈 Trending up</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)
            
            with prop_col2:
                met_col1, met_col2, met_col3 = st.columns(3)
                with met_col1:
                    st.metric("Line", "27.5", delta="O/U")
                with met_col2:
                    st.metric("Projection", "31.2", delta="+3.7")
                with met_col3:
                    st.metric("Edge", "13.5%", delta="+++")
            
            with prop_col3:
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button(f"🎯 BET OVER", key=f"prop_{i}", type="primary"):
                    st.success("Added to slip")
        
        st.markdown("---")

# ==================== TRENDS TAB ====================
with main_tab4:
    st.subheader("📈 Trends & Pattern Recognition")
    
    trend_tab1, trend_tab2, trend_tab3 = st.tabs(["Team Trends", "Player Streaks", "Market Inefficiencies"])
    
    with trend_tab1:
        # Team performance heatmap
        st.markdown("### 🔥 Team Performance Matrix (Last 10 Games)")
        
        # Sample heatmap data
        teams = ["Lakers", "Warriors", "Celtics", "Heat", "Nuggets"]
        metrics = ["ATS", "O/U", "ML", "1H", "2H"]
        data = np.random.rand(5, 5)
        
        fig = px.imshow(
            data,
            labels=dict(x="Metric", y="Team", color="Win Rate"),
            x=metrics,
            y=teams,
            color_continuous_scale="Viridis"
        )
        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font={'color': "white"}
        )
        st.plotly_chart(fig, use_container_width=True)
    
    with trend_tab2:
        st.markdown("### 📊 Active Player Streaks")
        
        streak_data = {
            "Player": ["LeBron James", "Stephen Curry", "Jayson Tatum"],
            "Stat": ["Points O25.5", "3PM O4.5", "Rebounds O8.5"],
            "Current": ["8 games", "5 games", "6 games"],
            "Success": ["80%", "83%", "67%"],
            "Status": ["🔥 HOT", "🔥 HOT", "📈 WARM"]
        }
        st.dataframe(streak_data, use_container_width=True)
    
    with trend_tab3:
        st.markdown("### 🎯 Market Bias Detection")
        st.info("**Public Heavy**: Lakers -3.5 (87% of bets, line moved from -2.5)")
        st.warning("**Reverse Line Movement**: Celtics +4.5 (35% bets but line moved from +5.5)")
        st.success("**Sharp Action Detected**: Under 218.5 Nuggets/Suns")

# ==================== BANKROLL TAB ====================
with main_tab5:
    st.subheader("💰 Bankroll Management System")
    
    bcol1, bcol2 = st.columns([1, 2])
    
    with bcol1:
        bankroll = st.number_input("Current Bankroll ($)", value=10000, step=1000)
        
        risk_profile = st.select_slider(
            "Risk Profile",
            options=["Conservative", "Standard", "Aggressive"],
            value="Standard"
        )
        
        unit_sizes = {"Conservative": 1, "Standard": 2, "Aggressive": 3}
        unit_size = bankroll * (unit_sizes[risk_profile] / 100)
        
        st.metric("Recommended Unit Size", f"${unit_size:.0f}")
        st.metric("Max Daily Risk", f"${unit_size * 3:.0f}")
        
        # Risk meter
        risk_value = {"Conservative": 25, "Standard": 50, "Aggressive": 75}[risk_profile]
        st.progress(risk_value / 100, text=f"Risk Level: {risk_value}%")
    
    with bcol2:
        # Bankroll chart
        dates = pd.date_range(end=datetime.now(), periods=30)
        bankroll_history = np.cumsum(np.random.randn(30) * 200) + bankroll
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=dates,
            y=bankroll_history,
            mode='lines',
            line=dict(color='#5865F2', width=3),
            fill='tozeroy',
            fillcolor='rgba(88, 101, 242, 0.1)'
        ))
        fig.update_layout(
            title="30-Day Bankroll Trend",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font={'color': "white"},
            showlegend=False,
            height=400
        )
        st.plotly_chart(fig, use_container_width=True)

# ==================== NEWS & INJURIES TAB ====================
with main_tab6:
    st.subheader("📰 Real-Time News & Injury Monitor")
    
    news_col1, news_col2 = st.columns([2, 1])
    
    with news_col1:
        st.markdown("### 📢 Latest Impact News")
        
        # News cards
        news_items = [
            {"time": "2 min ago", "tag": "INJURY", "text": "Curry upgraded to PROBABLE vs Lakers", "impact": "HIGH"},
            {"time": "15 min ago", "tag": "REST", "text": "Embiid sitting B2B vs Celtics", "impact": "HIGH"},
            {"time": "1 hour ago", "tag": "TRADE", "text": "Wizards trade Poole to Spurs", "impact": "MEDIUM"},
        ]
        
        for item in news_items:
            impact_color = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢"}[item["impact"]]
            st.markdown(f"""
            <div style="
                background: rgba(26, 31, 46, 0.6);
                padding: 1rem;
                border-radius: 8px;
                margin-bottom: 0.5rem;
                border-left: 3px solid {'#FF4444' if item['impact']=='HIGH' else '#FFD700'};
            ">
                <div style="display: flex; justify-content: space-between;">
                    <span style="color: #8892B0; font-size: 0.9rem;">{item['time']}</span>
                    <span style="background: rgba(88, 101, 242, 0.2); padding: 0.2rem 0.5rem; border-radius: 4px;">
                        {item['tag']}
                    </span>
                </div>
                <p style="color: white; margin: 0.5rem 0;">{item['text']}</p>
                <span>{impact_color} {item['impact']} IMPACT</span>
            </div>
            """, unsafe_allow_html=True)
    
    with news_col2:
        st.markdown("### 🏥 Injury Report")
        
        # Team filter
        team_filter = st.selectbox("Filter by Team", ["All Teams", "Lakers", "Warriors", "Celtics"])
        
        # Injury list
        injuries = {
            "OUT": ["Anthony Davis (LAL)", "Kawhi Leonard (LAC)"],
            "QUESTIONABLE": ["Stephen Curry (GSW)", "Jimmy Butler (MIA)"],
            "PROBABLE": ["LeBron James (LAL)", "Kevin Durant (PHX)"]
        }
        
        for status, players in injuries.items():
            status_color = {"OUT": "🔴", "QUESTIONABLE": "🟡", "PROBABLE": "🟢"}[status]
            st.markdown(f"**{status_color} {status}**")
            for player in players:
                st.caption(f"  • {player}")

# ==================== DATA EXPLORER TAB ====================
with main_tab7:
    st.subheader("📂 Advanced Data Explorer")
    
    # Filters row
    dcol1, dcol2, dcol3, dcol4 = st.columns(4)
    
    with dcol1:
        season_select = st.selectbox("Season", ["2024-25", "2023-24", "2022-23"])
    
    with dcol2:
        team_select = st.selectbox("Team", ["All Teams", "Lakers", "Warriors", "Celtics"])
    
    with dcol3:
        player_select = st.selectbox("Player", ["All Players", "LeBron James", "Stephen Curry"])
    
    with dcol4:
        metric_select = st.selectbox("Metric", ["Points", "ORtg", "DRtg", "Pace", "eFG%"])
    
    data_tab1, data_tab2, data_tab3 = st.tabs(["Team Stats", "Player Stats", "Game Logs"])
    
    with data_tab1:
        st.markdown("### Team Statistical Overview")
        # Placeholder for team stats table
        team_stats = pd.DataFrame({
            "Team": ["Lakers", "Warriors", "Celtics", "Heat", "Nuggets"],
            "W-L": ["15-8", "14-9", "18-5", "12-11", "16-7"],
            "ATS": ["13-10", "11-12", "15-8", "10-13", "14-9"],
            "O/U": ["12-11", "14-9", "11-12", "13-10", "15-8"],
            "Pace": [101.2, 98.5, 99.8, 97.2, 100.5],
            "ORtg": [118.5, 116.2, 119.8, 112.3, 117.9]
        })
        st.dataframe(team_stats, use_container_width=True)
    
    with data_tab2:
        st.markdown("### Player Performance Metrics")
        # Placeholder for player stats
        st.info("Select a player to view detailed statistics")
    
    with data_tab3:
        st.markdown("### Recent Game History")
        # Placeholder for game logs
        st.info("Select team/player to view game logs")

# ==================== REPORTS TAB ====================
with main_tab8:
    st.subheader("📊 Daily Performance Reports")
    
    # Yesterday's summary
    st.markdown("### Yesterday's Results")
    
    rcol1, rcol2, rcol3, rcol4 = st.columns(4)
    
    with rcol1:
        st.metric("Overall", "5-2", delta="+3 units")
    with rcol2:
        st.metric("Spreads", "3-1", delta="+1.9 units")
    with rcol3:
        st.metric("Totals", "2-1", delta="+0.9 units")
    with rcol4:
        st.metric("Props", "4-2", delta="+1.8 units")
    
    st.markdown("---")
    
    # Detailed breakdown
    st.markdown("### 📝 Detailed Breakdown")
    
    results_data = {
        "Game": ["LAL @ GSW", "BOS @ MIA", "DEN @ PHX"],
        "Pick": ["LAL -3.5", "Over 215.5", "DEN ML"],
        "Result": ["✅ WIN", "✅ WIN", "❌ LOSS"],
        "Units": ["+1.0", "+1.0", "-1.1"],
        "Notes": ["Covered by 7", "Went over by 8.5", "Lost in OT"]
    }
    
    st.dataframe(results_data, use_container_width=True)

# ==================== SETTINGS TAB ====================
with main_tab9:
    st.subheader("⚙️ Settings & Preferences")
    
    set_col1, set_col2 = st.columns(2)
    
    with set_col1:
        st.markdown("### Display Settings")
        
        dark_mode = st.checkbox("Dark Mode", value=True)
        compact_view = st.checkbox("Compact View", value=False)
        show_decimals = st.checkbox("Show Decimal Odds", value=False)
        timezone = st.selectbox("Time Zone", ["ET", "CT", "MT", "PT"])
    
    with set_col2:
        st.markdown("### Notification Preferences")
        
        push_notifications = st.checkbox("Push Notifications", value=True)
        email_alerts = st.checkbox("Email Alerts", value=False)
        high_confidence_only = st.checkbox("High Confidence Picks Only", value=False)
        
        st.markdown("### Default Settings")
        default_unit = st.number_input("Default Unit Size ($)", value=100, step=10)
        
    if st.button("Save Settings", type="primary"):
        st.success("✅ Settings saved successfully!")

# ADMIN SECTION (hidden unless logged in as admin)
if st.sidebar.checkbox("🔐 Admin Mode", value=False):
    st.sidebar.markdown("### Admin Controls")
    
    with st.sidebar.expander("Internal Metrics"):
        st.metric("True Edge", "4.7%")
        st.metric("Expected Value", "+$47")
        st.metric("Kelly Criterion", "2.3% of BR")
    
    st.sidebar.markdown("### Pick Management")
    approve_pick = st.sidebar.checkbox("Approve Pick", value=True)
    vip_only = st.sidebar.checkbox("VIP Only", value=False)
    
    st.sidebar.text_area("Internal Notes", placeholder="Add notes...")
    
    if st.sidebar.button("Push to Clients"):
        st.sidebar.success("Pushed to all clients")
