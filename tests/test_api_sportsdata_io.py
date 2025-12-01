from __future__ import annotations

import argparse
import datetime as dt
import json
import time
from typing import Any, Callable, Dict, List, Tuple

from data_pipeline.sources import sportsdata_io as source

APIError = source.SportsDataError
SEASON = "2024"
GAME_KEY = "20240115-LAL-BOS"


def attempt_fetch(
    fetcher: Callable[..., Any],
    *args: Any,
    **kwargs: Any,
) -> Tuple[Any, List[Dict[str, Any]]]:
    errors: List[Dict[str, Any]] = []
    for attempt in range(2):
        try:
            result = fetcher(*args, simulate_on_error=False, **kwargs)
            return result, errors
        except APIError as exc:
            errors.append(
                {
                    "message": str(exc),
                    "status_code": exc.status_code,
                    "payload": exc.payload,
                    "retry_after": exc.retry_after,
                }
            )
            if exc.status_code == 429 and attempt == 0:
                time.sleep(exc.retry_after or 2)
                continue
            break
        except Exception as exc:  # pragma: no cover
            errors.append({"message": str(exc), "exception": exc.__class__.__name__})
            break
    fallback = fetcher(*args, simulate_on_error=True, **kwargs)
    return fallback, errors


def print_section(label: str, payload: Any, errors: List[Dict[str, Any]]) -> None:
    print(f"=== {label} ===")
    print(json.dumps(payload, indent=2, sort_keys=True))
    if errors:
        print("Errors:")
        print(json.dumps(errors, indent=2, sort_keys=True))
    else:
        print("Errors: []")
    print()


def run_tests(base_date: dt.date) -> None:
    yesterday = base_date - dt.timedelta(days=1)
    historical = dt.date(2023, 1, 15)

    for label, target_date in (
        ("Yesterday Games", yesterday),
        ("Today Games", base_date),
        ("Historical Games", historical),
    ):
        data, errors = attempt_fetch(source.fetch_games_mapped, target_date)
        print_section(label, data, errors)

    team_stats, errors = attempt_fetch(source.fetch_team_stats, SEASON)
    print_section("Team Season Stats", team_stats, errors)

    player_stats, errors = attempt_fetch(source.fetch_player_stats, SEASON)
    print_section("Player Season Stats", player_stats, errors)

    boxscore, errors = attempt_fetch(source.fetch_boxscore, GAME_KEY)
    print_section("Boxscore", boxscore, errors)


def main() -> None:
    parser = argparse.ArgumentParser(description="SportsDataIO source smoke test")
    parser.add_argument(
        "--today",
        type=lambda value: dt.datetime.strptime(value, "%Y-%m-%d").date(),
        default=dt.date.today(),
    )
    args = parser.parse_args()
    run_tests(args.today)


if __name__ == "__main__":
    main()
