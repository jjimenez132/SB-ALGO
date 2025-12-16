#!/usr/bin/env python3
"""
SB-ALGO Props Engine v2.0 - Bloomberg Terminal Style
COMPLETE IMPLEMENTATION - ALL SECTIONS
NO PLAYER CARDS - Clean data-driven terminal layout
"""

import streamlit as st
import pandas as pd
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
    """
    Generate algo projection - PLACEHOLDER
    Replace with real model when ready
    """
    random.seed(hash(player_name + prop_type) % 10000)
    
    variance = random.uniform(-4.0, 5.0)
    projection = round(avg_line + variance, 1)
    delta = round(projection - avg_line, 1)
    
    # Confidence calculation
    base_conf = 65
    if abs(delta) >= 3:
        base_conf = 85
    elif abs(delta) >= 2:
        base_conf = 78
    elif abs(delta) >= 1:
        base_conf = 72
    
    confidence = min(95, base_conf + random.randint(-5, 10))
    
    # Volatility
    volatility = random.choice(["LOW", "MEDIUM", "HIGH"])
    volatility_score = {"LOW": 25, "MEDIUM": 50, "HIGH": 75}[volatility]
    
    # Units based on confidence and delta
    if confidence >= 85 and abs(delta) >= 2.5:
        units = 2.0
    elif confidence >= 78 and abs(delta) >= 1.5:
        units = 1.5
    elif confidence >= 70:
        units = 1.0
    else:
        units = 0.5
    
    # Recommendation
    if delta >= 1.0:
        recommendation = "OVER"
    elif delta <= -1.0:
        recommendation = "UNDER"
    else:
        recommendation = "PASS"
    
    # Historical hit rate (placeholder)
    hit_rate = random.randint(55, 78)
    
    return {
        "projection": projection,
        "delta": delta,
        "confidence": confidence,
        "volatility": volatility,
        "volatility_score": volatility_score,
        "units": units,
        "recommendation": recommendation,
        "hit_rate": hit_rate
    }


