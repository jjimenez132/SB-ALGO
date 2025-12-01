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


SOURCE_NAME = "prop_odds"
DEFAULT_MARKETS = [
    "player_points",
    "player_rebounds",
    "player_assists",
    "player_points_rebounds_assists",
    "player_threes",
]
SPORT_PATH = "/v1/odds/basketball/nba/player-props"
API_HOST_ENV = "PROP_ODDS_RAPIDAPI_HOST"
API_HOST = os.getenv(API_HOST_ENV, "prop-odds.p.rapidapi.com")
RAPID_API_KEY_ENV = "RAPIDAPI_KEY"


def _request(path: str, params: Dict[str, Any]) -> Dict[str, Any]:
    api_key = os.getenv(RAPID_API_KEY_ENV)
    if not api_key:
        raise PlayerPropsAPIError(
            f"{RAPID_API_KEY_ENV} environment variable is required for Prop-Odds requests"
        )

    headers = {
        "x-rapidapi-key": api_key,
        "x-rapidapi-host": API_HOST,
        "accept": "application/json",
    }
    url = f"https://{API_HOST}{path}"
    try:
        response = requests.get(url, headers=headers, params=params, timeout=15)
    except requests.RequestException as exc:  # pragma: no cover - network failure
        raise PlayerPropsAPIError(f"Prop-Odds request failed: {exc}") from exc

    if response.status_code == 200:
        try:
            return response.json()
        except ValueError as exc:  # pragma: no cover - unexpected provider failure
            raise PlayerPropsAPIError(
                "Prop-Odds returned invalid JSON", payload={"text": response.text}
            ) from exc

    retry_after = response.headers.get("Retry-After")
    retry_seconds = None
    if retry_after:
        try:
            retry_seconds = int(retry_after)
        except ValueError:
            retry_seconds = None

    payload: Dict[str, Any]
    try:
        payload = response.json()
    except ValueError:
        payload = {"text": response.text}

    if response.status_code == 429:
        raise PlayerPropsAPIError(
            "Prop-Odds rate limited the request",
            status_code=response.status_code,
            payload=payload,
            retry_after=retry_seconds,
        )

    raise PlayerPropsAPIError(
        f"Prop-Odds error ({response.status_code})",
        status_code=response.status_code,
        payload=payload,
        retry_after=retry_seconds,
    )


