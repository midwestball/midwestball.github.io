"""Phase 3 analytics and chart tests."""

from __future__ import annotations

import polars as pl
import pytest

from knowball.analytics import (
    filter_logs_by_player_context,
    filter_logs_by_timeframe,
    league_current_season,
    percentile_from_bins,
    player_best_season,
    player_is_active,
    player_percentiles,
    player_timeframe_options,
    robust_axis_range,
)
from knowball.config import (
    TIMEFRAME_ALL_TIME,
    TIMEFRAME_BEST_SEASON,
    TIMEFRAME_CURRENT_SEASON,
    TIMEFRAME_LAST_10_WEEKS,
)


def _sample_bins() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "bin_start": [0.0, 1.0, 2.0],
            "bin_end": [1.0, 2.0, 3.0],
            "count": [10, 20, 10],
        }
    )


def test_percentile_from_bins_midpoint():
    bins = _sample_bins()
    # Total 40; value 1.5 is halfway through second bin → cumulative 10 + 0.5*20 = 20 → 50th
    assert percentile_from_bins(bins, 1.5) == pytest.approx(50.0)


def test_percentile_from_bins_below_range():
    bins = _sample_bins()
    assert percentile_from_bins(bins, -5.0) == 0.0


def test_percentile_from_bins_above_range():
    bins = _sample_bins()
    assert percentile_from_bins(bins, 99.0) == 100.0


def test_filter_logs_last_10_weeks():
    logs = pl.DataFrame(
        {"season": [2025] * 5, "week": [1, 5, 10, 12, 18], "passing_epa": [1.0] * 5}
    )
    filtered = filter_logs_by_timeframe(logs, TIMEFRAME_LAST_10_WEEKS)
    assert filtered["week"].to_list() == [10, 12, 18]


def test_retired_player_last_10_weeks_is_empty():
    """Retired players should not surface old seasons as recent form."""
    cutler = pl.DataFrame(
        {
            "season": [2016, 2017, 2017],
            "week": [1, 1, 17],
            "passing_epa": [0.5, 1.0, 2.0],
            "rushing_epa": [None, None, None],
            "receiving_epa": [None, None, None],
        }
    )
    league = pl.DataFrame(
        {
            "season": [2025] * 3,
            "week": [1, 10, 18],
            "passing_epa": [1.0, 1.0, 1.0],
        }
    )
    current = league_current_season(league)
    assert current == 2025
    assert not player_is_active(cutler, current)

    filtered = filter_logs_by_player_context(
        cutler,
        TIMEFRAME_LAST_10_WEEKS,
        league_current_season=current,
    )
    assert filtered.is_empty()


def test_retired_player_season_options_exclude_recent_form():
    cutler = pl.DataFrame(
        {
            "season": [2016, 2017],
            "week": [1, 1],
            "passing_epa": [0.5, 1.0],
            "rushing_epa": [None, None],
            "receiving_epa": [None, None],
        }
    )
    options = player_timeframe_options(cutler, league_current_season=2025)
    values = [value for value, _ in options]
    assert values[0] == TIMEFRAME_ALL_TIME
    assert values[1] == TIMEFRAME_BEST_SEASON
    assert TIMEFRAME_LAST_10_WEEKS not in values
    assert "2017" in values
    assert "2016" in values


def test_active_player_gets_last_10_weeks_option():
    williams = pl.DataFrame(
        {
            "season": [2024, 2025, 2025],
            "week": [1, 1, 10],
            "passing_epa": [0.5, 1.0, 2.0],
            "rushing_epa": [None, None, None],
            "receiving_epa": [None, None, None],
        }
    )
    options = player_timeframe_options(williams, league_current_season=2025)
    values = [value for value, _ in options]
    assert TIMEFRAME_LAST_10_WEEKS in values


def test_player_best_season_picks_highest_epa_average():
    logs = pl.DataFrame(
        {
            "season": [2015, 2015, 2017, 2017],
            "week": [1, 2, 1, 2],
            "passing_epa": [0.0, 0.0, 2.0, 2.0],
            "rushing_epa": [None, None, None, None],
            "receiving_epa": [None, None, None, None],
        }
    )
    assert player_best_season(logs) == 2017


def test_filter_logs_by_player_context_specific_season():
    logs = pl.DataFrame(
        {
            "season": [2015, 2016, 2017],
            "week": [1, 1, 1],
            "passing_epa": [1.0, 2.0, 3.0],
        }
    )
    filtered = filter_logs_by_player_context(
        logs,
        "2016",
        league_current_season=2025,
    )
    assert filtered["season"].to_list() == [2016]


def test_robust_axis_range_handles_outlier():
    values = pl.Series("x", [-100.0, 0.0, 1.0, 2.0, 3.0, 500.0])
    lo, hi = robust_axis_range(values)
    assert hi < 500.0
    assert lo < hi


def test_player_percentiles_with_synthetic_data():
    league = pl.DataFrame(
        {
            "player_id": ["a", "b", "c"] * 3,
            "season": [2025] * 9,
            "week": [1, 1, 1, 2, 2, 2, 3, 3, 3],
            "passing_epa": [0.0, 1.0, 2.0, 0.0, 1.0, 2.0, 0.0, 1.0, 2.0],
            "rushing_epa": [None] * 9,
            "receiving_epa": [None] * 9,
        }
    )
    player = league.filter(pl.col("player_id") == "c")
    distributions = pl.DataFrame(
        {
            "metric": ["passing_epa"] * 3,
            "timeframe_context": [TIMEFRAME_CURRENT_SEASON] * 3,
            "bin_start": [0.0, 1.0, 2.0],
            "bin_end": [1.0, 2.0, 3.0],
            "count": [3, 3, 3],
        }
    )
    pct = player_percentiles(
        player,
        league,
        distributions,
        TIMEFRAME_CURRENT_SEASON,
        metrics=("passing_epa",),
    )
    assert pct["passing_epa"] == pytest.approx(66.67, abs=1.0)
