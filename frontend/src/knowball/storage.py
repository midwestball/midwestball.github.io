"""Local SQLite and Parquet persistence (Phase 1 escape hatch)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import polars as pl
from sqlalchemy import create_engine, text

from knowball.config import DB_PATH, PARQUET_DIR, PLAYER_GAME_LOGS_PATH
from knowball.schema import ALL_DDL


def ensure_data_dirs() -> None:
    PARQUET_DIR.mkdir(parents=True, exist_ok=True)
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)


def init_db(db_path: Path = DB_PATH) -> sqlite3.Connection:
    """Create SQLite tables if they do not exist."""
    ensure_data_dirs()
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    for ddl in ALL_DDL:
        conn.executescript(ddl)
    conn.commit()
    return conn


def init_remote_db(db_url: str) -> None:
    """Create Postgres tables if they do not exist."""
    engine = create_engine(db_url)
    try:
        with engine.begin() as conn:
            for ddl in ALL_DDL:
                conn.execute(text(ddl))
    finally:
        engine.dispose()


def drop_remote_tables(db_url: str) -> None:
    """Drop all knowball tables on Postgres so schema can be recreated."""
    engine = create_engine(db_url)
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "DROP TABLE IF EXISTS league_kde, league_distributions, "
                    "stats, games, players CASCADE"
                )
            )
    finally:
        engine.dispose()


def truncate_remote_tables(db_url: str) -> None:
    """Clear all knowball tables on Postgres (respects FK order via CASCADE)."""
    drop_remote_tables(db_url)


def _sqlite_uri(db_path: Path = DB_PATH) -> str:
    return f"sqlite:///{db_path.resolve().as_posix()}"


def write_table(
    df: pl.DataFrame,
    table: str,
    *,
    db_path: Path = DB_PATH,
    db_url: str | None = None,
    if_exists: str = "replace",
) -> None:
    """Write a Polars DataFrame to SQLite or Postgres."""
    if db_url:
        init_remote_db(db_url)
        engine = create_engine(db_url)
    else:
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
