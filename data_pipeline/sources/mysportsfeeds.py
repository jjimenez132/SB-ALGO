from __future__ import annotations

import base64
import datetime as dt
import os
from typing import Any, Dict, List, Optional

import requests


BASE_URL = "https://api.mysportsfeeds.com/v2.1/pull/nba"
REQUEST_TIMEOUT = 20


class MySportsFeedsError(Exception):
    """Raised when the MySportsFeeds API fails."""

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
    token = os.getenv("MYSPORTSFEEDS_TOKEN")
    if not token:
        raise MySportsFeedsError("MYSPORTSFEEDS_TOKEN environment variable is required")
    encoded = base64.b64encode(token.encode("utf-8")).decode("ascii")
    return {
        "Authorization": f"Basic {encoded}",
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
        raise MySportsFeedsError(f"Request failed: {exc}") from exc
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
        raise MySportsFeedsError(
            f"MySportsFeeds returned {response.status_code}",
            status_code=response.status_code,
            payload=payload,
            retry_after=retry_seconds,
        )
    return response.json()


def map_game_to_schema(game: Dict[str, Any]) -> Dict[str, Any]:
    schedule = game.get("schedule", {})
    score = game.get("score", {})
    date_str = (schedule.get("startTime") or "").split("T", 1)[0]
    home_team = (schedule.get("homeTeam") or {}).get("abbreviation")
    visitor_team = (schedule.get("awayTeam") or {}).get("abbreviation")
    home_pts = int(score.get("homeScoreTotal") or 0)
    visitor_pts = int(score.get("awayScoreTotal") or 0)
    total_points = home_pts + visitor_pts
    margin_home = home_pts - visitor_pts
    status = schedule.get("playedStatus") or schedule.get("status") or "Scheduled"
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
    path = f"current/date/{target_date.strftime('%Y-%m-%d')}/games.json"
    try:
        payload = _request(path, session=session)
        return payload.get("games", [])
    except MySportsFeedsError:
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
    season: str,
    player: Optional[str] = None,
    *,
    session: Optional[requests.Session] = None,
    simulate_on_error: bool = True,
) -> List[Dict[str, Any]]:
    path = f"{season}/player_gamelogs.json"
    params: Dict[str, Any] = {}
    if player:
        params["player"] = player
    try:
        payload = _request(path, params=params, session=session)
        return payload.get("gamelogs", [])
    except MySportsFeedsError:
        if simulate_on_error:
            return list(_simulate_player_stats(player or "generic"))
        raise


def fetch_team_stats(
    season: str,
    team: Optional[str] = None,
    *,
    session: Optional[requests.Session] = None,
    simulate_on_error: bool = True,
) -> List[Dict[str, Any]]:
    path = f"{season}/team_gamelogs.json"
    params: Dict[str, Any] = {}
    if team:
        params["team"] = team
    try:
        payload = _request(path, params=params, session=session)
        return payload.get("gamelogs", [])
    except MySportsFeedsError:
        if simulate_on_error:
            return list(_simulate_team_stats(team or "TEAM"))
        raise


def fetch_boxscore(
    season: str,
    game_id: str,
    *,
    session: Optional[requests.Session] = None,
    simulate_on_error: bool = True,
) -> Dict[str, Any]:
    path = f"{season}/game_boxscore.json"
    params = {"game": game_id}
    try:
        payload = _request(path, params=params, session=session)
        return payload.get("stats", {})
    except MySportsFeedsError:
        if simulate_on_error:
            return _simulate_boxscore(game_id)
        raise


def _simulate_games(target_date: dt.date) -> List[Dict[str, Any]]:
    iso_date = target_date.isoformat()
    return [
        {
            "schedule": {
                "id": f"{iso_date.replace('-', '')}-MSF",
                "startTime": f"{iso_date}T00:00:00",
                "homeTeam": {"abbreviation": "TOR"},
                "awayTeam": {"abbreviation": "BOS"},
                "playedStatus": "Final",
            },
            "score": {"homeScoreTotal": 111, "awayScoreTotal": 107},
        }
    ]


def _simulate_player_stats(player: str) -> List[Dict[str, Any]]:
    return [
        {
            "player": {"firstName": "Scottie", "lastName": "Barnes", "fullName": player},
            "team": {"abbreviation": "TOR"},
            "stats": {"Pts": 24, "Reb": 9, "Ast": 6},
        }
    ]


def _simulate_team_stats(team: str) -> List[Dict[str, Any]]:
    return [
        {
            "team": {"abbreviation": team},
            "stats": {"Pts": 112.4, "Reb": 44.2, "Ast": 25.1},
        }
    ]


def _simulate_boxscore(game_id: str) -> Dict[str, Any]:
    return {
        "game": game_id,
        "homeTeam": {"abbreviation": "TOR", "score": 111},
        "awayTeam": {"abbreviation": "BOS", "score": 107},
        "playerStats": [
            {"player": "Scottie Barnes", "team": "TOR", "Pts": 24},
            {"player": "Jayson Tatum", "team": "BOS", "Pts": 30},
        ],
    }
