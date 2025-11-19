"""Parsing helpers for Basketball-Reference raw exports."""

from __future__ import annotations

import csv
from datetime import date
from io import StringIO
from typing import Dict, List


BOX_HEADER_PREFIX = "Rk\tPlayer"


def parse_bref_boxscores(raw: str, game_date: date) -> List[Dict]:
    """Parse Basketball-Reference player boxscores table for a single day."""
    rows: List[Dict] = []
    reader = csv.reader(StringIO(raw.strip()), delimiter="\t")

    for raw_row in reader:
        if not raw_row:
            continue

        joined = "\t".join(raw_row).strip()
        if not joined:
            continue
        if joined.startswith(BOX_HEADER_PREFIX) or joined.startswith("Rk Player"):
            continue

        row = [col.strip() for col in raw_row]

        # Pad to the expected length since some rows omit trailing columns
        while len(row) < 27:
            row.append("")

        rk = row[0]
        if not rk or rk.lower() == "rk":
            continue

        player = row[1]
        team = row[2]
        location = row[3]
        opponent = row[4]
        mp = row[6]
        is_away = location == "@"

        def parse_int(idx: int) -> int:
            if idx >= len(row):
                return 0
            value = row[idx]
            if not value:
                return 0
            try:
                return int(value)
            except ValueError:
                try:
                    return int(float(value))
                except ValueError:
                    return 0

        def parse_float(idx: int) -> float | None:
            if idx >= len(row):
                return None
            value = row[idx]
            if not value:
                return None
            try:
                return float(value)
            except ValueError:
                return None

        fg = parse_int(7)
        fga = parse_int(8)
        fg_pct = parse_float(9)
        fg3 = parse_int(10)
        fg3a = parse_int(11)
        fg3_pct = parse_float(12)
        ft = parse_int(13)
        fta = parse_int(14)
        ft_pct = parse_float(15)
        orb = parse_int(16)
        drb = parse_int(17)
        trb = parse_int(18)
        ast = parse_int(19)
        stl = parse_int(20)
        blk = parse_int(21)
        tov = parse_int(22)
        pf = parse_int(23)
        pts = parse_int(24)
        plus_minus = parse_int(25)

        rows.append(
            {
                "game_date": game_date,
                "player_name": player,
                "team": team,
                "opponent": opponent,
                "is_away": is_away,
                "mp": mp,
                "fgm": fg,
                "fga": fga,
                "fg_pct": fg_pct,
                "fg3m": fg3,
                "fg3a": fg3a,
                "fg3_pct": fg3_pct,
                "ftm": ft,
                "fta": fta,
                "ft_pct": ft_pct,
                "orb": orb,
                "dreb": drb,
                "trb": trb,
                "ast": ast,
                "stl": stl,
                "blk": blk,
                "tov": tov,
                "pf": pf,
                "pts": pts,
                "plus_minus": plus_minus,
            }
        )

    return rows


def parse_bref_games_table(raw: str, game_date: date) -> List[Dict]:
    """Parse Basketball-Reference daily game summary table."""
    rows: List[Dict] = []
    reader = csv.reader(StringIO(raw.strip()), delimiter="\t")

    header = None
    visitor_pts_idx = None
    home_pts_idx = None

    for raw_row in reader:
        if not raw_row:
            continue
        row = [col.strip() for col in raw_row]
        if not any(row):
            continue

        if "Visitor/Neutral" in row and "Home/Neutral" in row:
            header = row
            visitor_pts_idx = None
            home_pts_idx = None
            continue

        if not header:
            continue

        if row[0] == header[0] or row[0].lower() == "date":
            continue

        visitor_team = _safe_get(row, header, "Visitor/Neutral")
        home_team = _safe_get(row, header, "Home/Neutral")
        if not visitor_team or not home_team:
            continue

        if visitor_pts_idx is None or home_pts_idx is None:
            visitor_pts_idx, home_pts_idx = _resolve_pts_indexes(header)

        visitor_pts = _safe_int_by_index(row, visitor_pts_idx)
        home_pts = _safe_int_by_index(row, home_pts_idx)

        rows.append(
            {
                "date": game_date,
                "visitor_team": visitor_team,
                "visitor_pts": visitor_pts,
                "home_team": home_team,
                "home_pts": home_pts,
            }
        )

    return rows


def _resolve_pts_indexes(header: List[str]) -> tuple[int, int]:
    first = second = None
    for idx, col in enumerate(header):
        if col == "PTS":
            if first is None:
                first = idx
            else:
                second = idx
                break
    if first is None or second is None:
        raise ValueError("Could not locate both PTS columns in header")
    return first, second


def _safe_get(row: List[str], header: List[str], key: str) -> str:
    try:
        idx = header.index(key)
    except ValueError:
        return ""
    if idx >= len(row):
        return ""
    return row[idx]


def _safe_int_by_index(row: List[str], idx: int) -> int:
    if idx is None or idx >= len(row):
        return 0
    value = row[idx]
    if not value:
        return 0
    try:
        return int(value)
    except ValueError:
        try:
            return int(float(value))
        except ValueError:
            return 0
