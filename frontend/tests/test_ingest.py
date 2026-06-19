"""Tests for ingest column selection and schema alignment."""

from __future__ import annotations

import re

import polars as pl
import pytest

from knowball.ingest import _prepare_parquet_logs, _prepare_stats, _resolve_stat_columns
from knowball.schema import STATS_DDL
from knowball.stats_schema import (
    STAT_COLUMN_DTYPES,
    STAT_CONTEXT_COLUMNS,
    STAT_METRIC_COLUMNS,
    STATS_TABLE_SCHEMA,
)


def _mock_raw_stats() -> pl.DataFrame:
    """Minimal nflverse-shaped frame with all known stat columns."""
    data: dict[str, list] = {
        "player_id": ["00-001"],
        "season": [2024],
        "week": [1],
        "season_type": ["REG"],
        "team": ["KC"],
        "opponent_team": ["BAL"],
        "position": ["QB"],
        "position_group": ["QB"],
        "player_name": ["Test Player"],
        "player_display_name": ["T. Player"],
        "headshot_url": ["http://example.com/h.png"],
    }
    for col in STAT_METRIC_COLUMNS:
        data[col] = [1 if STATS_TABLE_SCHEMA[col] == pl.Int64 else 1.0]
    return pl.DataFrame(data)


def test_resolve_stat_columns_includes_all_schema_metrics() -> None:
    raw = _mock_raw_stats()
    columns = _resolve_stat_columns(raw)
    assert columns[: len(STAT_CONTEXT_COLUMNS)] == STAT_CONTEXT_COLUMNS
    for metric in STAT_METRIC_COLUMNS:
        assert metric in columns


def test_prepare_stats_has_full_schema() -> None:
    stats = _prepare_stats(_mock_raw_stats())
    assert stats.height == 1
    for col in STATS_TABLE_SCHEMA:
        assert col in stats.columns, col


def test_prepare_parquet_logs_includes_display_names() -> None:
    logs = _prepare_parquet_logs(_mock_raw_stats())
    assert "player_name" in logs.columns
    assert "player_display_name" in logs.columns
    assert "headshot_url" not in logs.columns


def test_unknown_nflverse_column_warns() -> None:
    raw = _mock_raw_stats().with_columns(pl.lit(1).alias("new_nflverse_col"))
    with pytest.warns(UserWarning, match="not in schema"):
        _resolve_stat_columns(raw)


def test_ddl_column_names_match_table_schema() -> None:
    ddl_cols = re.findall(r"^\s+(\w+)\s+(?:INTEGER|REAL|TEXT)", STATS_DDL, re.MULTILINE)
    schema_cols = list(STATS_TABLE_SCHEMA.keys())
    assert ddl_cols == schema_cols


def test_stat_metric_count() -> None:
    assert len(STAT_COLUMN_DTYPES) == len(STAT_METRIC_COLUMNS) == 103
