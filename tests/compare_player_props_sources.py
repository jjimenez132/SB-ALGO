from __future__ import annotations

"""
Comparison harness for NBA player props sources.

Usage:
    export RAPIDAPI_KEY="..."
    # Optional overrides per provider:
    # export PROP_ODDS_RAPIDAPI_HOST="prop-odds.p.rapidapi.com"
    # export RAFISTAN_RAPIDAPI_KEY="..."
    PYTHONPATH=. python3 tests/compare_player_props_sources.py --today YYYY-MM-DD

The script only touches HTTP APIs (no DB writes) and prints coverage stats plus an
auto-generated ranking for each provider that currently has a usable HTTP props feed.
"""

import argparse
import datetime as dt
import json
from typing import Any, Dict, List, Tuple

from data_pipeline.sources import prop_odds_player_props
from data_pipeline.sources import rafistan_player_props


ProviderModule = Any

PROVIDERS: List[Tuple[str, ProviderModule]] = [
    ("Prop-Odds (RapidAPI)", prop_odds_player_props),
    ("Rafistan RapidAPI", rafistan_player_props),
]

SKIPPED_PROVIDERS = [
    (
        "BoltOdds",
        "Docs show a WebSocket-first feed (`wss://spro.agency/api`) with GET helpers "
        "but no REST odds endpoint, so it cannot plug into the SB-ALGO HTTP pattern yet.",
    ),
    (
        "SportsGameOdds",
        "Public docs are served via hashed VitePress assets that currently return HTTP 500 "
        "errors, preventing discovery of the REST interface for player props.",
    ),
    (
        "SportsAPIs.dev",
        "This site is a directory of third-party APIs, not a provider of odds data itself.",
    ),
]


def fetch_provider_data(module: ProviderModule, target_date: dt.date) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    try:
        return module.fetch_props_for_date_mapped(target_date)
    except Exception as exc:  # pragma: no cover - defensive
        return [], [
            {
                "message": f"Unexpected error: {exc}",
                "source": getattr(module, "SOURCE_NAME", "unknown"),
            }
        ]


def pick_example(props: List[Dict[str, Any]], market_key: str) -> Dict[str, Any] | None:
    for prop in props:
        if prop.get("market") == market_key:
            return prop
    return None


def summarize_provider(name: str, module: ProviderModule, target_date: dt.date) -> Dict[str, Any]:
    props, errors = fetch_provider_data(module, target_date)
    unique_players = {prop.get("player_name") for prop in props if prop.get("player_name")}
    unique_markets = sorted({prop.get("market") for prop in props if prop.get("market")})

    completeness_ratio = 0.0
    if props:
        filled = sum(
            1
            for prop in props
            if prop.get("line") is not None
            and prop.get("over_odds") is not None
            and prop.get("under_odds") is not None
        )
        completeness_ratio = filled / len(props)

    examples = {
        "points": pick_example(props, "points"),
        "rebounds": pick_example(props, "rebounds"),
        "assists": pick_example(props, "assists"),
        "pra": pick_example(props, "pra"),
        "threes": pick_example(props, "threes"),
    }

    score = (
        len(props)
        + len(unique_players) * 0.5
        + len(unique_markets) * 5
        + (5 if not errors else 0)
        + completeness_ratio * 10
    )

    return {
        "name": name,
        "prop_count": len(props),
        "players": len(unique_players),
        "markets": unique_markets,
        "examples": examples,
        "errors": errors,
        "score": score,
    }


def print_summary(summary: Dict[str, Any]) -> None:
    print(f"Provider: {summary['name']}")
    print(f"  total_props: {summary['prop_count']}")
    print(f"  unique_players: {summary['players']}")
    print(f"  markets: {summary['markets']}")
    print("  example_props:")
    pretty_examples = {
        market: summary["examples"][market]
        for market in summary["examples"]
        if summary["examples"][market]
    }
    print(json.dumps(pretty_examples, indent=2, sort_keys=True))
    print("  errors:")
    if summary["errors"]:
        print(json.dumps(summary["errors"], indent=2, sort_keys=True))
    else:
        print("  []")
    print()


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare NBA player props sources.")
    parser.add_argument(
        "--today",
        type=lambda value: dt.datetime.strptime(value, "%Y-%m-%d").date(),
        default=dt.date.today(),
    )
    args = parser.parse_args()
    target_date = args.today

    summaries = [summarize_provider(name, module, target_date) for name, module in PROVIDERS]
    for summary in summaries:
        print_summary(summary)

    print("Skipped providers (no HTTP props feed available):")
    for name, reason in SKIPPED_PROVIDERS:
        print(f"- {name}: {reason}")
    print()

    ranked = sorted(summaries, key=lambda data: data["score"], reverse=True)
    print("AUTO-RANKING:")
    for idx, summary in enumerate(ranked, 1):
        status = " (errors)" if summary["errors"] else ""
        print(f"{idx}. {summary['name']} – score {summary['score']:.1f}{status}")


if __name__ == "__main__":
    main()
