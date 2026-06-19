"""Tests for position-aware stat registry."""

from __future__ import annotations

import polars as pl

from knowball.stat_registry import (
    applicable_metrics,
    filter_logs_for_metric,
)


def test_qb_gets_passing_metrics() -> None:
    metrics = applicable_metrics("QB", "QB")
    assert "passing_epa" in metrics
    assert "passing_yards" in metrics
    assert "def_sacks" not in metrics


def test_k_gets_kicking_metrics() -> None:
    metrics = applicable_metrics("K", "SPEC")
    assert "fg_made" in metrics
    assert "passing_yards" not in metrics


def test_wr_does_not_include_defense_in_applicable() -> None:
    metrics = applicable_metrics("WR", "WR")
    assert "receiving_yards" in metrics
    assert "def_tackles_solo" not in metrics


def test_filter_logs_for_metric_passing_epa() -> None:
    logs = pl.DataFrame(
        {
            "position": ["QB", "WR", "RB"],
            "position_group": ["QB", "WR", "RB"],
            "passing_epa": [1.0, None, None],
        }
    )
    filtered = filter_logs_for_metric(logs, "passing_epa")
    assert filtered.height == 1
    assert filtered["position"][0] == "QB"


def test_filter_logs_for_defense_metric() -> None:
    logs = pl.DataFrame(
        {
            "position": ["LB", "WR"],
            "position_group": ["LB", "WR"],
            "def_sacks": [1.0, None],
        }
    )
    filtered = filter_logs_for_metric(logs, "def_sacks")
    assert filtered.height == 1
    assert filtered["position_group"][0] == "LB"
