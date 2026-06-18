"""Local SQLite and Parquet persistence (Phase 1 escape hatch)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import polars as pl
from sqlalchemy import create_engine

from knowball.config import DB_PATH, PARQUET_DIR, PLAYER_GAME_LOGS_PATH
from knowball.schema import ALL_DDL


def ensure_data_dirs() -> None:
    PARQUET_DIR.mkdir(parents=True, exist_ok=True)
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)


def init_db(db_path: Path = DB_PATH) -> sqlite3.Connection:
    """Create tables if they do not exist."""
    ensure_data_dirs()
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    for ddl in ALL_DDL:
        conn.executescript(ddl)
    conn.commit()
    return conn


def _sqlite_uri(db_path: Path = DB_PATH) -> str:
    return f"sqlite:///{db_path.resolve().as_posix()}"


def write_table(
    df: pl.DataFrame,
    table: str,
    *,
    db_path: Path = DB_PATH,
    if_exists: str = "replace",
) -> None:
    """Write a Polars DataFrame to a SQLite table."""
    ensure_data_dirs()
    init_db(db_path).close()
    engine = create_engine(_sqlite_uri(db_path))
    try:
        df.write_database(
            table_name=table,
            connection=engine,
            if_table_exists=if_exists,  # type: ignore[arg-type]
        )
    finally:
        engine.dispose()


def write_parquet(df: pl.DataFrame, path: Path = PLAYER_GAME_LOGS_PATH) -> None:
    ensure_data_dirs()
    df.write_parquet(path, compression="zstd")
