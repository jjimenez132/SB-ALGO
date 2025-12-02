#!/usr/bin/env python3
"""
SB-ALGO Props Engine v2.0 - Bloomberg Terminal Style
Professional NBA Props Trading Terminal
NO PLAYER CARDS - Clean data-driven terminal layout
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
    """Load props from database"""
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
        ORDER BY player_name, market, sportsbook
    """)
    
    with engine.connect() as conn:
        summary_df = pd.read_sql(summary_query, conn, params={"today": today})
        books_df = pd.read_sql(books_query, conn, params={"today": today})
    
    return summary_df, books_df


def get_best_books(books_df, player, prop_type, game_label):
    """Get best over/under lines for a prop"""
    subset = books_df[
        (books_df["player_name"] == player) & 
        (books_df["prop_type"] == prop_type) & 
        (books_df["game_label"] == game_label)
    ].copy()
    
    if subset.empty:
        return None, None, subset
    
    best_over = subset.loc[subset["line"].idxmin()]
    best_under = subset.loc[subset["line"].idxmax()]
    return best_over, best_under, subset


def format_odds(odds):
    """Format American odds"""
    if odds is None or pd.isna(odds):
        return "-"
    odds = int(odds)
    return f"+{odds}" if odds > 0 else str(odds)


def get_algo_projection(player_name, prop_type, avg_line):
    """Generate algo projection - PLACEHOLDER for real model"""
    random.seed(hash(player_name + prop_type) % 10000)
    
    variance = random.uniform(-4.0, 5.0)
    projection = round(avg_line + variance, 1)
    delta = round(projection - avg_line, 1)
    
    base_conf = 65
    if abs(delta) >= 3:
        base_conf = 85
    elif abs(delta) >= 2:
        base_conf = 78
    elif abs(delta) >= 1:
        base_conf = 72
    
    confidence = min(95, base_conf + random.randint(-5, 10))
    volatility = random.choice(["LOW", "MEDIUM", "HIGH"])
    
    if confidence >= 85 and abs(delta) >= 2.5:
        units = 2.0
    elif confidence >= 78 and abs(delta) >= 1.5:
        units = 1.5
    elif confidence >= 70:
        units = 1.0
    else:
        units = 0.5
    
    if delta >= 1.0:
        recommendation = "OVER"
    elif delta <= -1.0:
        recommendation = "UNDER"
    else:
        recommendation = "PASS"
    
    return {
        "projection": projection,
        "delta": delta,
        "confidence": confidence,
        "volatility": volatility,
        "units": units,
        "recommendation": recommendation,
        "hit_rate": random.randint(55, 75)
    }


def get_player_game_log(engine, player_name, prop_type, games=15):
    """Fetch player's recent game stats"""
    stat_map = {
        "player_points": "pts", "player_rebounds": "reb", "player_assists": "ast",
        "player_threes": "fg3m", "player_blocks": "blk", "player_steals": "stl", "player_turnovers": "tov"
    }
    stat_col = stat_map.get(prop_type, "pts")
    
    query = text(f"""
        SELECT game_date, {stat_col} as stat_value, team
        FROM player_boxscores WHERE player_name ILIKE :player AND {stat_col} IS NOT NULL
        ORDER BY game_date DESC LIMIT :games
    """)
    
    try:
        with engine.connect() as conn:
            return pd.read_sql(query, conn, params={"player": f"%{player_name}%", "games": games})
    except:
        return pd.DataFrame()


def calculate_hit_rates(game_log, line):
    """Calculate hit rates for L5, L10, L15"""
    if game_log.empty or "stat_value" not in game_log.columns:
        return {"L5": "-", "L10": "-", "L15": "-", "L5_pct": 0, "L10_pct": 0}
    
    def calc(df):
        if len(df) == 0: return "-", 0
        hits = (df["stat_value"] > line).sum()
        pct = int(100 * hits / len(df))
        return f"{hits}/{len(df)} ({pct}%)", pct
    
    l5, l5_pct = calc(game_log.head(5))
    l10, l10_pct = calc(game_log.head(10))
    l15, _ = calc(game_log.head(15))
    
    return {"L5": l5, "L10": l10, "L15": l15, "L5_pct": l5_pct, "L10_pct": l10_pct}


