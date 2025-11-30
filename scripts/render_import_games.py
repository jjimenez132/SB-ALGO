#!/usr/bin/env python3
from __future__ import annotations

import csv
import os
from collections import Counter
from datetime import date, datetime
from pathlib import Path

import psycopg2
from psycopg2.extras import execute_batch


DATASET_DIR = Path(
    os.environ.get(
        "KAGGLE_DATASET_DIR",
        "/Users/javierjimenez/.cache/kagglehub/datasets/eoinamoore/historical-nba-data-and-player-box-scores/versions/288",
    )
)
GAMES_CSV = DATASET_DIR / "Games.csv"
TEAM_HISTORIES_CSV = DATASET_DIR / "TeamHistories.csv"
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://sb_algo_db_user:0HDtYp4EY2Lo5At8iyf44PD1zDioSPK7@dpg-d495uhchg0os738l1a50-a.virginia-postgres.render.com/sb_algo_db?sslmode=require",
)
MIN_EXPECTED_GAMES = 70000
REQUIRED_MAX_DATE = date(2025, 11, 28)
PLAYOFF_GAME_TYPES = {"Playoffs", "Play-In Tournament", "PlayIn"}


def parse_int(value: str | None) -> int | None:
    if value is None:
        return None
    value = value.strip()
    if not value:
        return None
    return int(round(float(value)))


def load_team_lookup() -> dict[str, str]:
    lookup: dict[str, tuple[int, str]] = {}
    with TEAM_HISTORIES_CSV.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            team_id = row["teamId"].strip()
            abbrev = row["teamAbbrev"].strip().upper()
            if not team_id or not abbrev:
                continue
            season_active_till = row["seasonActiveTill"].strip()
            end_season = int(season_active_till) if season_active_till else 0
            current = lookup.get(team_id)
            if current is None or end_season >= current[0]:
                lookup[team_id] = (end_season, abbrev)

    overrides = {
        "1610612746": "LAC",
        "1610612747": "LAL",
    }
    return {team_id: overrides.get(team_id, data[1]) for team_id, data in lookup.items()}


def compute_season(game_date: date) -> int:
    return game_date.year if game_date.month >= 7 else game_date.year - 1


def load_games(team_lookup: dict[str, str]) -> tuple[list[dict], Counter, set[str], date, date]:
    rows = []
    seasons_counter: Counter[int] = Counter()
    seen_ids: set[str] = set()
    min_date = None
    max_date = None
    game_types: set[str] = set()

    with GAMES_CSV.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for raw in reader:
            game_id = raw["gameId"].strip()
            if not game_id or game_id in seen_ids:
                continue
            seen_ids.add(game_id)

            dt_str = raw["gameDateTimeEst"].strip()
            if not dt_str:
                continue
            game_dt = datetime.fromisoformat(dt_str)
            game_date = game_dt.date()
            start_time = game_dt.strftime("%H:%M:%S")

            home_id = raw["hometeamId"].strip()
            visitor_id = raw["awayteamId"].strip()
            home_abbrev = team_lookup.get(home_id)
            visitor_abbrev = team_lookup.get(visitor_id)
            if not home_abbrev or not visitor_abbrev:
                continue

            home_pts = parse_int(raw["homeScore"]) or 0
            visitor_pts = parse_int(raw["awayScore"]) or 0
            total_points = home_pts + visitor_pts
            margin_home = home_pts - visitor_pts
            abs_margin = abs(margin_home)
            home_win = 1 if margin_home > 0 else 0
            attendance = parse_int(raw.get("attendance"))

            game_type = raw.get("gameType", "").strip() or "Regular Season"
            label = raw.get("gameLabel", "").strip()
            sub_label = raw.get("gameSubLabel", "").strip()
            notes = " | ".join(filter(None, [game_type, label, sub_label]))

            season_value = compute_season(game_date)
            seasons_counter[season_value] += 1
            game_types.add(game_type)

            if min_date is None or game_date < min_date:
                min_date = game_date
            if max_date is None or game_date > max_date:
                max_date = game_date

            rows.append(
                {
                    "date": game_date,
                    "start_time": start_time,
                    "visitor_team": visitor_abbrev,
                    "visitor_pts": visitor_pts,
                    "home_team": home_abbrev,
                    "home_pts": home_pts,
                    "attendance": attendance,
                    "notes": notes if notes else None,
                    "season": season_value,
                    "total_points": total_points,
                    "margin_home": margin_home,
                    "abs_margin": abs_margin,
                    "home_win": home_win,
                    "home_team_std": home_abbrev,
                    "visitor_team_std": visitor_abbrev,
                    "possible_playoff": 1 if game_type in PLAYOFF_GAME_TYPES else 0,
                }
            )

    if not rows:
        raise RuntimeError("No se pudieron cargar juegos desde el CSV.")
    return rows, seasons_counter, game_types, min_date, max_date


