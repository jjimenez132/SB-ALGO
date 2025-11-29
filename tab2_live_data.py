# ========================================
# TAB 2 - TODAY'S GAMES - WITH REAL DATA
# Replace your entire "with tab2:" section with this
# ========================================

with tab2:
    # Premium Header
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
    
    # Fetch real games from database
    todays_games = get_todays_games(engine)
    
    if not todays_games:
        st.markdown("""
        <div style="
            background: rgba(0, 0, 0, 0.2);
            border-radius: 12px;
            padding: 3rem;
            text-align: center;
            border: 1px dashed rgba(102, 126, 234, 0.3);
        ">
            <span style="font-size: 3rem;">📅</span>
            <p style="color: #6b7280; font-size: 1.2rem; margin: 1rem 0 0 0;">No games scheduled for today</p>
            <p style="color: #4b5563; font-size: 0.9rem; margin-top: 0.5rem;">Check back tomorrow for new matchups</p>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div style="
            background: rgba(16, 185, 129, 0.1);
            border: 1px solid rgba(16, 185, 129, 0.3);
            border-radius: 10px;
            padding: 0.8rem 1.2rem;
            margin-bottom: 1.5rem;
            display: flex;
            align-items: center;
            gap: 0.8rem;
        ">
            <div style="width: 10px; height: 10px; border-radius: 50%; background: #10b981; box-shadow: 0 0 8px #10b981;"></div>
            <span style="color: #10b981; font-weight: 600;">{len(todays_games)} Games Today</span>
            <span style="color: #6b7280;">|</span>
            <span style="color: #a0aec0;">{datetime.now().strftime('%B %d, %Y')}</span>
        </div>
        """, unsafe_allow_html=True)
        
        # Loop through REAL games
        for i, game in enumerate(todays_games):
            home_team = game['home_team']
            visitor_team = game['visitor_team']
            start_time = game.get('start_time', 'TBD')
            home_pts = game.get('home_pts')
            visitor_pts = game.get('visitor_pts')
            home_win = game.get('home_win')
            home_rest = game.get('home_days_rest', 'N/A')
            visitor_rest = game.get('visitor_days_rest', 'N/A')
            home_b2b = game.get('home_is_b2b', False)
            visitor_b2b = game.get('visitor_is_b2b', False)
            season_avg = game.get('season_avg_total', 0)
            total_pts = game.get('total_points', 0)
            
            # Get team records
            home_record = get_recent_team_record(engine, home_team)
            visitor_record = get_recent_team_record(engine, visitor_team)
            
            # Determine game status
            if home_pts is not None and visitor_pts is not None:
                game_status = "FINAL"
                score_display = f"{visitor_pts} - {home_pts}"
                if home_win:
                    winner = home_team
                else:
                    winner = visitor_team
            else:
                game_status = "UPCOMING"
                score_display = "vs"
                winner = None
            
            # Game expander
            expander_title = f"🏀 {visitor_team} @ {home_team} — {start_time if start_time else 'TBD'}"
            if game_status == "FINAL":
                expander_title = f"✅ {visitor_team} {visitor_pts} @ {home_team} {home_pts} — FINAL"
            
            with st.expander(expander_title, expanded=(i==0)):
                
                # Key Metrics Mini-Cards
                st.markdown("""
                <p style="color: #667eea; font-weight: 600; margin-bottom: 0.8rem; font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.5px;">📊 Key Metrics</p>
                """, unsafe_allow_html=True)
                
                metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)
                
                with metric_col1:
                    st.markdown(f"""
                    <div style="
                        background: linear-gradient(135deg, rgba(102, 126, 234, 0.15) 0%, rgba(102, 126, 234, 0.05) 100%);
                        border: 1px solid rgba(102, 126, 234, 0.3);
                        border-radius: 10px;
                        padding: 0.8rem;
                        text-align: center;
                    ">
                        <p style="color: #6b7280; font-size: 0.7rem; margin: 0; text-transform: uppercase;">Home Rest</p>
                        <p style="color: #667eea; font-size: 1.2rem; margin: 0.2rem 0 0 0; font-weight: 600;">{home_rest} days</p>
                        <p style="color: #ef4444; font-size: 0.65rem; margin: 0;">{'⚠️ B2B' if home_b2b else ''}</p>
                    </div>
                    """, unsafe_allow_html=True)
                
                with metric_col2:
                    st.markdown(f"""
                    <div style="
                        background: linear-gradient(135deg, rgba(16, 185, 129, 0.15) 0%, rgba(16, 185, 129, 0.05) 100%);
                        border: 1px solid rgba(16, 185, 129, 0.3);
                        border-radius: 10px;
                        padding: 0.8rem;
                        text-align: center;
                    ">
                        <p style="color: #6b7280; font-size: 0.7rem; margin: 0; text-transform: uppercase;">Away Rest</p>
                        <p style="color: #10b981; font-size: 1.2rem; margin: 0.2rem 0 0 0; font-weight: 600;">{visitor_rest} days</p>
                        <p style="color: #ef4444; font-size: 0.65rem; margin: 0;">{'⚠️ B2B' if visitor_b2b else ''}</p>
                    </div>
                    """, unsafe_allow_html=True)
                
                with metric_col3:
                    st.markdown(f"""
                    <div style="
                        background: linear-gradient(135deg, rgba(251, 191, 36, 0.15) 0%, rgba(251, 191, 36, 0.05) 100%);
                        border: 1px solid rgba(251, 191, 36, 0.3);
                        border-radius: 10px;
                        padding: 0.8rem;
                        text-align: center;
                    ">
                        <p style="color: #6b7280; font-size: 0.7rem; margin: 0; text-transform: uppercase;">Avg Total</p>
                        <p style="color: #fbbf24; font-size: 1.2rem; margin: 0.2rem 0 0 0; font-weight: 600;">{season_avg:.1f if season_avg else '—'}</p>
                    </div>
                    """, unsafe_allow_html=True)
                
                with metric_col4:
                    if total_pts:
                        over_under = "OVER ✅" if total_pts > season_avg else "UNDER ✅"
                        color = "#10b981" if total_pts > season_avg else "#ef4444"
                    else:
                        over_under = "TBD"
                        color = "#6b7280"
                    st.markdown(f"""
                    <div style="
                        background: linear-gradient(135deg, rgba(239, 68, 68, 0.15) 0%, rgba(239, 68, 68, 0.05) 100%);
                        border: 1px solid rgba(239, 68, 68, 0.3);
                        border-radius: 10px;
                        padding: 0.8rem;
                        text-align: center;
                    ">
                        <p style="color: #6b7280; font-size: 0.7rem; margin: 0; text-transform: uppercase;">Total Pts</p>
                        <p style="color: {color}; font-size: 1.2rem; margin: 0.2rem 0 0 0; font-weight: 600;">{total_pts if total_pts else '—'}</p>
                    </div>
                    """, unsafe_allow_html=True)
                
                st.markdown("<br>", unsafe_allow_html=True)
                
                # Two column layout
                col1, col2 = st.columns([2, 1])
                
                with col1:
                    # Game Analysis Panel with REAL data
                    st.markdown(f"""
                    <div style="
                        background: linear-gradient(135deg, rgba(15, 20, 35, 0.8) 0%, rgba(15, 20, 35, 0.6) 100%);
                        border: 1px solid rgba(102, 126, 234, 0.25);
                        border-radius: 12px;
                        padding: 1.5rem;
                        margin-bottom: 1rem;
                        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3), 0 0 15px rgba(102, 126, 234, 0.1);
                    ">
                        <div style="display: flex; align-items: center; gap: 0.6rem; margin-bottom: 1rem;">
                            <span style="font-size: 1.3rem;">📊</span>
                            <h3 style="color: #e2e8f0; margin: 0; font-size: 1.1rem; font-weight: 600;">Game Analysis</h3>
                        </div>
                        
                        <div style="
                            background: rgba(0, 0, 0, 0.25);
                            border-radius: 8px;
                            padding: 1rem;
                            margin-bottom: 0.8rem;
                            border-left: 3px solid #667eea;
                        ">
                            <p style="color: #667eea; font-size: 0.85rem; font-weight: 600; margin-bottom: 0.5rem;">Matchup Overview</p>
                            <div style="display: grid; gap: 0.4rem;">
                                <p style="color: #a0aec0; font-size: 0.85rem; margin: 0;">• {home_team}: {home_record['wins']}-{home_record['losses']} (Home: {home_record['home_record']})</p>
                                <p style="color: #a0aec0; font-size: 0.85rem; margin: 0;">• {visitor_team}: {visitor_record['wins']}-{visitor_record['losses']} (Away: {visitor_record['away_record']})</p>
                            </div>
                        </div>
                        
                        <div style="
                            background: rgba(0, 0, 0, 0.25);
                            border-radius: 8px;
                            padding: 1rem;
                            border-left: 3px solid #fbbf24;
                        ">
                            <p style="color: #fbbf24; font-size: 0.85rem; font-weight: 600; margin-bottom: 0.5rem;">Key Factors</p>
                            <div style="display: grid; gap: 0.4rem;">
                                <p style="color: #a0aec0; font-size: 0.85rem; margin: 0;">• {home_team} rest: {home_rest} days {'(B2B ⚠️)' if home_b2b else ''}</p>
                                <p style="color: #a0aec0; font-size: 0.85rem; margin: 0;">• {visitor_team} rest: {visitor_rest} days {'(B2B ⚠️)' if visitor_b2b else ''}</p>
                                <p style="color: #a0aec0; font-size: 0.85rem; margin: 0;">• Season avg total: {season_avg:.1f if season_avg else 'N/A'}</p>
                            </div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # Algorithm Recommendation
                    if game_status == "FINAL":
                        # Show result
                        result_color = "#10b981" if winner == home_team else "#ef4444"
                        st.markdown(f"""
                        <div style="
                            background: linear-gradient(135deg, rgba(16, 185, 129, 0.2) 0%, rgba(16, 185, 129, 0.05) 100%);
                            border: 2px solid rgba(16, 185, 129, 0.4);
                            border-radius: 12px;
                            padding: 1.5rem;
                            margin-bottom: 1rem;
                        ">
                            <div style="display: flex; align-items: center; gap: 0.6rem; margin-bottom: 1rem;">
                                <span style="font-size: 1.3rem;">✅</span>
                                <h3 style="color: #10b981; margin: 0; font-size: 1.1rem; font-weight: 600;">Final Result</h3>
                            </div>
                            <h2 style="color: #fff; margin: 0; font-size: 1.8rem; font-weight: 700;">{winner} Wins</h2>
                            <p style="color: #a0aec0; margin: 0.5rem 0 0 0;">{visitor_team} {visitor_pts} - {home_team} {home_pts}</p>
                        </div>
                        """, unsafe_allow_html=True)
                    else:
                        # Show placeholder recommendation
                        st.markdown("""
                        <div style="
                            background: linear-gradient(135deg, rgba(16, 185, 129, 0.2) 0%, rgba(16, 185, 129, 0.05) 100%);
                            border: 2px solid rgba(16, 185, 129, 0.4);
                            border-radius: 12px;
                            padding: 1.5rem;
                            margin-bottom: 1rem;
                            box-shadow: 0 0 25px rgba(16, 185, 129, 0.15);
                        ">
                            <div style="display: flex; align-items: center; gap: 0.6rem; margin-bottom: 1rem;">
                                <span style="font-size: 1.3rem;">🎯</span>
                                <h3 style="color: #10b981; margin: 0; font-size: 1.1rem; font-weight: 600;">Algorithm Recommendation</h3>
                            </div>
                            <p style="color: #6b7280; font-size: 0.9rem; margin: 0;">Analysis processing... Check back closer to game time.</p>
                        </div>
                        """, unsafe_allow_html=True)
                
                with col2:
                    # Win probability gauge
                    st.markdown("""
                    <div style="
                        background: linear-gradient(135deg, rgba(15, 20, 35, 0.8) 0%, rgba(15, 20, 35, 0.6) 100%);
                        border: 1px solid rgba(102, 126, 234, 0.25);
                        border-radius: 12px;
                        padding: 1.5rem;
                    ">
                        <div style="display: flex; align-items: center; gap: 0.6rem; margin-bottom: 1rem;">
                            <span style="font-size: 1.3rem;">📈</span>
                            <h3 style="color: #e2e8f0; margin: 0; font-size: 1rem; font-weight: 600;">Win Probability</h3>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # Calculate a simple win probability based on records
                    home_games_total = home_record['wins'] + home_record['losses']
                    visitor_games_total = visitor_record['wins'] + visitor_record['losses']
                    
                    if home_games_total > 0 and visitor_games_total > 0:
                        home_win_pct = (home_record['wins'] / home_games_total) * 100
                        visitor_win_pct = (visitor_record['wins'] / visitor_games_total) * 100
                        # Simple weighted probability (home team gets slight boost)
                        home_prob = min(85, max(15, (home_win_pct * 0.55 + (100 - visitor_win_pct) * 0.45)))
                    else:
                        home_prob = 50
                    
                    fig = go.Figure(go.Indicator(
                        mode = "gauge+number",
                        value = home_prob,
                        domain = {'x': [0, 1], 'y': [0, 1]},
                        title = {'text': f"{home_team} Win %", 'font': {'size': 14, 'color': '#a0aec0'}},
                        number = {'font': {'size': 36, 'color': '#ffffff'}, 'suffix': '%'},
                        gauge = {
                            'axis': {'range': [None, 100], 'tickwidth': 1, 'tickcolor': "#667eea", 'tickfont': {'color': '#6b7280', 'size': 10}},
                            'bar': {'color': "#667eea", 'thickness': 0.3},
                            'bgcolor': "rgba(15, 20, 35, 0.8)",
                            'borderwidth': 2,
                            'bordercolor': "rgba(102, 126, 234, 0.3)",
                            'steps': [
                                {'range': [0, 40], 'color': "rgba(239, 68, 68, 0.2)"},
                                {'range': [40, 60], 'color': "rgba(251, 191, 36, 0.2)"},
                                {'range': [60, 100], 'color': "rgba(16, 185, 129, 0.2)"}
                            ],
                            'threshold': {'line': {'color': "#10b981", 'width': 3}, 'thickness': 0.8, 'value': home_prob}
                        }
                    ))
                    
                    fig.update_layout(
                        height=280,
                        margin=dict(l=20, r=20, t=50, b=20),
                        paper_bgcolor='rgba(0,0,0,0)',
                        plot_bgcolor='rgba(0,0,0,0)',
                        font={'color': '#e2e8f0'}
                    )
                    
                    st.plotly_chart(fig, use_container_width=True, key=f"game_prob_{i}")
                
                # Divider
                st.markdown("""
                <div style="height: 1px; background: linear-gradient(90deg, transparent 0%, rgba(102, 126, 234, 0.3) 50%, transparent 100%); margin: 1rem 0;"></div>
                """, unsafe_allow_html=True)
