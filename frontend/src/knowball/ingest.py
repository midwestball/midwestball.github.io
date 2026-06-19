"""Pull nflverse data via nflreadpy and persist to local storage."""

from __future__ import annotations

import warnings
from pathlib import Path

import nflreadpy as nfl
import polars as pl

from knowball.binning import histogram_bins
from knowball.config import (
    DISTRIBUTION_METRICS,
    PLAYER_GAME_LOGS_PATH,
    TIMEFRAME_ALL_TIME,
    TIMEFRAME_CURRENT_SEASON,
    TIMEFRAME_LAST_10_WEEKS,
)
from knowball.density import compute_league_kde_frame
from knowball.stats_schema import (
    EXCLUDE_FROM_STATS,
    PARQUET_DISPLAY_COLUMNS,
    PARQUET_LOGS_SCHEMA,
    STAT_CONTEXT_COLUMNS,
    STAT_METRIC_COLUMNS,
    STATS_TABLE_SCHEMA,
)
from knowball.storage import drop_remote_tables, init_db, init_remote_db, write_parquet, write_table

PLAYER_COLUMNS = [
    "gsis_id",
    "display_name",
    "position",
    "position_group",
    "headshot_url",
    "first_name",
    "last_name",
    "college_name",
    "height",
    "weight",
    "birth_date",
]

GAME_COLUMNS = [
    "game_id",
    "season",
    "week",
    "game_type",
    "gameday",
    "weekday",
    "gametime",
    "home_team",
    "away_team",
    "home_score",
    "away_score",
    "location",
    "result",
    "total",
    "overtime",
]

RAW_CONTEXT_COLUMNS = frozenset(
    {
        "player_id",
        "game_id",
        "season",
        "week",
        "season_type",
        "team",
        "opponent_team",
        "position",
        "position_group",
    }
)


def _ensure_game_id(df: pl.DataFrame) -> pl.DataFrame:
    """
    nflverse weekly files omit game_id for some seasons.

    Synthesize a stable per-game key from season/week/player so rows are not
    collapsed when deduplicating.
    """
    if "game_id" not in df.columns:
        df = df.with_columns(pl.lit(None, dtype=pl.Utf8).alias("game_id"))

    return df.with_columns(
        pl.when(pl.col("game_id").is_not_null())
        .then(pl.col("game_id"))
        .otherwise(
            pl.concat_str(
                [
                    pl.col("season").cast(pl.Utf8),
                    pl.col("week").cast(pl.Utf8),
                    pl.col("player_id"),
                ],
                separator="_",
            )
        )
        .alias("game_id")
    )


def _resolve_stat_columns(raw: pl.DataFrame) -> list[str]:
    """Intersect nflverse columns with our canonical stats schema."""
    raw_metrics = set(raw.columns) - RAW_CONTEXT_COLUMNS - EXCLUDE_FROM_STATS
    schema_metrics = set(STAT_METRIC_COLUMNS)

    unknown = sorted(raw_metrics - schema_metrics)
    missing = sorted(schema_metrics - raw_metrics)
    if unknown:
        warnings.warn(f"nflverse columns not in schema: {unknown}", stacklevel=2)
    if missing:
        warnings.warn(f"schema columns missing from nflverse: {missing}", stacklevel=2)

    selected_metrics = [col for col in STAT_METRIC_COLUMNS if col in raw.columns]
    return [*STAT_CONTEXT_COLUMNS, *selected_metrics]


def _cast_to_schema(df: pl.DataFrame, schema: dict[str, pl.DataType]) -> pl.DataFrame:
    casts = [
        pl.col(name).cast(dtype)
        for name, dtype in schema.items()
        if name in df.columns
    ]
    if not casts:
        return df
    return df.with_columns(casts)


def _prepare_players(raw: pl.DataFrame) -> pl.DataFrame:
    return raw.select(
        pl.col("gsis_id"),
        pl.col("display_name"),
        pl.col("position"),
        pl.col("position_group"),
        pl.col("headshot").alias("headshot_url"),
        pl.col("first_name"),
        pl.col("last_name"),
        pl.col("college_name").alias("college"),
        pl.col("height"),
        pl.col("weight"),
        pl.col("birth_date"),
    ).filter(pl.col("gsis_id").is_not_null())


def _prepare_games(raw: pl.DataFrame) -> pl.DataFrame:
    return raw.select(GAME_COLUMNS)


def _prepare_stats(raw: pl.DataFrame) -> pl.DataFrame:
    columns = _resolve_stat_columns(raw)
    return _cast_to_schema(
        _ensure_game_id(raw.filter(pl.col("player_id").is_not_null()))
        .select(columns)
        .unique(subset=["player_id", "game_id"]),
        STATS_TABLE_SCHEMA,
    )


