"""Percentile and distribution helpers for the Savant UI (Phase 3)."""

from __future__ import annotations

import polars as pl

from knowball.binning import histogram_bins
from knowball.config import (
    DISTRIBUTION_METRICS,
    TIMEFRAME_ALL_TIME,
    TIMEFRAME_BEST_SEASON,
    TIMEFRAME_CURRENT_SEASON,
    TIMEFRAME_LAST_10_WEEKS,
)


def league_current_season(logs: pl.DataFrame) -> int | None:
    """Most recent season present in league-wide game logs."""
    if "season" not in logs.columns or logs.is_empty():
        return None
    return logs.select(pl.col("season").max()).item()


def player_seasons(logs: pl.DataFrame) -> list[int]:
    """Distinct seasons for one player, newest first."""
    if "season" not in logs.columns or logs.is_empty():
        return []
    return (
        logs.select("season")
        .unique()
        .sort("season", descending=True)
        .to_series()
        .to_list()
    )


def player_is_active(logs: pl.DataFrame, league_current_season: int | None) -> bool:
    """True when the player has at least one game in the league's current season."""
    if league_current_season is None or logs.is_empty():
        return False
    return not logs.filter(pl.col("season") == league_current_season).is_empty()


def player_best_season(logs: pl.DataFrame) -> int | None:
    """Season with the highest per-game average across EPA metrics."""
    if logs.is_empty() or "season" not in logs.columns:
        return None

    epa_cols = [metric for metric in DISTRIBUTION_METRICS if metric in logs.columns]
    if not epa_cols:
        return None

    game_epa = logs.with_columns(
        pl.mean_horizontal(*[pl.col(metric) for metric in epa_cols]).alias("_epa")
    ).filter(pl.col("_epa").is_not_null())
    if game_epa.is_empty():
        return None

    season_avg = (
        game_epa.group_by("season")
        .agg(pl.col("_epa").mean().alias("avg_epa"), pl.len().alias("games"))
        .sort(["avg_epa", "games", "season"], descending=[True, True, True])
    )
    return season_avg["season"][0]


def player_timeframe_options(
    logs: pl.DataFrame,
    *,
    league_current_season: int | None,
) -> list[tuple[str, str]]:
    """
    Ordered (value, label) pairs for a player's context selector.

    All-Time first, Best Season second, Last 10 Weeks for active players, then seasons.
    """
    options: list[tuple[str, str]] = [(TIMEFRAME_ALL_TIME, TIMEFRAME_ALL_TIME)]

    best = player_best_season(logs)
    if best is not None:
        options.append((TIMEFRAME_BEST_SEASON, f"Best Season ({best})"))

    if player_is_active(logs, league_current_season):
        options.append((TIMEFRAME_LAST_10_WEEKS, TIMEFRAME_LAST_10_WEEKS))

    for season in player_seasons(logs):
        season_key = str(season)
        options.append((season_key, season_key))

    return options


def format_player_context_label(context: str, logs: pl.DataFrame) -> str:
    """Human-readable label for charts and cards."""
    if context == TIMEFRAME_ALL_TIME:
        return TIMEFRAME_ALL_TIME
    if context == TIMEFRAME_BEST_SEASON:
        best = player_best_season(logs)
        return f"Best Season ({best})" if best is not None else "Best Season"
    if context == TIMEFRAME_LAST_10_WEEKS:
        return TIMEFRAME_LAST_10_WEEKS
    if context.isdigit():
        return context
    return context


