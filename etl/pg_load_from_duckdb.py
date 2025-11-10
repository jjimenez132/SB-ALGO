"""Load DuckDB history into Postgres with clean typing and fast COPY."""
from __future__ import annotations

import os
from pathlib import Path
from tempfile import NamedTemporaryFile

import duckdb
import pandas as pd
import psycopg
from sqlalchemy import create_engine, text

BASE_DIR = Path(__file__).resolve().parents[1]
DUCKDB_PATH = BASE_DIR / "warehouse" / "nba.duckdb"

GAMES_COLUMNS = [
    "date",
    "start_time",
    "visitor_team",
    "visitor_pts",
    "home_team",
    "home_pts",
    "attendance",
    "notes",
    "season",
    "total_points",
    "margin_home",
    "abs_margin",
    "home_win",
    "home_team_std",
    "visitor_team_std",
    "possible_playoff",
    "home_days_rest",
    "home_is_b2b",
    "visitor_days_rest",
    "visitor_is_b2b",
    "season_avg_total",
    "season_std",
    "total_minus_season_avg",
]

PLAYER_BOXSCORES_COLUMNS = [
    "GAME_ID",
    "TEAM_ID",
    "TEAM_ABBREVIATION",
    "TEAM_CITY",
    "PLAYER_ID",
    "PLAYER_NAME",
    "NICKNAME",
    "START_POSITION",
    "COMMENT",
    "MIN",
    "FGM",
    "FGA",
    "FG_PCT",
    "FG3M",
    "FG3A",
    "FG3_PCT",
    "FTM",
    "FTA",
    "FT_PCT",
    "OREB",
    "DREB",
    "REB",
    "AST",
    "STL",
    "BLK",
    "TO",
    "PF",
    "PTS",
    "PLUS_MINUS",
    "season",
    "SEASON_1",
]


def ensure_sslmode(url: str) -> str:
    if "sslmode=" in url:
        return url
    sep = "&" if "?" in url else "?"
    return f"{url}{sep}sslmode=require"


def duckdb_to_df(table: str) -> pd.DataFrame:
    if not DUCKDB_PATH.exists():
        raise FileNotFoundError(f"DuckDB file not found at {DUCKDB_PATH}")
    with duckdb.connect(str(DUCKDB_PATH), read_only=True) as con:
        return con.execute(f"SELECT * FROM {table}").df()


def normalize_none_strings(df: pd.DataFrame) -> pd.DataFrame:
    return df.replace("None", pd.NA)


