"""Shared database helpers for Postgres/DuckDB dual mode."""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping, Optional

import duckdb
import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

DUCKDB_DEFAULT = Path("warehouse") / "nba.duckdb"


def _ensure_sslmode(url: str) -> str:
    if "sslmode=" in url:
        return url
    return f"{url}{'&' if '?' in url else '?'}sslmode=require"


@lru_cache(maxsize=1)
def get_engine():
    """Return a cached DB handle (Postgres engine or DuckDB connection)."""
    url = os.getenv("DATABASE_URL", "").strip()
    if url:
        return create_engine(_ensure_sslmode(url), pool_pre_ping=True, future=True)
    duck_path = Path(os.getenv("DUCKDB_PATH", DUCKDB_DEFAULT))
    duck_path.parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(duck_path), read_only=True)


def read_sql(query: str, params: Optional[Mapping[str, Any]] = None) -> pd.DataFrame:
    """Run SQL against whichever engine is active and return a DataFrame."""
    params = params or {}
    engine = get_engine()
    if isinstance(engine, Engine):
        return pd.read_sql(text(query), engine, params=params)
    return engine.execute(query, params).df()


def engine_label() -> str:
    engine = get_engine()
    if isinstance(engine, Engine):
        return engine.url.get_backend_name()
    return "duckdb"
