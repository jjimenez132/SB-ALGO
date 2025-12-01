from __future__ import annotations

import datetime as dt
import json
import time
from typing import Any, Dict, List, Tuple

from data_pipeline.sources import balldontlie
from data_pipeline.sources.balldontlie import BalldontlieAPIError


MAX_RETRIES = 3
BASE_BACKOFF_SECONDS = 3


def fetch_with_retry(target_date: dt.date) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Fetch mapped games for the given date with basic retry/backoff on rate limits.
    """
    errors: List[Dict[str, Any]] = []
    attempt = 0
    while attempt < MAX_RETRIES:
        try:
            data = balldontlie.fetch_and_map(target_date)
            return data, errors
        except BalldontlieAPIError as exc:
            error_detail: Dict[str, Any] = {
                "status_code": exc.status_code,
                "message": str(exc),
                "payload": exc.payload,
            }
            if exc.retry_after is not None:
                error_detail["retry_after"] = exc.retry_after
            errors.append(error_detail)

            if exc.status_code == 429 and attempt < MAX_RETRIES - 1:
                wait_time = exc.retry_after or BASE_BACKOFF_SECONDS * (attempt + 1)
                time.sleep(wait_time)
                attempt += 1
                continue
            break
        except Exception as exc:
            errors.append(
                {
                    "message": str(exc),
                    "exception": exc.__class__.__name__,
                }
            )
            if attempt < MAX_RETRIES - 1:
                time.sleep(BASE_BACKOFF_SECONDS * (attempt + 1))
                attempt += 1
                continue
            break

    return [], errors


def print_report(label: str, games: List[Dict[str, Any]], errors: List[Dict[str, Any]]) -> None:
    print(f"=== {label} ===")
    print(f"Game count: {len(games)}")
    print(json.dumps(games, indent=2, sort_keys=True))
    if errors:
        print("Errors:")
        print(json.dumps(errors, indent=2, sort_keys=True))
    else:
        print("Errors: []")
    print()


def main() -> None:
    today = dt.date.today()
    yesterday = today - dt.timedelta(days=1)

    for label, target_date in (
        ("Yesterday", yesterday),
        ("Today", today),
    ):
        games, errors = fetch_with_retry(target_date)
        print_report(f"{label} ({target_date.isoformat()})", games, errors)


if __name__ == "__main__":
    main()
