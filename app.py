import streamlit as st
import os
from sqlalchemy import create_engine, text
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

st.set_page_config(
    page_title="NBA Algo Engine",
    page_icon="🎯",
    layout="wide"
)

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://sb_algo_db_user:0HDtYp4EY2Lo5At8iyf44PD1zDioSPK7@dpg-d495uhchg0os738l1a50-a.virginia-postgres.render.com/sb_algo_db?sslmode=require")
engine = create_engine(DATABASE_URL)

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
        st.text_input("Access Code", type="password", on_change=password_entered, key="password")
        return False
    
    if not st.session_state["authenticated"]:
        st.error("Invalid code")
        st.text_input("Access Code", type="password", on_change=password_entered, key="password")
        return False
    
    return True

if not check_password():
    st.stop()

st.title("🎯 NBA ALGO ENGINE")
st.success(f"Access Level: {st.session_state.get("access", "Unknown")}")

tab1, tab2, tab3 = st.tabs(["🏀 Today Games", "📊 Analysis", "💰 Performance"])

with tab1:
    st.header("Today Games")
    st.info("Loading games...")

with tab2:
    st.header("Analysis")
    st.info("Coming soon")

with tab3:
    st.header("Performance")
    st.metric("Win Rate", "73.2%")