def insert_games(rows: list[dict]) -> None:
    with psycopg2.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("TRUNCATE TABLE games")
            insert_sql = """
                INSERT INTO games (
                    date, start_time, visitor_team, visitor_pts,
                    home_team, home_pts, attendance, notes, season,
                    total_points, margin_home, abs_margin, home_win,
                    home_team_std, visitor_team_std, possible_playoff
                ) VALUES (
                    %(date)s, %(start_time)s, %(visitor_team)s, %(visitor_pts)s,
                    %(home_team)s, %(home_pts)s, %(attendance)s, %(notes)s, %(season)s,
                    %(total_points)s, %(margin_home)s, %(abs_margin)s, %(home_win)s,
                    %(home_team_std)s, %(visitor_team_std)s, %(possible_playoff)s
                )
                ON CONFLICT (date, home_team, visitor_team) DO NOTHING
            """
            execute_batch(cur, insert_sql, rows, page_size=2000)
        conn.commit()


def fetch_stats() -> tuple[int, date, date, list[tuple[int, int]], int]:
    with psycopg2.connect(DATABASE_URL) as conn, conn.cursor() as cur:
        cur.execute("SELECT COUNT(*), MIN(date), MAX(date) FROM games")
        total, min_date, max_date = cur.fetchone()
        cur.execute(
            """
            SELECT EXTRACT(YEAR FROM date)::INT AS year, COUNT(*)
            FROM games
            GROUP BY 1
            ORDER BY 1
            """
        )
        per_year = cur.fetchall()
        cur.execute("SELECT COUNT(*) FROM games WHERE season = 2025")
        season_2025 = cur.fetchone()[0]
    return total, min_date, max_date, per_year, season_2025


def main() -> None:
    if not GAMES_CSV.exists():
        raise FileNotFoundError(f"No existe {GAMES_CSV}")
    if not TEAM_HISTORIES_CSV.exists():
        raise FileNotFoundError(f"No existe {TEAM_HISTORIES_CSV}")

    team_lookup = load_team_lookup()
    rows, season_counts, game_types, src_min_date, src_max_date = load_games(team_lookup)
    insert_games(rows)
    total, db_min_date, db_max_date, per_year_counts, season_2025_total = fetch_stats()

    if total < MIN_EXPECTED_GAMES:
        raise RuntimeError(f"La tabla games solo tiene {total} filas; se esperaban al menos {MIN_EXPECTED_GAMES}.")
    if db_max_date < REQUIRED_MAX_DATE:
        raise RuntimeError(f"La fecha máxima en Postgres ({db_max_date}) es menor al mínimo requerido ({REQUIRED_MAX_DATE}).")
    if db_max_date != src_max_date:
        raise RuntimeError(f"La fecha máxima cargada ({db_max_date}) no coincide con la del CSV ({src_max_date}).")

    expected_2025 = season_counts.get(2025, 0)
    missing_2025 = max(expected_2025 - season_2025_total, 0)

    print(f"Total games importados: {total}")
    print(f"Fecha mínima en Postgres: {db_min_date}")
    print(f"Fecha máxima en Postgres: {db_max_date}")
    print("Juegos por año:")
    for year, count in per_year_counts:
        print(f"  {year}: {count}")
    print(f"Juegos faltantes en 2025-26: {missing_2025}")
    print(f"Game types detectados ({len(game_types)}): {', '.join(sorted(game_types))}")


if __name__ == "__main__":
    main()
