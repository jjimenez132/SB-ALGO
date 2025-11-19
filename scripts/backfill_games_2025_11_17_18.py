"""Backfill games table entries for Nov 17-18, 2025."""

from __future__ import annotations

from datetime import date
from pathlib import Path
import sys
from typing import Sequence

from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from etl.daily_update_pg import get_pg_engine


GAMES_TO_INSERT: Sequence[dict] = [
    # November 17, 2025
    {
        "date": date(2025, 11, 17),
        "visitor_team": "Milwaukee Bucks",
        "visitor_pts": 106,
        "home_team": "Cleveland Cavaliers",
        "home_pts": 118,
    },
    {
        "date": date(2025, 11, 17),
        "visitor_team": "Chicago Bulls",
        "visitor_pts": 130,
        "home_team": "Denver Nuggets",
        "home_pts": 127,
    },
    {
        "date": date(2025, 11, 17),
        "visitor_team": "Indiana Pacers",
        "visitor_pts": 112,
        "home_team": "Detroit Pistons",
        "home_pts": 127,
    },
    {
        "date": date(2025, 11, 17),
        "visitor_team": "New York Knicks",
        "visitor_pts": 113,
        "home_team": "Miami Heat",
        "home_pts": 115,
    },
    {
        "date": date(2025, 11, 17),
        "visitor_team": "Dallas Mavericks",
        "visitor_pts": 96,
        "home_team": "Minnesota Timberwolves",
        "home_pts": 120,
    },
    {
        "date": date(2025, 11, 17),
        "visitor_team": "Oklahoma City Thunder",
        "visitor_pts": 126,
        "home_team": "New Orleans Pelicans",
        "home_pts": 109,
    },
    {
        "date": date(2025, 11, 17),
        "visitor_team": "Los Angeles Clippers",
        "visitor_pts": 108,
        "home_team": "Philadelphia 76ers",
        "home_pts": 110,
    },
    {
        "date": date(2025, 11, 17),
        "visitor_team": "Charlotte Hornets",
        "visitor_pts": 108,
        "home_team": "Toronto Raptors",
        "home_pts": 110,
    },
    # November 18, 2025
    {
        "date": date(2025, 11, 18),
        "visitor_team": "Detroit Pistons",
        "visitor_pts": 120,
        "home_team": "Atlanta Hawks",
        "home_pts": 112,
    },
    {
        "date": date(2025, 11, 18),
        "visitor_team": "Boston Celtics",
        "visitor_pts": 113,
        "home_team": "Brooklyn Nets",
        "home_pts": 99,
    },
    {
        "date": date(2025, 11, 18),
        "visitor_team": "Utah Jazz",
        "visitor_pts": 126,
        "home_team": "Los Angeles Lakers",
        "home_pts": 140,
    },
    {
        "date": date(2025, 11, 18),
        "visitor_team": "Golden State Warriors",
        "visitor_pts": 113,
        "home_team": "Orlando Magic",
        "home_pts": 121,
    },
    {
        "date": date(2025, 11, 18),
        "visitor_team": "Phoenix Suns",
        "visitor_pts": 127,
        "home_team": "Portland Trail Blazers",
        "home_pts": 110,
    },
    {
        "date": date(2025, 11, 18),
        "visitor_team": "Memphis Grizzlies",
        "visitor_pts": 101,
        "home_team": "San Antonio Spurs",
        "home_pts": 111,
    },
]


DELETE_SQL = text(
    """
    DELETE FROM games
    WHERE date IN (:date_1, :date_2)
    """
)

INSERT_SQL = text(
    """
    INSERT INTO games (date, visitor_team, visitor_pts, home_team, home_pts)
    VALUES (:date, :visitor_team, :visitor_pts, :home_team, :home_pts)
    """
)

SELECT_SQL = text(
    """
    SELECT date, visitor_team, visitor_pts, home_team, home_pts
    FROM games
    WHERE date IN (:date_1, :date_2)
    ORDER BY date, home_team, visitor_team
    """
)


def main() -> None:
    engine = get_pg_engine()
    with engine.begin() as conn:
        conn.execute(
            DELETE_SQL,
            {
                "date_1": date(2025, 11, 17),
                "date_2": date(2025, 11, 18),
            },
        )
        conn.execute(INSERT_SQL, GAMES_TO_INSERT)
        rows = conn.execute(
            SELECT_SQL,
            {
                "date_1": date(2025, 11, 17),
                "date_2": date(2025, 11, 18),
            },
        ).fetchall()

    print("Games on 2025-11-17 and 2025-11-18:")
    for row in rows:
        print(
            f"{row.date} | {row.visitor_team} ({row.visitor_pts}) @ "
            f"{row.home_team} ({row.home_pts})"
        )


if __name__ == "__main__":
    main()
