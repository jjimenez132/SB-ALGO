from __future__ import annotations

import datetime as dt
import os
from typing import Any, Dict, List, Optional

import requests


BASE_URL = "https://tank01-fantasy-stats.p.rapidapi.com"
REQUEST_TIMEOUT = 20


class Tank01NBAError(Exception):
    """Raised when the Tank01 legacy API fails."""

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
        raise Tank01NBAError("RAPIDAPI_KEY environment variable is required")
    return {
        "x-rapidapi-key": api_key,
        "x-rapidapi-host": "tank01-fantasy-stats.p.rapidapi.com",
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
            params=params or {},
            headers=_build_headers(),
            timeout=REQUEST_TIMEOUT,
        )
    except requests.RequestException as exc:  # pragma: no cover - network failure
        raise Tank01NBAError(f"Request failed: {exc}") from exc

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
        raise Tank01NBAError(
            f"Tank01 API returned {response.status_code}",
            status_code=response.status_code,
            payload=payload,
            retry_after=retry_seconds,
        )
    return response.json()


def map_game_to_schema(game: Dict[str, Any]) -> Dict[str, Any]:
    date_str = (
        game.get("gameDate")
        or game.get("gameTime")
        or (game.get("gameDateTime") or "").split("T", 1)[0]
    )
    if date_str and len(date_str) == 8 and date_str.isdigit():
        date_str = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"
    home_team = game.get("home") or game.get("homeTeam")
    visitor_team = game.get("away") or game.get("awayTeam")
    home_pts = int(game.get("homeScore") or game.get("homePts") or 0)
    visitor_pts = int(game.get("awayScore") or game.get("awayPts") or 0)
    total_points = home_pts + visitor_pts
    margin_home = home_pts - visitor_pts
    status = (
        game.get("gameStatusText")
        or game.get("gameStatus")
        or game.get("gameStatusDesc")
        or "Unknown"
    )
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


def _simulate_games(target_date: dt.date) -> List[Dict[str, Any]]:
    iso_date = target_date.isoformat()
    return [
        {
            "gameID": f"{iso_date.replace('-', '')}-001",
            "gameDate": iso_date.replace("-", ""),
            "home": "NYK",
            "away": "PHI",
            "homeScore": 107,
            "awayScore": 103,
            "gameStatusText": "Final",
        }
    ]


def _simulate_boxscore(game_id: str) -> Dict[str, Any]:
    return {
        "gameID": game_id,
        "homeTeam": {
            "teamAbv": "NYK",
            "score": 107,
            "players": [
                {"player": "Jalen Brunson", "points": 32, "assists": 8},
            ],
        },
        "awayTeam": {
            "teamAbv": "PHI",
            "score": 103,
            "players": [
                {"player": "Tyrese Maxey", "points": 28, "assists": 6},
            ],
        },
    }


def _simulate_player_stats(player_id: str) -> Dict[str, Any]:
    return {
        "playerID": player_id,
        "games": [
            {
                "gameID": "20240115-NYKPHI",
                "fantasyPoints": 45.7,
                "stats": {"points": 27, "rebounds": 5, "assists": 6},
            }
        ],
    }


def _simulate_team_stats(team_abbr: str) -> Dict[str, Any]:
    return {
        "teamAbv": team_abbr,
        "season": "2024",
        "games": [
            {
                "gameID": "20240115-NYKPHI",
                "teamPoints": 107,
                "opponentPoints": 103,
            }
        ],
    }


def _simulate_odds(target_date: dt.date) -> Dict[str, Any]:
    iso_date = target_date.isoformat()
    return {
        "gameDate": iso_date,
        "odds": [
            {
                "gameID": f"{iso_date.replace('-', '')}-001",
                "spread": -3.5,
                "home": "NYK",
                "away": "PHI",
            }
        ],
    }


def _get_schedule_from_payload(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    body = payload.get("body")
    if isinstance(body, dict):
        if isinstance(body.get("schedule"), list):
            return body["schedule"]
        if isinstance(body.get("games"), list):
            return body["games"]
    if isinstance(body, list):
        return body
    return []


def fetch_games_raw(
    target_date: dt.date,
    *,
    session: Optional[requests.Session] = None,
    simulate_on_error: bool = True,
) -> List[Dict[str, Any]]:
    params = {"gameDate": target_date.strftime("%Y%m%d")}
    try:
        payload = _request("getNBADailySchedule", params, session=session)
        games = _get_schedule_from_payload(payload)
        if games:
            return games
        # fallback to odds endpoint in case schedule empty but odds exist
        odds_payload = _request(
            "getNBAOdds",
            {"gameDate": params["gameDate"], "playerProps": "true", "nFormat": "list"},
            session=session,
        )
        return odds_payload.get("body", {}).get("schedule", [])
    except Tank01NBAError:
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


def fetch_boxscore_raw(
    game_id: str,
    *,
    session: Optional[requests.Session] = None,
    simulate_on_error: bool = True,
) -> Dict[str, Any]:
    params = {"gameID": game_id}
    try:
        payload = _request("getNBAGameBoxScore", params, session=session)
        return payload.get("body", {})
    except Tank01NBAError:
        if simulate_on_error:
            return _simulate_boxscore(game_id)
        raise


def fetch_player_stats_raw(
    player_id: str,
    *,
    season: str = "2024",
    session: Optional[requests.Session] = None,
    simulate_on_error: bool = True,
) -> Dict[str, Any]:
    params = {
        "playerID": player_id,
        "season": season,
        "fantasyPoints": "true",
    }
    try:
        payload = _request("getNBAGamesForPlayer", params, session=session)
        return payload.get("body", {})
    except Tank01NBAError:
        if simulate_on_error:
            return _simulate_player_stats(player_id)
        raise


def fetch_team_stats_raw(
    team_abbr: str,
    *,
    season: str = "2024",
    session: Optional[requests.Session] = None,
    simulate_on_error: bool = True,
) -> Dict[str, Any]:
    params = {"teamAbv": team_abbr, "season": season}
    try:
        payload = _request("getNBAGamesAndStatsForTeam", params, session=session)
        return payload.get("body", {})
    except Tank01NBAError:
        if simulate_on_error:
            return _simulate_team_stats(team_abbr)
        raise


def fetch_odds_raw(
    target_date: dt.date,
    *,
    session: Optional[requests.Session] = None,
    simulate_on_error: bool = True,
) -> Dict[str, Any]:
    params = {
        "gameDate": target_date.strftime("%Y%m%d"),
        "playerProps": "true",
        "nFormat": "list",
    }
    try:
        payload = _request("getNBAOdds", params, session=session)
        return payload.get("body", {})
    except Tank01NBAError:
        if simulate_on_error:
            return _simulate_odds(target_date)
        raise
