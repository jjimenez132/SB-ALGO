from __future__ import annotations

import datetime as dt
import os
from typing import Any, Dict, List, Optional

import requests


BASE_URL = "https://api.sportsdata.io/v3/nba"
REQUEST_TIMEOUT = 15


class SportsDataError(Exception):
    """Raised when the SportsDataIO API fails."""

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
    key = os.getenv("SPORTSDATA_API_KEY")
    if not key:
        raise SportsDataError("SPORTSDATA_API_KEY environment variable is required")
    return {"Ocp-Apim-Subscription-Key": key}


def _request(
    path: str,
    *,
    session: Optional[requests.Session] = None,
) -> Any:
    url = f"{BASE_URL.rstrip('/')}/{path.lstrip('/')}"
    sess = session or requests.Session()
    try:
        response = sess.get(url, headers=_build_headers(), timeout=REQUEST_TIMEOUT)
    except requests.RequestException as exc:  # pragma: no cover - network errors
        raise SportsDataError(f"Request failed: {exc}") from exc
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
        raise SportsDataError(
            f"SportsDataIO returned {response.status_code}",
            status_code=response.status_code,
            payload=payload,
            retry_after=retry_seconds,
        )
    try:
        return response.json()
    except ValueError as exc:
        raise SportsDataError(
            "SportsDataIO response did not contain valid JSON",
            status_code=response.status_code,
        ) from exc


def map_game_to_schema(game: Dict[str, Any]) -> Dict[str, Any]:
    date_str = (game.get("Day") or "").split("T", 1)[0]
    home_team = game.get("HomeTeam")
    visitor_team = game.get("AwayTeam")
    home_pts = int(game.get("HomeTeamScore") or 0)
    visitor_pts = int(game.get("AwayTeamScore") or 0)
    total_points = home_pts + visitor_pts
    margin_home = home_pts - visitor_pts
    status = game.get("Status") or "Scheduled"
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
    date_str = target_date.strftime("%Y-%m-%d")
    try:
        return _request(f"scores/json/GamesByDate/{date_str}", session=session)
    except SportsDataError:
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


def fetch_team_stats(
    season: str,
    *,
    session: Optional[requests.Session] = None,
    simulate_on_error: bool = True,
) -> List[Dict[str, Any]]:
    try:
        return _request(f"stats/json/TeamSeasonStats/{season}", session=session)
    except SportsDataError:
        if simulate_on_error:
            return list(_simulate_team_stats())
        raise


def fetch_player_stats(
    season: str,
    *,
    session: Optional[requests.Session] = None,
    simulate_on_error: bool = True,
) -> List[Dict[str, Any]]:
    try:
        return _request(f"stats/json/PlayerSeasonStats/{season}", session=session)
    except SportsDataError:
        if simulate_on_error:
            return list(_simulate_player_stats())
        raise


def fetch_boxscore(
    game_key: str,
    *,
    session: Optional[requests.Session] = None,
    simulate_on_error: bool = True,
) -> Dict[str, Any]:
    try:
        return _request(f"stats/json/BoxScore/{game_key}", session=session)
    except SportsDataError:
        if simulate_on_error:
            return _simulate_boxscore(game_key)
        raise


def _simulate_games(target_date: dt.date) -> List[Dict[str, Any]]:
    iso_date = target_date.isoformat()
    return [
        {
            "GameID": 10000 + idx,
            "Day": f"{iso_date}T00:00:00",
            "HomeTeam": home,
            "AwayTeam": away,
            "HomeTeamScore": home_pts,
            "AwayTeamScore": away_pts,
            "Status": status,
        }
        for idx, (home, away, home_pts, away_pts, status) in enumerate(
            [
                ("LAL", "BOS", 115, 109, "Final"),
                ("MIL", "CHI", 0, 0, "Scheduled"),
            ],
            start=1,
        )
    ]


def _simulate_team_stats() -> List[Dict[str, Any]]:
    return [
        {
            "Team": "LAL",
            "Season": "2024",
            "Wins": 45,
            "Losses": 37,
            "Points": 118.2,
            "Rebounds": 44.1,
        }
    ]


def _simulate_player_stats() -> List[Dict[str, Any]]:
    return [
        {
            "PlayerID": 20000555,
            "Name": "Nikola Jokic",
            "Team": "DEN",
            "Points": 26.4,
            "Rebounds": 12.2,
            "Assists": 9.1,
            "Season": "2024",
        }
    ]


def _simulate_boxscore(game_key: str) -> Dict[str, Any]:
    return {
        "GameKey": game_key,
        "Quarter": 4,
        "TimeRemaining": "00:30",
        "HomeTeam": {
            "Team": "LAL",
            "Score": 115,
            "Players": [
                {"Name": "LeBron James", "Points": 30, "Rebounds": 8, "Assists": 9}
            ],
        },
        "AwayTeam": {
            "Team": "BOS",
            "Score": 109,
            "Players": [
                {"Name": "Jayson Tatum", "Points": 27, "Rebounds": 7, "Assists": 4}
            ],
        },
    }
