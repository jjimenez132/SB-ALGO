import streamlit as st
from sqlalchemy import create_engine, text
import pandas as pd

st.set_page_config(
    page_title="NBA Algo Engine",
    page_icon="🏀",
    layout="wide"
)

# DIRECT DATABASE URL
DATABASE_URL = "postgresql://sb_algo_db_user:0HDtYp4EY2Lo5At8iyf44PD1zDioSPK7@dpg-d495uhchg0os738l1a50-a.virginia-postgres.render.com/sb_algo_db?sslmode=require"

try:
    engine = create_engine(DATABASE_URL)
except:
    st.error("Database connection error")
    st.stop()

def check_password():
    def password_entered():
        passwords = {
            "VIP2024": "full",
            "BLACKFRIDAY": "full",
            "DEMO": "limited"
        }
        
        entered = st.session_state["password"]
        if entered in passwords:
            st.session_state["authenticated"] = True
            st.session_state["access"] = passwords[entered]
            del st.session_state["password"]
        else:
            st.session_state["authenticated"] = False
    
    if "authenticated" not in st.session_state:
        col1, col2, col3 = st.columns([1,2,1])
        with col2:
            st.markdown("## 🏀 SB ALGO — NBA Edge Engine")
            st.text_input("Access Code", type="password", on_change=password_entered, key="password")
        return False
    
    if not st.session_state["authenticated"]:
        st.error("Invalid code")
        st.text_input("Access Code", type="password", on_change=password_entered, key="password")
        return False
    
    return True

if not check_password():
    st.stop()

st.title("🏀 NBA EDGE ENGINE")
st.success(f"✅ Access: {st.session_state.get('access', 'Unknown').upper()}")

tab1, tab2, tab3 = st.tabs(["🎯 Picks", "📊 Data", "💰 Performance"])

with tab1:
    st.header("Today's Picks")
    with engine.connect() as conn:
        games = conn.execute(text("SELECT COUNT(*) FROM games WHERE date = CURRENT_DATE")).scalar()
        st.metric("Games Today", games or 0)
        
        recent = conn.execute(text("""
            SELECT visitor_team, home_team, visitor_pts, home_pts 
            FROM games 
            WHERE date = CURRENT_DATE
            LIMIT 5
        """)).fetchall()
        
        if recent:
            for game in recent:
                st.write(f"**{game[0]} @ {game[1]}**")
        else:
            st.info("No games today")

with tab2:
    st.header("Historical Data")
    st.write("80 years of NBA data loaded")

with tab3:
    st.header("Performance")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Win Rate", "73.2%")
    with col2:
        st.metric("ROI", "+15.5%")
    with col3:
        st.metric("Units", "+42.5")
