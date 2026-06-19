"""Uncached data loaders for SQLite and Parquet (Phase 2)."""

from __future__ import annotations

from typing import Any

import polars as pl

from knowball.config import DB_URL, PLAYER_GAME_LOGS_PATH
from knowball.db import (
    PLAYER_GAME_LOGS_SCHEMA,
    cast_dataframe,
    query_polars,
)
from knowball.density import kde_df_to_dict


def load_player_game_logs() -> pl.DataFrame:
    """Load the full player game log Parquet cache."""
    df = pl.read_parquet(PLAYER_GAME_LOGS_PATH)
    return cast_dataframe(df, PLAYER_GAME_LOGS_SCHEMA)


def load_league_distributions() -> pl.DataFrame:
    """Load all pre-computed league histogram bins."""
    return query_polars(
        "SELECT metric, timeframe_context, bin_start, bin_end, count "
        "FROM league_distributions",
        schema="league_distributions",
    )


def load_league_kde_curve(
    metric: str,
    timeframe: str,
    *,
    db_url: str = DB_URL,
) -> dict[str, Any]:
    """Load a precomputed league KDE curve from SQLite/Postgres."""
    df = query_polars(
        """
        SELECT grid_index, x, density, axis_min, axis_max
        FROM league_kde
        WHERE metric = :metric AND timeframe_context = :timeframe
        ORDER BY grid_index
        """,
        {"metric": metric, "timeframe": timeframe},
        db_url=db_url,
        schema="league_kde",
    )
    return kde_df_to_dict(df)


def load_players(*, position: str | None = None, limit: int | None = None) -> pl.DataFrame:
    """Load player directory rows, optionally filtered by position."""
    sql = "SELECT * FROM players"
    params: dict[str, str | int] = {}

    if position is not None:
        sql += " WHERE position = :position"
        params["position"] = position
    if limit is not None:
        sql += f" LIMIT {int(limit)}"

    return query_polars(sql, params or None, schema="players")


def fetch_player_stats(player_id: str, *, db_url: str = DB_URL) -> pl.DataFrame:
    """Parameterized query for a single player's game stats."""
    return query_polars(
        """
        SELECT *
        FROM stats
        WHERE player_id = :player_id
        ORDER BY season, week
        """,
        {"player_id": player_id},
        db_url=db_url,
        schema="stats",
    )


def fetch_sample_rows(
    table: str,
    *,
    limit: int = 5,
    db_url: str = DB_URL,
) -> pl.DataFrame:
    """Fetch a small sample from a table (used by connection tests)."""
    if table not in ("players", "games", "stats", "league_distributions", "league_kde"):
        raise ValueError(f"Unknown table: {table}")
    return query_polars(
        f"SELECT * FROM {table} LIMIT {int(limit)}",
        db_url=db_url,
        schema=table,
    )
