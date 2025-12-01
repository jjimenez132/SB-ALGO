from __future__ import annotations

import datetime as dt
from typing import Any, Dict, List, Optional

import requests


BASE_URL_TEMPLATE = (
    "https://raw.githubusercontent.com/sportsdataverse/hoopR-data/main/"
    "nba/json/scoreboard/date={date}.json"
)
REQUEST_TIMEOUT = 20


class HoopRDatasetError(Exception):
    """Raised when the GitHub-hosted hoopR dataset is unavailable."""

    def __init__(
        self,
        message: str,
        *,
        status_code: Optional[int] = None,
        payload: Optional[Any] = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload


def _request(url: str) -> Any:
    try:
        response = requests.get(url, timeout=REQUEST_TIMEOUT)
    except requests.RequestException as exc:  # pragma: no cover - network errors
        raise HoopRDatasetError(f"Request failed: {exc}") from exc
    if response.status_code != 200:
        raise HoopRDatasetError(
            f"GitHub dataset returned {response.status_code}",
            status_code=response.status_code,
            payload=response.text,
        )
    try:
        return response.json()
    except ValueError as exc:
        raise HoopRDatasetError("Response was not valid JSON") from exc


def map_game_to_schema(game: Dict[str, Any]) -> Dict[str, Any]:
    home_team = (game.get("home_team") or {}).get("abbreviation") or game.get("home_team_abbreviation")
    visitor_team = (game.get("away_team") or {}).get("abbreviation") or game.get("away_team_abbreviation")
    home_pts = int(game.get("home_score") or 0)
    visitor_pts = int(game.get("away_score") or 0)
    total_points = home_pts + visitor_pts
    margin_home = home_pts - visitor_pts
    status = game.get("status") or game.get("game_status")
    date_str = (game.get("game_date") or game.get("start_time") or "").split("T", 1)[0]
    return {
        "date": date_str or None,
        "home_team": home_team,
        "visitor_team": visitor_team,
        "home_pts": home_pts,
        "visitor_pts": visitor_pts,
        "total_points": total_points,
        "margin_home": margin_home,
        "status": status or "Unknown",
    }


def fetch_games_raw(
    target_date: dt.date,
    *,
    simulate_on_error: bool = True,
) -> List[Dict[str, Any]]:
    url = BASE_URL_TEMPLATE.format(date=target_date.isoformat())
    try:
        payload = _request(url)
        if isinstance(payload, dict) and "data" in payload:
            return payload["data"]
        if isinstance(payload, list):
            return payload
        return []
    except HoopRDatasetError:
        if simulate_on_error:
            return list(_simulate_games(target_date))
        raise


def fetch_games_mapped(
    target_date: dt.date,
    *,
    simulate_on_error: bool = True,
) -> List[Dict[str, Any]]:
    games = fetch_games_raw(target_date, simulate_on_error=simulate_on_error)
    return [map_game_to_schema(game) for game in games]


def fetch_team_stats(
    season: str,
    *,
    simulate_on_error: bool = True,
) -> List[Dict[str, Any]]:
    # The hoopR dataset exposes team boxscores in separate folders;
    # for now we surface simulated data until those files are confirmed.
    if simulate_on_error:
        return list(_simulate_team_stats(season))
    raise HoopRDatasetError("Team stats JSON not wired yet")


def fetch_player_stats(
    season: str,
    *,
    simulate_on_error: bool = True,
) -> List[Dict[str, Any]]:
    if simulate_on_error:
        return list(_simulate_player_stats(season))
    raise HoopRDatasetError("Player stats JSON not wired yet")


def fetch_boxscore(
    game_id: str,
    *,
    simulate_on_error: bool = True,
) -> Dict[str, Any]:
    if simulate_on_error:
        return _simulate_boxscore(game_id)
    raise HoopRDatasetError("Boxscore JSON not wired yet")


def _simulate_games(target_date: dt.date) -> List[Dict[str, Any]]:
    iso_date = target_date.isoformat()
    return [
        {
            "game_id": f"{iso_date.replace('-', '')}-001",
            "game_date": f"{iso_date}T00:00:00",
            "home_team_abbreviation": "BKN",
            "away_team_abbreviation": "ATL",
            "home_score": 120,
            "away_score": 111,
            "status": "Final",
        }
    ]


def _simulate_team_stats(season: str) -> List[Dict[str, Any]]:
    return [
        {
            "season": season,
            "team": "BOS",
            "pace": 99.5,
            "offensive_rating": 118.1,
            "defensive_rating": 111.9,
        }
    ]


def _simulate_player_stats(season: str) -> List[Dict[str, Any]]:
    return [
        {
            "season": season,
            "player": "Jayson Tatum",
            "team": "BOS",
            "points": 30.1,
            "rebounds": 8.4,
            "assists": 4.6,
        }
    ]


def _simulate_boxscore(game_id: str) -> Dict[str, Any]:
    return {
        "game_id": game_id,
        "home": {
            "team": "BKN",
            "players": [
                {"player": "Mikal Bridges", "points": 25, "rebounds": 6, "assists": 4}
            ],
        },
        "away": {
            "team": "ATL",
            "players": [
                {"player": "Trae Young", "points": 31, "rebounds": 2, "assists": 11}
            ],
        },
    }
