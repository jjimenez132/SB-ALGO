from __future__ import annotations

import argparse
import datetime as dt
import json
from typing import Any, Dict, List, Tuple

from data_pipeline.sources import odds_api_player_props as source


def attempt_fetch(target_date: dt.date) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    errors: List[Dict[str, Any]] = []
    try:
        mapped, fetch_errors = source.fetch_props_for_date_mapped(target_date)
        errors.extend(fetch_errors)
        return mapped, errors
    except source.PlayerPropsAPIError as exc:
        errors.append(
            {
                "message": str(exc),
                "status_code": exc.status_code,
                "payload": exc.payload,
                "retry_after": exc.retry_after,
            }
        )
    except Exception as exc:  # pragma: no cover - defensive
        errors.append({"message": str(exc), "exception": exc.__class__.__name__})
    return [], errors


def print_section(provider: str, target_date: dt.date, data, errors: List[Dict[str, Any]]) -> None:
    preview = data[:5]
    print(f"=== {provider} – {target_date.isoformat()} ===")
    print(f"Prop count: {len(data)}")
    print(json.dumps(preview, indent=2, sort_keys=True))
    print("Errors:")
    if errors:
        print(json.dumps(errors, indent=2, sort_keys=True))
    else:
        print("[]")
    print()


def run_tests(base_date: dt.date) -> None:
    yesterday = base_date - dt.timedelta(days=1)

    for target in (yesterday, base_date):
        data, errors = attempt_fetch(target)
        print_section("TheOddsAPI", target, data, errors)


def main() -> None:
    parser = argparse.ArgumentParser(description="TheOddsAPI player props harness")
    parser.add_argument(
        "--today",
        type=lambda value: dt.datetime.strptime(value, "%Y-%m-%d").date(),
        default=dt.date.today(),
    )
    args = parser.parse_args()
    run_tests(args.today)


if __name__ == "__main__":
    main()