def filter_logs_by_player_context(
    logs: pl.DataFrame,
    context: str,
    *,
    league_current_season: int | None,
) -> pl.DataFrame:
    """Subset one player's game logs to a per-player context selection."""
    if context == TIMEFRAME_ALL_TIME:
        return logs

    if context == TIMEFRAME_BEST_SEASON:
        season = player_best_season(logs)
        if season is None:
            return logs.head(0)
        return logs.filter(pl.col("season") == season)

    if context == TIMEFRAME_LAST_10_WEEKS:
        if league_current_season is None:
            return logs.head(0)
        season_logs = logs.filter(pl.col("season") == league_current_season)
        if season_logs.is_empty():
            return season_logs
        max_week = season_logs.select(pl.col("week").max()).item()
        if max_week is None:
            return season_logs.head(0)
        cutoff = max(1, int(max_week) - 9)
        return season_logs.filter(pl.col("week") >= cutoff)

    if context.isdigit():
        return logs.filter(pl.col("season") == int(context))

    raise ValueError(f"Unknown player context: {context}")


def resolve_player_context_season(context: str, logs: pl.DataFrame) -> int | None:
    """Map a player context to a concrete season, when applicable."""
    if context == TIMEFRAME_BEST_SEASON:
        return player_best_season(logs)
    if context.isdigit():
        return int(context)
    return None


def league_subset_for_player_context(
    league_logs: pl.DataFrame,
    context: str,
    *,
    player_logs: pl.DataFrame,
    league_current_season: int | None,
) -> tuple[pl.DataFrame, str]:
    """
    Return league logs and a timeframe key for percentile/bin lookups.

    Precomputed league bins exist for All-Time and Last 10 Weeks; season-specific
    contexts use on-the-fly bins keyed by the season year string.
    """
    if context == TIMEFRAME_ALL_TIME:
        return (
            filter_logs_by_timeframe(league_logs, TIMEFRAME_ALL_TIME),
            TIMEFRAME_ALL_TIME,
        )
    if context == TIMEFRAME_LAST_10_WEEKS:
        return (
            filter_logs_by_timeframe(league_logs, TIMEFRAME_LAST_10_WEEKS),
            TIMEFRAME_LAST_10_WEEKS,
        )

    season = resolve_player_context_season(context, player_logs)
    if season is None:
        return league_logs.head(0), context

    return league_logs.filter(pl.col("season") == season), str(season)


def filter_logs_by_timeframe(logs: pl.DataFrame, timeframe: str) -> pl.DataFrame:
    """Subset game logs to a league-wide timeframe context."""
    if timeframe == TIMEFRAME_ALL_TIME:
        return logs

    if "season" in logs.columns:
        max_season = logs.select(pl.col("season").max()).item()
        if timeframe == TIMEFRAME_CURRENT_SEASON:
            if max_season is None:
                return logs
            return logs.filter(pl.col("season") == max_season)

        if timeframe == TIMEFRAME_LAST_10_WEEKS:
            if max_season is not None:
                logs = logs.filter(pl.col("season") == max_season)

    if timeframe == TIMEFRAME_LAST_10_WEEKS:
        max_week = logs.select(pl.col("week").max()).item()
        if max_week is None:
            return logs
        cutoff = max(1, int(max_week) - 9)
        return logs.filter(pl.col("week") >= cutoff)

    raise ValueError(f"Unknown timeframe: {timeframe}")


def league_bins_for_metric(
    distributions: pl.DataFrame,
    metric: str,
    timeframe: str,
    *,
    fallback_logs: pl.DataFrame | None = None,
) -> pl.DataFrame:
    """Return histogram bins for a metric/timeframe, computing on the fly if needed."""
    bins = (
        distributions.filter(
            (pl.col("metric") == metric) & (pl.col("timeframe_context") == timeframe)
        )
        .select("bin_start", "bin_end", "count")
        .sort("bin_start")
    )
    if not bins.is_empty():
        return bins

    if fallback_logs is None:
        return bins

    subset = filter_logs_by_timeframe(fallback_logs, timeframe)
    return histogram_bins(subset, metric)