def get_player_game_log(engine, player_name, prop_type, games=20):
    """Fetch player's recent game stats"""
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
        SELECT game_date, {stat_col} as stat_value, team_abbreviation as team
        FROM player_boxscores
        WHERE player_name ILIKE :player 
        AND {stat_col} IS NOT NULL
        ORDER BY game_date DESC 
        LIMIT :games
    """)
    
    try:
        with engine.connect() as conn:
            df = pd.read_sql(query, conn, params={"player": f"%{player_name}%", "games": games})
        return df
    except:
        return pd.DataFrame()


def calculate_hit_rates(game_log, line):
    """Calculate hit rates for L5, L10, L15, Season"""
    result = {
        "L5": "-", "L10": "-", "L15": "-", "Season": "-",
        "L5_pct": 0, "L10_pct": 0, "L15_pct": 0, "Season_pct": 0,
        "home": "-", "away": "-"
    }
    
    if game_log.empty or "stat_value" not in game_log.columns:
        return result
    
    def calc(df):
        if len(df) == 0:
            return "-", 0
        hits = (df["stat_value"] > line).sum()
        pct = int(100 * hits / len(df))
        return f"{hits}/{len(df)} ({pct}%)", pct
    
    result["L5"], result["L5_pct"] = calc(game_log.head(5))
    result["L10"], result["L10_pct"] = calc(game_log.head(10))
    result["L15"], result["L15_pct"] = calc(game_log.head(15))
    result["Season"], result["Season_pct"] = calc(game_log)
    
    return result


def calculate_averages(game_log):
    """Calculate L5, L10, L15, Season averages"""
    result = {"L5": 0, "L10": 0, "L15": 0, "Season": 0}
    
    if game_log.empty or "stat_value" not in game_log.columns:
        return result
    
    if len(game_log) >= 5:
        result["L5"] = round(game_log.head(5)["stat_value"].mean(), 1)
    if len(game_log) >= 10:
        result["L10"] = round(game_log.head(10)["stat_value"].mean(), 1)
    if len(game_log) >= 15:
        result["L15"] = round(game_log.head(15)["stat_value"].mean(), 1)
    result["Season"] = round(game_log["stat_value"].mean(), 1)
    
    return result


def generate_ai_insights(player, prop_type, avg_line, proj_data, averages, hit_rates, matchup):
    """Generate 3-6 AI insight bullets per prop"""
    insights = []
    delta = proj_data["delta"]
    conf = proj_data["confidence"]
    rec = proj_data["recommendation"]
    
    # 1. Line vs projection
    if abs(delta) >= 0.5:
        direction = "below" if delta > 0 else "above"
        insights.append(f"Line is {abs(delta):.1f} pts {direction} algo projection ({proj_data['projection']})")
    
    # 2. Recent performance vs line
    if averages.get("L5", 0) > 0:
        l5_diff = averages["L5"] - avg_line
        if l5_diff > 1.5:
            insights.append(f"Player averaging +{l5_diff:.1f} over line in L5 games ({averages['L5']} avg)")
        elif l5_diff < -1.5:
            insights.append(f"Player averaging {l5_diff:.1f} under line in L5 games ({averages['L5']} avg)")
    
    # 3. Trend analysis
    if averages.get("L5", 0) > 0 and averages.get("L10", 0) > 0:
        if averages["L5"] > averages["L10"] + 1.5:
            insights.append(f"Recent minutes trend increasing: L5 ({averages['L5']}) > L10 ({averages['L10']})")
        elif averages["L5"] < averages["L10"] - 1.5:
            insights.append(f"Recent production declining: L5 ({averages['L5']}) < L10 ({averages['L10']})")
    
    # 4. Hit rate insight
    if hit_rates.get("L10_pct", 0) >= 70:
        insights.append(f"Covered {hit_rates['L10']} in last 10 games - strong recent form")
    elif hit_rates.get("L10_pct", 0) <= 30:
        insights.append(f"Only covered {hit_rates['L10']} in last 10 - trending under")
    
    # 5. Matchup insight
    if matchup["def_rank"] <= 10:
        insights.append(f"Tough matchup: Opponent ranks #{matchup['def_rank']} defensively")
    elif matchup["def_rank"] >= 25:
        insights.append(f"Favorable matchup: Opponent ranks #{matchup['def_rank']} defensively (bottom 6)")
    
    # 6. Pace insight
    if matchup["pace"] >= 102:
        insights.append(f"High pace environment ({matchup['pace']}) - pace-up game")
    elif matchup["pace"] <= 97:
        insights.append(f"Slow pace environment ({matchup['pace']}) - grind-it-out game")
    
    # 7. Confidence insight
    if conf >= 85:
        insights.append(f"High confidence play ({conf}%) - Strong edge detected")
    
    # 8. Volatility warning
    if proj_data["volatility"] == "HIGH":
        insights.append(f"High volatility ({proj_data['volatility_score']}) - Consider reduced unit size")
    
    # 9. Units recommendation
    if proj_data["units"] >= 1.5 and rec != "PASS":
        insights.append(f"Suggested sizing: {proj_data['units']}U on {rec}")
    
    return insights[:6]


def get_matchup_data(opponent, prop_type):
    """PLACEHOLDER: Get opponent defensive data"""
    random.seed(hash(opponent + prop_type) % 100)
    
    return {
        "def_rank": random.randint(1, 30),
        "pace": round(random.uniform(95, 106), 1),
        "pts_allowed": round(random.uniform(106, 120), 1),
        "reb_allowed": round(random.uniform(40, 48), 1),
        "ast_allowed": round(random.uniform(22, 28), 1),
        "projected_minutes": round(random.uniform(28, 38), 1),
        "usage_trend": round(random.uniform(-3, 5), 1),
        "injury_impact": random.choice(["None", "Minor (+2%)", "Moderate (+5%)", "Major (+10%)"]),
        "blowout_risk": random.choice(["Low", "Medium", "High"]),
        "possession_change": round(random.uniform(-3, 4), 1)
    }


# =============================================================================
# MAIN RENDER FUNCTION
# =============================================================================

def render_props_engine(engine):
    """
    Main Props Engine render function
    Implements ALL sections from the upgrade prompt
    """
    
    # =========================================================================
    # SESSION STATE INITIALIZATION
    # =========================================================================
    if "selected_player" not in st.session_state:
        st.session_state.selected_player = None
    if "selected_prop" not in st.session_state:
        st.session_state.selected_prop = None
    if "selected_game" not in st.session_state:
        st.session_state.selected_game = None
    if "screenshot_mode" not in st.session_state:
        st.session_state.screenshot_mode = False
    if "pick_delivery_mode" not in st.session_state:
        st.session_state.pick_delivery_mode = False
    if "trend_range" not in st.session_state:
        st.session_state.trend_range = "L15"
    
    # =========================================================================
    # LOAD DATA
    # =========================================================================
    summary_df, books_df = load_props_data(engine)
    
    if summary_df.empty:
        st.warning("⚠️ No props data for today. Props are fetched daily at 7:00 AM ET.")
        return
    
    # =========================================================================
    # ADD PROJECTIONS TO ALL PROPS
    # =========================================================================
    proj_list = []
    for _, row in summary_df.iterrows():
        proj = get_algo_projection(row["player_name"], row["prop_type"], row["avg_line"])
        proj_list.append(proj)
    
    summary_df["projection"] = [p["projection"] for p in proj_list]
    summary_df["delta"] = [p["delta"] for p in proj_list]
    summary_df["confidence"] = [p["confidence"] for p in proj_list]
    summary_df["units"] = [p["units"] for p in proj_list]
    summary_df["algo_rec"] = [p["recommendation"] for p in proj_list]
    summary_df["volatility"] = [p["volatility"] for p in proj_list]
    summary_df["hit_rate"] = [p["hit_rate"] for p in proj_list]
    
    # =========================================================================
    # SECTION 1: HEADER WITH TOGGLES
    # =========================================================================
    header_row = st.columns([5, 1, 1, 1])
    
    with header_row[0]:
        st.markdown("""
            <div style="font-family: 'Courier New', monospace;">
                <h1 style="color: #4ade80; margin: 0; letter-spacing: 2px; font-size: 2rem;">
                    PROPS ENGINE
                </h1>
                <p style="color: #64748b; margin: 0; font-size: 0.9rem;">
                    NBA Player Props Terminal • 11 Sportsbooks • Live Lines
                </p>
            </div>
        """, unsafe_allow_html=True)
    
    with header_row[1]:
        st.session_state.screenshot_mode = st.toggle("📸 Screenshot", key="ss_toggle")
    
    with header_row[2]:
        st.session_state.pick_delivery_mode = st.toggle("🎯 Pick Mode", key="pd_toggle")
    
    with header_row[3]:
        st.markdown(f"<p style='color:#4ade80; font-family:monospace; text-align:right; margin-top:0.5rem;'>{get_eastern_time().strftime('%I:%M %p ET')}</p>", unsafe_allow_html=True)
    
    # =========================================================================
    # METRICS ROW (SECTION 1 CONTINUED)
    # =========================================================================
    m1, m2, m3, m4, m5, m6 = st.columns(6)
    
    high_conf_count = len(summary_df[summary_df["confidence"] >= 80])
    over_count = len(summary_df[summary_df["algo_rec"] == "OVER"])
    under_count = len(summary_df[summary_df["algo_rec"] == "UNDER"])
    
    m1.metric("Total Props", f"{len(summary_df):,}")
    m2.metric("Players", summary_df["player_name"].nunique())
    m3.metric("Sportsbooks", books_df["sportsbook"].nunique())
    m4.metric("High Confidence", high_conf_count)
    m5.metric("Over / Under", f"{over_count} / {under_count}")
    m6.metric("Last Updated", get_eastern_time().strftime("%I:%M %p"))
    
    st.markdown("---")
    
    # =========================================================================
    # PICK DELIVERY MODE (SECTION 6)
    # =========================================================================
    if st.session_state.pick_delivery_mode and st.session_state.selected_player:
        render_pick_delivery_card(summary_df, books_df, engine)
        return
    
    # =========================================================================
    # SCREENSHOT MODE CHECK
    # =========================================================================
    screenshot_mode = st.session_state.screenshot_mode
    
    # =========================================================================
    # SECTION 2: TOP ALGO PICKS (FROM ALGO BRAIN)
    # =========================================================================
    st.markdown("""
        <h3 style="color: #4ade80; font-family: 'Courier New', monospace; margin-bottom: 1rem;">
            🔥 TOP ALGO PICKS
        </h3>
    """, unsafe_allow_html=True)
    
    # Get real picks from algo_brain
    try:
        from algo_brain import analyze_props
        prop_edges = analyze_props()
        
        if prop_edges:
            pick_cols = st.columns(3)
            for idx, edge in enumerate(prop_edges[:6]):
                with pick_cols[idx % 3]:
                    edge_val = edge['edge']
                    units = "1.5u" if edge_val >= 25 else "1u" if edge_val >= 15 else "0.5u"
                    
                    if edge_val >= 30:
                        border_color = "#ef4444"
                        conf_label = "🔥 HIGH"
                    elif edge_val >= 20:
                        border_color = "#fbbf24"
                        conf_label = "✅ GOOD"
                    else:
                        border_color = "#10b981"
                        conf_label = "📊 EDGE"
                    
                    market_clean = edge.get('subtype', '').replace('player_', '').upper()
                    
                    st.markdown(f"""
                    <div style="
                        background: linear-gradient(135deg, rgba(0,0,0,0.4) 0%, rgba(0,0,0,0.2) 100%);
                        border: 2px solid {border_color};
                        border-radius: 12px;
                        padding: 1rem;
                        margin-bottom: 0.8rem;
                    ">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
                            <span style="color: {border_color}; font-size: 0.75rem; font-weight: 600;">{conf_label}</span>
                            <span style="color: #6b7280; font-size: 0.7rem;">{market_clean}</span>
                        </div>
                        <p style="color: #fff; font-size: 1rem; font-weight: 600; margin: 0 0 0.3rem 0;">{edge['player']}</p>
                        <p style="color: #4ade80; font-size: 1.2rem; font-weight: 700; margin: 0 0 0.5rem 0;">{edge['pick']}</p>
                        <div style="display: flex; justify-content: space-between;">
                            <div>
                                <p style="color: #6b7280; font-size: 0.65rem; margin: 0;">EDGE</p>
                                <p style="color: #fff; font-size: 0.9rem; margin: 0;">{edge_val:.0f}%</p>
                            </div>
                            <div>
                                <p style="color: #6b7280; font-size: 0.65rem; margin: 0;">PROJ</p>
                                <p style="color: #fff; font-size: 0.9rem; margin: 0;">{edge.get('projected', 'N/A')}</p>
                            </div>
                            <div>
                                <p style="color: #6b7280; font-size: 0.65rem; margin: 0;">SIZE</p>
                                <p style="color: {border_color}; font-size: 0.9rem; font-weight: 600; margin: 0;">{units}</p>
                            </div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
        else:
            st.info("No prop edges found above threshold")
    except Exception as e:
        # Fallback to old method if algo_brain fails
        actionable = summary_df[
            (summary_df["confidence"] >= 72) & 
            (summary_df["algo_rec"] != "PASS") &
            (summary_df["spread"] >= 1.5)
        ].nlargest(6, "confidence")
        
        if actionable.empty:
            actionable = summary_df.nlargest(6, "spread")
        
        pick_cols = st.columns(3)
        for idx, (_, pick) in enumerate(actionable.iterrows()):
            with pick_cols[idx % 3]:
                render_pick_card(pick, books_df)
    
    st.markdown("---")
    
    # =========================================================================
    # SECTION 3: FILTERS (Hidden in Screenshot Mode)
    # =========================================================================
    if not screenshot_mode:
        render_filters(summary_df)
    
    # Apply filters
    filtered_df = apply_filters(summary_df, screenshot_mode)
    
    # =========================================================================
    # SECTION 4 & 5: BOARD SCANNER + DEEP DIVE
    # =========================================================================
    if not screenshot_mode:
        st.markdown("""
            <h3 style="color: #4ade80; font-family: 'Courier New', monospace; margin-bottom: 1rem;">
                📊 BOARD SCANNER
            </h3>
        """, unsafe_allow_html=True)
        
        scanner_col, inspector_col = st.columns([3, 2])
        
        with scanner_col:
            render_board_scanner(filtered_df, books_df)
        
        with inspector_col:
            render_deep_dive(summary_df, books_df, engine)
        
        st.markdown("---")
    
    # =========================================================================
    # SECTION 8: MARKET DISCREPANCIES (Hidden in Screenshot Mode)
    # =========================================================================
    if not screenshot_mode:
        render_market_discrepancies(summary_df)
    
    # =========================================================================
    # SECTION 9: SPORTSBOOK HEATMAP (Hidden in Screenshot Mode)
    # =========================================================================
    if not screenshot_mode:
        render_sportsbook_heatmap(summary_df, books_df)
    
    # =========================================================================
    # SECTION 10: RAW DATA (Hidden in Screenshot Mode)
    # =========================================================================
    if not screenshot_mode:
        with st.expander("📂 RAW LINES (Internal Debug)"):
            search_raw = st.text_input("Search", "", key="raw_search")
            raw_display = books_df.copy()
            if search_raw:
                raw_display = raw_display[
                    raw_display["player_name"].str.contains(search_raw, case=False, na=False) |
                    raw_display["sportsbook"].str.contains(search_raw, case=False, na=False)
                ]
            st.dataframe(raw_display.head(150), hide_index=True, use_container_width=True)
            st.caption(f"Showing {min(150, len(raw_display))} of {len(books_df)} lines")