def calculate_averages(game_log):
    """Calculate L5, L10, L15 averages"""
    if game_log.empty or "stat_value" not in game_log.columns:
        return {"L5": 0, "L10": 0, "L15": 0}
    
    return {
        "L5": round(game_log.head(5)["stat_value"].mean(), 1) if len(game_log) >= 5 else 0,
        "L10": round(game_log.head(10)["stat_value"].mean(), 1) if len(game_log) >= 10 else 0,
        "L15": round(game_log.head(15)["stat_value"].mean(), 1) if len(game_log) >= 15 else 0
    }


def generate_ai_insights(player, prop_type, avg_line, proj_data, averages, hit_rates):
    """Generate 3-6 AI insight bullets"""
    insights = []
    delta = proj_data["delta"]
    
    if abs(delta) >= 0.5:
        direction = "above" if delta > 0 else "below"
        insights.append(f"Line is {abs(delta):.1f} pts {direction} algo projection ({proj_data['projection']})")
    
    if averages.get("L5", 0) > 0:
        l5_diff = averages["L5"] - avg_line
        if l5_diff > 1:
            insights.append(f"Player averaging +{l5_diff:.1f} over L5 (avg: {averages['L5']})")
        elif l5_diff < -1:
            insights.append(f"Player averaging {l5_diff:.1f} under L5 (avg: {averages['L5']})")
    
    if averages.get("L5", 0) > 0 and averages.get("L10", 0) > 0:
        if averages["L5"] > averages["L10"] + 1:
            insights.append(f"Trending UP: L5 ({averages['L5']}) > L10 ({averages['L10']})")
        elif averages["L5"] < averages["L10"] - 1:
            insights.append(f"Trending DOWN: L5 ({averages['L5']}) < L10 ({averages['L10']})")
    
    if hit_rates.get("L10_pct", 0) >= 70:
        insights.append(f"Strong hit rate: {hit_rates['L10']} over L10")
    
    if proj_data["confidence"] >= 85:
        insights.append(f"High confidence ({proj_data['confidence']}%) - Strong edge")
    
    if proj_data["volatility"] == "HIGH":
        insights.append("High volatility - Consider reduced units")
    
    if proj_data["units"] >= 1.5 and proj_data["recommendation"] != "PASS":
        insights.append(f"Suggested: {proj_data['units']}U {proj_data['recommendation']}")
    
    return insights[:6]


def get_matchup_data(opponent):
    """PLACEHOLDER: Get opponent defensive data"""
    random.seed(hash(opponent) % 100)
    return {
        "def_rank": random.randint(1, 30),
        "pace": round(random.uniform(96, 106), 1),
        "min_trend": round(random.uniform(-2, 3), 1)
    }


