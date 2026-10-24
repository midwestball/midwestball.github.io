"""Cutoff-safe feature construction for ROS snapshots (§3.4, §3.5).

Two families, both strictly knowable at the cutoff:

* current season through the cutoff, from recorded player-weeks;
* completed prior seasons (1-3 back), from recorded player-weeks.

Missed games enter rate denominators (points per team game) but not the EWMA /
volatility form statistics, which use recorded active games.  Missingness is
preserved as null with explicit indicators for the important families; nothing
is imputed to zero.
"""

from __future__ import annotations

import polars as pl

from . import config as C

# Columns fed to the tabular models (identity + horizon + current + prior).
IDENTITY_FEATURES: tuple[str, ...] = (
    "position",
    "cutoff_week",
    "season",
    "team",
    "remaining_team_games",
    "team_games_elapsed",
    "team_season_games",
    "years_exp",
    "age",
    "is_rookie",
    "team_changed_from_prior_season",
)
# ``depth_chart_rank`` is kept in the snapshot but is NOT a model feature: the
# 2025 depth file uses a different schema, so the column is null for every 2025
# row.  A feature whose availability changes by season breaks holdout routing
# (LightGBM learned "missing depth -> low value" and collapsed 2025 predictions).
# Reintroduce behind an ablation once a schema-stable depth source exists (§3.4).

CURRENT_FEATURES: tuple[str, ...] = (
    "cur_games_active",
    "cur_points_total",
    "cur_points_mean",
    "cur_points_std",
    "cur_points_last",
    "cur_points_ewma_short",
    "cur_points_ewma_med",
    "cur_points_last16",
    "cur_points_per_team_game",
    "cur_points_per_active_game",
    "cur_zero_game_freq",
    "cur_snaps_mean",
    "cur_snap_pct_mean",
    "cur_targets_per_team_game",
    "cur_carries_per_team_game",
    "cur_attempts_per_team_game",
    "cur_target_share_mean",
    "cur_air_yards_share_mean",
    "cur_wopr_mean",
    "cur_trend",
)

PRIOR_FEATURES: tuple[str, ...] = tuple(
    f"prior{w}_{name}"
    for w in (1, 2, 3)
    for name in (
        "games_active",
        "points_total",
        "points_per_team_game",
        "points_per_active_game",
        "snap_pct_mean",
        "targets_per_team_game",
        "carries_per_team_game",
        "attempts_per_team_game",
        "target_share_mean",
    )
) + ("prior_ppg_weighted",)

MISSING_INDICATORS: tuple[str, ...] = ("cur_missing", "prior_missing")

FEATURE_COLUMNS: tuple[str, ...] = (
    IDENTITY_FEATURES + CURRENT_FEATURES + PRIOR_FEATURES + MISSING_INDICATORS
)

CATEGORICAL_FEATURES: tuple[str, ...] = ("position", "team")

_PRIOR_RAW = (
    "games_active",
    "points_total",
    "points_per_team_game",
    "points_per_active_game",
    "snap_pct_mean",
    "targets_per_team_game",
    "carries_per_team_game",
    "attempts_per_team_game",
    "target_share_mean",
)

_PRIOR_WEIGHTS = {1: 0.5, 2: 0.3, 3: 0.2}


def _safe_div(num: pl.Expr, den: pl.Expr) -> pl.Expr:
    return pl.when(den > 0).then(num / den).otherwise(None)


def _current_season_features(snap: pl.DataFrame, panel: pl.DataFrame) -> pl.DataFrame:
    cur_cols = [
        "player_id",
        "season",
        "week",
        "points",
        "active",
        "offense_snaps",
        "offense_snap_pct",
        "targets",
        "carries",
        "attempts",
        "target_share",
        "air_yards_share",
        "wopr",
        "points_ewma_short",
        "points_ewma_med",
    ]
    cur = (
        snap.select("snapshot_id", "player_id", "season", "cutoff_week")
        .join(panel.select(cur_cols), on=["player_id", "season"], how="inner")
        .filter(pl.col("week") <= pl.col("cutoff_week"))
    )
    agg = cur.group_by("snapshot_id").agg(
        pl.col("active").sum().alias("cur_games_active"),
        pl.col("points").sum().alias("cur_points_total"),
        pl.col("points").mean().alias("cur_points_mean"),
        pl.col("points").std().alias("cur_points_std"),
        pl.col("points").sort_by("week").last().alias("cur_points_last"),
        pl.col("points_ewma_short").sort_by("week").last().alias("cur_points_ewma_short"),
        pl.col("points_ewma_med").sort_by("week").last().alias("cur_points_ewma_med"),
        pl.col("points").sort_by("week").tail(16).mean().alias("cur_points_last16"),
        pl.col("offense_snaps").mean().alias("cur_snaps_mean"),
        pl.col("offense_snap_pct").mean().alias("cur_snap_pct_mean"),
        pl.col("targets").sum().alias("cur_targets_total"),
        pl.col("carries").sum().alias("cur_carries_total"),
        pl.col("attempts").sum().alias("cur_attempts_total"),
        pl.col("target_share").mean().alias("cur_target_share_mean"),
        pl.col("air_yards_share").mean().alias("cur_air_yards_share_mean"),
        pl.col("wopr").mean().alias("cur_wopr_mean"),
    )
    snap = snap.join(agg, on="snapshot_id", how="left")
    elapsed = pl.col("team_games_elapsed")
    return snap.with_columns(
        _safe_div(pl.col("cur_points_total"), elapsed).alias("cur_points_per_team_game"),
        _safe_div(pl.col("cur_points_total"), pl.col("cur_games_active")).alias(
            "cur_points_per_active_game"
        ),
        (1 - _safe_div(pl.col("cur_games_active"), elapsed)).alias("cur_zero_game_freq"),
        _safe_div(pl.col("cur_targets_total"), elapsed).alias("cur_targets_per_team_game"),
        _safe_div(pl.col("cur_carries_total"), elapsed).alias("cur_carries_per_team_game"),
        _safe_div(pl.col("cur_attempts_total"), elapsed).alias("cur_attempts_per_team_game"),
        (pl.col("cur_points_ewma_short") - pl.col("cur_points_ewma_med")).alias("cur_trend"),
    )