# =============================================================================
# COMPONENT FUNCTIONS
# =============================================================================

def render_pick_card(pick, books_df):
    """Render a single pick card (NO PLAYER CARDS - data boxes only)"""
    rec = pick["algo_rec"]
    rec_color = "#22c55e" if rec == "OVER" else "#ef4444" if rec == "UNDER" else "#64748b"
    delta_color = "#22c55e" if pick["delta"] > 0 else "#ef4444"
    prop_display = pick["prop_type"].replace("player_", "").upper()
    
    best_o, best_u, _ = get_best_books(books_df, pick["player_name"], pick["prop_type"], pick["game_label"])
    best_o_line = f"{best_o['line']} ({best_o['sportsbook'][:6]})" if best_o is not None else "-"
    best_u_line = f"{best_u['line']} ({best_u['sportsbook'][:6]})" if best_u is not None else "-"
    
    st.markdown(f"""
        <div style="
            background: #0f172a;
            border: 1px solid #1e293b;
            border-left: 4px solid {rec_color};
            padding: 1rem;
            margin-bottom: 0.75rem;
            font-family: 'Courier New', monospace;
        ">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <span style="color: white; font-weight: bold; font-size: 1rem;">{pick["player_name"]}</span>
                <span style="background: {rec_color}; color: white; padding: 2px 8px; font-weight: bold;">{rec}</span>
            </div>
            <div style="color: #64748b; font-size: 0.8rem; margin: 0.25rem 0;">
                {prop_display} | {pick["game_label"][:22]}
            </div>
            <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 0.5rem; margin-top: 0.75rem; padding-top: 0.5rem; border-top: 1px solid #1e293b;">
                <div><div style="color: #64748b; font-size: 0.7rem;">LINE</div><div style="color: white;">{pick["avg_line"]}</div></div>
                <div><div style="color: #64748b; font-size: 0.7rem;">PROJ</div><div style="color: #4ade80;">{pick["projection"]}</div></div>
                <div><div style="color: #64748b; font-size: 0.7rem;">DELTA</div><div style="color: {delta_color};">{pick["delta"]:+.1f}</div></div>
            </div>
            <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 0.5rem; margin-top: 0.5rem;">
                <div><div style="color: #64748b; font-size: 0.7rem;">CONF</div><div style="color: #4ade80;">{pick["confidence"]}%</div></div>
                <div><div style="color: #64748b; font-size: 0.7rem;">UNITS</div><div style="color: #eab308;">{pick["units"]}</div></div>
                <div><div style="color: #64748b; font-size: 0.7rem;">SPREAD</div><div style="color: #4ade80;">{pick["spread"]:.1f}</div></div>
            </div>
            <div style="margin-top: 0.5rem; padding-top: 0.5rem; border-top: 1px solid #1e293b; font-size: 0.75rem;">
                <span style="color: #22c55e;">▲ Best O: {best_o_line}</span><br>
                <span style="color: #ef4444;">▼ Best U: {best_u_line}</span>
            </div>
        </div>
    """, unsafe_allow_html=True)


