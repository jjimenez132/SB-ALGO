cat > app.py << 'EOF'
import os
from datetime import datetime

import pandas as pd
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import streamlit as st

# ------------------------------------------------------
# Configuración básica
# ------------------------------------------------------
st.set_page_config(
    page_title="SB ALGO — NBA Edge Engine",
    page_icon="🏀",
    layout="wide",
)

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

# ------------------------------------------------------
# Conexión a Postgres
# ------------------------------------------------------
@st.cache_resource
def get_engine():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not set. Add it to your .env file.")
    return create_engine(DATABASE_URL)


@st.cache_data(show_spinner=False)
def load_games():
    engine = get_engine()
    with engine.connect() as conn:
        return pd.read_sql("SELECT * FROM games ORDER BY date", conn)


@st.cache_data(show_spinner=False)
def load_player_boxscores():
    engine = get_engine()
    with engine.connect() as conn:
        return pd.read_sql("SELECT * FROM player_boxscores LIMIT 10000", conn)


@st.cache_data(show_spinner=False)
def load_seasons():
    """
    Calcular temporadas distintas desde games.
    """
    engine = get_engine()
    with engine.connect() as conn:
        result = conn.execute(text("SELECT DISTINCT season FROM games ORDER BY season"))
        seasons = [row[0] for row in result.fetchall()]
        return seasons


# ------------------------------------------------------
# Layout principal
# ------------------------------------------------------
def main():
    st.title("🏀 SB ALGO — NBA Edge Engine")

    # Status de conexión
    try:
        engine = get_engine()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        st.success("✅ Database Connected | Live on Render")
    except Exception as e:
        st.error("❌ Database Connection Failed")
        st.exception(e)
        st.stop()

    # Cargar data
    with st.spinner("Loading NBA data from PostgreSQL..."):
        try:
            games_df = load_games()
        except Exception as e:
            st.error(f"Error loading games: {e}")
            games_df = pd.DataFrame()

        try:
            boxscores_df = load_player_boxscores()
        except Exception as e:
            st.error(f"Error loading boxscores: {e}")
            boxscores_df = pd.DataFrame()

        try:
            seasons = load_seasons()
        except Exception as e:
            st.error(f"Error loading seasons: {e}")
            seasons = []

    # Panel superior de resumen
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("🏀 Games", f"{len(games_df):,}")
    with col2:
        st.metric("📊 Player Performances", f"{len(boxscores_df):,}")
    with col3:
        st.metric("📅 Seasons", len(seasons))

    if seasons:
        st.caption(f"Seasons Available: {', '.join(str(s) for s in seasons)}")

    # Tabs principales
    tab_overview, tab_games, tab_players = st.tabs(
        ["📊 Overview", "📅 Games Explorer", "👤 Player Explorer"]
    )

    # --------------------------------------------------
    # TAB 1: OVERVIEW
    # --------------------------------------------------
    with tab_overview:
        st.subheader("Database Overview")

        if games_df.empty or boxscores_df.empty:
            st.info("Waiting for data to be loaded into PostgreSQL...")
        else:
            season_choice = st.selectbox(
                "Select Season",
                seasons,
                index=len(seasons) - 1 if seasons else 0,
            )

            season_games = games_df[games_df["season"] == season_choice]
            st.write(f"**{len(season_games):,}** games in {season_choice} season")

            # Show recent games
            st.dataframe(
                season_games.sort_values("date", ascending=False).head(50),
                use_container_width=True,
                hide_index=True,
            )

    # --------------------------------------------------
    # TAB 2: GAMES EXPLORER
    # --------------------------------------------------
    with tab_games:
        st.subheader("Games Explorer")

        if games_df.empty:
            st.info("No games data available yet.")
        else:
            left, right = st.columns(2)
            with left:
                season_filter = st.selectbox(
                    "Season",
                    seasons,
                    index=len(seasons) - 1 if seasons else 0,
                    key="games_season"
                )
            with right:
                teams = sorted(
                    set(games_df["home_team"].dropna().unique())
                    | set(games_df["visitor_team"].dropna().unique())
                )
                team_filter = st.selectbox("Team (Home/Visitor)", ["(All)"] + teams)

            df = games_df.copy()
            df = df[df["season"] == season_filter]

            if team_filter != "(All)":
                df = df[
                    (df["home_team"] == team_filter)
                    | (df["visitor_team"] == team_filter)
                ]

            st.write(f"**{len(df):,}** games found")
            st.dataframe(
                df.sort_values("date", ascending=False).head(200),
                use_container_width=True,
                hide_index=True,
            )

    # --------------------------------------------------
    # TAB 3: PLAYER EXPLORER
    # --------------------------------------------------
    with tab_players:
        st.subheader("Player Explorer")

        if boxscores_df.empty:
            st.info("No player boxscore data available yet.")
        else:
            players = sorted(boxscores_df["player_name"].dropna().unique())
            player = st.selectbox("Select Player", players)

            player_df = boxscores_df[boxscores_df["player_name"] == player]

            st.write(f"**{len(player_df):,}** performances for {player}")

            # Show stats
            if not player_df.empty and "pts" in player_df.columns:
                cols = st.columns(4)
                with cols[0]:
                    st.metric("Avg PTS", f"{player_df['pts'].mean():.1f}")
                with cols[1]:
                    st.metric("Avg REB", f"{player_df['reb'].mean():.1f}")
                with cols[2]:
                    st.metric("Avg AST", f"{player_df['ast'].mean():.1f}")
                with cols[3]:
                    st.metric("Games", len(player_df))

            st.dataframe(
                player_df.head(50),
                use_container_width=True,
                hide_index=True,
            )


if __name__ == "__main__":
    main()
EOF