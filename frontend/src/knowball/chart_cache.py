"""Precomputed league KDE and other chart caches."""

from __future__ import annotations

from typing import Any

import polars as pl
import streamlit as st

from knowball.analytics import (
    filter_logs_by_player_context,
    league_subset_for_player_context,
    player_metric_values,
    player_percentiles,
)
from knowball.cache import (
    filter_player_logs,
    get_league_distributions,
    get_player_game_logs,
)
from knowball.config import (
    DISTRIBUTION_METRICS,
    TIMEFRAME_ALL_TIME,
    TIMEFRAME_LAST_10_WEEKS,
)
from knowball.density import kde_curve_dict
from knowball.loaders import load_league_kde_curve


@st.cache_data
def get_league_kde(metric: str, timeframe: str) -> dict[str, Any]:
    """Load a precomputed league KDE curve (cached in memory after first read)."""
    return load_league_kde_curve(metric, timeframe)


@st.cache_data
def get_league_kde_for_player_context(
    metric: str,
    context: str,
    player_id: str,
    league_current_season: int | None,
) -> dict[str, Any]:
    """League KDE aligned to a player's selected context."""
    if context in (TIMEFRAME_ALL_TIME, TIMEFRAME_LAST_10_WEEKS):
        return get_league_kde(metric, context)

    player_logs = filter_player_logs(player_id)
    league_logs = get_player_game_logs()
    league_subset, _ = league_subset_for_player_context(
        league_logs,
        context,
        player_logs=player_logs,
        league_current_season=league_current_season,
    )
    return kde_curve_dict(player_metric_values(league_subset, metric))


@st.cache_data
def get_cached_player_percentiles(
    player_id: str,
    context: str,
    league_current_season: int | None,
) -> dict[str, float | None]:
    """Cached percentile ranks for one player and context."""
    player_logs = filter_player_logs(player_id)
    league_logs = get_player_game_logs()
    filtered_player = filter_logs_by_player_context(
        player_logs,
        context,
        league_current_season=league_current_season,
    )
    league_subset, timeframe_key = league_subset_for_player_context(
        league_logs,
        context,
        player_logs=player_logs,
        league_current_season=league_current_season,
    )
    return player_percentiles(
        filtered_player,
        league_subset,
        get_league_distributions(),
        timeframe_key,
        metrics=DISTRIBUTION_METRICS,
        prefiltered=True,
    )
