"""Pull nflverse data via nflreadpy and persist to local storage."""

from __future__ import annotations

from pathlib import Path

import nflreadpy as nfl
import polars as pl

from knowball.binning import histogram_bins
from knowball.config import (
    DISTRIBUTION_METRICS,
    PLAYER_GAME_LOGS_PATH,
    TIMEFRAME_CURRENT_SEASON,
    TIMEFRAME_LAST_10_WEEKS,
)
from knowball.storage import init_db, write_parquet, write_table

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

STATS_COLUMNS = [
    "player_id",
    "game_id",
    "season",
    "week",
    "season_type",
    "team",
    "opponent_team",
    "position",
    "position_group",
    "passing_epa",
    "rushing_epa",
    "receiving_epa",
    "completions",
    "attempts",
    "passing_yards",
    "passing_tds",
    "rushing_yards",
    "rushing_tds",
    "receptions",
    "targets",
    "receiving_yards",
    "receiving_tds",
]

PARQUET_LOG_COLUMNS = STATS_COLUMNS + ["player_name", "player_display_name"]


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
    return (
        raw.filter(pl.col("player_id").is_not_null())
        .select(STATS_COLUMNS)
        .unique(subset=["player_id", "game_id"])
    )


def _prepare_parquet_logs(raw: pl.DataFrame) -> pl.DataFrame:
    return (
        raw.filter(pl.col("player_id").is_not_null())
        .select(PARQUET_LOG_COLUMNS)
        .unique(subset=["player_id", "game_id"])
    )


def _filter_timeframe(stats: pl.DataFrame, timeframe: str) -> pl.DataFrame:
    if timeframe == TIMEFRAME_CURRENT_SEASON:
        return stats

    if timeframe == TIMEFRAME_LAST_10_WEEKS:
        max_week = stats.select(pl.col("week").max()).item()
        if max_week is None:
            return stats
        cutoff = max(1, int(max_week) - 9)
        return stats.filter(pl.col("week") >= cutoff)

    raise ValueError(f"Unknown timeframe: {timeframe}")


def compute_league_distributions(
    stats: pl.DataFrame,
    *,
    timeframes: tuple[str, ...] = (TIMEFRAME_CURRENT_SEASON, TIMEFRAME_LAST_10_WEEKS),
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
    parquet_path: Path = PLAYER_GAME_LOGS_PATH,
) -> dict[str, int]:
    """
    Download nflverse data and write to local SQLite + Parquet.

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

    kwargs = {}
    if db_path is not None:
        kwargs["db_path"] = db_path

    init_db(**kwargs)
    write_table(players, "players", **kwargs)
    write_table(games, "games", **kwargs)
    write_table(stats, "stats", **kwargs)
    write_table(distributions, "league_distributions", **kwargs)
    write_parquet(parquet_logs, parquet_path)

    return {
        "players": players.height,
        "games": games.height,
        "stats": stats.height,
        "league_distributions": distributions.height,
        "player_game_logs_parquet": parquet_logs.height,
        "seasons": seasons,
    }
