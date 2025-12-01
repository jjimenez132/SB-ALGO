from __future__ import annotations

import os
from datetime import date, datetime
from typing import Any, Dict, Iterable, List, Tuple

import requests

from data_pipeline.utils.validators import TEAM_ABBREVIATIONS


class PlayerPropsAPIError(Exception):
    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        payload: Dict[str, Any] | None = None,
        retry_after: int | None = None,
    ) -> None:
        self.message = message
        self.status_code = status_code
        self.payload = payload or {}
        self.retry_after = retry_after
        super().__init__(message)


SOURCE_NAME = "rafistan_rapidapi"
API_HOST = os.getenv("RAFISTAN_RAPIDAPI_HOST", "nba-player-props-odds.p.rapidapi.com")
API_KEY_ENV = "RAFISTAN_RAPIDAPI_KEY"
FALLBACK_API_KEY_ENV = "RAPIDAPI_KEY"
DEFAULT_MARKETS = [
    "points",
    "rebounds",
    "assists",
    "points+rebounds+assists",
    "three-pointers-made",
]
ODDS_PATH = "/odds"


def _request(path: str, params: Dict[str, Any]) -> Dict[str, Any] | List[Any]:
    api_key = os.getenv(API_KEY_ENV) or os.getenv(FALLBACK_API_KEY_ENV)
    if not api_key:
        raise PlayerPropsAPIError(
            f"Missing RapidAPI key. Set {API_KEY_ENV} or {FALLBACK_API_KEY_ENV}."
        )

    headers = {
        "x-rapidapi-key": api_key,
        "x-rapidapi-host": API_HOST,
        "accept": "application/json",
    }
    url = f"https://{API_HOST}{path}"
    try:
        response = requests.get(url, headers=headers, params=params, timeout=20)
    except requests.RequestException as exc:  # pragma: no cover - network failure
        raise PlayerPropsAPIError(
            f"Rafistan RapidAPI request failed: {exc}",
        ) from exc

    if response.status_code == 200:
        try:
            return response.json()
        except ValueError as exc:  # pragma: no cover
            raise PlayerPropsAPIError(
                "Rafistan RapidAPI returned invalid JSON",
                payload={"text": response.text},
            ) from exc

    retry_after = response.headers.get("Retry-After")
    retry_seconds = None
    if retry_after:
        try:
            retry_seconds = int(retry_after)
        except ValueError:
            retry_seconds = None

    try:
        payload = response.json()
    except ValueError:
        payload = {"text": response.text}

    if response.status_code == 429:
        raise PlayerPropsAPIError(
            "Rafistan RapidAPI rate limit hit",
            status_code=response.status_code,
            payload=payload,
            retry_after=retry_seconds,
        )

    raise PlayerPropsAPIError(
        f"Rafistan RapidAPI error ({response.status_code})",
        status_code=response.status_code,
        payload=payload,
        retry_after=retry_seconds,
    )


def _simulate_payload(target_date: date) -> Dict[str, Any]:
    compact = target_date.strftime("%Y%m%d")
    iso = target_date.isoformat()
    return {
        "_simulated": True,
        "events": [
            {
                "id": f"{compact}-GSWLAL",
                "commence_time": f"{iso}T03:30:00Z",
                "home_team": "Los Angeles Lakers",
                "away_team": "Golden State Warriors",
                "sportsbooks": [
                    {
                        "book": "FanDuel",
                        "markets": [
                            {
                                "market": "points",
                                "participants": [
                                    {
                                        "player": "Stephen Curry",
                                        "team": "Golden State Warriors",
                                        "line": 29.5,
                                        "over": -115,
                                        "under": -105,
                                    },
                                    {
                                        "player": "LeBron James",
                                        "team": "Los Angeles Lakers",
                                        "line": 25.5,
                                        "over": -110,
                                        "under": -110,
                                    },
                                ],
                            },
                            {
                                "market": "assists",
                                "participants": [
                                    {
                                        "player": "LeBron James",
                                        "team": "Los Angeles Lakers",
                                        "line": 8.5,
                                        "over": +105,
                                        "under": -130,
                                    }
                                ],
                            },
                        ],
                    }
                ],
            }
        ],
    }


def fetch_props_for_date_raw(
    target_date: date, simulate_on_error: bool = True
) -> Dict[str, Any] | List[Any]:
    params = {
        "date": target_date.isoformat(),
        "markets": ",".join(DEFAULT_MARKETS),
    }
    try:
        return _request(ODDS_PATH, params)
    except PlayerPropsAPIError:
        if not simulate_on_error:
            raise
        return _simulate_payload(target_date)


MARKET_ALIASES = {
    "player_points": "points",
    "player_rebounds": "rebounds",
    "player_assists": "assists",
    "player_points_rebounds_assists": "pra",
    "points+rebounds+assists": "pra",
    "three_pointers_made": "threes",
    "three-pointers-made": "threes",
}


def _normalize_market(raw: str | None) -> str:
    if not raw:
        return "unknown"
    key = raw.strip().lower().replace(" ", "_")
    return MARKET_ALIASES.get(key, raw.strip().lower())


def _normalize_team(raw: str | None) -> str | None:
    if not raw:
        return None
    lookup = raw.strip().lower()
    return TEAM_ABBREVIATIONS.get(lookup, raw.strip().upper()[:3])


def _normalize_book(raw: Dict[str, Any]) -> str:
    for field in ("book", "title", "name", "key"):
        value = raw.get(field)
        if value:
            return str(value).upper()
    return "UNKNOWN"


