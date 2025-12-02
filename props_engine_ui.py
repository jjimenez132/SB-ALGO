#!/usr/bin/env python3
"""
SB-ALGO Props Engine - Premium Casino-Grade UI
Full implementation with all 10 sections
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from sqlalchemy import text
from datetime import datetime
import pytz

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_eastern_time():
    """Get current time in Eastern timezone"""
    return datetime.now(pytz.timezone("US/Eastern"))

def load_props_data(engine):
    """Load props summary and individual book lines from database"""
    today = get_eastern_time().strftime("%Y-%m-%d")
    
    # Summary: aggregated by player/prop/game
    summary_query = text("""
        SELECT 
            player_name,
            market as prop_type,
            home_team || ' vs ' || away_team as game_label,
            home_team,
            away_team,
            game_date,
            MIN(line) as min_line,
            MAX(line) as max_line,
            ROUND(AVG(line)::numeric, 1) as avg_line,
            MAX(line) - MIN(line) as spread,
            COUNT(DISTINCT sportsbook) as books_count
        FROM player_props 
        WHERE game_date = :today
        GROUP BY player_name, market, home_team, away_team, game_date
        ORDER BY spread DESC
    """)
    
    # Individual book lines
    books_query = text("""
        SELECT 
            player_name,
            market as prop_type,
            home_team || ' vs ' || away_team as game_label,
            sportsbook,
            line,
            over_odds,
            under_odds
        FROM player_props 
        WHERE game_date = :today
        ORDER BY player_name, market, line
    """)
    
    with engine.connect() as conn:
        summary_df = pd.read_sql(summary_query, conn, params={"today": today})
        books_df = pd.read_sql(books_query, conn, params={"today": today})
    
    return summary_df, books_df

def get_best_books(books_df, player, prop_type, game_label):
    """Get best over/under books for a specific prop"""
    subset = books_df[
        (books_df["player_name"] == player) & 
        (books_df["prop_type"] == prop_type) & 
        (books_df["game_label"] == game_label)
    ]
    
    if subset.empty:
        return None, None, subset
    
    best_over = subset.loc[subset["line"].idxmin()]  # Lowest line = best over
    best_under = subset.loc[subset["line"].idxmax()]  # Highest line = best under
    
    return best_over, best_under, subset

def calculate_edge_tier(spread, books_count):
    """Calculate edge tier based on spread and book coverage"""
    if spread >= 4.0 and books_count >= 4:
        return "HIGH", "#22c55e"
    elif spread >= 2.0 and books_count >= 3:
        return "MEDIUM", "#eab308"
    else:
        return "LOW", "#6b7280"

def format_odds(odds):
    """Format American odds with + sign for positive"""
    if odds is None:
        return "-"
    odds = int(odds)
    return f"+{odds}" if odds > 0 else str(odds)

def get_recommendation(avg_line, min_line, max_line):
    """Simple algo logic: compare distance from avg to min vs max"""
    dist_to_min = avg_line - min_line
    dist_to_max = max_line - avg_line
    
    if dist_to_min > dist_to_max:
        return "OVER", "#22c55e"
    else:
        return "UNDER", "#ef4444"

def load_player_recent_stats(engine, player_name, prop_type, games=15):
    """Load recent game stats for a player"""
    # Map prop type to boxscore column
    stat_map = {
        "player_points": "pts",
        "player_rebounds": "reb",
        "player_assists": "ast",
        "player_threes": "fg3m",
        "player_blocks": "blk",
        "player_steals": "stl",
        "player_turnovers": "tov"
    }
    
    stat_col = stat_map.get(prop_type, "pts")
    
    query = text(f"""
        SELECT game_date, {stat_col} as stat_value
        FROM player_boxscores
        WHERE player_name ILIKE :player
        ORDER BY game_date DESC
        LIMIT :games
    """)
    
    try:
        with engine.connect() as conn:
            df = pd.read_sql(query, conn, params={"player": f"%{player_name}%", "games": games})
        return df
    except:
        return pd.DataFrame()

# =============================================================================
# MAIN RENDER FUNCTION
# =============================================================================

def render_props_engine(engine):
    """Render the full Props Engine UI"""
    
    # Initialize session state
    if "selected_player" not in st.session_state:
        st.session_state.selected_player = None
    if "selected_prop" not in st.session_state:
        st.session_state.selected_prop = None
    if "selected_game" not in st.session_state:
        st.session_state.selected_game = None
    if "screenshot_mode" not in st.session_state:
        st.session_state.screenshot_mode = False
    
    # Load data
    summary_df, books_df = load_props_data(engine)
    
    if summary_df.empty:
        st.warning("⚠️ No props data for today. Run player_props.py to fetch data.")
        st.info("Props are fetched daily at 7:00 AM EST via cron job")
        return
    
    # =========================================================================
    # SECTION I - Screenshot Mode Toggle (Top Right)
    # =========================================================================
    _, toggle_col = st.columns([6, 1])
    with toggle_col:
        st.session_state.screenshot_mode = st.toggle("📸", value=st.session_state.screenshot_mode, help="Screenshot Mode")
    
    screenshot_mode = st.session_state.screenshot_mode
    
    # =========================================================================
    # SECTION B - Hero Header
    # =========================================================================
    st.markdown("""
        <div style="background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
                    border-radius: 16px; padding: 1.5rem; margin-bottom: 1.5rem;
                    border: 1px solid rgba(74, 222, 128, 0.3);
                    text-align: center;">
            <h1 style="color: #4ade80; margin: 0; font-size: 2.2rem;">
                🎰 Props Engine
            </h1>
            <p style="color: #94a3b8; margin: 0.5rem 0 0 0; font-size: 1rem;">
                Live NBA player props from 11 sportsbooks · Auto-updated daily
            </p>
        </div>
    """, unsafe_allow_html=True)
    
    # Metrics Row
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Total Props", f"{len(summary_df):,}")
    m2.metric("Players", summary_df["player_name"].nunique())
    m3.metric("Sportsbooks", books_df["sportsbook"].nunique())
    high_edge = len(summary_df[(summary_df["spread"] >= 4) & (summary_df["books_count"] >= 4)])
    m4.metric("High Edge", high_edge)
    m5.metric("Updated", get_eastern_time().strftime("%I:%M %p ET"))
    
    st.markdown("---")
    
    # =========================================================================
    # SECTION A - Top Algo Picks (Hero Cards)
    # =========================================================================
    st.markdown("""
        <div style="background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
                    border-radius: 12px; padding: 1rem; margin-bottom: 1rem;
                    border: 1px solid rgba(74, 222, 128, 0.3);">
            <h2 style="color: #4ade80; margin: 0; font-size: 1.5rem;">
                🔥 Top Algo Picks
            </h2>
            <p style="color: #64748b; margin: 0.3rem 0 0 0; font-size: 0.85rem;">
                Highest edge opportunities based on line discrepancies
            </p>
        </div>
    """, unsafe_allow_html=True)
    
    # Get top picks: spread >= 3, books >= 5
    top_picks = summary_df[(summary_df["spread"] >= 3) & (summary_df["books_count"] >= 5)].head(6)
    
    if top_picks.empty:
        top_picks = summary_df.nlargest(6, "spread")
    
    pick_cols = st.columns(3)
    for idx, (_, pick) in enumerate(top_picks.iterrows()):
        with pick_cols[idx % 3]:
            best_over, best_under, _ = get_best_books(books_df, pick["player_name"], pick["prop_type"], pick["game_label"])
            tier, tier_color = calculate_edge_tier(pick["spread"], pick["books_count"])
            rec, rec_color = get_recommendation(pick["avg_line"], pick["min_line"], pick["max_line"])
            
            prop_display = pick["prop_type"].replace("player_", "").upper()
            
            # Best book info
            if best_over is not None:
                over_book = best_over["sportsbook"][:10]
                over_odds = format_odds(best_over["over_odds"])
                under_book = best_under["sportsbook"][:10]
                under_odds = format_odds(best_under["under_odds"])
            else:
                over_book, over_odds, under_book, under_odds = "-", "-", "-", "-"
            
            st.markdown(f"""
                <div style="background: linear-gradient(135deg, #1e293b 0%, #334155 100%);
                            border-radius: 12px; padding: 1rem; margin-bottom: 0.8rem;
                            border-left: 4px solid {rec_color};
                            border: 1px solid rgba(255,255,255,0.1);">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <span style="color: white; font-weight: 700; font-size: 1.1rem;">{pick["player_name"]}</span>
                        <span style="background: {tier_color}; color: white; padding: 2px 8px; 
                                     border-radius: 4px; font-size: 0.7rem; font-weight: 600;">{tier}</span>
                    </div>
                    <div style="color: #94a3b8; font-size: 0.85rem; margin: 0.3rem 0;">
                        {prop_display} · {pick["avg_line"]}
                    </div>
                    <div style="color: #64748b; font-size: 0.75rem; margin-bottom: 0.5rem;">
                        {pick["game_label"]}
                    </div>
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 0.5rem;">
                        <span style="background: {rec_color}; color: white; padding: 4px 12px; 
                                     border-radius: 6px; font-weight: 700; font-size: 0.9rem;">{rec}</span>
                        <span style="color: #4ade80; font-size: 0.85rem;">
                            📊 {pick["spread"]:.1f} spread · {int(pick["books_count"])} books
                        </span>
                    </div>
                    <div style="margin-top: 0.5rem; padding-top: 0.5rem; border-top: 1px solid rgba(255,255,255,0.1);">
                        <span style="color: #22c55e; font-size: 0.75rem;">▲ {over_book} {over_odds}</span>
                        <span style="color: #64748b; font-size: 0.75rem;"> | </span>
                        <span style="color: #ef4444; font-size: 0.75rem;">▼ {under_book} {under_odds}</span>
                    </div>
                </div>
            """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    # =========================================================================
    # SECTION C - Filter Control Room (Hidden in Screenshot Mode)
    # =========================================================================
    if not screenshot_mode:
        st.markdown("### 🎛️ Filters")
        
        f1, f2, f3, f4 = st.columns(4)
        
        with f1:
            prop_options = ["All"] + sorted(summary_df["prop_type"].unique().tolist())
            selected_prop_filter = st.selectbox("Prop Type", prop_options)
        
        with f2:
            teams = sorted(set(summary_df["home_team"].tolist() + summary_df["away_team"].tolist()))
            team_options = ["All"] + teams
            selected_team = st.selectbox("Team", team_options)
        
        with f3:
            min_spread = st.slider("Min Spread", 0.0, 8.0, 0.0, 0.5)
        
        with f4:
            min_books = st.slider("Min Books", 1, 11, 3)
        
        # Search and Edge filter
        s1, s2, s3 = st.columns([2, 1, 1])
        with s1:
            search_player = st.text_input("🔍 Search Player", "")
        with s2:
            edge_options = ["All", "HIGH", "MEDIUM", "LOW"]
            selected_edge = st.selectbox("Edge Tier", edge_options)
        with s3:
            if st.button("🔄 Reset Filters"):
                st.rerun()
        
        # Apply filters
        filtered_df = summary_df.copy()
        
        if selected_prop_filter != "All":
            filtered_df = filtered_df[filtered_df["prop_type"] == selected_prop_filter]
        
        if selected_team != "All":
            filtered_df = filtered_df[
                (filtered_df["home_team"] == selected_team) | 
                (filtered_df["away_team"] == selected_team)
            ]
        
        if min_spread > 0:
            filtered_df = filtered_df[filtered_df["spread"] >= min_spread]
        
        if min_books > 1:
            filtered_df = filtered_df[filtered_df["books_count"] >= min_books]
        
        if search_player:
            filtered_df = filtered_df[
                filtered_df["player_name"].str.contains(search_player, case=False, na=False)
            ]
        
        if selected_edge != "All":
            def check_tier(row):
                tier, _ = calculate_edge_tier(row["spread"], row["books_count"])
                return tier == selected_edge
            filtered_df = filtered_df[filtered_df.apply(check_tier, axis=1)]
        
        st.caption(f"Showing {len(filtered_df)} of {len(summary_df)} props")
    else:
        # Screenshot mode: show top spreads only
        filtered_df = summary_df[summary_df["spread"] >= 2].head(25)
    
    st.markdown("---")
    
    # =========================================================================
    # SECTION D & E - Board Scanner + Deep Dive Inspector
    # =========================================================================
    st.markdown("### 📊 Board Scanner")
    
    table_col, inspector_col = st.columns([3, 2])
    
    with table_col:
        # Build display table
        display_rows = []
        for _, row in filtered_df.head(50).iterrows():
            best_over, best_under, _ = get_best_books(books_df, row["player_name"], row["prop_type"], row["game_label"])
            
            spread_val = row["spread"]
            if spread_val >= 4:
                spread_display = f"🎯 {spread_val:.1f}"
            elif spread_val >= 2:
                spread_display = f"✅ {spread_val:.1f}"
            else:
                spread_display = f"{spread_val:.1f}"
            
            if best_over is not None:
                over_display = f"{best_over['line']} @ {best_over['sportsbook'][:8]} ({format_odds(best_over['over_odds'])})"
                under_display = f"{best_under['line']} @ {best_under['sportsbook'][:8]} ({format_odds(best_under['under_odds'])})"
            else:
                over_display = "-"
                under_display = "-"
            
            tier, _ = calculate_edge_tier(spread_val, row["books_count"])
            
            display_rows.append({
                "Player": row["player_name"],
                "Prop": f"{row['prop_type'].replace('player_', '').title()} {row['avg_line']}",
                "Game": row["game_label"][:20],
                "Best Over": over_display,
                "Best Under": under_display,
                "Spread": spread_display,
                "Books": int(row["books_count"]),
                "Edge": tier,
                "_player": row["player_name"],
                "_prop": row["prop_type"],
                "_game": row["game_label"]
            })
        
        display_df = pd.DataFrame(display_rows)
        
        if not display_df.empty:
            st.dataframe(
                display_df[["Player", "Prop", "Game", "Best Over", "Best Under", "Spread", "Books", "Edge"]],
                hide_index=True,
                height=450,
                use_container_width=True
            )
            
            # Player selector for deep dive
            player_options = ["Select a player..."] + display_df["Player"].tolist()
            selected = st.selectbox("🔬 Inspect Player", player_options, key="player_selector")
            
            if selected != "Select a player...":
                row_data = display_df[display_df["Player"] == selected].iloc[0]
                st.session_state.selected_player = row_data["_player"]
                st.session_state.selected_prop = row_data["_prop"]
                st.session_state.selected_game = row_data["_game"]
        else:
            st.info("No props match your filters")
    
    # =========================================================================
    # SECTION E - Deep Dive Inspector Panel
    # =========================================================================
    with inspector_col:
        st.markdown("""
            <div style="background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
                        border-radius: 12px; padding: 1rem;
                        border: 1px solid rgba(74, 222, 128, 0.2);">
                <h3 style="color: #4ade80; margin: 0 0 0.5rem 0;">🔬 Deep Dive</h3>
            </div>
        """, unsafe_allow_html=True)
        
        if st.session_state.selected_player:
            player = st.session_state.selected_player
            prop_type = st.session_state.selected_prop
            game = st.session_state.selected_game
            
            # Get row data
            row = summary_df[
                (summary_df["player_name"] == player) & 
                (summary_df["prop_type"] == prop_type) & 
                (summary_df["game_label"] == game)
            ]
            
            if not row.empty:
                row = row.iloc[0]
                best_over, best_under, all_books = get_best_books(books_df, player, prop_type, game)
                tier, tier_color = calculate_edge_tier(row["spread"], row["books_count"])
                rec, rec_color = get_recommendation(row["avg_line"], row["min_line"], row["max_line"])
                
                # Player Header
                prop_display = prop_type.replace("player_", "").upper()
                st.markdown(f"""
                    <div style="background: #1e293b; border-radius: 8px; padding: 0.8rem; margin: 0.5rem 0;">
                        <h4 style="color: white; margin: 0;">{player}</h4>
                        <div style="margin-top: 0.3rem;">
                            <span style="background: #3b82f6; color: white; padding: 2px 8px; 
                                         border-radius: 4px; font-size: 0.75rem; margin-right: 0.5rem;">{prop_display}</span>
                            <span style="background: {tier_color}; color: white; padding: 2px 8px; 
                                         border-radius: 4px; font-size: 0.75rem;">{tier} EDGE</span>
                        </div>
                        <p style="color: #94a3b8; margin: 0.3rem 0 0 0; font-size: 0.85rem;">{game}</p>
                    </div>
                """, unsafe_allow_html=True)
                
                # Consensus Card
                st.markdown(f"""
                    <div style="background: linear-gradient(135deg, #1e293b 0%, #334155 100%);
                                border-radius: 8px; padding: 0.8rem; margin: 0.5rem 0;">
                        <div style="text-align: center;">
                            <span style="color: #64748b; font-size: 0.75rem;">CONSENSUS LINE</span>
                            <h2 style="color: white; margin: 0.2rem 0;">{row["avg_line"]}</h2>
                        </div>
                        <div style="display: flex; justify-content: space-between; margin-top: 0.5rem;">
                            <div style="text-align: center;">
                                <span style="color: #22c55e; font-size: 0.7rem;">MIN (OVER)</span>
                                <div style="color: #22c55e; font-weight: 700;">{row["min_line"]}</div>
                            </div>
                            <div style="text-align: center;">
                                <span style="color: #ef4444; font-size: 0.7rem;">MAX (UNDER)</span>
                                <div style="color: #ef4444; font-weight: 700;">{row["max_line"]}</div>
                            </div>
                            <div style="text-align: center;">
                                <span style="color: #4ade80; font-size: 0.7rem;">SPREAD</span>
                                <div style="color: #4ade80; font-weight: 700;">{row["spread"]:.1f}</div>
                            </div>
                        </div>
                    </div>
                """, unsafe_allow_html=True)
                
                # Algo Recommendation
                st.markdown(f"""
                    <div style="background: {rec_color}; border-radius: 8px; padding: 0.6rem; 
                                margin: 0.5rem 0; text-align: center;">
                        <span style="color: white; font-weight: 700; font-size: 1.1rem;">
                            ALGO SAYS: {rec}
                        </span>
                    </div>
                """, unsafe_allow_html=True)
                
                # Sportsbook Comparison
                st.markdown("**📚 All Sportsbooks:**")
                if not all_books.empty:
                    books_sorted = all_books.sort_values("line")
                    
                    for _, book in books_sorted.iterrows():
                        is_best_over = book["line"] == row["min_line"]
                        is_best_under = book["line"] == row["max_line"]
                        
                        if is_best_over:
                            bg_color = "rgba(34, 197, 94, 0.2)"
                            border_color = "#22c55e"
                        elif is_best_under:
                            bg_color = "rgba(239, 68, 68, 0.2)"
                            border_color = "#ef4444"
                        else:
                            bg_color = "#1e293b"
                            border_color = "transparent"
                        
                        st.markdown(f"""
                            <div style="background: {bg_color}; border-radius: 6px; padding: 0.4rem 0.6rem;
                                        margin: 0.2rem 0; border: 1px solid {border_color};
                                        display: flex; justify-content: space-between; align-items: center;">
                                <span style="color: white; font-size: 0.8rem;">{book["sportsbook"]}</span>
                                <span style="color: #94a3b8; font-weight: 600;">{book["line"]}</span>
                                <span style="color: #22c55e; font-size: 0.75rem;">{format_odds(book["over_odds"])}</span>
                                <span style="color: #ef4444; font-size: 0.75rem;">{format_odds(book["under_odds"])}</span>
                            </div>
                        """, unsafe_allow_html=True)
                
                # Line Distribution Chart
                st.markdown("**📊 Line Distribution:**")
                if not all_books.empty:
                    line_counts = all_books.groupby("line").size().reset_index(name="count")
                    fig = px.bar(
                        line_counts, 
                        x="line", 
                        y="count",
                        color_discrete_sequence=["#4ade80"]
                    )
                    fig.update_layout(
                        height=150,
                        margin=dict(l=0, r=0, t=10, b=0),
                        paper_bgcolor="rgba(0,0,0,0)",
                        plot_bgcolor="rgba(0,0,0,0)",
                        xaxis=dict(showgrid=False, color="#94a3b8"),
                        yaxis=dict(showgrid=False, color="#94a3b8"),
                        showlegend=False
                    )
                    st.plotly_chart(fig, use_container_width=True)
                
                # Recent Performance
                recent_stats = load_player_recent_stats(engine, player, prop_type)
                if not recent_stats.empty and "stat_value" in recent_stats.columns:
                    avg_stat = recent_stats["stat_value"].mean()
                    diff = avg_stat - row["avg_line"]
                    diff_color = "#22c55e" if diff > 0 else "#ef4444"
                    
                    st.markdown(f"""
                        <div style="background: #1e293b; border-radius: 8px; padding: 0.6rem; margin-top: 0.5rem;">
                            <span style="color: #64748b; font-size: 0.75rem;">LAST 15 GAMES AVG</span>
                            <div style="display: flex; justify-content: space-between; align-items: center;">
                                <span style="color: white; font-weight: 700; font-size: 1.2rem;">{avg_stat:.1f}</span>
                                <span style="color: {diff_color}; font-size: 0.9rem;">
                                    {'+' if diff > 0 else ''}{diff:.1f} vs line
                                </span>
                            </div>
                        </div>
                    """, unsafe_allow_html=True)
        else:
            st.markdown("""
                <div style="background: #1e293b; border-radius: 8px; padding: 2rem; 
                            text-align: center; margin-top: 1rem;">
                    <p style="color: #64748b; margin: 0;">👆 Select a player from the table to inspect</p>
                </div>
            """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    # =========================================================================
    # SECTION F - Biggest Market Discrepancies
    # =========================================================================
    st.markdown("### 🎯 Biggest Market Discrepancies")
    st.caption("Props with highest disagreement between sportsbooks")
    
    discrepancies = summary_df[
        (summary_df["spread"] >= 2) & 
        (summary_df["books_count"] >= 3)
    ].nlargest(10, "spread")
    
    disc_cols = st.columns(2)
    for idx, (_, disc) in enumerate(discrepancies.iterrows()):
        with disc_cols[idx % 2]:
            tier, tier_color = calculate_edge_tier(disc["spread"], disc["books_count"])
            prop_display = disc["prop_type"].replace("player_", "").upper()
            
            st.markdown(f"""
                <div style="background: linear-gradient(135deg, rgba(34, 197, 94, 0.1) 0%, rgba(34, 197, 94, 0.05) 100%);
                            border-radius: 10px; padding: 0.8rem; margin-bottom: 0.5rem;
                            border: 1px solid rgba(34, 197, 94, 0.3);">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <span style="color: white; font-weight: 600;">{disc["player_name"]}</span>
                        <span style="background: {tier_color}; color: white; padding: 2px 6px; 
                                     border-radius: 4px; font-size: 0.7rem;">{tier}</span>
                    </div>
                    <div style="color: #94a3b8; font-size: 0.8rem;">{prop_display} · {disc["game_label"][:25]}</div>
                    <div style="margin-top: 0.3rem;">
                        <span style="color: #22c55e;">{disc["min_line"]}</span>
                        <span style="color: #64748b;"> → </span>
                        <span style="color: #ef4444;">{disc["max_line"]}</span>
                        <span style="color: #4ade80; margin-left: 0.5rem; font-weight: 700;">
                            ({disc["spread"]:.1f} spread)
                        </span>
                    </div>
                </div>
            """, unsafe_allow_html=True)
    
    # =========================================================================
    # SECTION G - Sportsbook Heatmap (Collapsible)
    # =========================================================================
    if not screenshot_mode:
        with st.expander("🌡️ Sportsbook Heatmap"):
            st.caption("Line differences from consensus by sportsbook")
            
            # Get top 10 high-spread props for heatmap
            heatmap_props = summary_df.nlargest(10, "spread")
            
            if not heatmap_props.empty:
                heatmap_data = []
                
                for _, prop in heatmap_props.iterrows():
                    _, _, prop_books = get_best_books(books_df, prop["player_name"], prop["prop_type"], prop["game_label"])
                    
                    if not prop_books.empty:
                        for _, book in prop_books.iterrows():
                            diff = book["line"] - prop["avg_line"]
                            heatmap_data.append({
                                "Prop": f"{prop['player_name'][:12]} {prop['prop_type'].replace('player_', '')[:3].upper()}",
                                "Book": book["sportsbook"][:8],
                                "Diff": diff
                            })
                
                if heatmap_data:
                    heatmap_df = pd.DataFrame(heatmap_data)
                    pivot = heatmap_df.pivot_table(index="Prop", columns="Book", values="Diff", aggfunc="first")
                    
                    fig = px.imshow(
                        pivot,
                        color_continuous_scale=["#ef4444", "#ffffff", "#22c55e"],
                        color_continuous_midpoint=0,
                        aspect="auto"
                    )
                    fig.update_layout(
                        height=400,
                        paper_bgcolor="rgba(0,0,0,0)",
                        plot_bgcolor="rgba(0,0,0,0)"
                    )
                    st.plotly_chart(fig, use_container_width=True)
    
    # =========================================================================
    # SECTION H - Raw Lines Debug (Collapsible, Hidden in Screenshot Mode)
    # =========================================================================
    if not screenshot_mode:
        with st.expander("📂 Raw Lines (Debug)"):
            search_raw = st.text_input("Search raw data", "", key="raw_search")
            
            raw_display = books_df.copy()
            if search_raw:
                raw_display = raw_display[
                    raw_display["player_name"].str.contains(search_raw, case=False, na=False) |
                    raw_display["sportsbook"].str.contains(search_raw, case=False, na=False)
                ]
            
            st.dataframe(raw_display.head(200), hide_index=True, use_container_width=True)
            st.caption(f"Showing {min(200, len(raw_display))} of {len(books_df)} total lines")


# =============================================================================
# STANDALONE TEST
# =============================================================================
if __name__ == "__main__":
    st.set_page_config(page_title="Props Engine Test", layout="wide")
    st.warning("This is a standalone test. Import render_props_engine() into your dashboard.")
