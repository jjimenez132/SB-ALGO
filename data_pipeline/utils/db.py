from __future__ import annotations

import os
from typing import Iterable, Mapping, MutableMapping, Sequence

from sqlalchemy import (
    BigInteger,
    Column,
    Date,
    Float,
    Integer,
    MetaData,
    String,
    Table,
    bindparam,
    create_engine,
    text,
)
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Engine


METADATA = MetaData()

GAMES_TABLE = Table(
    "games",
    METADATA,
    Column("date", Date),
    Column("start_time", String),
    Column("visitor_team", String),
    Column("visitor_pts", Float),
    Column("home_team", String),
    Column("home_pts", Float),
    Column("attendance", Integer),
    Column("notes", String),
    Column("season", Integer),
    Column("total_points", Float),
    Column("margin_home", Float),
    Column("abs_margin", Float),
    Column("home_win", Integer),
    Column("home_team_std", String),
    Column("visitor_team_std", String),
    Column("possible_playoff", Integer),
    Column("home_days_rest", Float),
    Column("home_is_b2b", Integer),
    Column("visitor_days_rest", Float),
    Column("visitor_is_b2b", Integer),
    Column("season_avg_total", Float),
    Column("season_std", Float),
    Column("total_minus_season_avg", Float),
)

PLAYER_BOXSCORES_TABLE = Table(
    "player_boxscores",
    METADATA,
    Column("game_id", BigInteger),
    Column("team_id", BigInteger),
    Column("team_abbreviation", String),
    Column("team_city", String),
    Column("player_id", BigInteger),
    Column("player_name", String),
    Column("nickname", String),
    Column("start_position", String),
    Column("comment", String),
    Column("min", String),
    Column("fgm", Float),
    Column("fga", Float),
    Column("fg_pct", Float),
    Column("fg3m", Float),
    Column("fg3a", Float),
    Column("fg3_pct", Float),
    Column("ftm", Float),
    Column("fta", Float),
    Column("ft_pct", Float),
    Column("oreb", Float),
    Column("dreb", Float),
    Column("reb", Float),
    Column("ast", Float),
    Column("stl", Float),
    Column("blk", Float),
    Column("to", Float),
    Column("pf", Float),
    Column("pts", Float),
    Column("plus_minus", Float),
    Column("season", String),
    Column("season_1", String),
    Column("game_date", Date),
)


TABLE_SPECS = {
    "games": {
        "table": GAMES_TABLE,
        "columns": [
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
        ],
        "conflict": ["date", "home_team", "visitor_team"],
    },
    "player_boxscores": {
        "table": PLAYER_BOXSCORES_TABLE,
        "columns": [
            "game_id",
            "team_id",
            "team_abbreviation",
            "team_city",
            "player_id",
            "player_name",
            "nickname",
            "start_position",
            "comment",
            "min",
            "fgm",
            "fga",
            "fg_pct",
            "fg3m",
            "fg3a",
            "fg3_pct",
            "ftm",
            "fta",
            "ft_pct",
            "oreb",
            "dreb",
            "reb",
            "ast",
            "stl",
            "blk",
            "to",
            "pf",
            "pts",
            "plus_minus",
            "season",
            "season_1",
            "game_date",
        ],
        "conflict": ["game_id", "player_id"],
    },
}


def get_engine(db_url: str | None = None) -> Engine:
    url = (db_url or os.getenv("DATABASE_URL", "")).strip()
    if not url:
        raise EnvironmentError("DATABASE_URL must be set")
    return create_engine(url, pool_pre_ping=True, future=True)


def chunked(iterable: Iterable[Mapping], chunk_size: int = 500) -> Iterable[list[Mapping]]:
    batch: list[Mapping] = []
    for row in iterable:
        batch.append(row)
        if len(batch) >= chunk_size:
            yield batch
            batch = []
    if batch:
        yield batch


def sanitize_row(row: Mapping, allowed_columns: Sequence[str]) -> MutableMapping:
    return {column: row.get(column) for column in allowed_columns}


def upsert_rows(
    engine: Engine,
    table_name: str,
    rows: Iterable[Mapping],
    chunk_size: int = 500,
) -> int:
    spec = TABLE_SPECS[table_name]
    table = spec["table"]
    columns = spec["columns"]
    conflict_cols = spec["conflict"]

    inserted = 0
    for batch in chunked(rows, chunk_size):
        payload = [sanitize_row(row, columns) for row in batch]
        stmt = insert(table).values(payload)
        stmt = stmt.on_conflict_do_nothing(index_elements=conflict_cols)
        with engine.begin() as conn:
            result = conn.execute(stmt)
        inserted += result.rowcount or 0
    return inserted


def fetch_existing_game_keys(engine: Engine, start_date, end_date) -> set[tuple]:
    query = text(
        """
        SELECT date, home_team, visitor_team
        FROM games
        WHERE date BETWEEN :start AND :end
        """
    )
    with engine.begin() as conn:
        rows = conn.execute(query, {"start": start_date, "end": end_date}).all()
    return {(row[0], row[1], row[2]) for row in rows}


def fetch_existing_boxscore_pairs(engine: Engine, game_ids: Sequence[int]) -> set[tuple]:
    if not game_ids:
        return set()
    query = (
        text(
            """
            SELECT game_id, player_id
            FROM player_boxscores
            WHERE game_id IN :ids
            """
        ).bindparams(bindparam("ids", expanding=True))
    )
    with engine.begin() as conn:
        rows = conn.execute(query, {"ids": list(game_ids)}).all()
    return {(row[0], row[1]) for row in rows}
