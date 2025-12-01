#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
from pathlib import Path

from utils.db import fetch_existing_game_keys, get_engine, upsert_rows
from utils.parsers import load_kaggle_games, resolve_kaggle_dir


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Daily NBA games updater")
    parser.add_argument(
        "--lookback-days",
        type=int,
        default=3,
        help="How many days back (inclusive) to reprocess",
    )
    parser.add_argument(
        "--kaggle-dir",
        type=str,
        default=None,
        help="Override Kaggle dataset directory (defaults to kagglehub cache or $KAGGLE_DATA_DIR)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Compute missing rows without writing to Postgres",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    today = dt.date.today()
    start_date = today - dt.timedelta(days=args.lookback_days)
    data_dir = resolve_kaggle_dir(args.kaggle_dir)
    print(f"📂 Using Kaggle data at {Path(data_dir)}")

    games = load_kaggle_games(data_dir, start_date, today)
    print(f"🔎 Loaded {len(games)} games from Kaggle window {start_date} → {today}")

    engine = get_engine()
    existing_keys = fetch_existing_game_keys(engine, start_date, today)
    new_games = [
        game
        for game in games
        if (game["date"], game["home_team"], game["visitor_team"]) not in existing_keys
    ]
    if not new_games:
        print("✅ No new games detected")
        return

    if args.dry_run:
        print(f"ℹ️ Dry-run only — would insert {len(new_games)} rows")
        return

    inserted = upsert_rows(engine, "games", new_games)
    print(f"✅ Inserted {inserted} games")


if __name__ == "__main__":
    main()
