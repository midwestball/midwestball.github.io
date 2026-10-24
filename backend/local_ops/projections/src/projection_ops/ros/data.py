"""Cutoff snapshots using the ops cache and the frozen research feature definitions."""

from __future__ import annotations

import numpy as np
import pandas as pd
import polars as pl

from ..live_data import _attach_snaps, _normalize_weekly, load_cached_table
from ..scoring import score
from .config import POSITIONS
from .features import add_snapshot_features


def load_inputs(season: int, *, refresh: bool = False):
    # Completed history is cached; the current season is shared with the weekly run.
    seasons = list(range(2016, season + 1))
    refresh_set = {season} if refresh else set()
    frames = {}
    sources = {}
    for name in ("weekly", "schedules", "rosters", "snaps"):
        frames[name], sources[name] = load_cached_table(name, seasons, refresh_seasons=refresh_set)
    ids, sources["player_ids"] = load_cached_table("player_ids", [0])
    panel = scored_panel(frames["weekly"], frames["snaps"], ids)
    schedule = team_schedule(frames["schedules"])
    roster = pl.from_pandas(frames["rosters"])
    return panel, schedule, roster, sources


def scored_panel(weekly: pd.DataFrame, snaps: pd.DataFrame, ids: pd.DataFrame) -> pl.DataFrame:
    weekly = _normalize_weekly(weekly)
    weekly = weekly[weekly.position.isin(POSITIONS)]
    weekly = weekly[weekly.season_type.astype(str).str.upper().eq("REG")].copy()
    weekly = _attach_snaps(weekly, snaps, ids)
    # Match the research scorer's null-as-zero rule across historical schemas.
    for col in (
        "passing_yards",
        "passing_tds",
        "interceptions",
        "rushing_yards",
        "rushing_tds",
        "receptions",
        "receiving_yards",
        "receiving_tds",
    ):
        if col not in weekly:
            weekly[col] = 0.0
        weekly[col] = pd.to_numeric(weekly[col], errors="coerce").fillna(0.0)
    weekly["points"] = weekly.apply(lambda row: score(row["position"], row), axis=1)
    required = (
        "targets",
        "carries",
        "attempts",
        "offense_snaps",
        "offense_snap_pct",
        "target_share",
        "air_yards_share",
        "wopr",
    )
    for col in required:
        if col not in weekly:
            weekly[col] = np.nan
    keep = ["player_id", "team", "position", "season", "week", "points", *required]
    panel = (
        pl.from_pandas(weekly[keep])
        .with_columns(pl.col("season", "week").cast(pl.Int32))
        .sort("player_id", "season", "week")
    )
    return panel.with_columns(
        (
            (pl.col("offense_snaps").fill_null(0) > 0)
            | (pl.sum_horizontal("targets", "carries", "attempts") > 0)
        ).alias("active"),
        pl.col("points")
        .ewm_mean(half_life=4, min_samples=1)
        .over("player_id", "season")
        .alias("points_ewma_short"),
        pl.col("points")
        .ewm_mean(half_life=16, min_samples=1)
        .over("player_id", "season")
        .alias("points_ewma_med"),
    )


def team_schedule(raw: pd.DataFrame) -> pl.DataFrame:
    raw = raw[raw.game_type.astype(str).str.upper().eq("REG")]
    frames = []
    for side in ("home", "away"):
        frames.append(
            pl.from_pandas(raw[["season", "week", f"{side}_team"]]).rename({f"{side}_team": "team"})
        )
    return pl.concat(frames).with_columns(pl.col("season", "week").cast(pl.Int32))


def roster_at_cutoff(rosters: pl.DataFrame, season: int, cutoff: int) -> pl.DataFrame:
    # Slice each team independently: bye-week teams have no roster rows that week.
    rows = rosters.filter(
        (pl.col("season") == season)
        & (pl.col("week") <= max(1, cutoff))
        & (pl.col("game_type").str.to_uppercase() == "REG")
    )
    latest = rows.group_by("team").agg(pl.col("week").max().alias("_latest"))
    rows = rows.join(latest, on="team").filter(pl.col("week") == pl.col("_latest"))
    rows = rows.with_columns(pl.col("position").replace({"FB": "RB", "HB": "RB"}))
    for col in ("years_exp", "entry_year", "birth_date"):
        if col not in rows.columns:
            rows = rows.with_columns(pl.lit(None).alias(col))
    return (
        rows.filter(pl.col("gsis_id").is_not_null() & pl.col("position").is_in(POSITIONS))
        .sort("week", "team")
        .unique(subset=["gsis_id"], keep="last", maintain_order=True)
        .select(
            pl.col("gsis_id").alias("player_id"),
            "position",
            "team",
            pl.col("full_name").alias("player_name"),
            pl.col("season").cast(pl.Int32),
            pl.lit(cutoff).cast(pl.Int32).alias("cutoff_week"),
            pl.col("years_exp").cast(pl.Float64),
            pl.col("entry_year").cast(pl.Int32),
            pl.col("birth_date")
            .cast(pl.String)
            .str.slice(0, 4)
            .cast(pl.Int32, strict=False)
            .alias("birth_year"),
        )
    )


def snapshots(panel, schedule, rosters, seasons, cutoffs) -> pl.DataFrame:
    counts = schedule.group_by("season", "team").agg(pl.len().alias("team_games"))
    blocks = []
    for season in seasons:
        history = panel.filter(pl.col("season") == season)
        for cutoff in cutoffs:
            block = roster_at_cutoff(rosters, season, cutoff)
            remaining = (
                schedule.filter((pl.col("season") == season) & (pl.col("week") > cutoff))
                .group_by("team")
                .agg(pl.len().alias("remaining_team_games"))
            )
            block = block.join(remaining, on="team", how="inner")
            labels = (
                history.filter(pl.col("week") > cutoff)
                .group_by("player_id")
                .agg(pl.col("points").sum().alias("ros_points"))
            )
            block = block.join(labels, on="player_id", how="left").with_columns(
                pl.col("ros_points").fill_null(0.0)
            )
            blocks.append(block)
    if not blocks:
        raise ValueError("no ROS cutoff snapshots")
    frame = pl.concat(blocks, how="diagonal_relaxed").join(
        counts.rename({"team_games": "team_season_games"}), on=["season", "team"]
    )
    return add_snapshot_features(frame, panel, schedule, counts).sort(
        "season", "cutoff_week", "position", "player_id"
    )
