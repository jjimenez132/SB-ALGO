from __future__ import annotations

import datetime as dt
import os
from typing import Any, Dict, List, Optional

import requests


BASE_URL = os.getenv("BALLDONTLIE_BASE_URL", "https://www.balldontlie.io/api/v1")
REQUEST_TIMEOUT = 15
PER_PAGE = 100


class BalldontlieAPIError(Exception):
    """Raised when the balldontlie API fails."""

    def __init__(
        self,
        message: str,
        *,
        status_code: Optional[int] = None,
        payload: Optional[Dict[str, Any]] = None,
        retry_after: Optional[int] = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload or {}
        self.retry_after = retry_after


def _build_headers() -> Dict[str, str]:
    token = os.getenv("BALLDONTLIE_API_KEY")
    headers: Dict[str, str] = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _request(
    path: str,
    params: Optional[Dict[str, Any]] = None,
    *,
    session: Optional[requests.Session] = None,
) -> Dict[str, Any]:
    url = f"{BASE_URL.rstrip('/')}/{path.lstrip('/')}"
    sess = session or requests.Session()
    try:
        response = sess.get(
            url,
            params=params,
            headers=_build_headers(),
            timeout=REQUEST_TIMEOUT,
        )
    except requests.RequestException as exc:  # pragma: no cover - network errors
        raise BalldontlieAPIError(f"Request failed: {exc}") from exc

    if response.status_code != 200:
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
            payload = {"raw": response.text}
        raise BalldontlieAPIError(
            f"balldontlie API returned {response.status_code}",
            status_code=response.status_code,
            payload=payload,
            retry_after=retry_seconds,
        )
    return response.json()


def _paginate(
    path: str,
    params: Dict[str, Any],
    *,
    session: Optional[requests.Session] = None,
) -> List[Dict[str, Any]]:
    page = 1
    data: List[Dict[str, Any]] = []
    while True:
        params_with_page = dict(params)
        params_with_page["per_page"] = PER_PAGE
        params_with_page["page"] = page
        payload = _request(path, params_with_page, session=session)
        data.extend(payload.get("data", []))
        meta = payload.get("meta") or {}
        next_page = meta.get("next_page")
        if not next_page:
            break
        page = next_page
    return data


def map_game_to_schema(game: Dict[str, Any]) -> Dict[str, Any]:
    raw_date = (game.get("date") or "").split("T", 1)[0]
    home_team = (game.get("home_team") or {}).get("abbreviation")
    visitor_team = (game.get("visitor_team") or {}).get("abbreviation")
    home_pts = int(game.get("home_team_score") or 0)
    visitor_pts = int(game.get("visitor_team_score") or 0)
    total_points = home_pts + visitor_pts
    margin_home = home_pts - visitor_pts
    return {
        "date": raw_date or None,
        "home_team": home_team,
        "visitor_team": visitor_team,
        "home_pts": home_pts,
        "visitor_pts": visitor_pts,
        "total_points": total_points,
        "margin_home": margin_home,
        "status": game.get("status") or "Unknown",
    }


def fetch_games_raw(
    target_date: dt.date,
    *,
    session: Optional[requests.Session] = None,
    simulate_on_error: bool = True,
) -> List[Dict[str, Any]]:
    params = {"dates[]": target_date.isoformat()}
    try:
        return _paginate("games", params, session=session)
    except BalldontlieAPIError:
        if simulate_on_error:
            return list(_simulate_games(target_date))
        raise


def fetch_games_mapped(
    target_date: dt.date,
    *,
    session: Optional[requests.Session] = None,
    simulate_on_error: bool = True,
) -> List[Dict[str, Any]]:
    games = fetch_games_raw(
        target_date, session=session, simulate_on_error=simulate_on_error
    )
    return [map_game_to_schema(game) for game in games]


def fetch_player_stats(
    player_id: int,
    *,
    target_date: Optional[dt.date] = None,
    season: Optional[int] = None,
    session: Optional[requests.Session] = None,
    simulate_on_error: bool = True,
) -> List[Dict[str, Any]]:
    params: Dict[str, Any] = {"player_ids[]": player_id}
    if target_date:
        params["dates[]"] = target_date.isoformat()
    if season:
        params["seasons[]"] = season
    try:
        return _paginate("stats", params, session=session)
    except BalldontlieAPIError:
        if simulate_on_error:
            return list(_simulate_player_stats(player_id))
        raise


def fetch_team_stats(
    team_id: int,
    *,
    season: Optional[int] = None,
    session: Optional[requests.Session] = None,
    simulate_on_error: bool = True,
) -> Dict[str, Any]:
    params: Dict[str, Any] = {
        "team_ids[]": team_id,
        "per_page": 1,
    }
    if season:
        params["seasons[]"] = season
    try:
        payload = _request("games", params, session=session)
        team = payload.get("data", [{}])[0].get("home_team") or {}
        return {
            "team_id": team.get("id", team_id),
            "abbreviation": team.get("abbreviation"),
            "full_name": team.get("full_name"),
            "conference": team.get("conference"),
            "division": team.get("division"),
        }
    except BalldontlieAPIError:
        if simulate_on_error:
            return _simulate_team_stats(team_id)
        raise


def fetch_boxscore(
    game_id: int,
    *,
    session: Optional[requests.Session] = None,
    simulate_on_error: bool = True,
) -> Dict[str, Any]:
    params = {"game_ids[]": game_id}
    try:
        stats = _paginate("stats", params, session=session)
        return {"game_id": game_id, "player_stats": stats}
    except BalldontlieAPIError:
        if simulate_on_error:
            return _simulate_boxscore(game_id)
        raise


def _simulate_games(target_date: dt.date) -> List[Dict[str, Any]]:
    iso_date = target_date.isoformat()
    return [
        {
            "id": 900000 + idx,
            "date": f"{iso_date}T00:00:00.000Z",
            "home_team": {"abbreviation": home, "id": 1},
            "visitor_team": {"abbreviation": away, "id": 2},
            "home_team_score": home_pts,
            "visitor_team_score": away_pts,
            "status": status,
        }
        for idx, (home, away, home_pts, away_pts, status) in enumerate(
            [
                ("LAL", "BOS", 112, 108, "Final"),
                ("GSW", "DAL", 101, 99, "Final"),
            ],
            start=1,
        )
    ]


def _simulate_player_stats(player_id: int) -> List[Dict[str, Any]]:
    return [
        {
            "id": 1,
            "player": {"id": player_id, "first_name": "LeBron", "last_name": "James"},
            "team": {"abbreviation": "LAL"},
            "pts": 28,
            "reb": 8,
            "ast": 7,
            "game": {"id": 900001, "date": "2023-01-15T00:00:00.000Z"},
        }
    ]


def _simulate_team_stats(team_id: int) -> Dict[str, Any]:
    return {
        "team_id": team_id,
        "abbreviation": "LAL",
        "full_name": "Los Angeles Lakers",
        "conference": "West",
        "division": "Pacific",
    }


def _simulate_boxscore(game_id: int) -> Dict[str, Any]:
    return {
        "game_id": game_id,
        "player_stats": [
            {
                "player": {"id": 237, "first_name": "LeBron", "last_name": "James"},
                "team": {"abbreviation": "LAL"},
                "pts": 30,
                "reb": 9,
                "ast": 8,
                "min": "34:12",
            },
            {
                "player": {"id": 140, "first_name": "Jayson", "last_name": "Tatum"},
                "team": {"abbreviation": "BOS"},
                "pts": 27,
                "reb": 7,
                "ast": 5,
                "min": "35:30",
            },
        ],
    }