def _simulate_payload(target_date: date) -> Dict[str, Any]:
    iso_date = target_date.strftime("%Y%m%d")
    commence_date = target_date.isoformat()
    return {
        "_simulated": True,
        "events": [
            {
                "id": f"{iso_date}-LALDEN",
                "commence_time": f"{commence_date}T02:00:00Z",
                "home_team": "Denver Nuggets",
                "away_team": "Los Angeles Lakers",
                "bookmakers": [
                    {
                        "key": "draftkings",
                        "title": "DraftKings",
                        "markets": [
                            {
                                "key": "player_points",
                                "outcomes": [
                                    {
                                        "player": "Nikola Jokic",
                                        "team": "Denver Nuggets",
                                        "type": "over",
                                        "line": 26.5,
                                        "price": -115,
                                    },
                                    {
                                        "player": "Nikola Jokic",
                                        "team": "Denver Nuggets",
                                        "type": "under",
                                        "line": 26.5,
                                        "price": -105,
                                    },
                                    {
                                        "player": "LeBron James",
                                        "team": "Los Angeles Lakers",
                                        "type": "over",
                                        "line": 25.5,
                                        "price": -110,
                                    },
                                    {
                                        "player": "LeBron James",
                                        "team": "Los Angeles Lakers",
                                        "type": "under",
                                        "line": 25.5,
                                        "price": -110,
                                    },
                                ],
                            },
                            {
                                "key": "player_rebounds",
                                "outcomes": [
                                    {
                                        "player": "Nikola Jokic",
                                        "team": "Denver Nuggets",
                                        "type": "over",
                                        "line": 12.5,
                                        "price": -120,
                                    },
                                    {
                                        "player": "Nikola Jokic",
                                        "team": "Denver Nuggets",
                                        "type": "under",
                                        "line": 12.5,
                                        "price": -105,
                                    },
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
) -> Dict[str, Any]:
    params = {
        "date": target_date.isoformat(),
        "markets": ",".join(DEFAULT_MARKETS),
        "oddsFormat": "american",
    }
    try:
        return _request(SPORT_PATH, params)
    except PlayerPropsAPIError:
        if not simulate_on_error:
            raise
        return _simulate_payload(target_date)


MARKET_MAP = {
    "player_points": "points",
    "player_rebounds": "rebounds",
    "player_assists": "assists",
    "player_points_rebounds_assists": "pra",
    "player_threes": "threes",
}


def _normalize_market_key(raw_key: str | None) -> str:
    if not raw_key:
        return "unknown"
    return MARKET_MAP.get(raw_key, raw_key.replace("player_", ""))


def _normalize_team(raw: str | None) -> str | None:
    if not raw:
        return None
    key = raw.strip().lower()
    return TEAM_ABBREVIATIONS.get(key, raw.strip().upper()[:3])


def _normalize_book(bookmaker: Dict[str, Any]) -> str:
    for field in ("key", "title", "book", "name"):
        value = bookmaker.get(field)
        if value:
            return str(value).upper()
    return "UNKNOWN"


def _extract_events(raw: Dict[str, Any]) -> Iterable[Dict[str, Any]]:
    if isinstance(raw, list):
        return raw
    if not isinstance(raw, dict):
        return []
    for key in ("events", "data", "results", "games", "odds", "body"):
        value = raw.get(key)
        if isinstance(value, list):
            return value
    return []


def _extract_line(outcome: Dict[str, Any]) -> float | None:
    for field in ("line", "point", "points", "total"):
        value = outcome.get(field)
        if value is not None:
            try:
                return float(value)
            except (TypeError, ValueError):
                continue
    return None


def _extract_price(outcome: Dict[str, Any]) -> float | None:
    for field in (
        "price",
        "odds",
        "american",
        "american_odds",
        "odds_american",
        "moneyline",
    ):
        value = outcome.get(field)
        if value is not None:
            try:
                return float(value)
            except (TypeError, ValueError):
                continue
    return None


def _infer_side(outcome: Dict[str, Any]) -> str | None:
    for field in ("type", "description", "label", "name", "side"):
        value = outcome.get(field)
        if not value:
            continue
        text = str(value).strip().lower()
        if "over" in text:
            return "over"
        if "under" in text:
            return "under"
    return None


def _build_game_id(event: Dict[str, Any], target_date: date) -> str:
    if event.get("id"):
        return str(event["id"])
    if event.get("game_id"):
        return str(event["game_id"])
    home = _normalize_team(event.get("home_team")) or "HOME"
    away = _normalize_team(event.get("away_team")) or "AWAY"
    return f"{target_date:%Y%m%d}-{away}{home}"


def _extract_player_id(outcome: Dict[str, Any]) -> str | None:
    for field in ("player_id", "playerId", "id"):
        value = outcome.get(field)
        if value:
            return str(value)
    return None


def _map_market_props(
    event: Dict[str, Any],
    bookmaker: Dict[str, Any],
    market: Dict[str, Any],
    game_date: str,
    game_id: str,
) -> List[Dict[str, Any]]:
    normalized_market = _normalize_market_key(market.get("key"))
    outcomes = market.get("outcomes") or market.get("props") or []
    grouped: Dict[str, Dict[str, Any]] = {}

    for outcome in outcomes:
        player_name = (
            outcome.get("player")
            or outcome.get("player_name")
            or outcome.get("participant")
            or outcome.get("name")
        )
        if not player_name:
            continue
        player_key = player_name.lower()
        player_team = _normalize_team(outcome.get("team") or outcome.get("player_team"))

        if player_key not in grouped:
            grouped[player_key] = {
                "date": game_date,
                "game_id": game_id,
                "book": _normalize_book(bookmaker),
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

        entry = grouped[player_key]
        line_value = _extract_line(outcome)
        if line_value is not None:
            entry["line"] = line_value
        side = _infer_side(outcome)
        odds_value = _extract_price(outcome)

        if side == "over":
            entry["over_odds"] = odds_value
        elif side == "under":
            entry["under_odds"] = odds_value
        elif entry["over_odds"] is None:
            entry["over_odds"] = odds_value
        else:
            entry["under_odds"] = odds_value

        if player_team:
            home_team = _normalize_team(event.get("home_team"))
            away_team = _normalize_team(event.get("away_team"))
            if player_team == home_team:
                entry["opponent"] = away_team
            elif player_team == away_team:
                entry["opponent"] = home_team

        if entry["line"] is None and "line" in outcome:
            try:
                entry["line"] = float(outcome["line"])
            except (TypeError, ValueError):
                pass

        if entry["over_odds"] is None and "over_odds" in outcome:
            try:
                entry["over_odds"] = float(outcome["over_odds"])
            except (TypeError, ValueError):
                pass
        if entry["under_odds"] is None and "under_odds" in outcome:
            try:
                entry["under_odds"] = float(outcome["under_odds"])
            except (TypeError, ValueError):
                pass

    return list(grouped.values())


def map_props_from_raw(raw: Dict[str, Any], target_date: date) -> List[Dict[str, Any]]:
    mapped: List[Dict[str, Any]] = []
    events = _extract_events(raw)

    for event in events:
        commence = event.get("commence_time")
        game_date = target_date.isoformat()
        if commence:
            try:
                commence_dt = datetime.fromisoformat(commence.replace("Z", "+00:00"))
                game_date = commence_dt.date().isoformat()
            except ValueError:
                game_date = target_date.isoformat()

        game_id = _build_game_id(event, target_date)
        for bookmaker in event.get("bookmakers", []):
            for market in bookmaker.get("markets", []):
                mapped.extend(
                    _map_market_props(event, bookmaker, market, game_date, game_id)
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
