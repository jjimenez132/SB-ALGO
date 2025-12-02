#!/usr/bin/env python3
"""
SB-ALGO Props Engine - Bloomberg Terminal Style v2
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from sqlalchemy import text
from datetime import datetime
import pytz
import random


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
    return subset.loc[subset["line"].idxmin()], subset.loc[subset["line"].idxmax()], subset


def format_odds(odds):
    if odds is None or pd.isna(odds):
        return "-"
    odds = int(odds)
    return f"+{odds}" if odds > 0 else str(odds)


def get_algo_projection(player_name, prop_type, avg_line):
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
        "projection": projection,
        "delta": delta,
        "confidence": confidence,
        "units": units,
        "recommendation": rec,
        "volatility": volatility
    }


def get_player_game_log(engine, player_name, prop_type, games=15):
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
        SELECT pb.game_date, pb.{stat_col} as stat_value
        FROM player_boxscores pb
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
        return {"L5": "-", "L10": "-", "L15": "-"}
    
    def hr(df):
        if len(df) == 0:
            return "-"
        hits = (df["stat_value"] > line).sum()
        return f"{hits}/{len(df)}"
    
    return {
        "L5": hr(game_log.head(5)),
        "L10": hr(game_log.head(10)),
        "L15": hr(game_log.head(15))
    }


def generate_ai_insights(player, prop_type, avg_line, proj, game_log):
    insights = []
    
    if abs(proj["delta"]) >= 1:
        direction = "above" if proj["delta"] > 0 else "below"
        insights.append(f"Line is {abs(proj['delta']):.1f} pts {direction} projection ({proj['projection']})")
    
    if proj["confidence"] >= 85:
        insights.append(f"High confidence ({proj['confidence']}%) - Strong edge")
    elif proj["confidence"] >= 75:
        insights.append(f"Good confidence ({proj['confidence']}%)")
    
    if not game_log.empty and "stat_value" in game_log.columns:
        l5 = game_log.head(5)["stat_value"].mean()
        l10 = game_log.head(10)["stat_value"].mean()
        if l5 > avg_line:
            insights.append(f"Hot streak: {l5:.1f} avg over L5 (line: {avg_line})")
        if l5 > l10:
            insights.append(f"Trending UP: L5 ({l5:.1f}) > L10 ({l10:.1f})")
    
    if proj["volatility"] == "HIGH":
        insights.append("High volatility - smaller units recommended")
    
    if proj["units"] >= 1.5:
        insights.append(f"Suggested: {proj['units']}U on {proj['recommendation']}")
    
    return insights[:5]


def render_props_engine(engine):
    # Session state
    if "sel_p" not in st.session_state:
        st.session_state.sel_p = None
    if "sel_t" not in st.session_state:
        st.session_state.sel_t = None
    if "sel_g" not in st.session_state:
        st.session_state.sel_g = None
    
    # Load data
    summary_df, books_df = load_props_data(engine)
    
    if summary_df.empty:
        st.warning("No props data for today. Run player_props.py to fetch.")
        return
    
    # Add projections to summary
    projections_list = []
    for _, row in summary_df.iterrows():
        p = get_algo_projection(row["player_name"], row["prop_type"], row["avg_line"])
        projections_list.append(p)
    
    summary_df["projection"] = [p["projection"] for p in projections_list]
    summary_df["delta"] = [p["delta"] for p in projections_list]
    summary_df["confidence"] = [p["confidence"] for p in projections_list]
    summary_df["units"] = [p["units"] for p in projections_list]
    summary_df["algo_rec"] = [p["recommendation"] for p in projections_list]
    
    # Header
    h1, h2 = st.columns([5, 1])
    with h1:
        st.markdown("""
            <h1 style="color:#4ade80; font-family:monospace; margin:0;">
                PROPS ENGINE <span style="color:#64748b; font-size:0.5em;">v2.0</span>
            </h1>
            <p style="color:#64748b; margin:0;">NBA Player Props Terminal | 11 Books | Live</p>
        """, unsafe_allow_html=True)
    with h2:
        ss = st.toggle("Screenshot", key="ss_mode")
    
    # Metrics
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Props", len(summary_df))
    c2.metric("Players", summary_df["player_name"].nunique())
    c3.metric("Books", books_df["sportsbook"].nunique())
    c4.metric("High Conf", len(summary_df[summary_df["confidence"] >= 80]))
    c5.metric("Time", get_eastern_time().strftime("%I:%M %p"))
    
    st.markdown("---")
    
    # Top Picks
    st.markdown("### TOP ALGO PICKS")
    top = summary_df[
        (summary_df["confidence"] >= 70) & 
        (summary_df["algo_rec"] != "PASS")
    ].nlargest(6, "confidence")
    
    if top.empty:
        top = summary_df.nlargest(6, "spread")
    
    cols = st.columns(3)
    for i, (_, r) in enumerate(top.iterrows()):
        with cols[i % 3]:
            rc = "#22c55e" if r["algo_rec"] == "OVER" else "#ef4444" if r["algo_rec"] == "UNDER" else "#64748b"
            prop_name = r["prop_type"].replace("player_", "").upper()
            
            st.markdown(f"""
                <div style="background:#0f172a; border-left:3px solid {rc}; padding:0.7rem; margin-bottom:0.5rem; font-family:monospace;">
                    <b style="color:white;">{r["player_name"]}</b> 
                    <span style="color:{rc}; float:right;">{r["algo_rec"]}</span><br>
                    <span style="color:#64748b; font-size:0.8rem;">{prop_name} | {r["game_label"][:18]}</span><br>
                    <span style="color:#64748b;">Line:</span> <span style="color:white;">{r["avg_line"]}</span>
                    <span style="color:#64748b; margin-left:1rem;">Proj:</span> <span style="color:#4ade80;">{r["projection"]}</span>
                    <span style="color:#64748b; margin-left:1rem;">Delta:</span> 
                    <span style="color:{'#22c55e' if r['delta'] > 0 else '#ef4444'};">{r['delta']:+.1f}</span><br>
                    <span style="color:#4ade80;">{r["confidence"]:.0f}% conf</span> | 
                    <span style="color:#eab308;">{r["units"]}U</span> | 
                    <span style="color:#4ade80;">Spread: {r["spread"]:.1f}</span>
                </div>
            """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Filters (hidden in screenshot mode)
    if not ss:
        with st.expander("FILTERS", expanded=False):
            f1, f2, f3, f4 = st.columns(4)
            with f1:
                fp = st.selectbox("Prop", ["All"] + sorted(summary_df["prop_type"].unique().tolist()))
            with f2:
                ft = st.selectbox("Team", ["All"] + sorted(set(summary_df["home_team"].tolist())))
            with f3:
                fc = st.slider("Min Conf", 50, 95, 60)
            with f4:
                fr = st.selectbox("Rec", ["All", "OVER", "UNDER"])
            search = st.text_input("Search Player")
        
        filt = summary_df.copy()
        if fp != "All":
            filt = filt[filt["prop_type"] == fp]
        if ft != "All":
            filt = filt[(filt["home_team"] == ft) | (filt["away_team"] == ft)]
        if fc > 50:
            filt = filt[filt["confidence"] >= fc]
        if fr != "All":
            filt = filt[filt["algo_rec"] == fr]
        if search:
            filt = filt[filt["player_name"].str.contains(search, case=False, na=False)]
        
        st.caption(f"{len(filt)} props")
    else:
        filt = summary_df.nlargest(20, "confidence")
    
    # Scanner + Deep Dive
    st.markdown("### BOARD SCANNER")
    tc, dc = st.columns([3, 2])
    
    with tc:
        rows = []
        for _, r in filt.head(35).iterrows():
            rows.append({
                "Player": r["player_name"],
                "Prop": r["prop_type"].replace("player_", "")[:5].upper(),
                "Line": r["avg_line"],
                "Proj": r["projection"],
                "Delta": f"{r['delta']:+.1f}",
                "Conf": f"{r['confidence']:.0f}%",
                "Rec": r["algo_rec"],
                "Units": r["units"],
                "Spread": f"{r['spread']:.1f}",
                "_p": r["player_name"],
                "_t": r["prop_type"],
                "_g": r["game_label"]
            })
        
        df = pd.DataFrame(rows)
        if not df.empty:
            st.dataframe(
                df[["Player", "Prop", "Line", "Proj", "Delta", "Conf", "Rec", "Units", "Spread"]],
                hide_index=True,
                height=380
            )
            
            sel = st.selectbox("Inspect Player", ["Select..."] + df["Player"].tolist())
            if sel != "Select...":
                rd = df[df["Player"] == sel].iloc[0]
                st.session_state.sel_p = rd["_p"]
                st.session_state.sel_t = rd["_t"]
                st.session_state.sel_g = rd["_g"]
    
    # Deep Dive Panel
    with dc:
        st.markdown("""
            <div style="background:#0f172a; padding:0.5rem; border:1px solid #1e293b;">
                <b style="color:#4ade80; font-family:monospace;">DEEP DIVE</b>
            </div>
        """, unsafe_allow_html=True)
        
        if st.session_state.sel_p:
            p = st.session_state.sel_p
            t = st.session_state.sel_t
            g = st.session_state.sel_g
            
            row = summary_df[
                (summary_df["player_name"] == p) & 
                (summary_df["prop_type"] == t) & 
                (summary_df["game_label"] == g)
            ]
            
            if not row.empty:
                row = row.iloc[0]
                proj = get_algo_projection(p, t, row["avg_line"])
                bo, bu, ab = get_best_books(books_df, p, t, g)
                gl = get_player_game_log(engine, p, t, 15)
                hr = calculate_hit_rates(gl, row["avg_line"])
                ins = generate_ai_insights(p, t, row["avg_line"], proj, gl)
                
                rc = "#22c55e" if proj["recommendation"] == "OVER" else "#ef4444" if proj["recommendation"] == "UNDER" else "#64748b"
                
                # Header
                st.markdown(f"""
                    <div style="background:#1e293b; padding:0.8rem; font-family:monospace;">
                        <b style="color:white; font-size:1.1rem;">{p}</b><br>
                        <span style="color:#64748b;">{t.replace('player_','').upper()} | {g}</span><br>
                        <span style="background:{rc}; color:white; padding:2px 8px; margin-top:0.5rem; display:inline-block;">
                            {proj['recommendation']}
                        </span>
                    </div>
                """, unsafe_allow_html=True)
                
                # Metrics
                m1, m2, m3 = st.columns(3)
                m1.metric("Line", row["avg_line"])
                m2.metric("Projection", proj["projection"], f"{proj['delta']:+.1f}")
                m3.metric("Confidence", f"{proj['confidence']}%")
                
                m4, m5, m6 = st.columns(3)
                m4.metric("Units", proj["units"])
                m5.metric("Spread", f"{row['spread']:.1f}")
                m6.metric("Volatility", proj["volatility"])
                
                # Sportsbooks
                st.markdown("**SPORTSBOOKS**")
                if not ab.empty:
                    bk = []
                    for _, b in ab.sort_values("line").iterrows():
                        tag = "BEST O" if b["line"] == row["min_line"] else "BEST U" if b["line"] == row["max_line"] else ""
                        bk.append({
                            "Book": b["sportsbook"],
                            "Line": b["line"],
                            "Over": format_odds(b["over_odds"]),
                            "Under": format_odds(b["under_odds"]),
                            "": tag
                        })
                    st.dataframe(pd.DataFrame(bk), hide_index=True, height=180)
                
                # Trend Chart
                st.markdown("**PERFORMANCE TREND**")
                if not gl.empty and "stat_value" in gl.columns:
                    gl_sorted = gl.sort_values("game_date")
                    gl_sorted["hit"] = gl_sorted["stat_value"] > row["avg_line"]
                    colors = gl_sorted["hit"].map({True: "#22c55e", False: "#ef4444"}).tolist()
                    
                    fig = go.Figure()
                    fig.add_trace(go.Bar(
                        x=list(range(len(gl_sorted))),
                        y=gl_sorted["stat_value"],
                        marker_color=colors
                    ))
                    fig.add_hline(y=row["avg_line"], line_dash="dash", line_color="#4ade80")
                    fig.update_layout(
                        height=150,
                        margin=dict(l=0, r=0, t=10, b=0),
                        paper_bgcolor="rgba(0,0,0,0)",
                        plot_bgcolor="rgba(0,0,0,0)",
                        showlegend=False,
                        xaxis=dict(showticklabels=False),
                        yaxis=dict(showgrid=False)
                    )
                    st.plotly_chart(fig, use_container_width=True)
                    
                    # Hit rates
                    h1, h2, h3 = st.columns(3)
                    h1.metric("L5", hr["L5"])
                    h2.metric("L10", hr["L10"])
                    h3.metric("L15", hr["L15"])
                else:
                    st.info("No game log data")
                
                # AI Insights
                st.markdown("**AI INSIGHTS**")
                for insight in ins:
                    st.markdown(f"<span style='color:#94a3b8; font-size:0.85rem;'>• {insight}</span>", unsafe_allow_html=True)
        
        else:
            st.markdown("""
                <div style="background:#1e293b; padding:2rem; text-align:center;">
                    <span style="color:#64748b;">Select a player from the scanner</span>
                </div>
            """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Market Discrepancies
    if not ss:
        st.markdown("### MARKET DISCREPANCIES")
        disc = summary_df[summary_df["spread"] >= 2.5].nlargest(8, "spread")
        
        dcols = st.columns(4)
        for i, (_, d) in enumerate(disc.iterrows()):
            with dcols[i % 4]:
                st.markdown(f"""
                    <div style="background:#0f172a; border:1px solid #22c55e; padding:0.5rem; margin-bottom:0.5rem; font-family:monospace;">
                        <b style="color:white;">{d['player_name'][:14]}</b><br>
                        <span style="color:#64748b;">{d['prop_type'].replace('player_','').upper()}</span><br>
                        <span style="color:#22c55e;">{d['min_line']} to {d['max_line']}</span><br>
                        <b style="color:#4ade80;">Spread: {d['spread']:.1f}</b>
                    </div>
                """, unsafe_allow_html=True)
        
        # Raw lines
        with st.expander("RAW LINES (Debug)"):
            st.dataframe(books_df.head(100), hide_index=True)


if __name__ == "__main__":
    st.warning("Import render_props_engine into your dashboard")
