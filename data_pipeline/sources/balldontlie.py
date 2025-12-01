from __future__ import annotations

import datetime as dt
from typing import Any, Dict, List

import requests


API_URL = "https://www.balldontlie.io/api/v1/games"
PER_PAGE = 100
REQUEST_TIMEOUT = 10


class BalldontlieAPIError(Exception):
    """Raised when a balldontlie API request fails."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        payload: Dict[str, Any] | None = None,
        retry_after: int | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload or {}
        self.retry_after = retry_after


def _request_page(
    iso_date: str,
    page: int,
) -> Dict[str, Any]:
    params = {
        "dates[]": iso_date,
        "per_page": PER_PAGE,
        "page": page,
    }
    try:
        response = requests.get(API_URL, params=params, timeout=REQUEST_TIMEOUT)
    except requests.RequestException as exc:  # pragma: no cover - network errors
        raise BalldontlieAPIError(
            f"Request to balldontlie failed: {exc}"
        ) from exc

    if response.status_code != 200:
        try:
            payload = response.json()
        except ValueError:
            payload = {"raw": response.text}
        retry_after = response.headers.get("Retry-After")
        retry_seconds = None
        if retry_after:
            try:
                retry_seconds = int(retry_after)
            except ValueError:
                retry_seconds = None
        raise BalldontlieAPIError(
            f"balldontlie API returned {response.status_code}",
            status_code=response.status_code,
            payload=payload,
            retry_after=retry_seconds,
        )
    return response.json()


def fetch_games_for_date(target_date: dt.date) -> List[Dict[str, Any]]:
    """
    Fetch raw balldontlie games for a specific date, handling pagination.
    """
    if not isinstance(target_date, dt.date):
        raise TypeError("target_date must be a datetime.date instance")

    iso_date = target_date.isoformat()
    games: List[Dict[str, Any]] = []
    page = 1
    while True:
        payload = _request_page(iso_date, page)
        games.extend(payload.get("data", []))
        meta = payload.get("meta") or {}
        next_page = meta.get("next_page")
        if not next_page:
            break
        page = next_page
    return games


def map_game_to_schema(game: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert a balldontlie game payload into the SB-ALGO canonical games schema.
    """
    raw_date = game.get("date") or ""
    # balldontlie dates look like 2024-03-01T00:00:00.000Z
    date_str = raw_date.split("T", 1)[0] if raw_date else None
    home_team = (game.get("home_team") or {}).get("abbreviation")
    visitor_team = (game.get("visitor_team") or {}).get("abbreviation")
    home_pts = int(game.get("home_team_score") or 0)
    visitor_pts = int(game.get("visitor_team_score") or 0)
    total_points = home_pts + visitor_pts
    margin_home = home_pts - visitor_pts
    status = game.get("status") or "Unknown"

    return {
        "date": date_str,
        "home_team": home_team,
        "visitor_team": visitor_team,
        "home_pts": home_pts,
        "visitor_pts": visitor_pts,
        "total_points": total_points,
        "margin_home": margin_home,
        "status": status,
    }


def fetch_and_map(target_date: dt.date) -> List[Dict[str, Any]]:
    """
    Fetch all games for the provided date and map them to SB-ALGO schema dicts.
    """
    games = fetch_games_for_date(target_date)
    return [map_game_to_schema(game) for game in games]
