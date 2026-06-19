"""Plotly chart builders — KDE density curves (Phase 3)."""

from __future__ import annotations

from typing import Any

import numpy as np
import polars as pl
import plotly.graph_objects as go

from knowball.analytics import player_metric_values, robust_axis_range
from knowball.config import METRIC_LABELS
from knowball.density import density_grid, gaussian_kde


def _metric_title(metric: str) -> str:
    return METRIC_LABELS.get(metric, metric.replace("_", " ").title())


def _hex_rgba(hex_color: str, alpha: float) -> str:
    color = hex_color.lstrip("#")
    red = int(color[0:2], 16)
    green = int(color[2:4], 16)
    blue = int(color[4:6], 16)
    return f"rgba({red},{green},{blue},{alpha})"


def _density_trace(
    x_grid: np.ndarray,
    density: np.ndarray,
    *,
    name: str,
    color: str,
    fill: bool = False,
    opacity: float = 0.75,
) -> go.Scatter:
    return go.Scatter(
        x=x_grid,
        y=density,
        name=name,
        mode="lines",
        line=dict(color=color, width=2.5),
        fill="tozeroy" if fill else "none",
        fillcolor=_hex_rgba(color, 0.25) if fill else None,
        opacity=opacity,
        hovertemplate="Value: %{x:.2f}<br>Density: %{y:.3f}<extra></extra>",
    )


def _resolve_axis_range(
    *series: pl.Series,
    fallback: tuple[float, float] | None = None,
) -> tuple[float, float] | None:
    axis_range = robust_axis_range(*series)
    if axis_range is None:
        return fallback
    if fallback is None:
        return axis_range
    return min(axis_range[0], fallback[0]), max(axis_range[1], fallback[1])


def context_comparison_chart(
    *,
    metric: str,
    league_kde: dict[str, Any],
    player_logs: pl.DataFrame,
    player_name: str,
    player_average: float | None,
    timeframe: str,
) -> go.Figure:
    """League KDE baseline (cached) with live player KDE overlay."""
    fig = go.Figure()
    player_values = player_metric_values(player_logs, metric)

    x_grid = np.asarray(league_kde["x"], dtype=float)
    league_density = np.asarray(league_kde["y"], dtype=float)
    axis_range = league_kde.get("axis_range")

    if x_grid.size == 0:
        x_grid, axis_range = density_grid(player_values)
        if x_grid.size == 0:
            return fig
        league_density = np.zeros_like(x_grid)
    else:
        axis_range = _resolve_axis_range(player_values, fallback=axis_range)
        if axis_range is not None:
            x_grid = np.linspace(axis_range[0], axis_range[1], len(x_grid))
            league_density = np.interp(
                x_grid,
                np.asarray(league_kde["x"], dtype=float),
                np.asarray(league_kde["y"], dtype=float),
            )

    fig.add_trace(
        _density_trace(
            x_grid,
            league_density,
            name=f"League ({timeframe})",
            color="#9ca3af",
            fill=True,
            opacity=0.55,
        )
    )

    if player_values.len() > 0:
        player_density = gaussian_kde(player_values, x_grid)
        fig.add_trace(
            _density_trace(
                x_grid,
                player_density,
                name=player_name,
                color="#2563eb",
                fill=False,
                opacity=0.85,
            )
        )

    if axis_range is not None:
        fig.update_xaxes(range=list(axis_range))

    if player_average is not None:
        fig.add_vline(
            x=player_average,
            line_width=2.5,
            line_color="#dc2626",
            annotation_text=f"Avg {player_average:.2f}",
            annotation_position="top",
        )

    fig.update_layout(
        title=_metric_title(metric),
        xaxis_title=_metric_title(metric),
        yaxis_title="Density",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
        margin=dict(t=60, b=40),
        height=360,
    )
    return fig


def head_to_head_chart(
    *,
    metric: str,
    logs_a: pl.DataFrame,
    logs_b: pl.DataFrame,
    name_a: str,
    name_b: str,
    context_label_a: str,
    context_label_b: str,
) -> go.Figure:
    """Overlay KDE curves for two players on a shared grid."""
    fig = go.Figure()
    values_a = player_metric_values(logs_a, metric)
    values_b = player_metric_values(logs_b, metric)
    x_grid, axis_range = density_grid(values_a, values_b)
    if x_grid.size == 0:
        return fig

    for values, name, color in (
        (values_a, name_a, "#2563eb"),
        (values_b, name_b, "#dc2626"),
    ):
        if values.len() == 0:
            continue
        density = gaussian_kde(values, x_grid)
        fig.add_trace(
            _density_trace(
                x_grid,
                density,
                name=name,
                color=color,
                fill=True,
                opacity=0.65,
            )
        )

    if axis_range is not None:
        fig.update_xaxes(range=list(axis_range))

    fig.update_layout(
        title=(
            f"{_metric_title(metric)} — "
            f"{name_a} ({context_label_a}) vs {name_b} ({context_label_b})"
        ),
        xaxis_title=_metric_title(metric),
        yaxis_title="Density",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
        margin=dict(t=60, b=40),
        height=360,
    )
    return fig