def _prepare_parquet_logs(raw: pl.DataFrame) -> pl.DataFrame:
    stats_columns = _resolve_stat_columns(raw)
    parquet_columns = stats_columns + [
        col for col in PARQUET_DISPLAY_COLUMNS if col in raw.columns
    ]
    return _cast_to_schema(
        _ensure_game_id(raw.filter(pl.col("player_id").is_not_null()))
        .select(parquet_columns)
        .unique(subset=["player_id", "game_id"]),
        PARQUET_LOGS_SCHEMA,
    )


def _filter_timeframe(stats: pl.DataFrame, timeframe: str) -> pl.DataFrame:
    if timeframe in (TIMEFRAME_CURRENT_SEASON, TIMEFRAME_ALL_TIME):
        if timeframe == TIMEFRAME_CURRENT_SEASON:
            max_season = stats.select(pl.col("season").max()).item()
            if max_season is not None:
                return stats.filter(pl.col("season") == max_season)
        return stats

    if timeframe == TIMEFRAME_LAST_10_WEEKS:
        max_season = stats.select(pl.col("season").max()).item()
        if max_season is not None:
            stats = stats.filter(pl.col("season") == max_season)
        max_week = stats.select(pl.col("week").max()).item()
        if max_week is None:
            return stats
        cutoff = max(1, int(max_week) - 9)
        return stats.filter(pl.col("week") >= cutoff)

    raise ValueError(f"Unknown timeframe: {timeframe}")


def compute_league_distributions(
    stats: pl.DataFrame,
    *,
    timeframes: tuple[str, ...] = (
        TIMEFRAME_CURRENT_SEASON,
        TIMEFRAME_LAST_10_WEEKS,
        TIMEFRAME_ALL_TIME,
    ),
    metrics: tuple[str, ...] = DISTRIBUTION_METRICS,
) -> pl.DataFrame:
    """Pre-compute histogram bins for league-wide metric baselines."""
    frames: list[pl.DataFrame] = []

    for timeframe in timeframes:
        subset = _filter_timeframe(stats, timeframe)
        for metric in metrics:
            bins = histogram_bins(subset, metric)
            if bins.is_empty():
                continue
            frames.append(
                bins.with_columns(
                    pl.lit(metric).alias("metric"),
                    pl.lit(timeframe).alias("timeframe_context"),
                )
            )

    if not frames:
        return pl.DataFrame(
            schema={
                "metric": pl.Utf8,
                "timeframe_context": pl.Utf8,
                "bin_start": pl.Float64,
                "bin_end": pl.Float64,
                "count": pl.Int64,
            }
        )

    return pl.concat(frames).select(
        "metric", "timeframe_context", "bin_start", "bin_end", "count"
    )


def ingest_seasons(
    seasons: list[int] | None = None,
    *,
    db_path: Path | None = None,
    db_url: str | None = None,
    parquet_path: Path = PLAYER_GAME_LOGS_PATH,
) -> dict[str, int]:
    """
    Download nflverse data and write to local SQLite + Parquet.

    Replaces all stored seasons with the seasons passed in — pass the full
    desired range on every run (e.g. ``--from-season 2010``).

    Returns row counts per table written.
    """
    if seasons is None:
        seasons = [nfl.get_current_season()]

    raw_players = nfl.load_players()
    raw_schedules = nfl.load_schedules(seasons)
    raw_stats = nfl.load_player_stats(seasons)

    players = _prepare_players(raw_players)
    games = _prepare_games(raw_schedules)
    stats = _prepare_stats(raw_stats)
    parquet_logs = _prepare_parquet_logs(raw_stats)
    distributions = compute_league_distributions(stats)
    league_kde = compute_league_kde_frame(stats, filter_timeframe=_filter_timeframe)

    kwargs: dict[str, Path | str] = {}
    if db_url is not None:
        kwargs["db_url"] = db_url
    elif db_path is not None:
        kwargs["db_path"] = db_path

    if db_url is not None:
        drop_remote_tables(db_url)
        init_remote_db(db_url)
    else:
        init_db(**({"db_path": db_path} if db_path is not None else {}))

    write_kwargs = kwargs

    write_table(players, "players", **write_kwargs)
    write_table(games, "games", **write_kwargs)
    write_table(stats, "stats", **write_kwargs)
    write_table(distributions, "league_distributions", **write_kwargs)
    write_table(league_kde, "league_kde", **write_kwargs)
    write_parquet(parquet_logs, parquet_path)

    return {
        "players": players.height,
        "games": games.height,
        "stats": stats.height,
        "league_distributions": distributions.height,
        "league_kde": league_kde.height,
        "player_game_logs_parquet": parquet_logs.height,
        "seasons": seasons,
    }
