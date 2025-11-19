"""Helpers to generate deterministic integer IDs for boxscore inserts."""

from __future__ import annotations

import hashlib
from datetime import date

MAX_SIGNED_BIGINT = 2**63 - 1


def stable_bigint(value: str) -> int:
    digest = hashlib.md5(value.encode("utf-8")).hexdigest()
    return int(digest, 16) % MAX_SIGNED_BIGINT


def compute_game_id(game_date: date, team: str, opponent: str) -> int:
    tags = "_".join(sorted([team, opponent]))
    return stable_bigint(f"{game_date.isoformat()}_{tags}")


def compute_team_id(team: str) -> int:
    return stable_bigint(f"team::{team}")


def compute_player_id(player: str, team: str, game_date: date) -> int:
    return stable_bigint(f"{player}::{team}::{game_date.isoformat()}")
