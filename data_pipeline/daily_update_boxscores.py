#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
from itertools import islice
from pathlib import Path
from typing import Iterable, Iterator, List

from utils.db import (
    fetch_existing_boxscore_pairs,
    get_engine,
    upsert_rows,
)
from utils.parsers import resolve_kaggle_dir, stream_kaggle_boxscores


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Daily NBA boxscore updater")
    parser.add_argument(
        "--lookback-days",
        type=int,
        default=5,
        help="How many days back to reprocess",
    )
    parser.add_argument(
        "--kaggle-dir",
        type=str,
        default=None,
        help="Override Kaggle dataset path",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=2000,
        help="Rows per database upsert",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Skip writing to the database",
    )
    return parser.parse_args()


def chunk_records(records: Iterator[dict], size: int) -> Iterator[list[dict]]:
    while True:
        batch = list(islice(records, size))
        if not batch:
            break
        yield batch


def main() -> None:
    args = parse_args()
    today = dt.date.today()
    start_date = today - dt.timedelta(days=args.lookback_days)

    data_dir = resolve_kaggle_dir(args.kaggle_dir)
    print(f"📂 Using Kaggle player stats at {Path(data_dir)}")

    rows = stream_kaggle_boxscores(data_dir, start_date, today)
    engine = get_engine()
    total_inserted = 0
    total_seen = 0

    for batch in chunk_records(rows, args.batch_size):
        total_seen += len(batch)
        game_ids = sorted({row["game_id"] for row in batch if row.get("game_id")})
        existing_pairs = fetch_existing_boxscore_pairs(engine, game_ids)
        filtered = [
            row
            for row in batch
            if row.get("player_id")
            and row.get("game_id")
            and (row["game_id"], row["player_id"]) not in existing_pairs
        ]
        if not filtered:
            continue

        if args.dry_run:
            print(f"ℹ️ Dry-run: would insert {len(filtered)} player rows (batch of {len(batch)})")
            continue

        total_inserted += upsert_rows(engine, "player_boxscores", filtered)

    print(
        f"✅ Boxscore ingestion complete. {total_inserted} new rows inserted "
        f"out of {total_seen} scanned between {start_date} and {today}."
    )


if __name__ == "__main__":
    main()
