from __future__ import annotations

import csv
import io
import os
from datetime import date
from pathlib import Path
from typing import Iterable, Iterator, Mapping

import pandas as pd

from .validators import (
    build_surrogate_game_id,
    build_surrogate_player_id,
    format_minutes,
    infer_season_label,
    infer_season_year,
    normalize_team_name,
    parse_date,
    to_float,
    to_int,
)


DATASET_ID = os.getenv(
    "KAGGLE_DATASET_ID", "eoinamoore/historical-nba-data-and-player-box-scores"
)
DEFAULT_GAME_TYPES = {
    "Regular Season",
    "Playoffs",
    "PlayIn",
    "Emirates NBA Cup",
}


def resolve_kaggle_dir(explicit: str | None = None) -> Path:
    if explicit:
        target = Path(explicit).expanduser()
        if not target.exists():
            raise FileNotFoundError(f"{target} does not exist")
        return target

    env_path = os.getenv("KAGGLE_DATA_DIR")
    if env_path:
        target = Path(env_path).expanduser()
        if not target.exists():
            raise FileNotFoundError(f"{target} does not exist")
        return target

    try:
        import kagglehub
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise RuntimeError(
            "kagglehub is not installed and KAGGLE_DATA_DIR is not set"
        ) from exc

    return Path(kagglehub.dataset_download(DATASET_ID))


def load_kaggle_games(
    kaggle_dir: Path,
    start_date: date,
    end_date: date,
    allowed_types: Iterable[str] | None = None,
) -> list[dict]:
    game_types = set(allowed_types or DEFAULT_GAME_TYPES)
    csv_path = kaggle_dir / "Games.csv"
    if not csv_path.exists():
        raise FileNotFoundError(f"Games.csv not found in {kaggle_dir}")

    usecols = [
        "gameId",
        "gameDateTimeEst",
        "gameType",
        "season",
        "hometeamName",
        "hometeamCity",
        "awayteamName",
        "awayteamCity",
        "homeScore",
        "awayScore",
        "attendance",
    ]
    try:
        frame = pd.read_csv(csv_path, usecols=usecols, parse_dates=["gameDateTimeEst"])
    except ValueError:
        frame = pd.read_csv(csv_path, parse_dates=["gameDateTimeEst"])
    frame["game_date"] = frame["gameDateTimeEst"].dt.date
    mask = (frame["game_date"] >= start_date) & (frame["game_date"] <= end_date)
    frame = frame.loc[mask]
    frame = frame[frame["gameType"].isin(game_types)]

    games: list[dict] = []
    for record in frame.to_dict("records"):
        game_date = record["game_date"]
        start_ts_val = record.get("gameDateTimeEst")
        start_time = None
        if pd.notna(start_ts_val):
            start_time = start_ts_val.to_pydatetime().strftime("%H:%M")
        visitor = normalize_team_name(record["awayteamName"] or record["awayteamCity"])
        home = normalize_team_name(record["hometeamName"] or record["hometeamCity"])
        visitor_pts = to_int(record.get("awayScore"), default=0)
        home_pts = to_int(record.get("homeScore"), default=0)
        margin = (home_pts or 0) - (visitor_pts or 0)
        games.append(
            {
                "game_id": to_int(record.get("gameId"))
                or build_surrogate_game_id(game_date, visitor, home),
                "date": game_date,
                "start_time": start_time,
                "visitor_team": visitor,
                "visitor_pts": visitor_pts,
                "home_team": home,
                "home_pts": home_pts,
                "attendance": to_int(record.get("attendance")),
                "notes": record.get("gameType"),
                "season": record.get("season") or infer_season_year(game_date),
                "total_points": (home_pts or 0) + (visitor_pts or 0),
                "margin_home": margin,
                "abs_margin": abs(margin),
                "home_win": 1 if margin > 0 else 0,
                "home_team_std": home,
                "visitor_team_std": visitor,
            }
        )
    return games