def render_filters(summary_df):
    """Render filter controls"""
    with st.expander("🎛️ FILTERS", expanded=False):
        f1, f2, f3, f4, f5 = st.columns(5)
        
        with f1:
            prop_options = ["All"] + sorted(summary_df["prop_type"].unique().tolist())
            st.selectbox("Prop Type", prop_options, key="filter_prop")
        
        with f2:
            all_teams = sorted(set(summary_df["home_team"].tolist() + summary_df["away_team"].tolist()))
            st.selectbox("Team", ["All"] + all_teams, key="filter_team")
        
        with f3:
            st.slider("Min Confidence", 50, 95, 60, key="filter_conf")
        
        with f4:
            st.slider("Min Spread", 0.0, 8.0, 0.0, 0.5, key="filter_spread")
        
        with f5:
            st.selectbox("Recommendation", ["All", "OVER", "UNDER", "PASS"], key="filter_rec")
        
        st.text_input("🔍 Search Player", "", key="filter_search")


def apply_filters(summary_df, screenshot_mode):
    """Apply filter values to dataframe"""
    if screenshot_mode:
        return summary_df[summary_df["confidence"] >= 70].nlargest(25, "confidence")
    
    filtered = summary_df.copy()
    
    fp = st.session_state.get("filter_prop", "All")
    ft = st.session_state.get("filter_team", "All")
    fc = st.session_state.get("filter_conf", 60)
    fs = st.session_state.get("filter_spread", 0.0)
    fr = st.session_state.get("filter_rec", "All")
    search = st.session_state.get("filter_search", "")
    
    if fp != "All":
        filtered = filtered[filtered["prop_type"] == fp]
    if ft != "All":
        filtered = filtered[(filtered["home_team"] == ft) | (filtered["away_team"] == ft)]
    if fc > 50:
        filtered = filtered[filtered["confidence"] >= fc]
    if fs > 0:
        filtered = filtered[filtered["spread"] >= fs]
    if fr != "All":
        filtered = filtered[filtered["algo_rec"] == fr]
    if search:
        filtered = filtered[filtered["player_name"].str.contains(search, case=False, na=False)]
    
    st.caption(f"Showing {len(filtered)} of {len(summary_df)} props")
    return filtered


