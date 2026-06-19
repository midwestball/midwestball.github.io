"""Database query helpers with Polars output (Phase 2)."""

from __future__ import annotations

from typing import Any

import polars as pl
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import Connection

from knowball.config import DB_URL
from knowball.stats_schema import PARQUET_LOGS_SCHEMA, STATS_TABLE_SCHEMA

TABLE_SCHEMAS: dict[str, dict[str, pl.DataType]] = {
    "players": {
        "gsis_id": pl.Utf8,
        "display_name": pl.Utf8,
        "position": pl.Utf8,
        "position_group": pl.Utf8,
        "headshot_url": pl.Utf8,
        "first_name": pl.Utf8,
        "last_name": pl.Utf8,
        "college": pl.Utf8,
        "height": pl.Utf8,
        "weight": pl.Int64,
        "birth_date": pl.Utf8,
    },
    "games": {
        "game_id": pl.Utf8,
        "season": pl.Int64,
        "week": pl.Int64,
        "game_type": pl.Utf8,
        "gameday": pl.Utf8,
        "weekday": pl.Utf8,
        "gametime": pl.Utf8,
        "home_team": pl.Utf8,
        "away_team": pl.Utf8,
        "home_score": pl.Int64,
        "away_score": pl.Int64,
        "location": pl.Utf8,
        "result": pl.Int64,
        "total": pl.Float64,
        "overtime": pl.Int64,
    },
    "stats": STATS_TABLE_SCHEMA,
    "league_distributions": {
        "metric": pl.Utf8,
        "timeframe_context": pl.Utf8,
        "bin_start": pl.Float64,
        "bin_end": pl.Float64,
        "count": pl.Int64,
    },
    "league_kde": {
        "metric": pl.Utf8,
        "timeframe_context": pl.Utf8,
        "grid_index": pl.Int64,
        "x": pl.Float64,
        "density": pl.Float64,
        "axis_min": pl.Float64,
        "axis_max": pl.Float64,
    },
}

PLAYER_GAME_LOGS_SCHEMA: dict[str, pl.DataType] = PARQUET_LOGS_SCHEMA


def get_engine(db_url: str = DB_URL) -> Engine:
    return create_engine(db_url)


def cast_dataframe(df: pl.DataFrame, schema: dict[str, pl.DataType]) -> pl.DataFrame:
    """Cast columns to expected Polars dtypes, ignoring unknown columns."""
    casts = [
        pl.col(name).cast(dtype)
        for name, dtype in schema.items()
        if name in df.columns
    ]
    if not casts:
        return df
    return df.with_columns(casts)


def query_polars(
    sql: str,
    params: dict[str, Any] | None = None,
    *,
    db_url: str = DB_URL,
    schema: dict[str, pl.DataType] | str | None = None,
) -> pl.DataFrame:
    """
    Run a parameterized SQL query and return a Polars DataFrame.

    Use named parameters in SQL (e.g. ``:player_id``) with a matching params dict.
    """
    engine = get_engine(db_url)
    try:
        with engine.connect() as conn:
            df = _read_query(conn, sql, params)
    finally:
        engine.dispose()

    if schema is None:
        return df
    if isinstance(schema, str):
        schema = TABLE_SCHEMAS[schema]
    return cast_dataframe(df, schema)


def _read_query(
    conn: Connection,
    sql: str,
    params: dict[str, Any] | None,
) -> pl.DataFrame:
    return pl.read_database(
        query=text(sql),
        connection=conn,
        execute_options={"parameters": params or {}},
    )


def pandas_to_polars(
    df: Any,
    schema: dict[str, pl.DataType] | str | None = None,
) -> pl.DataFrame:
    """Convert a pandas DataFrame (e.g. from st.connection) to typed Polars."""
    result = pl.from_pandas(df)
    if schema is None:
        return result
    if isinstance(schema, str):
        schema = TABLE_SCHEMAS[schema]
    return cast_dataframe(result, schema)