def _prior_season_features(
    snap: pl.DataFrame, panel: pl.DataFrame, tg_counts: pl.DataFrame
) -> pl.DataFrame:
    prior = panel.group_by("player_id", "season").agg(
        pl.col("points").sum().alias("p_points_total"),
        pl.col("active").sum().alias("p_games_active"),
        pl.col("offense_snap_pct").mean().alias("p_snap_pct_mean"),
        pl.col("targets").sum().alias("p_targets_total"),
        pl.col("carries").sum().alias("p_carries_total"),
        pl.col("attempts").sum().alias("p_attempts_total"),
        pl.col("target_share").mean().alias("p_target_share_mean"),
        pl.col("air_yards_share").mean().alias("p_air_yards_share_mean"),
        pl.col("team").sort_by("week").last().alias("p_team"),
    )
    tg = tg_counts.rename({"season": "_p_season", "team": "_p_team", "team_games": "p_team_games"})
    prior = prior.rename({"season": "_p_season", "p_team": "_p_team"}).join(
        tg, on=["_p_team", "_p_season"], how="left"
    )
    prior = prior.with_columns(
        _safe_div(pl.col("p_points_total"), pl.col("p_team_games")).alias("p_points_per_team_game"),
        _safe_div(pl.col("p_points_total"), pl.col("p_games_active")).alias(
            "p_points_per_active_game"
        ),
        _safe_div(pl.col("p_targets_total"), pl.col("p_team_games")).alias(
            "p_targets_per_team_game"
        ),
        _safe_div(pl.col("p_carries_total"), pl.col("p_team_games")).alias(
            "p_carries_per_team_game"
        ),
        _safe_div(pl.col("p_attempts_total"), pl.col("p_team_games")).alias(
            "p_attempts_per_team_game"
        ),
    )

    snap = snap.with_columns((pl.col("season") - 1).alias("_prior_season"))
    block1 = prior.select(
        ["player_id", "_p_season", pl.col("_p_team").alias("prior1_team")]
        + [pl.col(f"p_{name}").alias(f"prior1_{name}") for name in _PRIOR_RAW]
    )
    snap = snap.join(
        block1,
        left_on=["player_id", "_prior_season"],
        right_on=["player_id", "_p_season"],
        how="left",
    )

    for w in (2, 3):
        snap = snap.with_columns((pl.col("season") - w).alias("_prior_season"))
        block = prior.select(
            ["player_id", "_p_season"]
            + [pl.col(f"p_{name}").alias(f"prior{w}_{name}") for name in _PRIOR_RAW]
        )
        snap = snap.join(
            block,
            left_on=["player_id", "_prior_season"],
            right_on=["player_id", "_p_season"],
            how="left",
        )
    snap = snap.drop("_prior_season")

    numerator = None
    denominator = None
    for w, weight in _PRIOR_WEIGHTS.items():
        col = pl.col(f"prior{w}_points_per_team_game")
        numerator = (
            weight * col.fill_null(0.0)
            if numerator is None
            else numerator + weight * col.fill_null(0.0)
        )
        present = weight * col.is_not_null().cast(pl.Float64)
        denominator = present if denominator is None else denominator + present
    snap = snap.with_columns(_safe_div(numerator, denominator).alias("prior_ppg_weighted"))

    team_changed = pl.col("prior1_team").is_not_null() & (pl.col("prior1_team") != pl.col("team"))
    return snap.with_columns(team_changed.alias("team_changed_from_prior_season"))


def add_snapshot_features(
    snapshots: pl.DataFrame,
    panel: pl.DataFrame,
    team_schedule: pl.DataFrame,
    tg_counts: pl.DataFrame,
) -> pl.DataFrame:
    """Attach the Phase-A feature set to snapshot rows."""
    snap = snapshots.with_row_index("snapshot_id")
    snap = snap.with_columns(
        (pl.col("team_season_games") - pl.col("remaining_team_games")).alias("team_games_elapsed"),
        (pl.col("season") - pl.col("birth_year")).alias("age"),
        pl.coalesce([pl.col("years_exp"), pl.col("season") - pl.col("entry_year")]).alias(
            "years_exp"
        ),
    )
    snap = snap.with_columns(
        pl.coalesce(
            [
                pl.when(pl.col("years_exp") == 0).then(True),
                (pl.col("entry_year") == pl.col("season")),
            ]
        )
        .fill_null(False)
        .alias("is_rookie"),
    )
    snap = _current_season_features(snap, panel)
    snap = _prior_season_features(snap, panel, tg_counts)
    snap = snap.with_columns(
        pl.col("cur_games_active").is_null().alias("cur_missing"),
        pl.col("prior1_games_active").is_null().alias("prior_missing"),
    )
    for col in FEATURE_COLUMNS:
        if col not in snap.columns:
            snap = snap.with_columns(pl.lit(None).alias(col))
    return snap