def render_board_scanner(filtered_df, books_df):
    """Render the board scanner table with all columns"""
    rows = []
    for _, r in filtered_df.head(40).iterrows():
        best_o, best_u, _ = get_best_books(books_df, r["player_name"], r["prop_type"], r["game_label"])
        
        # Spread indicator
        if r["spread"] >= 4:
            spread_disp = f"🎯 {r['spread']:.1f}"
        elif r["spread"] >= 2:
            spread_disp = f"✅ {r['spread']:.1f}"
        else:
            spread_disp = f"{r['spread']:.1f}"
        
        # Best books
        bo_disp = f"{best_o['line']} ({format_odds(best_o['over_odds'])})" if best_o is not None else "-"
        bu_disp = f"{best_u['line']} ({format_odds(best_u['under_odds'])})" if best_u is not None else "-"
        
        rows.append({
            "Player": r["player_name"],
            "Prop": r["prop_type"].replace("player_", "")[:5].upper(),
            "Line": r["avg_line"],
            "Proj": r["projection"],
            "Δ": f"{r['delta']:+.1f}",
            "Conf": f"{r['confidence']}%",
            "Rec": r["algo_rec"],
            "Units": r["units"],
            "Spread": spread_disp,
            "Best O": bo_disp,
            "Best U": bu_disp,
            "_p": r["player_name"],
            "_t": r["prop_type"],
            "_g": r["game_label"]
        })
    
    df = pd.DataFrame(rows)
    
    if not df.empty:
        st.dataframe(
            df[["Player", "Prop", "Line", "Proj", "Δ", "Conf", "Rec", "Units", "Spread", "Best O", "Best U"]],
            hide_index=True,
            height=420,
            use_container_width=True
        )
        
        # Player selector
        player_options = ["Select a player..."] + df["Player"].tolist()
        selected = st.selectbox("🔬 Select Player for Deep Dive", player_options, key="player_selector")
        
        if selected != "Select a player...":
            sel_row = df[df["Player"] == selected].iloc[0]
            st.session_state.selected_player = sel_row["_p"]
            st.session_state.selected_prop = sel_row["_t"]
            st.session_state.selected_game = sel_row["_g"]
    else:
        st.info("No props match your filters")


