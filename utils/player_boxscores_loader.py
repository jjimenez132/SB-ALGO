"""Shared helpers to load player boxscores into Postgres."""

from __future__ import annotations

from datetime import date
from typing import Dict, Iterable, List, Sequence

from sqlalchemy import MetaData, Table, insert, text
from sqlalchemy.engine import Engine

from .boxscore_ids import compute_game_id, compute_player_id, compute_team_id


def get_player_boxscores_table(engine: Engine) -> Table:
    metadata = MetaData()
    metadata.reflect(bind=engine, only=["player_boxscores"])
    return metadata.tables["player_boxscores"]


def replace_player_boxscores(
    engine: Engine,
    rows: Iterable[Dict],
    dates: Sequence[date],
    season_label: str,
) -> List:
    """Delete and re-insert player boxscores for the provided dates."""
    dates = sorted({d for d in dates})
    if not dates:
        return []

    table = get_player_boxscores_table(engine)
    placeholder = ", ".join(f":d{i}" for i in range(len(dates)))
    params = {f"d{i}": d for i, d in enumerate(dates)}

    payloads = [
        {
            "game_id": compute_game_id(r["game_date"], r["team"], r["opponent"]),
            "team_id": compute_team_id(r["team"]),
            "team_abbreviation": r["team"],
            "team_city": r.get("team_city"),
            "player_id": compute_player_id(
                r["player_name"], r["team"], r["game_date"]
            ),
            "player_name": r["player_name"],
            "nickname": r.get("nickname"),
            "start_position": r.get("start_position"),
            "comment": r.get("comment"),
            "min": r["mp"],
            "fgm": r["fgm"],
            "fga": r["fga"],
            "fg_pct": r["fg_pct"],
            "fg3m": r["fg3m"],
            "fg3a": r["fg3a"],
            "fg3_pct": r["fg3_pct"],
            "ftm": r["ftm"],
            "fta": r["fta"],
            "ft_pct": r["ft_pct"],
            "oreb": r["orb"],
            "dreb": r["drb"],
            "reb": r["trb"],
            "ast": r["ast"],
            "stl": r["stl"],
            "blk": r["blk"],
            "TO": r["tov"],
            "pf": r["pf"],
            "pts": r["pts"],
            "plus_minus": r["plus_minus"],
            "season": season_label,
            "season_1": season_label,
            "game_date": r["game_date"],
        }
        for r in rows
    ]

    with engine.begin() as conn:
        conn.execute(
            text(
                f"DELETE FROM player_boxscores WHERE game_date IN ({placeholder})"
            ),
            params,
        )
        if payloads:
            conn.execute(insert(table), payloads)
        summary = conn.execute(
            text(
                f"""
                SELECT game_date,
                       team_abbreviation AS team,
                       SUM(pts) AS total_pts,
                       COUNT(*) AS players
                FROM player_boxscores
                WHERE game_date IN ({placeholder})
                GROUP BY game_date, team_abbreviation
                ORDER BY game_date, team_abbreviation
                """
            ),
            params,
        ).fetchall()

    return summary
