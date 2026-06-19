"""Checkpoint 2.1 — DB connection integration tests."""

from __future__ import annotations

import pytest
import polars as pl

from knowball.config import DB_PATH, get_supabase_db_url, sqlite_url
from knowball.loaders import fetch_sample_rows
from knowball.supabase_check import supabase_is_reachable


@pytest.mark.skipif(not DB_PATH.exists(), reason="Local SQLite DB not ingested")
def test_sqlite_connection_fetches_five_rows() -> None:
    url = sqlite_url()
    for table in ("players", "games", "stats", "league_distributions"):
        df = fetch_sample_rows(table, limit=5, db_url=url)
        assert df.height == 5, table
        assert len(df.columns) > 0, table


@pytest.mark.skipif(
    not supabase_is_reachable(),
    reason="Supabase not configured or not reachable",
)
def test_supabase_connection_fetches_five_rows() -> None:
    url = get_supabase_db_url()
    assert url is not None
    df = fetch_sample_rows("players", limit=5, db_url=url)
    assert df.height == 5
    assert "gsis_id" in df.columns


@pytest.mark.skipif(
    not supabase_is_reachable(),
    reason="Supabase not configured or not reachable",
)
def test_supabase_stats_marshalling() -> None:
    url = get_supabase_db_url()
    assert url is not None
    df = fetch_sample_rows("stats", limit=10, db_url=url)
    assert df.schema["week"] == pl.Int64
    assert df.schema["passing_epa"] == pl.Float64