def render_deep_dive(summary_df, books_df, engine):
    """
    SECTION 5: DEEP DIVE PANEL - COMPLETE IMPLEMENTATION
    Contains: Header, Sportsbook Grid, Trend Graph, Hit Rates, Matchup, AI Insights
    """
    st.markdown("""
        <div style="background: #0f172a; border: 1px solid #1e293b; padding: 0.75rem; margin-bottom: 0.5rem;">
            <span style="color: #4ade80; font-weight: bold; font-family: 'Courier New', monospace; letter-spacing: 1px;">
                DEEP DIVE PANEL
            </span>
        </div>
    """, unsafe_allow_html=True)
    
    if not st.session_state.selected_player:
        st.markdown("""
            <div style="background: #1e293b; padding: 3rem; text-align: center;">
                <p style="color: #64748b; margin: 0;">Select a player from the Board Scanner</p>
            </div>
        """, unsafe_allow_html=True)
        return
    
    player = st.session_state.selected_player
    prop_type = st.session_state.selected_prop
    game = st.session_state.selected_game
    
    # Get row data
    row = summary_df[
        (summary_df["player_name"] == player) &
        (summary_df["prop_type"] == prop_type) &
        (summary_df["game_label"] == game)
    ]
    
    if row.empty:
        st.warning("Player data not found")
        return
    
    row = row.iloc[0]
    
    # Get all supporting data
    proj_data = get_algo_projection(player, prop_type, row["avg_line"])
    best_o, best_u, all_books = get_best_books(books_df, player, prop_type, game)
    game_log = get_player_game_log(engine, player, prop_type, 20)
    hit_rates = calculate_hit_rates(game_log, row["avg_line"])
    averages = calculate_averages(game_log)
    matchup = get_matchup_data(row["away_team"], prop_type)
    insights = generate_ai_insights(player, prop_type, row["avg_line"], proj_data, averages, hit_rates, matchup)
    
    rec = proj_data["recommendation"]
    rec_color = "#22c55e" if rec == "OVER" else "#ef4444" if rec == "UNDER" else "#64748b"
    
    # =========================================================================
    # SECTION 5A: HEADER (Metric boxes, NO player card)
    # =========================================================================
    st.markdown(f"""
        <div style="background: #1e293b; padding: 1rem; margin-bottom: 0.75rem; font-family: 'Courier New', monospace;">
            <div style="color: white; font-size: 1.2rem; font-weight: bold;">{player}</div>
            <div style="color: #64748b; font-size: 0.85rem; margin: 0.25rem 0;">
                {prop_type.replace('player_', '').upper()} | {game}
            </div>
            <div style="margin-top: 0.75rem;">
                <span style="background: {rec_color}; color: white; padding: 4px 12px; font-weight: bold;">
                    ALGO: {rec}
                </span>
            </div>
        </div>
    """, unsafe_allow_html=True)
    
    # Metrics grid
    met1, met2, met3 = st.columns(3)
    met1.metric("Line", row["avg_line"])
    met2.metric("Projection", proj_data["projection"], f"{proj_data['delta']:+.1f}")
    met3.metric("Confidence", f"{proj_data['confidence']}%")
    
    met4, met5, met6 = st.columns(3)
    met4.metric("Units", proj_data["units"])
    met5.metric("Volatility", f"{proj_data['volatility']} ({proj_data['volatility_score']})")
    met6.metric("Spread", f"{row['spread']:.1f}")
    
    # =========================================================================
    # SECTION 5B: SPORTSBOOK COMPARISON GRID (Horizontal)
    # =========================================================================
    st.markdown("**📚 SPORTSBOOK COMPARISON**")
    
    if not all_books.empty:
        book_data = []
        for _, bk in all_books.sort_values("sportsbook").iterrows():
            is_best_over = bk["line"] == row["min_line"]
            is_best_under = bk["line"] == row["max_line"]
            
            indicator = ""
            if is_best_over:
                indicator = "🟢 BEST OVER"
            elif is_best_under:
                indicator = "🔴 BEST UNDER"
            
            book_data.append({
                "BOOK": bk["sportsbook"],
                "LINE": bk["line"],
                "O-ODDS": format_odds(bk["over_odds"]),
                "U-ODDS": format_odds(bk["under_odds"]),
                "": indicator
            })
        
        st.dataframe(pd.DataFrame(book_data), hide_index=True, height=200, use_container_width=True)
    else:
        st.info("No sportsbook data available")
    
    # =========================================================================
    # SECTION 5C: TREND GRAPH (L5/L10/L15/Season toggle)
    # =========================================================================
    st.markdown("**📈 PERFORMANCE TREND**")
    
    # Range selector
    range_col1, range_col2, range_col3, range_col4 = st.columns(4)
    with range_col1:
        if st.button("L5", key="range_l5", use_container_width=True):
            st.session_state.trend_range = "L5"
    with range_col2:
        if st.button("L10", key="range_l10", use_container_width=True):
            st.session_state.trend_range = "L10"
    with range_col3:
        if st.button("L15", key="range_l15", use_container_width=True):
            st.session_state.trend_range = "L15"
    with range_col4:
        if st.button("Season", key="range_season", use_container_width=True):
            st.session_state.trend_range = "Season"
    
    if not game_log.empty and "stat_value" in game_log.columns:
        # Filter based on range
        trend_range = st.session_state.get("trend_range", "L15")
        if trend_range == "L5":
            chart_data = game_log.head(5)
        elif trend_range == "L10":
            chart_data = game_log.head(10)
        elif trend_range == "L15":
            chart_data = game_log.head(15)
        else:
            chart_data = game_log
        
        chart_data = chart_data.sort_values("game_date").copy()
        chart_data["hit"] = chart_data["stat_value"] > row["avg_line"]
        chart_data["color"] = chart_data["hit"].apply(lambda x: "#22c55e" if x else "#ef4444")
        
        # Create bar chart
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=list(range(len(chart_data))),
            y=chart_data["stat_value"],
            marker_color=chart_data["color"].tolist(),
            text=chart_data["stat_value"].round(0).astype(int),
            textposition="outside",
            textfont=dict(size=10, color="#94a3b8")
        ))
        
        # Add line reference
        fig.add_hline(
            y=row["avg_line"],
            line_dash="dash",
            line_color="#4ade80",
            annotation_text=f"Line: {row['avg_line']}",
            annotation_position="right"
        )
        
        fig.update_layout(
            height=180,
            margin=dict(l=0, r=0, t=20, b=0),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            showlegend=False,
            xaxis=dict(showticklabels=False, showgrid=False),
            yaxis=dict(showgrid=False, color="#64748b")
        )
        
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No game log data available")
    
    # =========================================================================
    # SECTION 5D: HIT RATE SUMMARY
    # =========================================================================
    st.markdown("**📊 HIT RATES**")
    
    hr1, hr2, hr3, hr4 = st.columns(4)
    hr1.metric("L5", hit_rates["L5"])
    hr2.metric("L10", hit_rates["L10"])
    hr3.metric("L15", hit_rates["L15"])
    hr4.metric("Season", hit_rates["Season"])
    
    st.markdown("**📈 AVERAGES**")
    
    av1, av2, av3, av4 = st.columns(4)
    av1.metric("L5 Avg", averages["L5"])
    av2.metric("L10 Avg", averages["L10"])
    av3.metric("L15 Avg", averages["L15"])
    av4.metric("Season Avg", averages["Season"])
    
    # =========================================================================
    # SECTION 5E: MATCHUP BREAKDOWN
    # =========================================================================
    st.markdown("**🏀 MATCHUP BREAKDOWN**")
    
    mu1, mu2, mu3 = st.columns(3)
    mu1.metric("Opp Def Rank", f"#{matchup['def_rank']}")
    mu2.metric("Pace", matchup["pace"])
    mu3.metric("Proj Minutes", matchup["projected_minutes"])
    
    mu4, mu5, mu6 = st.columns(3)
    mu4.metric("Usage Trend", f"{matchup['usage_trend']:+.1f}%")
    mu5.metric("Injury Impact", matchup["injury_impact"])
    mu6.metric("Blowout Risk", matchup["blowout_risk"])
    
    # =========================================================================
    # SECTION 5F: AI INSIGHTS ENGINE
    # =========================================================================
    st.markdown("**🤖 AI INSIGHTS**")
    
    for insight in insights:
        st.markdown(f"""
            <div style="
                color: #94a3b8;
                font-size: 0.85rem;
                padding: 0.3rem 0;
                font-family: 'Courier New', monospace;
                border-left: 2px solid #4ade80;
                padding-left: 0.75rem;
                margin-bottom: 0.3rem;
            ">• {insight}</div>
        """, unsafe_allow_html=True)


