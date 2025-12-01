from __future__ import annotations

import argparse
import datetime as dt
import json
from typing import Any, Callable, Dict, List, Tuple

from data_pipeline.sources import github_hoopr_dataset as source

APIError = source.HoopRDatasetError


def attempt_fetch(
    fetcher: Callable[..., Any],
    *args: Any,
    **kwargs: Any,
) -> Tuple[Any, List[Dict[str, Any]]]:
    errors: List[Dict[str, Any]] = []
    try:
        result = fetcher(*args, simulate_on_error=False, **kwargs)
        return result, errors
    except APIError as exc:
        errors.append(
            {
                "message": str(exc),
                "status_code": exc.status_code,
                "payload": exc.payload,
            }
        )
    except Exception as exc:  # pragma: no cover
        errors.append({"message": str(exc), "exception": exc.__class__.__name__})
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

    team_stats, errors = attempt_fetch(source.fetch_team_stats, "2024")
    print_section("Team Stats", team_stats, errors)

    player_stats, errors = attempt_fetch(source.fetch_player_stats, "2024")
    print_section("Player Stats", player_stats, errors)

    boxscore, errors = attempt_fetch(source.fetch_boxscore, "20240115-001")
    print_section("Boxscore", boxscore, errors)


def main() -> None:
    parser = argparse.ArgumentParser(description="hoopR GitHub dataset test harness")
    parser.add_argument(
        "--today",
        type=lambda value: dt.datetime.strptime(value, "%Y-%m-%d").date(),
        default=dt.date.today(),
    )
    args = parser.parse_args()
    run_tests(args.today)


if __name__ == "__main__":
    main()
