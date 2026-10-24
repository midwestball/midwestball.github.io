"""Retrain four ROS forests and export only five quantiles and the draw mean."""

from __future__ import annotations

import numpy as np
import polars as pl

from .config import CUTOFF_WEEKS, POSITIONS
from .crps_forest import ROSForest
from .data import load_inputs, snapshots

MODEL_VERSION = "ros-crps-forest-f0-v1"
LEVELS = (0.05, 0.25, 0.5, 0.75, 0.95)


def project_frames(train, target, *, seed=0, n_draws=10_000, params=None):
    if train.is_empty() or target.is_empty():
        raise ValueError("ROS requires training and forecast snapshots")
    if train["season"].max() >= target["season"].min():
        raise ValueError("ROS training seasons must precede the forecast season")
    rng = np.random.default_rng(seed)
    entities = []
    for position in POSITIONS:
        tr = train.filter(pl.col("position") == position)
        te = target.filter(pl.col("position") == position)
        if tr.is_empty() or te.is_empty():
            raise ValueError(f"missing ROS position: {position}")
        model = ROSForest()
        if params:
            model.params = {**model.params, **params}
        fitted = model.fit(tr)  # Always a fresh fit, never a cached prior-week model.
        draws = np.maximum(fitted.predict_samples(te, n_draws=n_draws, rng=rng), 0)
        if not np.isfinite(draws).all():
            raise ValueError(f"non-finite ROS draws: {position}")
        quantiles = np.quantile(draws, LEVELS, axis=1)
        for i, row in enumerate(te.iter_rows(named=True)):
            entities.append(
                {
                    "playerId": row["player_id"],
                    "name": row["player_name"],
                    "position": position,
                    "team": row["team"],
                    "remainingTeamGames": row["remaining_team_games"],
                    "mean": round(float(draws[i].mean()), 2),
                    "quantiles": [round(float(x), 2) for x in quantiles[:, i]],
                }
            )
    return sorted(entities, key=lambda e: e["playerId"])


def generate_ros_forecasts(season, cutoff_week, *, seed=0, refresh=False):
    if not 0 <= cutoff_week < 18:
        raise ValueError("ROS cutoff must precede the end of the regular season")
    panel, schedule, rosters, sources = load_inputs(season, refresh=refresh)
    train = snapshots(panel, schedule, rosters, range(2016, season), CUTOFF_WEEKS)
    # Remove future player rows entirely from live feature construction.
    known_panel = panel.filter((pl.col("season") < season) | (pl.col("week") <= cutoff_week))
    target = snapshots(known_panel, schedule, rosters, [season], [cutoff_week])
    entities = project_frames(train, target, seed=seed)
    return {
        "schemaVersion": 1,
        "kind": "ros",
        "season": season,
        "cutoffWeek": cutoff_week,
        "modelVersion": MODEL_VERSION,
        "scoringProfile": "ppr-v1",
        "quantileLevels": list(LEVELS),
        "entities": entities,
        "methodology": "Remaining regular-season points; QB/RB/WR/TE; current injury news is not an input. Intervals can be conservative. Trade values sum individual medians, not a package median or win probability.",
    }, {
        "modelVersion": MODEL_VERSION,
        "mode": "retrain",
        "seed": seed,
        "trainSeasons": [2016, season - 1],
        "trainRows": train.height,
        "drawCount": 10_000,
        "cutoffOnTrainingGrid": cutoff_week in CUTOFF_WEEKS,
        "sources": sources,
    }