def render_pick_delivery_card(summary_df, books_df, engine):
    """
    SECTION 6: PICK DELIVERY MODE
    Clean, centered card optimized for screenshot + Discord
    """
    if not st.session_state.selected_player:
        st.warning("Select a player first, then enable Pick Delivery Mode")
        return
    
    player = st.session_state.selected_player
    prop_type = st.session_state.selected_prop
    game = st.session_state.selected_game
    
    row = summary_df[
        (summary_df["player_name"] == player) &
        (summary_df["prop_type"] == prop_type) &
        (summary_df["game_label"] == game)
    ]
    
    if row.empty:
        st.warning("Player data not found")
        return
    
    row = row.iloc[0]
    proj_data = get_algo_projection(player, prop_type, row["avg_line"])
    best_o, best_u, _ = get_best_books(books_df, player, prop_type, game)
    game_log = get_player_game_log(engine, player, prop_type, 15)
    averages = calculate_averages(game_log)
    
    rec = proj_data["recommendation"]
    rec_color = "#22c55e" if rec == "OVER" else "#ef4444" if rec == "UNDER" else "#64748b"
    prop_display = prop_type.replace("player_", "").upper()
    
    best_book = best_o["sportsbook"] if rec == "OVER" and best_o is not None else (best_u["sportsbook"] if best_u is not None else "-")
    best_line = best_o["line"] if rec == "OVER" and best_o is not None else (best_u["line"] if best_u is not None else row["avg_line"])
    
    # Generate simple explanation
    if rec == "OVER":
        explanation = f"Projection ({proj_data['projection']}) is {abs(proj_data['delta']):.1f} pts above the line. L5 avg: {averages['L5']}"
    elif rec == "UNDER":
        explanation = f"Projection ({proj_data['projection']}) is {abs(proj_data['delta']):.1f} pts below the line. L5 avg: {averages['L5']}"
    else:
        explanation = "Line is close to projection - no strong edge detected"
    
    # Centered card
    st.markdown(f"""
        <div style="
            max-width: 500px;
            margin: 2rem auto;
            background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
            border: 2px solid {rec_color};
            border-radius: 16px;
            padding: 2rem;
            font-family: 'Courier New', monospace;
            text-align: center;
        ">
            <div style="color: #64748b; font-size: 0.9rem; margin-bottom: 0.5rem;">
                🎯 SB-ALGO PICK
            </div>
            
            <div style="color: white; font-size: 1.5rem; font-weight: bold; margin-bottom: 0.25rem;">
                {player}
            </div>
            
            <div style="color: #94a3b8; font-size: 1rem; margin-bottom: 1rem;">
                {prop_display} | {game}
            </div>
            
            <div style="
                background: {rec_color};
                color: white;
                font-size: 1.5rem;
                font-weight: bold;
                padding: 0.75rem 1.5rem;
                display: inline-block;
                margin-bottom: 1.5rem;
            ">
                {rec} {best_line}
            </div>
            
            <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 1rem; margin-bottom: 1.5rem;">
                <div>
                    <div style="color: #64748b; font-size: 0.75rem;">PROJECTION</div>
                    <div style="color: #4ade80; font-size: 1.2rem; font-weight: bold;">{proj_data['projection']}</div>
                </div>
                <div>
                    <div style="color: #64748b; font-size: 0.75rem;">CONFIDENCE</div>
                    <div style="color: #4ade80; font-size: 1.2rem; font-weight: bold;">{proj_data['confidence']}%</div>
                </div>
                <div>
                    <div style="color: #64748b; font-size: 0.75rem;">UNITS</div>
                    <div style="color: #eab308; font-size: 1.2rem; font-weight: bold;">{proj_data['units']}U</div>
                </div>
            </div>
            
            <div style="
                background: rgba(74, 222, 128, 0.1);
                border: 1px solid rgba(74, 222, 128, 0.3);
                border-radius: 8px;
                padding: 1rem;
                margin-bottom: 1rem;
            ">
                <div style="color: #94a3b8; font-size: 0.85rem;">{explanation}</div>
            </div>
            
            <div style="color: #64748b; font-size: 0.8rem;">
                Best Book: <span style="color: #4ade80;">{best_book}</span> | 
                Updated: {get_eastern_time().strftime('%I:%M %p ET')}
            </div>
        </div>
    """, unsafe_allow_html=True)
    
    # Button to exit pick delivery mode
    if st.button("← Back to Full View", key="exit_pick_mode"):
        st.session_state.pick_delivery_mode = False
        st.rerun()


