#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
from utils.db import get_engine, upsert_rows
from utils.parsers import (
    parse_manual_boxscores_payload,
    parse_manual_games_payload,
)
from utils.validators import (
    TEAM_NUMERIC_CODES,
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


def normalize_tip_time(raw: str | None) -> str | None:
    if not raw:
        return None
    text = raw.strip().upper().replace(" ", "")
    if text.endswith("P") and not text.endswith("PM"):
        text = text[:-1] + "PM"
    if text.endswith("A") and not text.endswith("AM"):
        text = text[:-1] + "AM"
    for fmt in ("%I:%M%p", "%I:%M%pET", "%I:%M%pEST"):
        try:
            return dt.datetime.strptime(text, fmt).strftime("%H:%M")
        except ValueError:
            continue
    return raw.strip()


def import_manual_games(
    text_or_csv: str,
    *,
    default_date: str | None = None,
    dry_run: bool = False,
) -> int:
    records = parse_manual_games_payload(text_or_csv)
    if not records:
        print("⚠️ No parsable games found in manual payload")
        return 0

    default_dt = parse_date(default_date) if default_date else None
    ready: list[dict] = []

    for record in records:
        game_date = record.get("date") or default_dt
        if not game_date:
            raise ValueError("Each manual game row must include a Date or provide --default-date")
        game_date = parse_date(game_date)
        visitor = normalize_team_name(record.get("visitor_team"))
        home = normalize_team_name(record.get("home_team"))
        visitor_pts = to_int(record.get("visitor_pts"), default=0)
        home_pts = to_int(record.get("home_pts"), default=0)
        margin = (home_pts or 0) - (visitor_pts or 0)

        ready.append(
            {
                "date": game_date,
                "start_time": normalize_tip_time(record.get("start_time")),
                "visitor_team": visitor,
                "visitor_pts": visitor_pts,
                "home_team": home,
                "home_pts": home_pts,
                "notes": record.get("notes"),
                "season": infer_season_year(game_date),
                "total_points": (home_pts or 0) + (visitor_pts or 0),
                "margin_home": margin,
                "abs_margin": abs(margin),
                "home_win": 1 if margin > 0 else 0,
                "home_team_std": home,
                "visitor_team_std": visitor,
            }
        )

    if dry_run:
        print(f"ℹ️ Dry-run only — would insert {len(ready)} manual games")
        return 0

    engine = get_engine()
    inserted = upsert_rows(engine, "games", ready)
    print(f"✅ Inserted {inserted} manual games")
    return inserted


def _resolve_game_id(
    provided_game_id: str | None,
    game_date,
    home_team: str | None,
    visitor_team: str | None,
) -> int:
    if provided_game_id:
        return int(provided_game_id)
    if not home_team or not visitor_team:
        raise ValueError("home_team and visitor_team are required when game_id is omitted")
    home = normalize_team_name(home_team)
    visitor = normalize_team_name(visitor_team)
    return build_surrogate_game_id(game_date, visitor, home)


def import_manual_boxscores(
    text_or_csv: str,
    *,
    game_date: str,
    game_id: str | None = None,
    home_team: str | None = None,
    visitor_team: str | None = None,
    dry_run: bool = False,
) -> int:
    rows = parse_manual_boxscores_payload(text_or_csv)
    if not rows:
        print("⚠️ No parsable player rows found")
        return 0

    game_dt = parse_date(game_date)
    resolved_game_id = _resolve_game_id(game_id, game_dt, home_team, visitor_team)
    season_label = infer_season_label(game_dt)

    prepared: list[dict] = []
    for record in rows:
        player_name = record.get("player_name")
        if not player_name:
            continue

        team_abbr = normalize_team_name(record.get("team"))
        comment = None
        minutes_raw = record.get("mp")
        minutes = format_minutes(minutes_raw)
        if minutes_raw and "did not" in minutes_raw.lower():
            comment = minutes_raw
            minutes = None

        prepared.append(
            {
                "game_id": resolved_game_id,
                "team_id": TEAM_NUMERIC_CODES.get(team_abbr),
                "team_abbreviation": team_abbr,
                "team_city": None,
                "player_id": build_surrogate_player_id(resolved_game_id, f"{team_abbr}-{player_name}"),
                "player_name": player_name,
                "nickname": None,
                "start_position": None,
                "comment": comment,
                "min": minutes,
                "fgm": to_float(record.get("fgm"), default=0.0),
                "fga": to_float(record.get("fga"), default=0.0),
                "fg_pct": to_float(record.get("fg_pct")),
                "fg3m": to_float(record.get("fg3m"), default=0.0),
                "fg3a": to_float(record.get("fg3a"), default=0.0),
                "fg3_pct": to_float(record.get("fg3_pct")),
                "ftm": to_float(record.get("ftm"), default=0.0),
                "fta": to_float(record.get("fta"), default=0.0),
                "ft_pct": to_float(record.get("ft_pct")),
                "oreb": to_float(record.get("oreb"), default=0.0),
                "dreb": to_float(record.get("dreb"), default=0.0),
                "reb": to_float(record.get("reb"), default=0.0),
                "ast": to_float(record.get("ast"), default=0.0),
                "stl": to_float(record.get("stl"), default=0.0),
                "blk": to_float(record.get("blk"), default=0.0),
                "to": to_float(record.get("to"), default=0.0),
                "pf": to_float(record.get("pf"), default=0.0),
                "pts": to_float(record.get("pts"), default=0.0),
                "plus_minus": to_float(record.get("plus_minus")),
                "season": season_label,
                "season_1": season_label,
                "game_date": game_dt,
            }
        )

    if dry_run:
        print(f"ℹ️ Dry-run: would insert {len(prepared)} manual player rows")
        return 0

    engine = get_engine()
    inserted = upsert_rows(engine, "player_boxscores", prepared)
    print(f"✅ Inserted {inserted} manual player rows")
    return inserted


def build_cli() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manual NBA data importer")
    subparsers = parser.add_subparsers(dest="command", required=True)

    games_parser = subparsers.add_parser("games", help="Import manual game lines")
    games_parser.add_argument("input", help="File path or raw Basketball Reference text")
    games_parser.add_argument("--default-date", help="Fallback date if rows omit Date column")
    games_parser.add_argument("--dry-run", action="store_true")

    box_parser = subparsers.add_parser("boxscores", help="Import manual player boxscores")
    box_parser.add_argument("input", help="File path or raw Basketball Reference table")
    box_parser.add_argument("--game-date", required=True, help="Game date (YYYY-MM-DD)")
    box_parser.add_argument("--game-id", help="Optional numeric game_id to preserve official IDs")
    box_parser.add_argument("--home-team", help="Home team (required if game_id omitted)")
    box_parser.add_argument("--visitor-team", help="Visitor team (required if game_id omitted)")
    box_parser.add_argument("--dry-run", action="store_true")

    return parser


def main() -> None:
    parser = build_cli()
    args = parser.parse_args()
    if args.command == "games":
        import_manual_games(args.input, default_date=args.default_date, dry_run=args.dry_run)
    elif args.command == "boxscores":
        import_manual_boxscores(
            args.input,
            game_date=args.game_date,
            game_id=args.game_id,
            home_team=args.home_team,
            visitor_team=args.visitor_team,
            dry_run=args.dry_run,
        )


if __name__ == "__main__":
    main()
