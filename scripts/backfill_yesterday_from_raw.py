#!/usr/bin/env python3
"""Load games + player boxscores for a day using local Basketball-Reference TSV exports."""

from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta
from pathlib import Path
import sys
from typing import List

from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sb_algo_db import get_pg_engine
from utils.bref_parser import parse_bref_boxscores, parse_bref_games_table
from utils.player_boxscores_loader import replace_player_boxscores

RAW_DIR = Path("data/raw")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Backfill one day's games and player boxscores from Basketball-Reference raw TSV exports."
    )
    parser.add_argument(
        "--date",
        type=str,
        help="Target date in YYYY-MM-DD (defaults to yesterday).",
    )
    parser.add_argument(
        "--raw-dir",
        type=Path,
        default=RAW_DIR,
        help="Directory containing games_YYYY_MM_DD.tsv and player_boxscores_YYYY_MM_DD.tsv (default: data/raw).",
    )
    parser.add_argument(
        "--games-file",
        type=Path,
        help="Optional explicit path to the raw games TSV export.",
    )
    parser.add_argument(
        "--boxscores-file",
        type=Path,
        help="Optional explicit path to the raw player boxscores TSV export.",
    )
    return parser.parse_args()


def nba_season_label(game_date: date) -> str:
    start_year = game_date.year if game_date.month >= 7 else game_date.year - 1
    end_year = (start_year + 1) % 100
    return f"{start_year}-{str(end_year).zfill(2)}"


def resolve_paths(args: argparse.Namespace, target: date) -> tuple[Path, Path]:
    slug = target.strftime("%Y_%m_%d")
    raw_dir = args.raw_dir
    games_file = args.games_file or (raw_dir / f"games_{slug}.tsv")
    box_file = args.boxscores_file or (raw_dir / f"player_boxscores_{slug}.tsv")
    return games_file, box_file


def load_text(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"Missing required raw export: {path}")
    return path.read_text(encoding="utf-8")


def replace_games(engine, game_date: date, games: List[dict], season_label: str) -> None:
    if not games:
        raise ValueError("No games parsed from the raw export.")

    payloads = [
        {
            "date": game_date,
            "visitor_team": g["visitor_team"],
            "visitor_pts": g["visitor_pts"],
            "home_team": g["home_team"],
            "home_pts": g["home_pts"],
            "season": season_label,
        }
        for g in games
    ]

    with engine.begin() as conn:
        conn.execute(text("DELETE FROM games WHERE date = :date"), {"date": game_date})
        conn.execute(
            text(
                """
                INSERT INTO games (date, visitor_team, visitor_pts, home_team, home_pts, season)
                VALUES (:date, :visitor_team, :visitor_pts, :home_team, :home_pts, :season)
                """
            ),
            payloads,
        )
        rows = conn.execute(
            text(
                """
                SELECT date, visitor_team, visitor_pts, home_team, home_pts
                FROM games
                WHERE date = :date
                ORDER BY home_team, visitor_team
                """
            ),
            {"date": game_date},
        ).fetchall()

    print("Games table refreshed:")
    for row in rows:
        print(
            f"{row.date} | {row.visitor_team} ({row.visitor_pts}) @ "
            f"{row.home_team} ({row.home_pts})"
        )


def main() -> None:
    args = parse_args()
    target_date = (
        date.fromisoformat(args.date)
        if args.date
        else (datetime.now().date() - timedelta(days=1))
    )
    games_path, boxscores_path = resolve_paths(args, target_date)
    season_label = nba_season_label(target_date)

    games_raw = load_text(games_path)
    games = parse_bref_games_table(games_raw, target_date)

    boxscores_raw = load_text(boxscores_path)
    player_rows = parse_bref_boxscores(boxscores_raw, target_date)

    engine = get_pg_engine()
    replace_games(engine, target_date, games, season_label)
    summary = replace_player_boxscores(
        engine,
        player_rows,
        dates=[target_date],
        season_label=season_label,
    )

    print("Player boxscores summary grouped by team:")
    for row in summary:
        print(
            f"{row.game_date} {row.team}: {row.total_pts} pts "
            f"({row.players} players)"
        )


if __name__ == "__main__":
    main()
