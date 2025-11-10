"""Placeholder daily update job for Render with Postgres upserts."""
from __future__ import annotations

import os
from typing import Iterable, Mapping

from sqlalchemy import create_engine, text

GAMES_CREATE_SQL = """
CREATE TABLE IF NOT EXISTS games (
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
);
"""

PLAYER_BOXSCORES_CREATE_SQL = """
CREATE TABLE IF NOT EXISTS player_boxscores (
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
);
"""


def ensure_sslmode(url: str) -> str:
    if "sslmode=" in url:
        return url
    return f"{url}{'&' if '?' in url else '?'}sslmode=require"


def ident(name: str) -> str:
    return f'"{name.replace(chr(34), chr(34) * 2)}"'


def get_pg_engine():
    url = os.getenv("DATABASE_URL", "").strip()
    if not url:
        raise EnvironmentError("DATABASE_URL must be set for Render jobs.")
    return create_engine(ensure_sslmode(url), pool_pre_ping=True, future=True)


def ensure_tables(engine) -> None:
    with engine.begin() as conn:
        conn.execute(text(GAMES_CREATE_SQL))
        conn.execute(text(PLAYER_BOXSCORES_CREATE_SQL))


def upsert_games(engine, rows: Iterable[Mapping]) -> None:
    rows = list(rows)
    if not rows:
        return
    columns = [
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
    placeholders = ", ".join(f":{col}" for col in columns)
    insert_sql = text(
        f"""
        INSERT INTO games ({", ".join(ident(c) for c in columns)})
        VALUES ({placeholders})
        ON CONFLICT (date, home_team, visitor_team) DO NOTHING
        """
    )
    with engine.begin() as conn:
        conn.execute(insert_sql, list(rows))


def upsert_player_boxscores(engine, rows: Iterable[Mapping]) -> None:
    rows = list(rows)
    if not rows:
        return
    columns = [
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
    placeholders = ", ".join(f":{c}" for c in columns)
    insert_sql = text(
        f"""
        INSERT INTO player_boxscores ({", ".join(ident(c) for c in columns)})
        VALUES ({placeholders})
        ON CONFLICT (GAME_ID, PLAYER_ID) DO NOTHING
        """
    )
    with engine.begin() as conn:
        conn.execute(insert_sql, list(rows))


def main() -> None:
    engine = get_pg_engine()
    ensure_tables(engine)

    # TODO: Replace with NBA stats fetch + transform steps.
    new_games: list[Mapping] = []
    new_player_boxscores: list[Mapping] = []

    upsert_games(engine, new_games)
    upsert_player_boxscores(engine, new_player_boxscores)
    print("Daily update stub complete — awaiting data source wiring.")


if __name__ == "__main__":
    main()
