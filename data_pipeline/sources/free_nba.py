from __future__ import annotations

import datetime as dt
import os
from typing import Any, Dict, List, Optional

import requests


BASE_URL = "https://free-nba.p.rapidapi.com"
REQUEST_TIMEOUT = 15
DEFAULT_PER_PAGE = 100


class FreeNBAAPIError(Exception):
    """Raised when the free-nba RapidAPI endpoint fails."""

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
    api_key = os.getenv("RAPIDAPI_KEY")
    if not api_key:
        raise FreeNBAAPIError("RAPIDAPI_KEY environment variable is required")
    return {
        "X-RapidAPI-Key": api_key,
        "X-RapidAPI-Host": "free-nba.p.rapidapi.com",
    }


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
    except requests.RequestException as exc:  # pragma: no cover - network
        raise FreeNBAAPIError(f"Request failed: {exc}") from exc
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
        raise FreeNBAAPIError(
            f"free-nba API returned {response.status_code}",
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
    page = 0
    data: List[Dict[str, Any]] = []
    while True:
        params_with_page = dict(params)
        params_with_page["per_page"] = DEFAULT_PER_PAGE
        params_with_page["page"] = page
        payload = _request(path, params_with_page, session=session)
        batch = payload.get("data", [])
        data.extend(batch)
        meta = payload.get("meta") or {}
        total_pages = meta.get("total_pages") or 0
        page += 1
        if not batch or page >= total_pages:
            break
    return data


def map_game_to_schema(game: Dict[str, Any]) -> Dict[str, Any]:
    date_str = game.get("date", "").split("T", 1)[0]
    home_team = (game.get("home_team") or {}).get("abbreviation")
    visitor_team = (game.get("visitor_team") or {}).get("abbreviation")
    home_pts = int(game.get("home_team_score") or 0)
    visitor_pts = int(game.get("visitor_team_score") or 0)
    total_points = home_pts + visitor_pts
    margin_home = home_pts - visitor_pts
    status = game.get("status") or ("Final" if total_points else "Scheduled")
    return {
        "date": date_str or None,
        "home_team": home_team,
        "visitor_team": visitor_team,
        "home_pts": home_pts,
        "visitor_pts": visitor_pts,
        "total_points": total_points,
        "margin_home": margin_home,
        "status": status,
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
    except FreeNBAAPIError:
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
    season: Optional[int] = None,
    session: Optional[requests.Session] = None,
    simulate_on_error: bool = True,
) -> List[Dict[str, Any]]:
    params: Dict[str, Any] = {"player_ids[]": player_id}
    if season:
        params["seasons[]"] = season
    try:
        return _paginate("stats", params, session=session)
    except FreeNBAAPIError:
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
    params: Dict[str, Any] = {"per_page": 1, "id": team_id}
    try:
        payload = _request("teams", params, session=session)
        team = (payload.get("data") or [{}])[0]
        return {
            "team_id": team.get("id", team_id),
            "abbreviation": team.get("abbreviation"),
            "full_name": team.get("full_name"),
            "division": team.get("division"),
            "conference": team.get("conference"),
        }
    except FreeNBAAPIError:
        if simulate_on_error:
            return _simulate_team_stats(team_id)
        raise


def fetch_boxscore(
    game_id: int,
    *,
    session: Optional[requests.Session] = None,
    simulate_on_error: bool = True,
) -> Dict[str, Any]:
    params: Dict[str, Any] = {"game_ids[]": game_id}
    try:
        stats = _paginate("stats", params, session=session)
        return {"game_id": game_id, "player_stats": stats}
    except FreeNBAAPIError:
        if simulate_on_error:
            return _simulate_boxscore(game_id)
        raise


def _simulate_games(target_date: dt.date) -> List[Dict[str, Any]]:
    iso_date = target_date.isoformat()
    return [
        {
            "id": 500000 + idx,
            "date": f"{iso_date}T00:00:00.000Z",
            "home_team": {"abbreviation": home},
            "visitor_team": {"abbreviation": away},
            "home_team_score": home_pts,
            "visitor_team_score": away_pts,
            "status": status,
        }
        for idx, (home, away, home_pts, away_pts, status) in enumerate(
            [
                ("MIA", "NYK", 105, 101, "Final"),
                ("PHX", "DEN", 0, 0, "Scheduled"),
            ],
            start=1,
        )
    ]


def _simulate_player_stats(player_id: int) -> List[Dict[str, Any]]:
    return [
        {
            "id": 1,
            "player": {"id": player_id, "first_name": "Luka", "last_name": "Doncic"},
            "team": {"abbreviation": "DAL"},
            "pts": 34,
            "reb": 10,
            "ast": 9,
            "game": {"id": 500001, "date": "2023-01-15T00:00:00.000Z"},
        }
    ]


def _simulate_team_stats(team_id: int) -> Dict[str, Any]:
    return {
        "team_id": team_id,
        "abbreviation": "DAL",
        "full_name": "Dallas Mavericks",
        "division": "Southwest",
        "conference": "West",
    }


def _simulate_boxscore(game_id: int) -> Dict[str, Any]:
    return {
        "game_id": game_id,
        "player_stats": [
            {
                "player": {"id": 132, "first_name": "Steph", "last_name": "Curry"},
                "team": {"abbreviation": "GSW"},
                "pts": 29,
                "reb": 6,
                "ast": 8,
            }
        ],
    }
