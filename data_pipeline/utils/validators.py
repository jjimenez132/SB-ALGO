from __future__ import annotations

import hashlib
from datetime import date, datetime
from typing import Iterable, Mapping


TEAM_ABBREVIATIONS = {
    "hawks": "ATL",
    "atl": "ATL",
    "atlanta": "ATL",
    "celtics": "BOS",
    "bos": "BOS",
    "boston": "BOS",
    "nets": "BKN",
    "bkn": "BKN",
    "brooklyn": "BKN",
    "hornets": "CHA",
    "cha": "CHA",
    "charlotte": "CHA",
    "bulls": "CHI",
    "chi": "CHI",
    "chicago": "CHI",
    "cavaliers": "CLE",
    "cle": "CLE",
    "cleveland": "CLE",
    "mavericks": "DAL",
    "dal": "DAL",
    "dallas": "DAL",
    "nuggets": "DEN",
    "den": "DEN",
    "denver": "DEN",
    "pistons": "DET",
    "det": "DET",
    "detroit": "DET",
    "warriors": "GSW",
    "gsw": "GSW",
    "golden state": "GSW",
    "rockets": "HOU",
    "hou": "HOU",
    "houston": "HOU",
    "pacers": "IND",
    "ind": "IND",
    "indiana": "IND",
    "clippers": "LAC",
    "lac": "LAC",
    "la clippers": "LAC",
    "los angeles clippers": "LAC",
    "la": "LAC",
    "lakers": "LAL",
    "lal": "LAL",
    "los angeles lakers": "LAL",
    "los angeles": "LAL",
    "grizzlies": "MEM",
    "mem": "MEM",
    "memphis": "MEM",
    "heat": "MIA",
    "mia": "MIA",
    "miami": "MIA",
    "bucks": "MIL",
    "mil": "MIL",
    "milwaukee": "MIL",
    "timberwolves": "MIN",
    "wolves": "MIN",
    "min": "MIN",
    "minnesota": "MIN",
    "pelicans": "NOP",
    "nop": "NOP",
    "new orleans": "NOP",
    "knicks": "NYK",
    "ny": "NYK",
    "nyk": "NYK",
    "new york": "NYK",
    "thunder": "OKC",
    "okc": "OKC",
    "oklahoma city": "OKC",
    "magic": "ORL",
    "orl": "ORL",
    "orlando": "ORL",
    "76ers": "PHI",
    "sixers": "PHI",
    "phi": "PHI",
    "philadelphia": "PHI",
    "suns": "PHX",
    "phx": "PHX",
    "phoenix": "PHX",
    "trail blazers": "POR",
    "blazers": "POR",
    "por": "POR",
    "portland": "POR",
    "kings": "SAC",
    "sac": "SAC",
    "sacramento": "SAC",
    "spurs": "SAS",
    "sas": "SAS",
    "san antonio": "SAS",
    "raptors": "TOR",
    "tor": "TOR",
    "toronto": "TOR",
    "jazz": "UTA",
    "uta": "UTA",
    "utah": "UTA",
    "wizards": "WAS",
    "was": "WAS",
    "washington": "WAS",
}

TEAM_NUMERIC_CODES = {
    "ATL": 1,
    "BOS": 2,
    "BKN": 3,
    "CHA": 4,
    "CHI": 5,
    "CLE": 6,
    "DAL": 7,
    "DEN": 8,
    "DET": 9,
    "GSW": 10,
    "HOU": 11,
    "IND": 12,
    "LAC": 13,
    "LAL": 14,
    "MEM": 15,
    "MIA": 16,
    "MIL": 17,
    "MIN": 18,
    "NOP": 19,
    "NYK": 20,
    "OKC": 21,
    "ORL": 22,
    "PHI": 23,
    "PHX": 24,
    "POR": 25,
    "SAC": 26,
    "SAS": 27,
    "TOR": 28,
    "UTA": 29,
    "WAS": 30,
}


def normalize_team_name(raw: str | None) -> str:
    if not raw:
        return ""
    value = raw.strip().lower()
    return TEAM_ABBREVIATIONS.get(value, raw.strip().upper())


def infer_season_year(game_date: date) -> int:
    return game_date.year if game_date.month >= 7 else game_date.year - 1


def infer_season_label(game_date: date) -> str:
    start = infer_season_year(game_date)
    return f"{start}-{str(start + 1)[2:]}"


def parse_date(value) -> date:
    if isinstance(value, date):
        return value
    if isinstance(value, datetime):
        return value.date()
    if not value:
        raise ValueError("date is required")
    text = str(value).strip()
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(text).date()
    except ValueError:
        pass
    try:
        return datetime.strptime(text, "%a, %b %d, %Y").date()
    except ValueError as exc:
        raise ValueError(f"Could not parse date '{value}'") from exc


def to_float(value, default=None):
    if value is None or value == "":
        return default
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).replace(",", "").strip()
    try:
        return float(text)
    except ValueError:
        return default


def to_int(value, default=None):
    if value is None or value == "":
        return default
    if isinstance(value, int):
        return value
    try:
        return int(float(str(value).strip()))
    except ValueError:
        return default


def format_minutes(value) -> str | None:
    if value is None or value == "":
        return None
    text = str(value).strip()
    if ":" in text:
        parts = text.split(":")
        if len(parts) >= 2 and parts[0].isdigit() and parts[1].isdigit():
            return f"{int(parts[0]):02d}:{int(parts[1]):02d}"
        try:
            minutes = int(float(text))
            return f"{minutes:02d}:00"
        except ValueError:
            return None
    try:
        minutes = float(text)
    except ValueError:
        return None
    whole = int(minutes)
    seconds = int(round((minutes - whole) * 60))
    return f"{whole:02d}:{seconds:02d}"


def build_surrogate_game_id(game_date: date, visitor: str, home: str) -> int:
    visitor_code = TEAM_NUMERIC_CODES.get(visitor, 0)
    home_code = TEAM_NUMERIC_CODES.get(home, 0)
    return int(f"{game_date.strftime('%Y%m%d')}{home_code:02d}{visitor_code:02d}")


def build_surrogate_player_id(game_id: int, player_name: str) -> int:
    digest = hashlib.sha1(f"{game_id}:{player_name.lower()}".encode("utf-8")).hexdigest()
    return int(digest[:15], 16)


def ensure_required_fields(rows: Iterable[Mapping], required: tuple[str, ...]) -> None:
    for idx, row in enumerate(rows):
        for field in required:
            if field not in row or row[field] in (None, ""):
                raise ValueError(f"Row {idx} is missing required field '{field}'")
