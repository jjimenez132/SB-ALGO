"""Hourly NBA injury report placeholder for Render."""
from __future__ import annotations

import os
from typing import Iterable, Mapping

from sqlalchemy import create_engine, text

INJURY_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS injury_reports (
    timestamp TIMESTAMPTZ,
    team TEXT,
    player TEXT,
    status TEXT,
    note TEXT,
    PRIMARY KEY (timestamp, team, player)
);
"""


def ensure_sslmode(url: str) -> str:
    if "sslmode=" in url:
        return url
    return f"{url}{'&' if '?' in url else '?'}sslmode=require"


def get_pg_engine():
    url = os.getenv("DATABASE_URL", "").strip()
    if not url:
        raise EnvironmentError("DATABASE_URL must be set for injury updates.")
    return create_engine(ensure_sslmode(url), pool_pre_ping=True, future=True)


def ensure_table(engine) -> None:
    with engine.begin() as conn:
        conn.execute(text(INJURY_TABLE_SQL))


def insert_reports(engine, rows: Iterable[Mapping]) -> None:
    rows = list(rows)
    if not rows:
        return
    insert_sql = text(
        """
        INSERT INTO injury_reports (timestamp, team, player, status, note)
        VALUES (:timestamp, :team, :player, :status, :note)
        ON CONFLICT (timestamp, team, player) DO NOTHING
        """
    )
    with engine.begin() as conn:
        conn.execute(insert_sql, rows)


def main() -> None:
    engine = get_pg_engine()
    ensure_table(engine)

    # TODO: Fetch latest injury intel (NBA feed, book APIs, etc.).
    latest_reports: list[Mapping] = []
    insert_reports(engine, latest_reports)
    print("Injury update stub ready — plug in fetch layer.")


if __name__ == "__main__":
    main()