def percentile_from_bins(bins: pl.DataFrame, value: float) -> float | None:
    """
    Approximate a 0–100 percentile rank from a cumulative histogram.

    Uses left-inclusive bin edges; the final bin includes its upper edge.
    """
    if bins.is_empty():
        return None

    total = int(bins["count"].sum())
    if total == 0:
        return None

    cumulative = 0
    rows = bins.sort("bin_start").iter_rows(named=True)
    for index, row in enumerate(rows):
        lo = float(row["bin_start"])
        hi = float(row["bin_end"])
        count = int(row["count"])
        if count == 0:
            continue

        is_last = index == bins.height - 1
        in_bin = (lo <= value < hi) or (is_last and lo <= value <= hi)
        if not in_bin:
            cumulative += count
            continue

        if hi == lo:
            fraction = 1.0
        else:
            fraction = (value - lo) / (hi - lo)
            fraction = max(0.0, min(1.0, fraction))

        rank = cumulative + fraction * count
        return max(0.0, min(100.0, 100.0 * rank / total))

    if value < float(bins["bin_start"].min()):
        return 0.0
    return 100.0


def player_metric_values(logs: pl.DataFrame, metric: str) -> pl.Series:
    """Non-null per-game values for one metric."""
    if metric not in logs.columns:
        return pl.Series(name=metric, values=[], dtype=pl.Float64)
    return logs.select(pl.col(metric).drop_nulls().alias(metric))[metric]


def player_metric_average(logs: pl.DataFrame, metric: str) -> float | None:
    """Season/timeframe average for a metric; None when no games with data."""
    values = player_metric_values(logs, metric)
    if values.len() == 0:
        return None
    return float(values.mean())


def player_percentiles(
    player_logs: pl.DataFrame,
    league_logs: pl.DataFrame,
    distributions: pl.DataFrame,
    timeframe: str,
    *,
    metrics: tuple[str, ...] = DISTRIBUTION_METRICS,
    prefiltered: bool = False,
) -> dict[str, float | None]:
    """Percentile ranks for each metric within the selected timeframe."""
    if prefiltered:
        player_subset = player_logs
        league_subset = league_logs
    else:
        player_subset = filter_logs_by_timeframe(player_logs, timeframe)
        league_subset = filter_logs_by_timeframe(league_logs, timeframe)
    results: dict[str, float | None] = {}

    for metric in metrics:
        average = player_metric_average(player_subset, metric)
        if average is None:
            results[metric] = None
            continue

        bins = league_bins_for_metric(
            distributions,
            metric,
            timeframe,
            fallback_logs=league_subset,
        )
        results[metric] = percentile_from_bins(bins, average)

    return results


def player_summary(logs: pl.DataFrame) -> dict[str, object]:
    """High-level profile fields for the player card."""
    if logs.is_empty():
        return {
            "games": 0,
            "teams": [],
            "position": None,
            "display_name": None,
            "headshot_url": None,
        }

    teams = (
        logs.select("team")
        .drop_nulls()
        .unique()
        .sort("team")
        .to_series()
        .to_list()
    )
    position = logs.select(pl.col("position").drop_nulls().first()).item()
    display_name = logs.select(
        pl.coalesce(pl.col("player_display_name"), pl.col("player_name")).first()
    ).item()
    headshot_url = None

    return {
        "games": logs.height,
        "teams": teams,
        "position": position,
        "display_name": display_name,
        "headshot_url": headshot_url,
    }


def robust_axis_range(
    *series: pl.Series,
    padding_fraction: float = 0.05,
) -> tuple[float, float] | None:
    """
    Compute chart x-axis limits that tolerate outliers.

    Uses the 1st–99th percentile band of the combined non-null values.
    """
    values: list[float] = []
    for s in series:
        values.extend(s.drop_nulls().to_list())

    if not values:
        return None

    sorted_values = sorted(values)
    n = len(sorted_values)
    lo_idx = max(0, int(0.01 * (n - 1)))
    hi_idx = min(n - 1, int(0.99 * (n - 1)))
    lo = sorted_values[lo_idx]
    hi = sorted_values[hi_idx]

    if lo == hi:
        pad = max(abs(lo) * 0.1, 0.5)
        return lo - pad, hi + pad

    span = hi - lo
    pad = span * padding_fraction
    return lo - pad, hi + pad
