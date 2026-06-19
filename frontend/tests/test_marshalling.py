"""Checkpoint 2.3 — Polars dtype marshalling from SQLite."""

from __future__ import annotations

import pytest
import polars as pl

from knowball.config import DB_PATH, sqlite_url
from knowball.db import TABLE_SCHEMAS
from knowball.loaders import fetch_player_stats, fetch_sample_rows
from knowball.stats_schema import STATS_TABLE_SCHEMA


def test_stats_table_schema_matches_db_module() -> None:
    assert TABLE_SCHEMAS["stats"] == STATS_TABLE_SCHEMA


def test_stats_table_schema_column_count() -> None:
    assert len(STATS_TABLE_SCHEMA) == 112  # 9 context + 103 metrics


@pytest.mark.skipif(not DB_PATH.exists(), reason="Local SQLite DB not ingested")
def test_stats_dtypes_match_schema() -> None:
    sample = fetch_sample_rows("stats", limit=20, db_url=sqlite_url())
    expected = TABLE_SCHEMAS["stats"]
    for col, dtype in expected.items():
        assert col in sample.columns, col
        assert sample.schema[col] == dtype, f"{col}: {sample.schema[col]} != {dtype}"


@pytest.mark.skipif(not DB_PATH.exists(), reason="Local SQLite DB not ingested")
def test_games_gameday_and_float_columns() -> None:
    games = fetch_sample_rows("games", limit=10, db_url=sqlite_url())
    assert games.schema["gameday"] == pl.Utf8
    assert games.schema["season"] == pl.Int64
    assert games.schema["week"] == pl.Int64
    assert games.schema["total"] == pl.Float64


@pytest.mark.skipif(not DB_PATH.exists(), reason="Local SQLite DB not ingested")
def test_parameterized_player_stats_query() -> None:
    sample = fetch_sample_rows("stats", limit=1, db_url=sqlite_url())
    player_id = sample["player_id"][0]
    stats = fetch_player_stats(player_id, db_url=sqlite_url())
    assert stats.height >= 1
    assert stats["player_id"].unique().to_list() == [player_id]
    assert stats.schema["passing_epa"] == pl.Float64
    assert stats.schema["passing_yards"] == pl.Int64
    assert stats.schema["week"] == pl.Int64