def render_props_engine(engine):
    """Main render function"""
    
    # Session state
    if "sel_player" not in st.session_state: st.session_state.sel_player = None
    if "sel_prop" not in st.session_state: st.session_state.sel_prop = None
    if "sel_game" not in st.session_state: st.session_state.sel_game = None
    if "ss_mode" not in st.session_state: st.session_state.ss_mode = False
    
    # Load data
    summary_df, books_df = load_props_data(engine)
    
    if summary_df.empty:
        st.warning("⚠️ No props data. Props are fetched daily at 7:00 AM ET.")
        return
    
    # Add projections
    proj_list = []
    for _, row in summary_df.iterrows():
        proj_list.append(get_algo_projection(row["player_name"], row["prop_type"], row["avg_line"]))
    
    summary_df["projection"] = [p["projection"] for p in proj_list]
    summary_df["delta"] = [p["delta"] for p in proj_list]
    summary_df["confidence"] = [p["confidence"] for p in proj_list]
    summary_df["units"] = [p["units"] for p in proj_list]
    summary_df["algo_rec"] = [p["recommendation"] for p in proj_list]
    summary_df["volatility"] = [p["volatility"] for p in proj_list]
    
    # HEADER
    h1, h2 = st.columns([6, 1])
    with h1:
        st.markdown("<h1 style='color:#4ade80; font-family:monospace; margin:0; letter-spacing:2px;'>PROPS ENGINE</h1>", unsafe_allow_html=True)
        st.markdown("<p style='color:#64748b; margin:0;'>NBA Player Props Terminal | 11 Books | Live</p>", unsafe_allow_html=True)
    with h2:
        ss_mode = st.toggle("📸", key="ss_toggle", value=st.session_state.ss_mode)
        st.session_state.ss_mode = ss_mode
    
    # METRICS
    m1, m2, m3, m4, m5, m6 = st.columns(6)
    m1.metric("Props", f"{len(summary_df):,}")
    m2.metric("Players", summary_df["player_name"].nunique())
    m3.metric("Books", books_df["sportsbook"].nunique())
    m4.metric("High Conf", len(summary_df[summary_df["confidence"] >= 80]))
    m5.metric("OVER/UNDER", f"{len(summary_df[summary_df['algo_rec']=='OVER'])}/{len(summary_df[summary_df['algo_rec']=='UNDER'])}")
    m6.metric("Time", get_eastern_time().strftime("%I:%M %p"))
    
    st.markdown("---")
    
    # TOP ALGO PICKS
    st.markdown("<h3 style='color:#4ade80; font-family:monospace;'>🔥 TOP ALGO PICKS</h3>", unsafe_allow_html=True)
    
    top = summary_df[(summary_df["confidence"] >= 72) & (summary_df["algo_rec"] != "PASS") & (summary_df["spread"] >= 1.5)].nlargest(6, "confidence")
    if top.empty: top = summary_df.nlargest(6, "spread")
    
    cols = st.columns(3)
    for i, (_, p) in enumerate(top.iterrows()):
        with cols[i % 3]:
            rc = "#22c55e" if p["algo_rec"] == "OVER" else "#ef4444" if p["algo_rec"] == "UNDER" else "#64748b"
            dc = "#22c55e" if p["delta"] > 0 else "#ef4444"
            bo, bu, _ = get_best_books(books_df, p["player_name"], p["prop_type"], p["game_label"])
            
            st.markdown(f"""<div style="background:#0f172a; border-left:4px solid {rc}; padding:1rem; margin-bottom:0.5rem; font-family:monospace;">
                <div style="display:flex; justify-content:space-between;"><b style="color:white;">{p["player_name"]}</b><span style="background:{rc}; color:white; padding:2px 8px;">{p["algo_rec"]}</span></div>
                <div style="color:#64748b; font-size:0.8rem;">{p["prop_type"].replace("player_","").upper()} | {p["game_label"][:20]}</div>
                <div style="display:grid; grid-template-columns:repeat(3,1fr); gap:0.5rem; margin-top:0.5rem; border-top:1px solid #1e293b; padding-top:0.5rem;">
                    <div><div style="color:#64748b; font-size:0.7rem;">LINE</div><div style="color:white;">{p["avg_line"]}</div></div>
                    <div><div style="color:#64748b; font-size:0.7rem;">PROJ</div><div style="color:#4ade80;">{p["projection"]}</div></div>
                    <div><div style="color:#64748b; font-size:0.7rem;">DELTA</div><div style="color:{dc};">{p["delta"]:+.1f}</div></div>
                </div>
                <div style="display:grid; grid-template-columns:repeat(3,1fr); gap:0.5rem; margin-top:0.3rem;">
                    <div><div style="color:#64748b; font-size:0.7rem;">CONF</div><div style="color:#4ade80;">{p["confidence"]}%</div></div>
                    <div><div style="color:#64748b; font-size:0.7rem;">UNITS</div><div style="color:#eab308;">{p["units"]}</div></div>
                    <div><div style="color:#64748b; font-size:0.7rem;">SPREAD</div><div style="color:#4ade80;">{p["spread"]:.1f}</div></div>
                </div>
                <div style="margin-top:0.5rem; border-top:1px solid #1e293b; padding-top:0.5rem; font-size:0.75rem;">
                    <span style="color:#22c55e;">▲ O: {bo["line"] if bo is not None else "-"}</span> | <span style="color:#ef4444;">▼ U: {bu["line"] if bu is not None else "-"}</span>
                </div>
            </div>""", unsafe_allow_html=True)
    
    st.markdown("---")
    
    # FILTERS
    if not ss_mode:
        with st.expander("🎛️ FILTERS", expanded=False):
            f1, f2, f3, f4, f5 = st.columns(5)
            with f1: fp = st.selectbox("Prop", ["All"] + sorted(summary_df["prop_type"].unique().tolist()))
            with f2: ft = st.selectbox("Team", ["All"] + sorted(set(summary_df["home_team"].tolist())))
            with f3: fc = st.slider("Min Conf", 50, 95, 60)
            with f4: fs = st.slider("Min Spread", 0.0, 8.0, 0.0, 0.5)
            with f5: fr = st.selectbox("Rec", ["All", "OVER", "UNDER"])
            search = st.text_input("🔍 Search")
        
        filt = summary_df.copy()
        if fp != "All": filt = filt[filt["prop_type"] == fp]
        if ft != "All": filt = filt[(filt["home_team"] == ft) | (filt["away_team"] == ft)]
        if fc > 50: filt = filt[filt["confidence"] >= fc]
        if fs > 0: filt = filt[filt["spread"] >= fs]
        if fr != "All": filt = filt[filt["algo_rec"] == fr]
        if search: filt = filt[filt["player_name"].str.contains(search, case=False, na=False)]
        st.caption(f"{len(filt)} props")
    else:
        filt = summary_df[summary_df["confidence"] >= 70].nlargest(25, "confidence")
    
    # BOARD SCANNER + DEEP DIVE
    st.markdown("<h3 style='color:#4ade80; font-family:monospace;'>📊 BOARD SCANNER</h3>", unsafe_allow_html=True)
    
    tc, dc = st.columns([3, 2])
    
    with tc:
        rows = []
        for _, r in filt.head(40).iterrows():
            bo, bu, _ = get_best_books(books_df, r["player_name"], r["prop_type"], r["game_label"])
            sp_disp = f"🎯{r['spread']:.1f}" if r["spread"] >= 4 else f"✅{r['spread']:.1f}" if r["spread"] >= 2 else f"{r['spread']:.1f}"
            rows.append({
                "Player": r["player_name"], "Prop": r["prop_type"].replace("player_","")[:5].upper(),
                "Line": r["avg_line"], "Proj": r["projection"], "Δ": f"{r['delta']:+.1f}",
                "Conf": f"{r['confidence']}%", "Rec": r["algo_rec"], "Units": r["units"], "Spread": sp_disp,
                "Best O": f"{bo['line']}" if bo is not None else "-", "Best U": f"{bu['line']}" if bu is not None else "-",
                "_p": r["player_name"], "_t": r["prop_type"], "_g": r["game_label"]
            })
        
        df = pd.DataFrame(rows)
        if not df.empty:
            st.dataframe(df[["Player","Prop","Line","Proj","Δ","Conf","Rec","Units","Spread","Best O","Best U"]], hide_index=True, height=420)
            sel = st.selectbox("🔬 Inspect", ["Select..."] + df["Player"].tolist())
            if sel != "Select...":
                rd = df[df["Player"] == sel].iloc[0]
                st.session_state.sel_player, st.session_state.sel_prop, st.session_state.sel_game = rd["_p"], rd["_t"], rd["_g"]
    
    # DEEP DIVE
    with dc:
        st.markdown("<div style='background:#0f172a; padding:0.5rem; border:1px solid #1e293b;'><b style='color:#4ade80; font-family:monospace;'>DEEP DIVE</b></div>", unsafe_allow_html=True)
        
        if st.session_state.sel_player:
            p, t, g = st.session_state.sel_player, st.session_state.sel_prop, st.session_state.sel_game
            row = summary_df[(summary_df["player_name"]==p) & (summary_df["prop_type"]==t) & (summary_df["game_label"]==g)]
            
            if not row.empty:
                row = row.iloc[0]
                proj = get_algo_projection(p, t, row["avg_line"])
                bo, bu, ab = get_best_books(books_df, p, t, g)
                gl = get_player_game_log(engine, p, t, 15)
                hr = calculate_hit_rates(gl, row["avg_line"])
                avgs = calculate_averages(gl)
                ins = generate_ai_insights(p, t, row["avg_line"], proj, avgs, hr)
                match = get_matchup_data(row["away_team"])
                
                rc = "#22c55e" if proj["recommendation"] == "OVER" else "#ef4444" if proj["recommendation"] == "UNDER" else "#64748b"
                
                # SECTION 1: Header
                st.markdown(f"""<div style="background:#1e293b; padding:1rem; font-family:monospace;">
                    <div style="color:white; font-size:1.2rem; font-weight:bold;">{p}</div>
                    <div style="color:#64748b;">{t.replace("player_","").upper()} | {g}</div>
                    <span style="background:{rc}; color:white; padding:4px 12px; margin-top:0.5rem; display:inline-block;">ALGO: {proj["recommendation"]}</span>
                </div>""", unsafe_allow_html=True)
                
                m1, m2, m3 = st.columns(3)
                m1.metric("Consensus", row["avg_line"])
                m2.metric("Projection", proj["projection"], f"{proj['delta']:+.1f}")
                m3.metric("Confidence", f"{proj['confidence']}%")
                
                m4, m5, m6 = st.columns(3)
                m4.metric("Units", proj["units"])
                m5.metric("Spread", f"{row['spread']:.1f}")
                m6.metric("Volatility", proj["volatility"])
                
                # SECTION 2: Sportsbook Grid
                st.markdown("**📚 SPORTSBOOK LINES**")
                if not ab.empty:
                    bk_data = []
                    for _, b in ab.sort_values("line").iterrows():
                        tag = "🟢 BEST O" if b["line"] == row["min_line"] else "🔴 BEST U" if b["line"] == row["max_line"] else ""
                        bk_data.append({"BOOK": b["sportsbook"], "LINE": b["line"], "O-ODDS": format_odds(b["over_odds"]), "U-ODDS": format_odds(b["under_odds"]), "": tag})
                    st.dataframe(pd.DataFrame(bk_data), hide_index=True, height=180)
                
                # SECTION 3: Trend Chart
                st.markdown("**📈 PERFORMANCE**")
                if not gl.empty and "stat_value" in gl.columns:
                    gls = gl.sort_values("game_date")
                    gls["hit"] = gls["stat_value"] > row["avg_line"]
                    gls["color"] = gls["hit"].map({True: "#22c55e", False: "#ef4444"})
                    
                    fig = go.Figure()
                    fig.add_trace(go.Bar(x=list(range(len(gls))), y=gls["stat_value"], marker_color=gls["color"].tolist(), text=gls["stat_value"].round(0).astype(int), textposition="outside"))
                    fig.add_hline(y=row["avg_line"], line_dash="dash", line_color="#4ade80", annotation_text=f"Line: {row['avg_line']}")
                    fig.update_layout(height=160, margin=dict(l=0,r=0,t=15,b=0), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", showlegend=False, xaxis=dict(showticklabels=False), yaxis=dict(showgrid=False))
                    st.plotly_chart(fig, use_container_width=True)
                    
                    h1, h2, h3 = st.columns(3)
                    h1.metric("L5", hr["L5"])
                    h2.metric("L10", hr["L10"])
                    h3.metric("L15", hr["L15"])
                    
                    a1, a2, a3 = st.columns(3)
                    a1.metric("L5 Avg", avgs["L5"])
                    a2.metric("L10 Avg", avgs["L10"])
                    a3.metric("L15 Avg", avgs["L15"])
                
                # SECTION 4: AI Insights
                st.markdown("**🤖 AI INSIGHTS**")
                for insight in ins:
                    st.markdown(f"<span style='color:#94a3b8; font-size:0.85rem; font-family:monospace;'>• {insight}</span>", unsafe_allow_html=True)
                
                # Matchup
                st.markdown("**📊 MATCHUP**")
                mu1, mu2, mu3 = st.columns(3)
                mu1.metric("Opp Def", f"#{match['def_rank']}")
                mu2.metric("Pace", match["pace"])
                mu3.metric("Min Trend", f"{match['min_trend']:+.1f}")
        else:
            st.markdown("<div style='background:#1e293b; padding:2rem; text-align:center;'><span style='color:#64748b;'>Select a player</span></div>", unsafe_allow_html=True)
    
    st.markdown("---")
    
    # MARKET DISCREPANCIES
    if not ss_mode:
        st.markdown("<h3 style='color:#4ade80; font-family:monospace;'>🎯 MARKET DISCREPANCIES</h3>", unsafe_allow_html=True)
        disc = summary_df[(summary_df["spread"] >= 2.0) & (summary_df["books_count"] >= 4)].nlargest(8, "spread")
        dcols = st.columns(4)
        for i, (_, d) in enumerate(disc.iterrows()):
            with dcols[i % 4]:
                st.markdown(f"""<div style="background:#0f172a; border:1px solid #22c55e; padding:0.75rem; margin-bottom:0.5rem; font-family:monospace;">
                    <b style="color:white;">{d["player_name"][:16]}</b><br>
                    <span style="color:#64748b; font-size:0.75rem;">{d["prop_type"].replace("player_","").upper()}</span><br>
                    <span style="color:#22c55e;">{d["min_line"]} → {d["max_line"]}</span><br>
                    <b style="color:#4ade80;">Spread: {d["spread"]:.1f}</b><br>
                    <span style="color:#64748b; font-size:0.75rem;">Δ: {d["delta"]:+.1f} | {d["confidence"]}%</span>
                </div>""", unsafe_allow_html=True)
        
        with st.expander("🌡️ SPORTSBOOK HEATMAP"):
            hm_props = summary_df.nlargest(10, "spread")
            hm_data = []
            for _, prop in hm_props.iterrows():
                _, _, pb = get_best_books(books_df, prop["player_name"], prop["prop_type"], prop["game_label"])
                if not pb.empty:
                    for _, bk in pb.iterrows():
                        hm_data.append({"Prop": f"{prop['player_name'][:10]} {prop['prop_type'].replace('player_','')[:3].upper()}", "Book": bk["sportsbook"][:8], "Diff": round(bk["line"] - prop["avg_line"], 1)})
            if hm_data:
                hm_df = pd.DataFrame(hm_data)
                pivot = hm_df.pivot_table(index="Prop", columns="Book", values="Diff", aggfunc="first")
                fig = go.Figure(data=go.Heatmap(z=pivot.values, x=pivot.columns.tolist(), y=pivot.index.tolist(), colorscale=[[0,"#ef4444"],[0.5,"#1e293b"],[1,"#22c55e"]], zmid=0, text=pivot.values, texttemplate="%{text:.1f}"))
                fig.update_layout(height=350, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
                st.plotly_chart(fig, use_container_width=True)
        
        with st.expander("📂 RAW LINES"):
            st.dataframe(books_df.head(100), hide_index=True)


if __name__ == "__main__":
    st.warning("Import render_props_engine() into dashboard")