def stream_kaggle_boxscores(
    kaggle_dir: Path, start_date: date, end_date: date, chunk_size: int = 50000
) -> Iterator[dict]:
    csv_path = kaggle_dir / "PlayerStatistics.csv"
    if not csv_path.exists():
        raise FileNotFoundError(f"PlayerStatistics.csv not found in {kaggle_dir}")

    usecols = [
        "gameId",
        "gameDateTimeEst",
        "playerteamId",
        "playerteamName",
        "playerteamCity",
        "personId",
        "firstName",
        "lastName",
        "starterPosition",
        "comment",
        "numMinutes",
        "points",
        "assists",
        "reboundsTotal",
        "reboundsOffensive",
        "reboundsDefensive",
        "steals",
        "blocks",
        "fieldGoalsMade",
        "fieldGoalsAttempted",
        "fieldGoalsPercentage",
        "threePointersMade",
        "threePointersAttempted",
        "threePointersPercentage",
        "freeThrowsMade",
        "freeThrowsAttempted",
        "freeThrowsPercentage",
        "foulsPersonal",
        "turnovers",
        "plusMinusPoints",
    ]
    try:
        reader = pd.read_csv(csv_path, usecols=usecols, chunksize=chunk_size)
    except ValueError:
        reader = pd.read_csv(csv_path, chunksize=chunk_size)

    for chunk in reader:
        chunk["game_date"] = pd.to_datetime(chunk["gameDateTimeEst"]).dt.date
        mask = (chunk["game_date"] >= start_date) & (chunk["game_date"] <= end_date)
        filtered = chunk.loc[mask]
        if filtered.empty:
            continue

        for record in filtered.to_dict("records"):
            game_date = record["game_date"]
            team = normalize_team_name(record.get("playerteamName") or record.get("playerteamCity"))
            game_id = to_int(record.get("gameId"))
            if not game_id:
                game_id = build_surrogate_game_id(game_date, team, team)
            player_name = f"{record.get('firstName', '').strip()} {record.get('lastName', '').strip()}".strip()
            player_id = to_int(record.get("personId"))
            if not player_id:
                player_id = build_surrogate_player_id(game_id, player_name or team)

            yield {
                "game_id": game_id,
                "team_id": to_int(record.get("playerteamId")),
                "team_abbreviation": team,
                "team_city": record.get("playerteamCity"),
                "player_id": player_id,
                "player_name": player_name,
                "nickname": None,
                "start_position": record.get("starterPosition"),
                "comment": record.get("comment"),
                "min": format_minutes(record.get("numMinutes")),
                "fgm": to_float(record.get("fieldGoalsMade"), default=0.0),
                "fga": to_float(record.get("fieldGoalsAttempted"), default=0.0),
                "fg_pct": to_float(record.get("fieldGoalsPercentage")),
                "fg3m": to_float(record.get("threePointersMade"), default=0.0),
                "fg3a": to_float(record.get("threePointersAttempted"), default=0.0),
                "fg3_pct": to_float(record.get("threePointersPercentage")),
                "ftm": to_float(record.get("freeThrowsMade"), default=0.0),
                "fta": to_float(record.get("freeThrowsAttempted"), default=0.0),
                "ft_pct": to_float(record.get("freeThrowsPercentage")),
                "oreb": to_float(record.get("reboundsOffensive"), default=0.0),
                "dreb": to_float(record.get("reboundsDefensive"), default=0.0),
                "reb": to_float(record.get("reboundsTotal"), default=0.0),
                "ast": to_float(record.get("assists"), default=0.0),
                "stl": to_float(record.get("steals"), default=0.0),
                "blk": to_float(record.get("blocks"), default=0.0),
                "to": to_float(record.get("turnovers"), default=0.0),
                "pf": to_float(record.get("foulsPersonal"), default=0.0),
                "pts": to_float(record.get("points"), default=0.0),
                "plus_minus": to_float(record.get("plusMinusPoints")),
                "season": infer_season_label(game_date),
                "season_1": infer_season_label(game_date),
                "game_date": game_date,
            }


def _read_payload(raw: str | os.PathLike) -> str:
    candidate = str(raw)
    potential_path = Path(candidate)
    if potential_path.exists():
        return potential_path.read_text()
    return candidate


def _detect_delimiter(text: str) -> str:
    if text.count("\t") > text.count(","):
        return "\t"
    return ","


def parse_manual_games_payload(raw: str) -> list[dict]:
    text = _read_payload(raw)
    delimiter = _detect_delimiter(text)
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)

    header = None
    games: list[dict] = []
    for row in reader:
        row = [col.strip() for col in row]
        if not any(row):
            continue

        if "Visitor/Neutral" in row and "Home/Neutral" in row:
            header = row
            continue
        if header is None:
            continue

        if row[0].lower() in ("date", "visitor/neutral"):
            header = row
            continue

        record = _row_to_dict(row, header)
        visitor = record.get("Visitor/Neutral") or record.get("Visitor")
        home = record.get("Home/Neutral") or record.get("Home")
        if not visitor or not home:
            continue

        visitor_pts = record.get("PTS") or record.get("Visitor PTS")
        home_pts = record.get("PTS.1") or record.get("Home PTS")

        games.append(
            {
                "date": record.get("Date"),
                "start_time": record.get("Start (ET)") or record.get("Start"),
                "visitor_team": visitor,
                "visitor_pts": visitor_pts,
                "home_team": home,
                "home_pts": home_pts,
                "notes": record.get("Notes") or record.get("OT"),
            }
        )
    return games


def _row_to_dict(row: list[str], header: list[str]) -> dict:
    padded = list(row)
    if len(padded) < len(header):
        padded.extend([""] * (len(header) - len(row)))
    return {header[idx]: padded[idx] for idx in range(len(header))}


def parse_manual_boxscores_payload(raw: str) -> list[dict]:
    text = _read_payload(raw)
    delimiter = _detect_delimiter(text)
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)

    header: list[str] | None = None
    team_name: str | None = None
    players: list[dict] = []

    for row in reader:
        row = [col.strip() for col in row]
        if not any(row):
            continue

        if len(row) == 1 and row[0]:
            # Line describing the team
            team_name = row[0]
            header = None
            continue

        if row[0] in ("Starters", "Reserves"):
            header = ["Player"] + row[1:]
            continue

        if not header or not team_name:
            continue

        player_name = row[0]
        if player_name.lower() in ("team totals", "basic", "advanced"):
            continue

        stats = _row_to_dict(row[1:], header[1:])
        players.append(
            {
                "team": team_name,
                "player_name": player_name,
                "mp": stats.get("MP"),
                "fgm": stats.get("FG"),
                "fga": stats.get("FGA"),
                "fg_pct": stats.get("FG%"),
                "fg3m": stats.get("3P") or stats.get("3PM"),
                "fg3a": stats.get("3PA"),
                "fg3_pct": stats.get("3P%"),
                "ftm": stats.get("FT"),
                "fta": stats.get("FTA"),
                "ft_pct": stats.get("FT%"),
                "oreb": stats.get("ORB"),
                "dreb": stats.get("DRB"),
                "reb": stats.get("TRB") or stats.get("REB"),
                "ast": stats.get("AST"),
                "stl": stats.get("STL"),
                "blk": stats.get("BLK"),
                "to": stats.get("TOV") or stats.get("TO"),
                "pf": stats.get("PF"),
                "pts": stats.get("PTS"),
                "plus_minus": stats.get("+/-"),
            }
        )
    return players
