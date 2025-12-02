#!/usr/bin/env python3
"""
SB-ALGO Props Engine - Bloomberg Terminal Style
Professional NBA Props Trading Terminal with AI Insights
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from sqlalchemy import text
from datetime import datetime
import pytz
import random

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_eastern_time():
    return datetime.now(pytz.timezone("US/Eastern"))

def load_props_data(engine):
    today = get_eastern_time().strftime("%Y-%m-%d")
    
    summary_query = text("""
        SELECT player_name, market as prop_type,
            home_team || ' vs ' || away_team as game_label,
            home_team, away_team, game_date,
            MIN(line) as min_line, MAX(line) as max_line,
            ROUND(AVG(line)::numeric, 1) as avg_line,
            MAX(line) - MIN(line) as spread,
            COUNT(DISTINCT sportsbook) as books_count
        FROM player_props WHERE game_date = :today
        GROUP BY player_name, market, home_team, away_team, game_date
        ORDER BY spread DESC
    """)
    
    books_query = text("""
        SELECT player_name, market as prop_type,
            home_team || ' vs ' || away_team as game_label,
            sportsbook, line, over_odds, under_odds
        FROM player_props WHERE game_date = :today
        ORDER BY player_name, market, line
    """)
    
    with engine.connect() as conn:
        summary_df = pd.read_sql(summary_query, conn, params={"today": today})
        books_df = pd.read_sql(books_query, conn, params={"today": today})
    
    return summary_df, books_df

def get_best_books(books_df, player, prop_type, game_label):
    subset = books_df[
        (books_df["player_name"] == player) & 
        (books_df["prop_type"] == prop_type) & 
        (books_df["game_label"] == game_label)
    ]
    if subset.empty:
        return None, None, subset
    best_over = subset.loc[subset["line"].idxmin()]
    best_under = subset.loc[subset["line"].idxmax()]
    return best_over, best_under, subset

def calculate_edge_tier(spread, books_count):
    if spread >= 4.0 and books_count >= 4:
        return "HIGH", "#22c55e"
    elif spread >= 2.0 and books_count >= 3:
        return "MEDIUM", "#eab308"
    return "LOW", "#6b7280"

def format_odds(odds):
    if odds is None or pd.isna(odds):
        return "-"
    odds = int(odds)
    return f"+{odds}" if odds > 0 else str(odds)

def get_algo_projection(player_name, prop_type, avg_line):
    """PLACEHOLDER: Generate algo projection - replace with real model"""
    random.seed(hash(player_name + prop_type) % 1000)
    variance = random.uniform(-3.5, 4.5)
    projection = round(avg_line + variance, 1)
    delta = round(projection - avg_line, 1)
    confidence = min(95, max(55, 75 + int(abs(delta) * 5)))
    
    if confidence >= 85 and abs(delta) >= 2:
        units = 2.0
    elif confidence >= 75 and abs(delta) >= 1:
        units = 1.5
    elif confidence >= 65:
        units = 1.0
    else:
        units = 0.5
    
    rec = "OVER" if delta > 0.5 else "UNDER" if delta < -0.5 else "PASS"
    volatility = ["LOW", "MEDIUM", "HIGH"][hash(player_name) % 3]
    
    return {
        "projection": projection, "delta": delta, "confidence": confidence,
        "units": units, "recommendation": rec, "volatility": volatility
    }

def get_player_game_log(engine, player_name, prop_type, games=15):
    stat_map = {
        "player_points": "pts", "player_rebounds": "reb", "player_assists": "ast",
        "player_threes": "fg3m", "player_blocks": "blk", "player_steals": "stl",
        "player_turnovers": "tov", "player_points_rebounds_assists": "pts"
    }
    stat_col = stat_map.get(prop_type, "pts")
    
    query = text(f"""
        SELECT pb.game_date, pb.{stat_col} as stat_value,
            CASE WHEN g.home_team = pb.team THEN g.away_team ELSE g.home_team END as opponent,
            CASE WHEN g.home_team = pb.team THEN 'HOME' ELSE 'AWAY' END as location
        FROM player_boxscores pb
        LEFT JOIN games g ON pb.game_id = g.game_id
        WHERE pb.player_name ILIKE :player AND pb.{stat_col} IS NOT NULL
        ORDER BY pb.game_date DESC LIMIT :games
    """)
    
    try:
        with engine.connect() as conn:
            return pd.read_sql(query, conn, params={"player": f"%{player_name}%", "games": games})
    except:
        return pd.DataFrame()

def calculate_hit_rates(game_log, line):
    if game_log.empty or "stat_value" not in game_log.columns:
        return {"L5": "-", "L10": "-", "L15": "-", "Season": "-"}
    
    def hit_rate(df):
        if len(df) == 0:
            return "-"
        hits = (df["stat_value"] > line).sum()
        return f"{hits}/{len(df)} ({100*hits//len(df)}%)"
    
    return {
        "L5": hit_rate(game_log.head(5)),
        "L10": hit_rate(game_log.head(10)),
        "L15": hit_rate(game_log.head(15)),
        "Season": hit_rate(game_log)
    }

def generate_ai_insights(player, prop_type, avg_line, projection_data, game_log):
    """Generate AI insight bullets for a prop"""
    insights = []
    delta = projection_data["delta"]
    conf = projection_data["confidence"]
    rec = projection_data["recommendation"]
    
    if abs(delta) >= 1:
        direction = "above" if delta > 0 else "below"
        insights.append(f"Line is {abs(delta):.1f} pts {direction} algo projection ({projection_data['projection']})")
    
    if conf >= 85:
        insights.append(f"High confidence play ({conf}%) - Strong edge detected")
    elif conf >= 75:
        insights.append(f"Solid confidence ({conf}%) - Favorable setup")
    
    if not game_log.empty and "stat_value" in game_log.columns:
        l5_avg = game_log.head(5)["stat_value"].mean()
        l10_avg = game_log.head(10)["stat_value"].mean()
        if l5_avg > avg_line:
            insights.append(f"Hot streak: Averaging {l5_avg:.1f} over L5 (line: {avg_line})")
        elif l5_avg < avg_line - 2:
            insights.append(f"Cold streak: Averaging {l5_avg:.1f} over L5 (line: {avg_line})")
        
        if l5_avg > l10_avg:
            insights.append(f"Trending UP: L5 avg ({l5_avg:.1f}) > L10 avg ({l10_avg:.1f})")
        elif l5_avg < l10_avg - 1:
            insights.append(f"Trending DOWN: L5 avg ({l5_avg:.1f}) < L10 avg ({l10_avg:.1f})")
    
    vol = projection_data["volatility"]
    if vol == "HIGH":
        insights.append("High volatility - Consider smaller unit size")
    elif vol == "LOW":
        insights.append("Low volatility - Consistent performer")
    
    units = projection_data["units"]
    if units >= 1.5:
        insights.append(f"Suggested: {units}U on {rec}")
    
    return insights[:6]

def get_matchup_data(opponent):
    """PLACEHOLDER: Get opponent defensive data"""
    random.seed(hash(opponent) % 100)
    return {
        "def_rating": random.randint(18, 30),
        "pace": round(random.uniform(96, 104), 1),
        "pts_allowed": round(random.uniform(108, 118), 1),
        "reb_allowed": round(random.uniform(42, 48), 1),
        "ast_allowed": round(random.uniform(23, 28), 1),
        "fg3_pct_allowed": round(random.uniform(34, 39), 1)
    }

# =============================================================================
# MAIN RENDER FUNCTION
# =============================================================================

def render_props_engine(engine):
    # Session state
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
        st.warning("No props data for today. Run player_props.py to fetch.")
        return
    
    # Add projections to summary
    projections = []
    for _, row in summary_df.iterrows():
        proj = get_algo_projection(row["player_name"], row["prop_type"], row["avg_line"])
        projections.append(proj)
    
    summary_df["projection"] = [p["projection"] for p in projections]
    summary_df["delta"] = [p["delta"] for p in projections]
    summary_df["confidence"] = [p["confidence"] for p in projections]
    summary_df["units"] = [p["units"] for p in projections]
    summary_df["algo_rec"] = [p["recommendation"] for p in projections]
    
    # =========================================================================
    # HEADER + CONTROLS
    # =========================================================================
    h1, h2, h3 = st.columns([4, 1, 1])
    with h1:
        st.markdown("""
            <h1 style="color:#4ade80; margin:0; font-family: monospace;">
                PROPS ENGINE <span style="color:#64748b; font-size:0.5em;">v2.0</span>
            </h1>
            <p style="color:#64748b; margin:0; font-size:0.85rem;">
                NBA Player Props Terminal | 11 Books | Live Lines
            </p>
        """, unsafe_allow_html=True)
    with h2:
        screenshot_mode = st.toggle("Screenshot", value=st.session_state.screenshot_mode, key="ss_toggle")
        st.session_state.screenshot_mode = screenshot_mode
    with h3:
        st.markdown(f"<p style='color:#4ade80; text-align:right; margin:0; font-family:monospace;'>{get_eastern_time().strftime('%I:%M %p ET')}</p>", unsafe_allow_html=True)
    
    # Metrics bar
    m1, m2, m3, m4, m5, m6 = st.columns(6)
    high_conf = len(summary_df[summary_df["confidence"] >= 80])
    m1.metric("Props", len(summary_df))
    m2.metric("Players", summary_df["player_name"].nunique())
    m3.metric("Books", books_df["sportsbook"].nunique())
    m4.metric("High Conf", high_conf)
    m5.metric("Avg Spread", f"{summary_df['spread'].mean():.1f}")
    m6.metric("Best Edge", f"{summary_df['spread'].max():.1f}")
    
    st.markdown("<hr style='border-color:#1e293b; margin:0.5rem 0;'>", unsafe_allow_html=True)
    
    # =========================================================================
    # SECTION A: TOP ALGO PICKS
    # =========================================================================
    st.markdown("### TOP ALGO PICKS")
    
    top_picks = summary_df[
        (summary_df["confidence"] >= 75) & 
        (summary_df["algo_rec"] != "PASS") &
        (summary_df["spread"] >= 2)
    ].nlargest(6, "confidence")
    
    if top_picks.empty:
        top_picks = summary_df.nlargest(6, "spread")
    
    cols = st.columns(3)
    for idx, (_, pick) in enumerate(top_picks.iterrows()):
        with cols[idx % 3]:
            rec = pick["algo_rec"]
            rec_color = "#22c55e" if rec == "OVER" else "#ef4444" if rec == "UNDER" else "#64748b"
            prop_name = pick["prop_type"].replace("player_", "").upper()
            
            st.markdown(f"""
                <div style="background:#0f172a; border:1px solid #1e293b; border-left:3px solid {rec_color};
                            padding:0.8rem; margin-bottom:0.5rem; font-family:monospace;">
                    <div style="display:flex; justify-content:space-between;">
                        <span style="color:white; font-weight:bold;">{pick["player_name"]}</span>
                        <span style="color:{rec_color}; font-weight:bold;">{rec}</span>
                    </div>
                    <div style="color:#64748b; font-size:0.8rem;">{prop_name} | {pick["game_label"][:20]}</div>
                    <div style="display:flex; justify-content:space-between; margin-top:0.5rem;">
                        <div><span style="color:#64748b;">Line:</span> <span style="color:white;">{pick["avg_line"]}</span></div>
                        <div><span style="color:#64748b;">Proj:</span> <span style="color:#4ade80;">{pick["projection"]}</span></div>
                        <div><span style="color:#64748b;">Delta:</span> <span style="color:{'#22c55e' if pick['delta'] > 0 else '#ef4444'};">{pick["delta"]:+.1f}</span></div>
                    </div>
                    <div style="display:flex; justify-content:space-between; margin-top:0.3rem; font-size:0.85rem;">
                        <span style="color:#64748b;">Conf: <span style="color:#4ade80;">{pick["confidence"]}%</span></span>
                        <span style="color:#64748b;">Units: <span style="color:#eab308;">{pick["units"]}</span></span>
                        <span style="color:#64748b;">Spread: <span style="color:#4ade80;">{pick["spread"]:.1f}</span></span>
                    </div>
                </div>
            """, unsafe_allow_html=True)
    
    st.markdown("<hr style='border-color:#1e293b; margin:1rem 0;'>", unsafe_allow_html=True)
    
    # =========================================================================
    # FILTERS (Hidden in Screenshot Mode)
    # =========================================================================
    if not screenshot_mode:
        with st.expander("FILTERS", expanded=True):
            f1, f2, f3, f4, f5 = st.columns(5)
            with f1:
                prop_opts = ["All"] + sorted(summary_df["prop_type"].unique().tolist())
                sel_prop = st.selectbox("Prop Type", prop_opts, key="f_prop")
            with f2:
                teams = sorted(set(summary_df["home_team"].tolist() + summary_df["away_team"].tolist()))
                sel_team = st.selectbox("Team", ["All"] + teams, key="f_team")
            with f3:
                min_conf = st.slider("Min Confidence", 50, 95, 60, key="f_conf")
            with f4:
                min_spread = st.slider("Min Spread", 0.0, 6.0, 0.0, 0.5, key="f_spread")
            with f5:
                sel_rec = st.selectbox("Algo Rec", ["All", "OVER", "UNDER", "PASS"], key="f_rec")
            
            search = st.text_input("Search Player", "", key="f_search")
        
        # Apply filters
        filtered = summary_df.copy()
        if sel_prop != "All":
            filtered = filtered[filtered["prop_type"] == sel_prop]
        if sel_team != "All":
            filtered = filtered[(filtered["home_team"] == sel_team) | (filtered["away_team"] == sel_team)]
        if min_conf > 50:
            filtered = filtered[filtered["confidence"] >= min_conf]
        if min_spread > 0:
            filtered = filtered[filtered["spread"] >= min_spread]
        if sel_rec != "All":
            filtered = filtered[filtered["algo_rec"] == sel_rec]
        if search:
            filtered = filtered[filtered["player_name"].str.contains(search, case=False, na=False)]
        
        st.caption(f"Showing {len(filtered)} of {len(summary_df)} props")
    else:
        filtered = summary_df[summary_df["confidence"] >= 70].head(20)
    
    # =========================================================================
    # BOARD SCANNER + DEEP DIVE
    # =========================================================================
    st.markdown("### BOARD SCANNER")
    
    scanner_col, dive_col = st.columns([3, 2])
    
    with scanner_col:
        rows = []
        for _, r in filtered.head(40).iterrows():
            spread_icon = "🎯" if r["spread"] >= 4 else "✅" if r["spread"] >= 2 else ""
            rec_icon = "▲" if r["algo_rec"] == "OVER" else "▼" if r["algo_rec"] == "UNDER" else "—"
            
            rows.append({
                "Player": r["player_name"],
                "Prop": r["prop_type"].replace("player_", "")[:6].upper(),
                "Line": r["avg_line"],
                "Proj": r["projection"],
                "Δ": f"{r['delta']:+.1f}",
                "Conf": f"{r['confidence']}%",
                "Rec": f"{rec_icon} {r['algo_rec']}",
                "Units": r["units"],
                "Spread": f"{spread_icon}{r['spread']:.1f}",
                "Books": int(r["books_count"]),
                "_p": r["player_name"], "_t": r["prop_type"], "_g": r["game_label"]
            })
        
        df_display = pd.DataFrame(rows)
        
        if not df_display.empty:
            st.dataframe(
                df_display[["Player", "Prop", "Line", "Proj", "Δ", "Conf", "Rec", "Units", "Spread", "Books"]],
                hide_index=True, height=400, use_container_width=True
            )
            
            player_opts = ["Select player..."] + df_display["Player"].tolist()
            selected = st.selectbox("Deep Dive", player_opts, key="dive_select")
            
            if selected != "Select player...":
                row_data = df_display[df_display["Player"] == selected].iloc[0]
                st.session_state.selected_player = row_data["_p"]
                st.session_state.selected_prop = row_data["_t"]
                st.session_state.selected_game = row_data["_g"]
    
    # =========================================================================
    # DEEP DIVE PANEL
    # =========================================================================
    with dive_col:
        st.markdown("""
            <div style="background:#0f172a; border:1px solid #1e293b; padding:0.5rem; margin-bottom:0.5rem;">
                <span style="color:#4ade80; font-family:monospace; font-weight:bold;">DEEP DIVE</span>
            </div>
        """, unsafe_allow_html=True)
        
        if st.session_state.selected_player:
            player = st.session_state.selected_player
            prop_type = st.session_state.selected_prop
            game = st.session_state.selected_game
            
            row = summary_df[
                (summary_df["player_name"] == player) &
                (summary_df["prop_type"] == prop_type) &
                (summary_df["game_label"] == game)
            ]
            
            if not row.empty:
                row = row.iloc[0]
                proj_data = get_algo_projection(player, prop_type, row["avg_line"])
                best_o, best_u, all_books = get_best_books(books_df, player, prop_type, game)
                game_log = get_player_game_log(engine, player, prop_type, 15)
                hit_rates = calculate_hit_rates(game_log, row["avg_line"])
                insights = generate_ai_insights(player, prop_type, row["avg_line"], proj_data, game_log)
                
                rec = proj_data["recommendation"]
                rec_color = "#22c55e" if rec == "OVER" else "#ef4444" if rec == "UNDER" else "#64748b"
                
                # SECTION 1: Header
                st.markdown(f"""
                    <div style="background:#1e293b; padding:0.8rem; margin-bottom:0.5rem; font-family:monospace;">
                        <div style="color:white; font-size:1.1rem; font-weight:bold;">{player}</div>
                        <div style="color:#64748b;">{prop_type.replace('player_','').upper()} | {game}</div>
                        <div style="margin-top:0.5rem; padding:0.3rem 0.6rem; background:{rec_color}; display:inline-block;">
                            <span style="color:white; font-weight:bold;">ALGO: {rec}</span>
                        </div>
                    </div>
                """, unsafe_allow_html=True)
                
                # Key metrics
                mc1, mc2, mc3 = st.columns(3)
                mc1.metric("Consensus", row["avg_line"])
                mc2.metric("Projection", proj_data["projection"], f"{proj_data['delta']:+.1f}")
                mc3.metric("Confidence", f"{proj_data['confidence']}%")
                
                mc4, mc5, mc6 = st.columns(3)
                mc4.metric("Units", proj_data["units"])
                mc5.metric("Spread", f"{row['spread']:.1f}")
                mc6.metric("Volatility", proj_data["volatility"])
                
                # SECTION 2: Sportsbook Grid
                st.markdown("**SPORTSBOOK LINES**")
                if not all_books.empty:
                    book_rows = []
                    for _, b in all_books.sort_values("line").iterrows():
                        is_best_o = b["line"] == row["min_line"]
                        is_best_u = b["line"] == row["max_line"]
                        book_rows.append({
                            "Book": b["sportsbook"],
                            "Line": b["line"],
                            "Over": format_odds(b["over_odds"]),
                            "Under": format_odds(b["under_odds"]),
                            "": "▲ BEST" if is_best_o else "▼ BEST" if is_best_u else ""
                        })
                    st.dataframe(pd.DataFrame(book_rows), hide_index=True, height=200, use_container_width=True)
                
                # SECTION 3: Trends
                st.markdown("**PERFORMANCE TREND**")
                if not game_log.empty and "stat_value" in game_log.columns:
                    game_log_sorted = game_log.sort_values("game_date")
                    game_log_sorted["hit"] = game_log_sorted["stat_value"] > row["avg_line"]
                    game_log_sorted["color"] = game_log_sorted["hit"].map({True: "#22c55e", False: "#ef4444"})
                    
                    fig = go.Figure()
                    fig.add_trace(go.Bar(
                        x=list(range(len(game_log_sorted))),
                        y=game_log_sorted["stat_value"],
                        marker_color=game_log_sorted["color"].tolist(),
                        text=game_log_sorted["stat_value"].round(0).astype(int),
                        textposition="outside"
                    ))
                    fig.add_hline(y=row["avg_line"], line_dash="dash", line_color="#4ade80",
                                  annotation_text=f"Line: {row['avg_line']}")
                    fig.update_layout(
                        height=180, margin=dict(l=0,r=0,t=20,b=0),
                        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                        xaxis=dict(showticklabels=False, showgrid=False),
                        yaxis=dict(showgrid=False, color="#64748b"),
                        showlegend=False
                    )
                    st.plotly_chart(fig, use_container_width=True)
                    
                    # Hit rates
                    hr1, hr2, hr3, hr4 = st.columns(4)
                    hr1.metric("L5", hit_rates["L5"])
                    hr2.metric("L10", hit_rates["L10"])
                    hr3.metric("L15", hit_rates["L15"])
                    hr4.metric("Season", hit_rates["Season"])
                else:
                    st.info("No game log data available")
                
                # SECTION 4: AI Insights
                st.markdown("**AI INSIGHTS**")
                for insight in insights:
                    st.markdown(f"<div style='color:#94a3b8; font-size:0.85rem; padding:0.2rem 0; font-family:monospace;'>• {insight}</div>", unsafe_allow_html=True)
                
                # Matchup data
                if row["away_team"]:
                    matchup = get_matchup_data(row["away_team"])
                    st.markdown("**MATCHUP**")
                    mu1, mu2, mu3 = st.columns(3)
                    mu1.metric("Def Rank", f"#{matchup['def_rating']}")
                    mu2.metric("Pace", matchup["pace"])
                    mu3.metric("Pts Allow", matchup["pts_allowed"])
        
        else:
            st.markdown("""
                <div style="background:#1e293b; padding:2rem; text-align:center; font-family:monospace;">
                    <p style="color:#64748b;">Select a player from the scanner</p>
                </div>
            """, unsafe_allow_html=True)
    
    st.markdown("<hr style='border-color:#1e293b; margin:1rem 0;'>", unsafe_allow_html=True)
    
    # =========================================================================
    # MARKET DISCREPANCIES
    # =========================================================================
    if not screenshot_mode:
        st.markdown("### MARKET DISCREPANCIES")
        disc = summary_df[(summary_df["spread"] >= 2.5) & (summary_df["books_count"] >= 4)].nlargest(8, "spread")
        
        d_cols = st.columns(4)
        for idx, (_, d) in enumerate(disc.iterrows()):
            with d_cols[idx % 4]:
                st.markdown(f"""
                    <div style="background:#0f172a; border:1px solid #22c55e; padding:0.6rem; margin-bottom:0.5rem; font-family:monospace;">
                        <div style="color:white; font-weight:bold; font-size:0.9rem;">{d["player_name"][:15]}</div>
                        <div style="color:#64748b; font-size:0.75rem;">{d["prop_type"].replace("player_","").upper()}</div>
                        <div style="color:#22c55e; font-size:0.85rem;">{d["min_line"]} → {d["max_line"]}</div>
                        <div style="color:#4ade80; font-weight:bold;">Spread: {d["spread"]:.1f}</div>
                    </div>
                """, unsafe_allow_html=True)
    
    # =========================================================================
    # SPORTSBOOK HEATMAP
    # =========================================================================
    if not screenshot_mode:
        with st.expander("SPORTSBOOK HEATMAP"):
            heatmap_props = summary_df.nlargest(8, "spread")
            heatmap_data = []
            
            for _, prop in heatmap_props.iterrows():
                _, _, prop_books = get_best_books(books_df, prop["player_name"], prop["prop_type"], prop["game_label"])
                if not prop_books.empty:
                    for _, book in prop_books.iterrows():
                        diff = book["line"] - prop["avg_line"]
                        heatmap_data.append({
                            "Prop": f"{prop['player_name'][:10]} {prop['prop_type'].replace('player_','')[:3].upper()}",
                            "Book": book["sportsbook"][:8],
                            "Diff": diff
                        })
            
            if heatmap_data:
                hm_df = pd.DataFrame(heatmap_data)
                pivot = hm_df.pivot_table(index="Prop", columns="Book", values="Diff", aggfunc="first")
                
                fig = px.imshow(pivot, color_continuous_scale=["#ef4444", "#1e293b", "#22c55e"],
                               color_continuous_midpoint=0, aspect="auto")
                fig.update_layout(height=350, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
                st.plotly_chart(fig, use_container_width=True)
    
    # =========================================================================
    # RAW LINES (Debug)
    # =========================================================================
    if not screenshot_mode:
        with st.expander("RAW LINES (Debug)"):
            st.dataframe(books_df.head(150), hide_index=True, use_container_width=True)


if __name__ == "__main__":
    st.set_page_config(page_title="Props Engine", layout="wide")
    st.warning("Import render_props_engine() into your dashboard")
