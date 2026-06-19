"""Gaussian kernel density estimation for distribution charts."""

from __future__ import annotations

import math

import numpy as np
import polars as pl
from scipy.stats import gaussian_kde as scipy_gaussian_kde

from knowball.analytics import player_metric_values, robust_axis_range
from knowball.config import (
    DISTRIBUTION_METRICS,
    TIMEFRAME_ALL_TIME,
    TIMEFRAME_CURRENT_SEASON,
    TIMEFRAME_LAST_10_WEEKS,
)

DEFAULT_GRID_POINTS = 200


def _as_numpy(values: pl.Series | list[float] | np.ndarray) -> np.ndarray:
    if isinstance(values, pl.Series):
        arr = values.drop_nulls().to_numpy()
    else:
        arr = np.asarray(values, dtype=float)
        arr = arr[~np.isnan(arr)]
    return arr.astype(float, copy=False)


def gaussian_kde(values: pl.Series | list[float] | np.ndarray, x_grid: np.ndarray) -> np.ndarray:
    """
    Evaluate a Gaussian KDE on a grid using SciPy.

    Returns a probability density; integrating over the grid via trapezoid rule ≈ 1.
    """
    sample = _as_numpy(values)
    if sample.size == 0:
        return np.zeros_like(x_grid, dtype=float)

    if sample.size == 1:
        bandwidth = max(abs(float(sample[0])) * 0.1, 0.5)
        diffs = (x_grid - sample[0]) / bandwidth
        return np.exp(-0.5 * diffs * diffs) / (bandwidth * math.sqrt(2 * math.pi))

    estimator = scipy_gaussian_kde(sample)
    return estimator(x_grid)


def density_grid(
    *series: pl.Series,
    n_points: int = DEFAULT_GRID_POINTS,
) -> tuple[np.ndarray, tuple[float, float] | None]:
    """Shared evaluation grid for one or more value series."""
    axis_range = robust_axis_range(*series)
    if axis_range is None:
        return np.array([], dtype=float), None

    lo, hi = axis_range
    return np.linspace(lo, hi, n_points), axis_range


def kde_curve_dict(
    values: pl.Series | list[float] | np.ndarray,
    *,
    n_points: int = DEFAULT_GRID_POINTS,
) -> dict[str, list[float] | tuple[float, float] | None]:
    """Build a chart-ready KDE curve from raw values."""
    if isinstance(values, pl.Series):
        series = values
    else:
        series = pl.Series("value", _as_numpy(values))

    x_grid, axis_range = density_grid(series, n_points=n_points)
    if x_grid.size == 0:
        return {"x": [], "y": [], "axis_range": None}

    density = gaussian_kde(series, x_grid)
    return {
        "x": x_grid.tolist(),
        "y": density.tolist(),
        "axis_range": axis_range,
    }


def kde_df_to_dict(df: pl.DataFrame) -> dict[str, list[float] | tuple[float, float] | None]:
    """Convert stored league_kde rows to a chart payload."""
    if df.is_empty():
        return {"x": [], "y": [], "axis_range": None}

    ordered = df.sort("grid_index")
    axis_min = float(ordered["axis_min"][0])
    axis_max = float(ordered["axis_max"][0])
    return {
        "x": ordered["x"].to_list(),
        "y": ordered["density"].to_list(),
        "axis_range": (axis_min, axis_max),
    }


def compute_league_kde_frame(
    stats: pl.DataFrame,
    *,
    filter_timeframe,
    timeframes: tuple[str, ...] = (
        TIMEFRAME_CURRENT_SEASON,
        TIMEFRAME_LAST_10_WEEKS,
        TIMEFRAME_ALL_TIME,
    ),
    metrics: tuple[str, ...] = DISTRIBUTION_METRICS,
    n_points: int = DEFAULT_GRID_POINTS,
) -> pl.DataFrame:
    """Pre-compute league KDE curves for ingest."""
    frames: list[pl.DataFrame] = []

    for timeframe in timeframes:
        subset = filter_timeframe(stats, timeframe)
        for metric in metrics:
            values = player_metric_values(subset, metric)
            curve = kde_curve_dict(values, n_points=n_points)
            if not curve["x"]:
                continue

            axis_range = curve["axis_range"]
            assert axis_range is not None
            lo, hi = axis_range
            frames.append(
                pl.DataFrame(
                    {
                        "x": curve["x"],
                        "density": curve["y"],
                    }
                ).with_columns(
                    pl.lit(metric).alias("metric"),
                    pl.lit(timeframe).alias("timeframe_context"),
                    pl.int_range(0, pl.len()).alias("grid_index"),
                    pl.lit(lo).alias("axis_min"),
                    pl.lit(hi).alias("axis_max"),
                )
            )

    if not frames:
        return pl.DataFrame(
            schema={
                "metric": pl.Utf8,
                "timeframe_context": pl.Utf8,
                "grid_index": pl.Int64,
                "x": pl.Float64,
                "density": pl.Float64,
                "axis_min": pl.Float64,
                "axis_max": pl.Float64,
            }
        )

    return pl.concat(frames).select(
        "metric",
        "timeframe_context",
        "grid_index",
        "x",
        "density",
        "axis_min",
        "axis_max",
    )
