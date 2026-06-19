"""KDE density estimation tests."""

from __future__ import annotations

import numpy as np
import polars as pl
import pytest

from knowball.charts import context_comparison_chart, head_to_head_chart
from knowball.config import TIMEFRAME_CURRENT_SEASON
from knowball.density import gaussian_kde, kde_curve_dict


def test_gaussian_kde_integrates_to_one():
    values = pl.Series("x", np.random.default_rng(0).normal(size=500))
    x_grid = np.linspace(-4, 4, 400)
    density = gaussian_kde(values, x_grid)
    area = np.trapezoid(density, x_grid)
    assert area == pytest.approx(1.0, abs=0.05)


def test_gaussian_kde_empty_values():
    x_grid = np.linspace(-1, 1, 10)
    density = gaussian_kde(pl.Series("x", [], dtype=pl.Float64), x_grid)
    assert density.tolist() == [0.0] * 10


def test_kde_curve_dict_builds_payload():
    curve = kde_curve_dict([0.0, 1.0, 2.0, 3.0, 4.0])
    assert len(curve["x"]) == len(curve["y"])
    assert curve["axis_range"] is not None


def test_context_chart_uses_kde_and_clamps_outliers():
    league_logs = pl.DataFrame(
        {"passing_epa": [-1.0, 0.0, 0.5, 1.0, 1.5] * 20}
    )
    league_kde = kde_curve_dict(league_logs["passing_epa"])
    player_logs = pl.DataFrame(
        {
            "passing_epa": [50.0, -1.0, 0.5, 1.0],
            "rushing_epa": [None, None, None, None],
            "receiving_epa": [None, None, None, None],
        }
    )
    fig = context_comparison_chart(
        metric="passing_epa",
        league_kde=league_kde,
        player_logs=player_logs,
        player_name="Backup",
        player_average=12.625,
        timeframe=TIMEFRAME_CURRENT_SEASON,
    )
    assert fig.layout.xaxis.range is not None
    assert fig.layout.xaxis.range[1] < 50.0
    assert fig.layout.yaxis.title.text == "Density"
    assert all(isinstance(trace, type(fig.data[0])) for trace in fig.data)


def test_head_to_head_chart_builds_kde_traces():
    logs_a = pl.DataFrame({"passing_epa": [1.0, 2.0, 3.0, 2.5, 1.5]})
    logs_b = pl.DataFrame({"passing_epa": [0.5, 1.5, 2.5, 2.0, 1.0]})
    fig = head_to_head_chart(
        metric="passing_epa",
        logs_a=logs_a,
        logs_b=logs_b,
        name_a="A",
        name_b="B",
        context_label_a="All-Time",
        context_label_b="2017",
    )
    assert len(fig.data) == 2
    assert fig.layout.yaxis.title.text == "Density"
