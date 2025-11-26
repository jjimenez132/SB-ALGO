import streamlit as st
from sqlalchemy import create_engine, text
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

st.set_page_config(page_title="NBA Algo", page_icon="🏀", layout="wide")

DATABASE_URL = 'postgresql://sb_algo_db_user:0HDtYp4EY2Lo5At8iyf44PD1zDioSPK7@dpg-d495uhchg0os738l1a50-a.virginia-postgres.render.com/sb_algo_db?sslmode=require'
engine = create_engine(DATABASE_URL)

st.title("🏀 NBA BETTING ALGORITHM")
st.caption(f"Last Update: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

# Create tabs
tab1, tab2, tab3, tab4 = st.tabs(["📊 Today's Picks", "📈 Analysis", "💰 Performance", "⚙️ Settings"])

with tab1:
    st.header("Today's Games Analysis")
    
    with engine.connect() as conn:
        # Get today's games with 0-0 scores (not played yet)
        today = datetime.now().date()
        games_today = conn.execute(text("""
            SELECT visitor_team, home_team 
            FROM games 
            WHERE date = :today AND visitor_pts = 0 AND home_pts = 0
        """), {"today": today}).fetchall()
        
        if games_today:
            st.success(f"Found {len(games_today)} games scheduled for today")
            
            for game in games_today:
                visitor, home = game
                
                col1, col2, col3 = st.columns([2, 2, 1])
                
                with col1:
                    st.subheader(f"{visitor} @ {home}")
                
                # Get last 10 games for each team
                visitor_stats = conn.execute(text("""
                    SELECT 
                        AVG(CASE WHEN visitor_team = :team THEN visitor_pts 
                                 WHEN home_team = :team THEN home_pts END) as avg_pts,
                        AVG(CASE WHEN visitor_team = :team THEN home_pts 
                                 WHEN home_team = :team THEN visitor_pts END) as avg_allowed,
                        COUNT(*) as games_played,
                        SUM(CASE WHEN (visitor_team = :team AND visitor_pts > home_pts) OR 
                                      (home_team = :team AND home_pts > visitor_pts) THEN 1 ELSE 0 END) as wins
                    FROM games 
                    WHERE (visitor_team = :team OR home_team = :team) 
                    AND date > :cutoff
                    AND visitor_pts > 0
                """), {"team": visitor, "cutoff": today - timedelta(days=30)}).fetchone()
                
                home_stats = conn.execute(text("""
                    SELECT 
                        AVG(CASE WHEN visitor_team = :team THEN visitor_pts 
                                 WHEN home_team = :team THEN home_pts END) as avg_pts,
                        AVG(CASE WHEN visitor_team = :team THEN home_pts 
                                 WHEN home_team = :team THEN visitor_pts END) as avg_allowed,
                        COUNT(*) as games_played,
                        SUM(CASE WHEN (visitor_team = :team AND visitor_pts > home_pts) OR 
                                      (home_team = :team AND home_pts > visitor_pts) THEN 1 ELSE 0 END) as wins
                    FROM games 
                    WHERE (visitor_team = :team OR home_team = :team) 
                    AND date > :cutoff
                    AND visitor_pts > 0
                """), {"team": home, "cutoff": today - timedelta(days=30)}).fetchone()
                
                with col2:
                    if visitor_stats[0]:
                        visitor_avg = visitor_stats[0]
                        home_avg = home_stats[0] if home_stats[0] else 110
                        
                        # Simple prediction
                        visitor_proj = (visitor_avg + home_stats[1])/2 if home_stats[1] else visitor_avg
                        home_proj = (home_avg + visitor_stats[1])/2 if visitor_stats[1] else home_avg
                        total_proj = visitor_proj + home_proj
                        
                        st.metric("Projected Total", f"{total_proj:.1f}")
                        st.caption(f"{visitor}: {visitor_proj:.1f} | {home}: {home_proj:.1f}")
                
                with col3:
                    if visitor_stats[0] and home_stats[0]:
                        if home_proj > visitor_proj + 3:
                            pick = f"{home} -3.5"
                            confidence = "HIGH" if (home_proj - visitor_proj) > 7 else "MEDIUM"
                        elif visitor_proj > home_proj:
                            pick = f"{visitor} +3.5"
                            confidence = "HIGH" if (visitor_proj - home_proj) > 5 else "MEDIUM"
                        else:
                            pick = "PASS"
                            confidence = "LOW"
                        
                        if confidence == "HIGH":
                            st.success(f"🎯 {pick}")
                        elif confidence == "MEDIUM":
                            st.warning(f"📊 {pick}")
                        else:
                            st.info("↔️ No Edge")
                
                st.divider()
        else:
            st.info("No games scheduled for today. Add today's games using add_todays_games.py")

with tab2:
    st.header("Historical Analysis")
    
    # Date range selector
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("From", datetime.now() - timedelta(days=30))
    with col2:
        end_date = st.date_input("To", datetime.now())
    
    with engine.connect() as conn:
        games_data = conn.execute(text("""
            SELECT date, COUNT(*) as games, 
                   AVG(visitor_pts + home_pts) as avg_total,
                   AVG(ABS(home_pts - visitor_pts)) as avg_margin
            FROM games 
            WHERE date BETWEEN :start AND :end
            AND visitor_pts > 0
            GROUP BY date
            ORDER BY date DESC
        """), {"start": start_date, "end": end_date}).fetchall()
        
        if games_data:
            df = pd.DataFrame(games_data, columns=['Date', 'Games', 'Avg Total', 'Avg Margin'])
            
            # Display metrics
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Avg Total Points", f"{df['Avg Total'].mean():.1f}")
            with col2:
                st.metric("Avg Victory Margin", f"{df['Avg Margin'].mean():.1f}")
            with col3:
                st.metric("Total Games", f"{df['Games'].sum():.0f}")
            
            # Show data
            st.dataframe(df, use_container_width=True)
            
            # Chart
            st.line_chart(df.set_index('Date')['Avg Total'])

with tab3:
    st.header("Algorithm Performance")
    
    # Placeholder for when you start tracking bets
    st.info("Performance tracking will be available once you start logging your bets")
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Win Rate", "Pending")
    with col2:
        st.metric("ROI", "Pending")
    with col3:
        st.metric("Units Won", "Pending")
    with col4:
        st.metric("Streak", "Pending")

with tab4:
    st.header("Settings & Configuration")
    
    st.subheader("Betting Parameters")
    
    col1, col2 = st.columns(2)
    with col1:
        unit_size = st.slider("Unit Size ($)", 10, 500, 100, 10)
        confidence_threshold = st.slider("Min Confidence (%)", 50, 90, 70, 5)
    
    with col2:
        max_bets = st.slider("Max Bets Per Day", 1, 10, 3)
        bankroll = st.number_input("Current Bankroll ($)", 100, 100000, 5000, 100)
    
    if st.button("Save Settings"):
        st.success("Settings saved!")
    
    st.divider()
    
    st.subheader("Quick Actions")
    
    if st.button("🔄 Refresh Data"):
        st.rerun()
    
    st.info("Remember to run manual_input.py each morning to update yesterday's results")