def coerce_game_types(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    int_cols = [
        "attendance",
        "season",
        "home_win",
        "possible_playoff",
        "home_is_b2b",
        "visitor_is_b2b",
    ]
    float_cols = [
        "visitor_pts",
        "home_pts",
        "total_points",
        "margin_home",
        "abs_margin",
        "home_days_rest",
        "visitor_days_rest",
        "season_avg_total",
        "season_std",
        "total_minus_season_avg",
    ]

    for col in int_cols:
        if col not in df.columns:
            df[col] = pd.NA
        df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")
    for col in float_cols:
        if col not in df.columns:
            df[col] = pd.NA
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df["date"] = pd.to_datetime(df.get("date"), errors="coerce").dt.date
    return df


def coerce_player_types(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    int_cols = ["GAME_ID", "TEAM_ID", "PLAYER_ID"]
    float_cols = [
        "FGM",
        "FGA",
        "FG_PCT",
        "FG3M",
        "FG3A",
        "FG3_PCT",
        "FTM",
        "FTA",
        "FT_PCT",
        "OREB",
        "DREB",
        "REB",
        "AST",
        "STL",
        "BLK",
        "TO",
        "PF",
        "PTS",
        "PLUS_MINUS",
    ]

    for col in int_cols:
        if col not in df.columns:
            df[col] = pd.NA
        df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")
    for col in float_cols:
        if col not in df.columns:
            df[col] = pd.NA
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def write_temp_csv(df: pd.DataFrame, columns: list[str]) -> str:
    for col in columns:
        if col not in df.columns:
            df[col] = pd.NA
    tmp = NamedTemporaryFile(mode="w", newline="", suffix=".csv", delete=False)
    tmp_path = tmp.name
    df.to_csv(tmp, index=False, columns=columns, na_rep="")
    tmp.close()
    return tmp_path


def sql_ident(name: str) -> str:
    return f'"{name.replace(chr(34), chr(34) * 2)}"'


def copy_via_psycopg(csv_path: str, table: str, columns: list[str], pg_url: str) -> None:
    columns_sql = ", ".join(sql_ident(col) for col in columns)
    copy_sql = f"COPY {table} ({columns_sql}) FROM STDIN WITH (FORMAT CSV, HEADER TRUE)"
    with psycopg.connect(pg_url) as conn, conn.cursor() as cur, open(csv_path, "rb") as fh:
        with cur.copy(copy_sql) as copy:
            while chunk := fh.read(1024 * 1024):
                copy.write(chunk)
        conn.commit()


def main() -> None:
    pg_url = os.getenv("DATABASE_URL", "").strip()
    if not pg_url:
        raise EnvironmentError("DATABASE_URL is required for Postgres load.")
    pg_url = ensure_sslmode(pg_url)

    games_df = normalize_none_strings(duckdb_to_df("games"))
    pbs_df = normalize_none_strings(duckdb_to_df("player_boxscores"))
    games_df = coerce_game_types(games_df)
    pbs_df = coerce_player_types(pbs_df)

    engine = create_engine(pg_url, pool_pre_ping=True, future=True)

    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS player_boxscores"))
        conn.execute(text("DROP TABLE IF EXISTS games"))
        conn.execute(
            text(
                """
                CREATE TABLE games (
                    date DATE,
                    start_time VARCHAR,
                    visitor_team VARCHAR,
                    visitor_pts DOUBLE PRECISION,
                    home_team VARCHAR,
                    home_pts DOUBLE PRECISION,
                    attendance BIGINT,
                    notes VARCHAR,
                    season BIGINT,
                    total_points DOUBLE PRECISION,
                    margin_home DOUBLE PRECISION,
                    abs_margin DOUBLE PRECISION,
                    home_win BIGINT,
                    home_team_std VARCHAR,
                    visitor_team_std VARCHAR,
                    possible_playoff BIGINT,
                    home_days_rest DOUBLE PRECISION,
                    home_is_b2b BIGINT,
                    visitor_days_rest DOUBLE PRECISION,
                    visitor_is_b2b BIGINT,
                    season_avg_total DOUBLE PRECISION,
                    season_std DOUBLE PRECISION,
                    total_minus_season_avg DOUBLE PRECISION,
                    PRIMARY KEY (date, home_team, visitor_team)
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE player_boxscores (
                    GAME_ID BIGINT,
                    TEAM_ID BIGINT,
                    TEAM_ABBREVIATION VARCHAR,
                    TEAM_CITY VARCHAR,
                    PLAYER_ID BIGINT,
                    PLAYER_NAME VARCHAR,
                    NICKNAME VARCHAR,
                    START_POSITION VARCHAR,
                    COMMENT VARCHAR,
                    MIN VARCHAR,
                    FGM DOUBLE PRECISION,
                    FGA DOUBLE PRECISION,
                    FG_PCT DOUBLE PRECISION,
                    FG3M DOUBLE PRECISION,
                    FG3A DOUBLE PRECISION,
                    FG3_PCT DOUBLE PRECISION,
                    FTM DOUBLE PRECISION,
                    FTA DOUBLE PRECISION,
                    FT_PCT DOUBLE PRECISION,
                    OREB DOUBLE PRECISION,
                    DREB DOUBLE PRECISION,
                    REB DOUBLE PRECISION,
                    AST DOUBLE PRECISION,
                    STL DOUBLE PRECISION,
                    BLK DOUBLE PRECISION,
                    "TO" DOUBLE PRECISION,
                    PF DOUBLE PRECISION,
                    PTS DOUBLE PRECISION,
                    PLUS_MINUS DOUBLE PRECISION,
                    season VARCHAR,
                    SEASON_1 VARCHAR,
                    PRIMARY KEY (GAME_ID, PLAYER_ID)
                )
                """
            )
        )

    games_csv = write_temp_csv(games_df, GAMES_COLUMNS)
    pbs_csv = write_temp_csv(pbs_df, PLAYER_BOXSCORES_COLUMNS)
    try:
        copy_via_psycopg(games_csv, "games", GAMES_COLUMNS, pg_url)
        copy_via_psycopg(pbs_csv, "player_boxscores", PLAYER_BOXSCORES_COLUMNS, pg_url)
    finally:
        os.remove(games_csv)
        os.remove(pbs_csv)

    def distinct(series: pd.Series) -> list[str]:
        return sorted({str(val) for val in series.dropna().unique()})

    game_seasons = distinct(games_df["season"])
    player_seasons = distinct(pbs_df["season"])
    print(f"games rows loaded: {len(games_df)} — seasons: {game_seasons}")
    print(f"player_boxscores rows loaded: {len(pbs_df)} — seasons: {player_seasons}")


if __name__ == "__main__":
    main()