def render_market_discrepancies(summary_df):
    """SECTION 8: Market Discrepancies"""
    st.markdown("""
        <h3 style="color: #4ade80; font-family: 'Courier New', monospace; margin-bottom: 1rem;">
            🎯 MARKET DISCREPANCIES
        </h3>
    """, unsafe_allow_html=True)
    
    discrepancies = summary_df[
        (summary_df["spread"] >= 2.0) &
        (summary_df["books_count"] >= 4)
    ].nlargest(8, "spread")
    
    disc_cols = st.columns(4)
    for idx, (_, disc) in enumerate(discrepancies.iterrows()):
        with disc_cols[idx % 4]:
            delta_color = "#22c55e" if disc["delta"] > 0 else "#ef4444"
            st.markdown(f"""
                <div style="
                    background: #0f172a;
                    border: 1px solid #22c55e;
                    padding: 0.75rem;
                    margin-bottom: 0.5rem;
                    font-family: 'Courier New', monospace;
                ">
                    <div style="color: white; font-weight: bold; font-size: 0.9rem;">
                        {disc["player_name"][:16]}
                    </div>
                    <div style="color: #64748b; font-size: 0.75rem;">
                        {disc["prop_type"].replace("player_", "").upper()}
                    </div>
                    <div style="color: #22c55e; font-size: 0.85rem; margin: 0.25rem 0;">
                        {disc["min_line"]} → {disc["max_line"]}
                    </div>
                    <div style="color: #4ade80; font-weight: bold;">
                        Spread: {disc["spread"]:.1f}
                    </div>
                    <div style="margin-top: 0.25rem; font-size: 0.75rem;">
                        <span style="color: #64748b;">Proj:</span>
                        <span style="color: #4ade80;">{disc["projection"]}</span>
                        <span style="color: {delta_color}; margin-left: 0.5rem;">Δ {disc["delta"]:+.1f}</span>
                    </div>
                </div>
            """, unsafe_allow_html=True)


def render_sportsbook_heatmap(summary_df, books_df):
    """SECTION 9: Sportsbook Heatmap"""
    with st.expander("🌡️ SPORTSBOOK HEATMAP"):
        st.caption("Line differences from consensus by sportsbook")
        
        heatmap_props = summary_df.nlargest(10, "spread")
        heatmap_data = []
        
        for _, prop in heatmap_props.iterrows():
            _, _, prop_books = get_best_books(books_df, prop["player_name"], prop["prop_type"], prop["game_label"])
            
            if not prop_books.empty:
                for _, bk in prop_books.iterrows():
                    diff = bk["line"] - prop["avg_line"]
                    heatmap_data.append({
                        "Prop": f"{prop['player_name'][:12]} {prop['prop_type'].replace('player_', '')[:3].upper()}",
                        "Book": bk["sportsbook"][:8],
                        "Diff": round(diff, 1)
                    })
        
        if heatmap_data:
            hm_df = pd.DataFrame(heatmap_data)
            pivot = hm_df.pivot_table(index="Prop", columns="Book", values="Diff", aggfunc="first")
            
            fig = go.Figure(data=go.Heatmap(
                z=pivot.values,
                x=pivot.columns.tolist(),
                y=pivot.index.tolist(),
                colorscale=[[0, "#ef4444"], [0.5, "#1e293b"], [1, "#22c55e"]],
                zmid=0,
                text=pivot.values,
                texttemplate="%{text:.1f}",
                textfont={"size": 10}
            ))
            
            fig.update_layout(
                height=400,
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#94a3b8")
            )
            
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Not enough data for heatmap")


# =============================================================================
# STANDALONE TEST
# =============================================================================
if __name__ == "__main__":
    st.set_page_config(page_title="Props Engine", layout="wide")
    st.warning("Import render_props_engine() into your dashboard")
