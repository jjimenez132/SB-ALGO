# ========================================
# TAB 4 - TRENDS & PATTERNS - WITH REAL DATA
# Replace your entire "with tab4:" section with this
# ========================================

with tab4:
    # Header
    st.markdown("""
    <div style="text-align: center; padding: 1rem 0 0.5rem 0;">
        <h1 style="margin-bottom: 0.2rem;">📈 Trends & Patterns</h1>
        <p style="color: #a0aec0; font-size: 1rem; margin-bottom: 0.5rem;">Analyze team trends, player patterns, and prop-related performance indicators.</p>
        <div style="height: 3px; background: linear-gradient(90deg, #667eea 0%, #764ba2 100%); border-radius: 2px; max-width: 400px; margin: 0 auto;"></div>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # Trend Type Selector
    st.markdown("""
    <div style="
        background: rgba(102, 126, 234, 0.08);
        border: 1px solid rgba(102, 126, 234, 0.25);
        border-radius: 12px;
        padding: 1.2rem 1.5rem;
        margin-bottom: 1.5rem;
        box-shadow: 0 0 20px rgba(102, 126, 234, 0.1);
    ">
        <p style="color: #667eea; font-weight: 600; margin-bottom: 0.8rem; font-size: 0.9rem;">🎛️ SELECT TREND VIEW</p>
    </div>
    """, unsafe_allow_html=True)
    
    trend_type = st.selectbox(
        "View Trends For:",
        ["Team Trends", "Player Trends", "Situational Edges"],
        key="trends_selector",
        label_visibility="collapsed"
    )
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    if trend_type == "Team Trends":
        # ========== HOT TEAMS - REAL DATA ==========
        st.markdown("""
        <div style="
            background: linear-gradient(135deg, rgba(239, 68, 68, 0.1) 0%, rgba(251, 191, 36, 0.1) 100%);
            border: 1px solid rgba(239, 68, 68, 0.3);
            border-radius: 12px;
            padding: 1.5rem;
            margin-bottom: 1.5rem;
            box-shadow: 0 4px 20px rgba(239, 68, 68, 0.1);
        ">
            <div style="display: flex; align-items: center; gap: 0.8rem; margin-bottom: 0.5rem;">
                <span style="font-size: 1.5rem;">🔥</span>
                <h3 style="color: #e2e8f0; margin: 0; font-size: 1.2rem;">Hot Teams (Last 30 Days)</h3>
            </div>
            <p style="color: #a0aec0; font-size: 0.85rem; margin: 0;">Teams with the best recent records — real data from your database.</p>
        </div>
        """, unsafe_allow_html=True)
        
        # Fetch REAL hot teams
        hot_teams_df = get_hot_teams(engine, limit=5)
        
        if not hot_teams_df.empty:
            st.dataframe(hot_teams_df, use_container_width=True, hide_index=True)
        else:
            st.info("Loading hot teams data...")
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        # ========== TOTALS TRENDS - REAL DATA ==========
        st.markdown("""
        <div style="
            background: linear-gradient(135deg, rgba(16, 185, 129, 0.1) 0%, rgba(79, 172, 254, 0.1) 100%);
            border: 1px solid rgba(16, 185, 129, 0.3);
            border-radius: 12px;
            padding: 1.5rem;
            margin-bottom: 1.5rem;
            box-shadow: 0 4px 20px rgba(16, 185, 129, 0.1);
        ">
            <div style="display: flex; align-items: center; gap: 0.8rem; margin-bottom: 0.5rem;">
                <span style="font-size: 1.5rem;">💥</span>
                <h3 style="color: #e2e8f0; margin: 0; font-size: 1.2rem;">Totals Trends (Season)</h3>
            </div>
            <p style="color: #a0aec0; font-size: 0.85rem; margin: 0;">Teams sorted by average total points — identify Over/Under trends.</p>
        </div>
        """, unsafe_allow_html=True)
        
        # Fetch REAL totals trends
        totals_df = get_totals_trends(engine, limit=6)
        
        if not totals_df.empty:
            st.dataframe(totals_df, use_container_width=True, hide_index=True)
        else:
            st.info("Loading totals trends...")
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        # ========== COLD TEAMS - REAL DATA ==========
        st.markdown("""
        <div style="
            background: linear-gradient(135deg, rgba(59, 130, 246, 0.1) 0%, rgba(99, 102, 241, 0.1) 100%);
            border: 1px solid rgba(59, 130, 246, 0.3);
            border-radius: 12px;
            padding: 1.5rem;
            margin-bottom: 1.5rem;
            box-shadow: 0 4px 20px rgba(59, 130, 246, 0.1);
        ">
            <div style="display: flex; align-items: center; gap: 0.8rem; margin-bottom: 0.5rem;">
                <span style="font-size: 1.5rem;">❄️</span>
                <h3 style="color: #e2e8f0; margin: 0; font-size: 1.2rem;">Cold Teams (Last 30 Days)</h3>
            </div>
            <p style="color: #a0aec0; font-size: 0.85rem; margin: 0;">Teams in a slump — potential fade opportunities.</p>
        </div>
        """, unsafe_allow_html=True)
        
        # Fetch REAL cold teams
        cold_teams_df = get_cold_teams(engine, limit=5)
        
        if not cold_teams_df.empty:
            st.dataframe(cold_teams_df, use_container_width=True, hide_index=True)
        else:
            st.info("Loading cold teams data...")
    
    elif trend_type == "Player Trends":
        # Player Trends section (keep as placeholder for now - needs player_boxscores analysis)
        st.markdown("""
        <div style="
            background: linear-gradient(135deg, rgba(102, 126, 234, 0.1) 0%, rgba(118, 75, 162, 0.1) 100%);
            border: 1px solid rgba(102, 126, 234, 0.3);
            border-radius: 12px;
            padding: 1.5rem;
            margin-bottom: 1.5rem;
        ">
            <div style="display: flex; align-items: center; gap: 0.8rem; margin-bottom: 0.5rem;">
                <span style="font-size: 1.5rem;">👤</span>
                <h3 style="color: #e2e8f0; margin: 0; font-size: 1.2rem;">Player Performance Trends</h3>
            </div>
            <p style="color: #a0aec0; font-size: 0.85rem; margin: 0;">Track hot and cold players across key stat categories.</p>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("""
        <p style="color: #667eea; font-weight: 600; margin-bottom: 1rem; font-size: 0.9rem;">🔥 HOT PERFORMERS (Last 5-10 Games)</p>
        """, unsafe_allow_html=True)
        
        # Player trend cards
        ptr_col1, ptr_col2, ptr_col3, ptr_col4 = st.columns(4)
        
        with ptr_col1:
            st.markdown("""
            <div style="
                background: linear-gradient(135deg, rgba(239, 68, 68, 0.15) 0%, rgba(239, 68, 68, 0.05) 100%);
                border: 1px solid rgba(239, 68, 68, 0.3);
                border-radius: 12px;
                padding: 1.2rem;
                text-align: center;
                min-height: 160px;
            ">
                <span style="font-size: 1.8rem;">🏀</span>
                <h5 style="color: #ef4444; margin: 0.5rem 0 0.3rem 0; font-size: 0.95rem;">Hot Scorers</h5>
                <p style="color: #a0aec0; font-size: 0.75rem; margin: 0;">Points leaders trending up</p>
                <div style="background: rgba(0, 0, 0, 0.2); border-radius: 6px; padding: 0.6rem; margin-top: 0.8rem;">
                    <p style="color: #718096; font-size: 0.7rem; font-style: italic; margin: 0;">Coming soon</p>
                </div>
            </div>
            """, unsafe_allow_html=True)
        
        with ptr_col2:
            st.markdown("""
            <div style="
                background: linear-gradient(135deg, rgba(16, 185, 129, 0.15) 0%, rgba(16, 185, 129, 0.05) 100%);
                border: 1px solid rgba(16, 185, 129, 0.3);
                border-radius: 12px;
                padding: 1.2rem;
                text-align: center;
                min-height: 160px;
            ">
                <span style="font-size: 1.8rem;">📊</span>
                <h5 style="color: #10b981; margin: 0.5rem 0 0.3rem 0; font-size: 0.95rem;">Hot Rebounders</h5>
                <p style="color: #a0aec0; font-size: 0.75rem; margin: 0;">Board leaders trending up</p>
                <div style="background: rgba(0, 0, 0, 0.2); border-radius: 6px; padding: 0.6rem; margin-top: 0.8rem;">
                    <p style="color: #718096; font-size: 0.7rem; font-style: italic; margin: 0;">Coming soon</p>
                </div>
            </div>
            """, unsafe_allow_html=True)
        
        with ptr_col3:
            st.markdown("""
            <div style="
                background: linear-gradient(135deg, rgba(102, 126, 234, 0.15) 0%, rgba(102, 126, 234, 0.05) 100%);
                border: 1px solid rgba(102, 126, 234, 0.3);
                border-radius: 12px;
                padding: 1.2rem;
                text-align: center;
                min-height: 160px;
            ">
                <span style="font-size: 1.8rem;">🎯</span>
                <h5 style="color: #667eea; margin: 0.5rem 0 0.3rem 0; font-size: 0.95rem;">Hot Assisters</h5>
                <p style="color: #a0aec0; font-size: 0.75rem; margin: 0;">Playmakers trending up</p>
                <div style="background: rgba(0, 0, 0, 0.2); border-radius: 6px; padding: 0.6rem; margin-top: 0.8rem;">
                    <p style="color: #718096; font-size: 0.7rem; font-style: italic; margin: 0;">Coming soon</p>
                </div>
            </div>
            """, unsafe_allow_html=True)
        
        with ptr_col4:
            st.markdown("""
            <div style="
                background: linear-gradient(135deg, rgba(251, 191, 36, 0.15) 0%, rgba(251, 191, 36, 0.05) 100%);
                border: 1px solid rgba(251, 191, 36, 0.3);
                border-radius: 12px;
                padding: 1.2rem;
                text-align: center;
                min-height: 160px;
            ">
                <span style="font-size: 1.8rem;">🎯</span>
                <h5 style="color: #fbbf24; margin: 0.5rem 0 0.3rem 0; font-size: 0.95rem;">Hot 3PT Shooters</h5>
                <p style="color: #a0aec0; font-size: 0.75rem; margin: 0;">Snipers trending up</p>
                <div style="background: rgba(0, 0, 0, 0.2); border-radius: 6px; padding: 0.6rem; margin-top: 0.8rem;">
                    <p style="color: #718096; font-size: 0.7rem; font-style: italic; margin: 0;">Coming soon</p>
                </div>
            </div>
            """, unsafe_allow_html=True)
    
    else:  # Situational Edges
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
            <p style="color: #a0aec0; font-size: 0.85rem; margin: 0;">Rest advantages, B2B fades, and travel fatigue situations.</p>
        </div>
        """, unsafe_allow_html=True)
        
        sit_col1, sit_col2 = st.columns(2)
        
        with sit_col1:
            # Rest advantage - calculated from real data
            st.markdown("""
            <div style="
                background: rgba(15, 20, 35, 0.6);
                border: 1px solid rgba(16, 185, 129, 0.3);
                border-radius: 12px;
                padding: 1.2rem;
                margin-bottom: 1rem;
            ">
                <h5 style="color: #10b981; margin-bottom: 0.8rem; font-size: 0.95rem;">💤 Rest Advantage Today</h5>
            </div>
            """, unsafe_allow_html=True)
            
            # Find games with rest advantage from today's games
            todays_games = get_todays_games(engine)
            rest_advantages = []
            for game in todays_games:
                home_rest = game.get('home_days_rest', 0) or 0
                visitor_rest = game.get('visitor_days_rest', 0) or 0
                if home_rest >= 3 and visitor_rest <= 1:
                    rest_advantages.append(f"✅ {game['home_team']} ({home_rest} days) vs {game['visitor_team']} ({visitor_rest} days)")
                elif visitor_rest >= 3 and home_rest <= 1:
                    rest_advantages.append(f"✅ {game['visitor_team']} ({visitor_rest} days) vs {game['home_team']} ({home_rest} days)")
            
            if rest_advantages:
                for adv in rest_advantages:
                    st.markdown(f"<p style='color: #a0aec0; font-size: 0.85rem;'>{adv}</p>", unsafe_allow_html=True)
            else:
                st.markdown("<p style='color: #6b7280; font-size: 0.85rem;'>No significant rest advantages today</p>", unsafe_allow_html=True)
        
        with sit_col2:
            # B2B fades
            st.markdown("""
            <div style="
                background: rgba(15, 20, 35, 0.6);
                border: 1px solid rgba(239, 68, 68, 0.3);
                border-radius: 12px;
                padding: 1.2rem;
                margin-bottom: 1rem;
            ">
                <h5 style="color: #ef4444; margin-bottom: 0.8rem; font-size: 0.95rem;">🔄 Back-to-Back Teams Today</h5>
            </div>
            """, unsafe_allow_html=True)
            
            b2b_teams = []
            for game in todays_games:
                if game.get('home_is_b2b'):
                    b2b_teams.append(f"⚠️ {game['home_team']} (Home B2B)")
                if game.get('visitor_is_b2b'):
                    b2b_teams.append(f"⚠️ {game['visitor_team']} (Away B2B)")
            
            if b2b_teams:
                for team in b2b_teams:
                    st.markdown(f"<p style='color: #ef4444; font-size: 0.85rem;'>{team}</p>", unsafe_allow_html=True)
            else:
                st.markdown("<p style='color: #6b7280; font-size: 0.85rem;'>No B2B teams today</p>", unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # Trend Insights
    st.markdown("""
    <div style="
        background: linear-gradient(135deg, rgba(102, 126, 234, 0.1) 0%, rgba(118, 75, 162, 0.1) 100%);
        border: 1px solid rgba(102, 126, 234, 0.25);
        border-radius: 12px;
        padding: 1.5rem;
    ">
        <div style="display: flex; align-items: center; gap: 0.8rem; margin-bottom: 1rem;">
            <span style="font-size: 1.3rem;">📝</span>
            <h4 style="color: #e2e8f0; margin: 0; font-size: 1rem;">Trend Insights (Real-Time)</h4>
        </div>
        <div style="
            background: rgba(0, 0, 0, 0.25);
            border-radius: 8px;
            padding: 1.2rem;
            border-left: 3px solid #667eea;
        ">
            <p style="color: #a0aec0; font-size: 0.9rem; margin: 0;">
                ✅ Data is now pulling from your live database<br>
                ✅ Hot/Cold teams calculated from last 30 days<br>
                ✅ Totals trends based on actual game results
            </p>
        </div>
    </div>
    """, unsafe_allow_html=True)