def _extract_events(raw: Dict[str, Any] | List[Any]) -> Iterable[Dict[str, Any]]:
    if isinstance(raw, list):
        return raw
    if isinstance(raw, dict):
        for field in ("events", "games", "data", "results"):
            value = raw.get(field)
            if isinstance(value, list):
                return value
    return []


def _build_game_id(event: Dict[str, Any], fallback_date: date) -> str:
    if event.get("game_id"):
        return str(event["game_id"])
    if event.get("id"):
        return str(event["id"])
    home = _normalize_team(event.get("home_team")) or "HOME"
    away = _normalize_team(event.get("away_team")) or "AWAY"
    return f"{fallback_date:%Y%m%d}-{away}{home}"


def _extract_line(outcome: Dict[str, Any]) -> float | None:
    for field in ("line", "points", "value", "handicap"):
        value = outcome.get(field)
        if value is None:
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return None


def _extract_price(outcome: Dict[str, Any], field_candidates: Iterable[str]) -> float | None:
    for field in field_candidates:
        value = outcome.get(field)
        if value is None:
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return None


def _extract_player_name(outcome: Dict[str, Any]) -> str | None:
    for field in ("player", "player_name", "participant", "name"):
        value = outcome.get(field)
        if value:
            return str(value)
    return None


def _extract_player_id(outcome: Dict[str, Any]) -> str | None:
    for field in ("player_id", "id", "athlete_id"):
        value = outcome.get(field)
        if value:
            return str(value)
    return None


def _map_outcomes(
    event: Dict[str, Any],
    book: Dict[str, Any],
    market: Dict[str, Any],
    game_date: str,
    game_id: str,
) -> List[Dict[str, Any]]:
    normalized_market = _normalize_market(market.get("market") or market.get("key"))
    outcomes: Iterable[Dict[str, Any]] = (
        market.get("participants")
        or market.get("outcomes")
        or market.get("lines")
        or []
    )
    grouped: Dict[str, Dict[str, Any]] = {}

    for outcome in outcomes:
        player_name = _extract_player_name(outcome)
        if not player_name:
            continue
        key = player_name.lower()
        player_team = _normalize_team(outcome.get("team") or outcome.get("team_name"))

        if key not in grouped:
            grouped[key] = {
                "date": game_date,
                "game_id": game_id,
                "book": _normalize_book(book),
                "player_name": player_name,
                "player_id": _extract_player_id(outcome),
                "team": player_team,
                "opponent": None,
                "market": normalized_market,
                "line": _extract_line(outcome),
                "over_odds": None,
                "under_odds": None,
                "source": SOURCE_NAME,
            }

        entry = grouped[key]
        line_value = _extract_line(outcome)
        if line_value is not None:
            entry["line"] = line_value

        over_value = _extract_price(
            outcome,
            ("over", "over_price", "american_over", "overOdds", "odds_over"),
        )
        under_value = _extract_price(
            outcome,
            ("under", "under_price", "american_under", "underOdds", "odds_under"),
        )

        if over_value is not None:
            entry["over_odds"] = over_value
        if under_value is not None:
            entry["under_odds"] = under_value

        # Some providers encode odds as nested dicts with {type: "over", odds: -110}
        if over_value is None or under_value is None:
            nested_prices = outcome.get("prices") or []
            if isinstance(nested_prices, list):
                for price in nested_prices:
                    descriptor = str(price.get("type") or price.get("label") or "").lower()
                    val = _extract_price(price, ("price", "odds", "american"))
                    if descriptor == "over" and val is not None:
                        entry["over_odds"] = val
                    elif descriptor == "under" and val is not None:
                        entry["under_odds"] = val

        home = _normalize_team(event.get("home_team"))
        away = _normalize_team(event.get("away_team"))
        if player_team and home and away:
            entry["opponent"] = away if player_team == home else home if player_team == away else entry["opponent"]

    return list(grouped.values())


def map_props_from_raw(
    raw: Dict[str, Any] | List[Any], target_date: date
) -> List[Dict[str, Any]]:
    mapped: List[Dict[str, Any]] = []
    for event in _extract_events(raw):
        commence = event.get("commence_time") or event.get("start_time")
        game_date = target_date.isoformat()
        if commence:
            try:
                commence_dt = datetime.fromisoformat(commence.replace("Z", "+00:00"))
                game_date = commence_dt.date().isoformat()
            except ValueError:
                game_date = target_date.isoformat()

        game_id = _build_game_id(event, target_date)
        books = event.get("bookmakers") or event.get("sportsbooks") or []

        for book in books:
            for market in book.get("markets", []):
                mapped.extend(
                    _map_outcomes(event, book, market, game_date, game_id)
                )

    return mapped


def fetch_props_for_date_mapped(
    target_date: date,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    errors: List[Dict[str, Any]] = []
    simulated = False
    try:
        raw = fetch_props_for_date_raw(target_date, simulate_on_error=False)
    except PlayerPropsAPIError as exc:
        errors.append(
            {
                "message": str(exc),
                "status_code": exc.status_code,
                "payload": exc.payload,
                "retry_after": exc.retry_after,
                "source": SOURCE_NAME,
            }
        )
        raw = fetch_props_for_date_raw(target_date, simulate_on_error=True)
        simulated = True
    except Exception as exc:  # pragma: no cover - defensive
        errors.append({"message": f"Unexpected error: {exc}", "source": SOURCE_NAME})
        raw = _simulate_payload(target_date)
        simulated = True

    if isinstance(raw, dict) and raw.get("_simulated"):
        simulated = True

    mapped = map_props_from_raw(raw, target_date)

    if simulated:
        errors.append(
            {
                "message": "Simulated props, real API call failed or key missing",
                "status_code": None,
                "payload": {},
                "retry_after": None,
                "source": SOURCE_NAME,
            }
        )

    return mapped, errors
