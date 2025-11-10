# app.py — SB ALGO (Postgres or DuckDB auto)
import math
import re

import numpy as np
import pandas as pd
import streamlit as st

from db.utils import get_engine, read_sql

st.set_page_config(page_title="SB ALGO — NBA Edge Engine", page_icon="🏀", layout="wide")
st.title("🏀 SB ALGO — NBA Edge Engine")
st.caption("Lean MVP · Postgres/DuckDB autodetect")

ENGINE = get_engine()
ENGINE_LABEL = "Postgres" if hasattr(ENGINE, "dialect") else "DuckDB"
st.caption(f"Active data source: {ENGINE_LABEL}")

# ---------- Connections ----------
def query_df(sql: str, params=None) -> pd.DataFrame:
    return read_sql(sql, params=params)

# ---------- Helpers ----------
def normalize_season_str(season: str) -> str:
    s = str(season)
    if "-" in s:
        return s.split("-")[0]
    try:
        start = int(s); return f"{start}-{str((start+1)%100).zfill(2)}"
    except: return s

def to_minutes(series: pd.Series) -> pd.Series:
    s = series.fillna("").astype(str)
    def parse(x):
        m = re.match(r"^(\d+):(\d{1,2})$", x.strip())
        if m: return int(m.group(1)) + int(m.group(2))/60.0
        try: return float(x)
        except: return np.nan
    return s.map(parse)

# ---------- Cached queries ----------
@st.cache_data(ttl=600)
def seasons_available():
    try:
        df = query_df("SELECT DISTINCT season FROM games ORDER BY season")
        return df["season"].astype(str).tolist()
    except Exception:
        return []

@st.cache_data(ttl=600)
def teams_for_season(season: str):
    return query_df("""
        SELECT DISTINCT TEAM_ABBREVIATION AS team_abbr
        FROM player_boxscores
        WHERE season = :s OR season = :s_norm
        ORDER BY team_abbr
    """, {"s": season, "s_norm": normalize_season_str(season)})

@st.cache_data(ttl=600)
def players_for_team_season(team: str, season: str):
    return query_df("""
        SELECT PLAYER_ID, PLAYER_NAME
        FROM player_boxscores
        WHERE (season = :s OR season = :s_norm) AND TEAM_ABBREVIATION = :t
        GROUP BY PLAYER_ID, PLAYER_NAME
        ORDER BY PLAYER_NAME
    """, {"s": season, "s_norm": normalize_season_str(season), "t": team})

@st.cache_data(ttl=300)
def last_n_games(player_id: int, season: str, n: int):
    d = query_df("""
        SELECT GAME_ID, TEAM_ABBREVIATION, START_POSITION, MIN, PTS, REB, AST, FG3M
        FROM player_boxscores
        WHERE (season = :s OR season = :s_norm) AND PLAYER_ID = :pid
        ORDER BY GAME_ID DESC
        LIMIT :n
    """, {"s": season, "s_norm": normalize_season_str(season), "pid": int(player_id), "n": int(n)}).copy()
    if not d.empty: d["MIN_float"] = to_minutes(d["MIN"])
    return d

@st.cache_data(ttl=600)
def season_averages(player_id: int, season: str):
    d = query_df("""
        SELECT
          AVG(CAST(PTS AS DOUBLE PRECISION))  AS PTS_avg,
          AVG(CAST(REB AS DOUBLE PRECISION))  AS REB_avg,
          AVG(CAST(AST AS DOUBLE PRECISION))  AS AST_avg,
          AVG(CAST(FG3M AS DOUBLE PRECISION)) AS FG3M_avg,
          AVG(CASE
                WHEN MIN ~ '^[0-9]+:[0-5][0-9]$' THEN
                      (CAST(split_part(MIN, ':', 1) AS DOUBLE PRECISION)
                       + CAST(split_part(MIN, ':', 2) AS DOUBLE PRECISION)/60.0)
                ELSE NULLIF(MIN, '')::DOUBLE PRECISION
              END) AS MIN_avg
        FROM player_boxscores
        WHERE (season = :s OR season = :s_norm) AND PLAYER_ID = :pid
    """, {"s": season, "s_norm": normalize_season_str(season), "pid": int(player_id)})
    return d.iloc[0] if not d.empty else pd.Series(dtype=float)

# ---------- UI ----------
tabs = st.tabs(["🔥 Player Props", "💵 Moneylines", "📈 Spreads", "📊 Totals"])

with tabs[0]:
    st.subheader("Player Props — Historical Snapshot (Lean)")

    seasons = seasons_available()
    if not seasons:
        st.error("No seasons found.")
        st.stop()
    season_choice = st.selectbox("Season", options=seasons, index=len(seasons)-1)

    tdf = teams_for_season(season_choice)
    team_choice = st.selectbox("Team", tdf["team_abbr"].tolist())

    pdf = players_for_team_season(team_choice, season_choice)
    player_name = st.selectbox("Player", pdf["PLAYER_NAME"].tolist())
    player_id = int(pdf.loc[pdf["PLAYER_NAME"]==player_name, "PLAYER_ID"].iloc[0])

    last_n = st.slider("Last N games", 5, 20, 10)
    lg = last_n_games(player_id, season_choice, last_n)
    av = season_averages(player_id, season_choice)

    colL, colR = st.columns([1,1], gap="large")

    with colL:
        st.markdown(f"**Recent Games (last {last_n}) — {player_name} ({team_choice})**")
        if lg.empty:
            st.info("No recent rows found.")
        else:
            st.dataframe(lg[["GAME_ID","TEAM_ABBREVIATION","START_POSITION","MIN","PTS","REB","AST","FG3M"]],
                         use_container_width=True, hide_index=True)

    with colR:
        st.markdown("**Season Averages**")
        if av.empty:
            st.info("No season averages available.")
        else:
            metrics = {k: av.get(k, np.nan) for k in ["PTS_avg","REB_avg","AST_avg","FG3M_avg","MIN_avg"]}
            p1,p2,p3,p4,p5 = st.columns(5)
            p1.metric("PTS", f"{metrics['PTS_avg']:.1f}" if not math.isnan(metrics['PTS_avg']) else "—")
            p2.metric("REB", f"{metrics['REB_avg']:.1f}" if not math.isnan(metrics['REB_avg']) else "—")
            p3.metric("AST", f"{metrics['AST_avg']:.1f}" if not math.isnan(metrics['AST_avg']) else "—")
            p4.metric("3PM", f"{metrics['FG3M_avg']:.1f}" if not math.isnan(metrics['FG3M_avg']) else "—")
            p5.metric("MIN", f"{metrics['MIN_avg']:.1f}" if not math.isnan(metrics['MIN_avg']) else "—")

        st.divider()
        st.markdown("**Baseline Projection (mean of last N)**")
        if not lg.empty:
            proj = lg[["PTS","REB","AST","FG3M"]].apply(pd.to_numeric, errors="coerce").mean()
            c1,c2,c3,c4 = st.columns(4)
            c1.metric("PTS proj", f"{proj['PTS']:.1f}")
            c2.metric("REB proj", f"{proj['REB']:.1f}")
            c3.metric("AST proj", f"{proj['AST']:.1f}")
            c4.metric("3PM proj", f"{proj['FG3M']:.1f}")
        else:
            st.info("Need at least one recent game.")

with tabs[1]:
    st.subheader("Moneylines (placeholder)")
with tabs[2]:
    st.subheader("Spreads (placeholder)")
with tabs[3]:
    st.subheader("Totals (placeholder)")
