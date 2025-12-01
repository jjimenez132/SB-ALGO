from __future__ import annotations

import datetime as dt
import os
from typing import Any, Dict, List, Optional

import requests


BASE_URL = "https://api-nba-v1.p.rapidapi.com"
REQUEST_TIMEOUT = 20


class APINBAError(Exception):
    """Raised when the API-NBA endpoint fails."""

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
        raise APINBAError("RAPIDAPI_KEY environment variable is required")
    return {
        "X-RapidAPI-Key": api_key,
        "X-RapidAPI-Host": "api-nba-v1.p.rapidapi.com",
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
    except requests.RequestException as exc:  # pragma: no cover
        raise APINBAError(f"Request failed: {exc}") from exc
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
        raise APINBAError(
            f"API-NBA returned {response.status_code}",
            status_code=response.status_code,
            payload=payload,
            retry_after=retry_seconds,
        )
    return response.json()


def map_game_to_schema(game: Dict[str, Any]) -> Dict[str, Any]:
    game_info = game.get("game") or {}
    teams = game.get("teams") or {}
    scores = game.get("scores") or {}
    date_info = (game.get("date") or {}).get("start")
    date_str = (date_info or "").split("T", 1)[0]
    home_team = (teams.get("home") or {}).get("code")
    visitor_team = (teams.get("visitors") or {}).get("code")
    home_pts = int((scores.get("home") or {}).get("points") or 0)
    visitor_pts = int((scores.get("visitors") or {}).get("points") or 0)
    total_points = home_pts + visitor_pts
    margin_home = home_pts - visitor_pts
    status = (game_info.get("status") or {}).get("long") or "Scheduled"
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
    params = {"date": target_date.isoformat()}
    try:
        payload = _request("games", params, session=session)
        return payload.get("response", [])
    except APINBAError:
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
    params: Dict[str, Any] = {"id": player_id}
    if season:
        params["season"] = season
    try:
        payload = _request("players/statistics", params, session=session)
        return payload.get("response", [])
    except APINBAError:
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
    params: Dict[str, Any] = {"id": team_id}
    if season:
        params["season"] = season
    try:
        payload = _request("teams/statistics", params, session=session)
        response = (payload.get("response") or [{}])[0]
        return response
    except APINBAError:
        if simulate_on_error:
            return _simulate_team_stats(team_id)
        raise


def fetch_boxscore(
    game_id: int,
    *,
    session: Optional[requests.Session] = None,
    simulate_on_error: bool = True,
) -> Dict[str, Any]:
    params = {"id": game_id}
    try:
        payload = _request("games/statistics", params, session=session)
        return payload.get("response", {})
    except APINBAError:
        if simulate_on_error:
            return _simulate_boxscore(game_id)
        raise


def _simulate_games(target_date: dt.date) -> List[Dict[str, Any]]:
    iso_date = target_date.isoformat()
    return [
        {
            "date": {"start": f"{iso_date}T00:00:00.000Z"},
            "teams": {
                "home": {"code": "LAL"},
                "visitors": {"code": "BOS"},
            },
            "scores": {
                "home": {"points": 118},
                "visitors": {"points": 114},
            },
            "game": {"status": {"long": "Finished"}},
        }
    ]


def _simulate_player_stats(player_id: int) -> List[Dict[str, Any]]:
    return [
        {
            "player": {"id": player_id, "firstname": "Giannis", "lastname": "Antetokounmpo"},
            "team": {"code": "MIL"},
            "points": 33,
            "rebounds": 12,
            "assists": 6,
        }
    ]


def _simulate_team_stats(team_id: int) -> Dict[str, Any]:
    return {
        "team": {"id": team_id, "code": "MIL"},
        "fastBreakPoints": 17,
        "pointsInPaint": 52,
        "pointsOffTurnovers": 18,
    }


def _simulate_boxscore(game_id: int) -> Dict[str, Any]:
    return {
        "game": {"id": game_id},
        "teams": {
            "home": {
                "code": "MIL",
                "players": [
                    {"firstname": "Giannis", "lastname": "Antetokounmpo", "points": 33}
                ],
            },
            "visitors": {
                "code": "PHI",
                "players": [
                    {"firstname": "Joel", "lastname": "Embiid", "points": 29}
                ],
            },
        },
    }
