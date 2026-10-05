"""Fit/reuse six live CRPS forests and persist private 10,000-draw artifacts."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any, Literal

import joblib
import numpy as np
import pandas as pd
import sklearn

from .config import HARD_WALLS, POSITIONS, SCORING_DESCRIPTIONS, SETTINGS
from .live_data import LiveTables, PreparedPosition, load_live_tables, prepare_position_data
from .model import CRPSRandomForest, FIT_SCHEMA_VERSION, FittedCRPSForest, training_fingerprint

MODEL_VERSION = "crps-forest-ppr-v1"
SOURCE_VERSION = "nflverse-live-v1"
DEFAULT_DRAWS = 10_000
ModelMode = Literal["auto", "retrain", "reuse"]


def _canonical_hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, default=str, separators=(",", ":"), allow_nan=True
        ).encode()
    ).hexdigest()


def _thresholds(position: str) -> tuple[float, ...]:
    # Zero is not a skill-position support assumption.  Negative outcomes are
    # both fitted and sampleable.  Only the two formula walls start at K=0/DST=-4.
    lower = 0 if position == "K" else -4 if position == "DST" else -20
    return tuple(float(x) for x in range(lower, 61))


def _paths(season: int, week: int, position: str) -> tuple[Path, Path]:
    root = SETTINGS.assert_local_write(
        SETTINGS.artifacts / "models" / str(season) / f"w{week}" / position.lower()
    )
    return root / "fit.joblib", root / "metadata.json"


def _atomic_joblib(value: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp.joblib")
    joblib.dump(value, tmp, compress=3)
    tmp.replace(path)


def _atomic_json(value: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp.json")
    tmp.write_text(
        json.dumps(value, sort_keys=True, indent=2, default=str) + "\n", encoding="utf-8"
    )
    tmp.replace(path)


def _spec(
    prepared: PreparedPosition, *, trees: int, min_samples_leaf: int, seed: int
) -> tuple[CRPSRandomForest, dict[str, Any], dict[str, Any]]:
    forest = CRPSRandomForest(
        prepared.feature_columns,
        thresholds=_thresholds(prepared.position),
        n_estimators=trees,
        min_samples_leaf=min_samples_leaf,
        max_features=0.7,
        max_samples=0.8,
        random_state=seed,
    )
    estimator_config = {
        k: getattr(forest, k)
        for k in (
            "thresholds",
            "n_estimators",
            "min_samples_leaf",
            "max_features",
            "max_samples",
            "random_state",
        )
    }
    rows = sorted(
        prepared.train_rows,
        key=lambda r: (int(r.get("season", 0)), int(r.get("week", 0)), str(r.get("player_id", ""))),
    )
    training_fp = training_fingerprint(rows, prepared.feature_columns, estimator_config)
    config = {
        "position": prepared.position,
        "modelVersion": MODEL_VERSION,
        "sourceVersion": SOURCE_VERSION,
        "features": list(prepared.feature_columns),
        "thresholds": list(forest.thresholds),
        "trees": trees,
        "minSamplesLeaf": min_samples_leaf,
        "maxFeatures": forest.max_features,
        "maxSamples": forest.max_samples,
        "seed": seed,
        "scoring": SCORING_DESCRIPTIONS[prepared.position],
    }
    compatibility = {
        "fitSchemaVersion": FIT_SCHEMA_VERSION,
        "sourceFingerprint": prepared.source_metadata["positionSourceFingerprint"],
        "modelVersion": MODEL_VERSION,
        "sklearnVersion": sklearn.__version__,
        "configFingerprint": _canonical_hash(config),
        "trainingFingerprint": training_fp,
        "featureFingerprint": _canonical_hash(list(prepared.feature_columns)),
    }
    return forest, config, compatibility


def _compatible(metadata: dict[str, Any], expected: dict[str, Any]) -> bool:
    return all(metadata.get(k) == v for k, v in expected.items())


def fit_position(
    prepared: PreparedPosition,
    *,
    season: int,
    week: int,
    mode: ModelMode = "auto",
    trees: int = 200,
    min_samples_leaf: int = 20,
    seed: int = 0,
) -> tuple[FittedCRPSForest, dict[str, Any]]:
    """Fit or safely reuse one forest; every compatibility dimension is exact."""
    if mode not in {"auto", "retrain", "reuse"}:
        raise ValueError("mode must be auto, retrain, or reuse")
    forest, config, expected = _spec(
        prepared, trees=trees, min_samples_leaf=min_samples_leaf, seed=seed
    )
    fit_path, meta_path = _paths(season, week, prepared.position)
    metadata = json.loads(meta_path.read_text()) if meta_path.exists() else {}
    can_reuse = fit_path.exists() and _compatible(metadata, expected)
    if mode == "reuse" and not can_reuse:
        raise RuntimeError(f"no compatible cached {prepared.position} fit")
    if mode != "retrain" and can_reuse:
        fitted = joblib.load(fit_path)
        object_ok = (
            isinstance(fitted, FittedCRPSForest)
            and fitted.fit_schema_version == FIT_SCHEMA_VERSION
            and fitted.sklearn_version == sklearn.__version__
            and fitted.fingerprint == expected["trainingFingerprint"]
            and tuple(fitted.feature_columns) == prepared.feature_columns
        )
        if not object_ok:
            if mode == "reuse":
                raise RuntimeError(f"cached {prepared.position} fit object is incompatible")
            can_reuse = False
    if not can_reuse or mode == "retrain":
        rows = sorted(
            prepared.train_rows,
            key=lambda r: (
                int(r.get("season", 0)),
                int(r.get("week", 0)),
                str(r.get("player_id", "")),
            ),
        )
        fitted = forest.fit(rows, target="fantasy_points")
        if fitted.fingerprint != expected["trainingFingerprint"]:
            raise RuntimeError("training fingerprint mismatch after fit")
        _atomic_joblib(fitted, fit_path)
        action = "retrained"
        metadata = {
            **expected,
            "position": prepared.position,
            "config": config,
            "trainRows": len(rows),
            "trainThrough": {"season": season, "week": week - 1},
            "createdAt": datetime.now(timezone.utc).isoformat(),
        }
        _atomic_json(metadata, meta_path)
    else:
        action = "reused_fit"
    return fitted, {**metadata, "action": action, "forecastRows": len(prepared.forecast_rows)}


def _entity(row: dict[str, Any], draws: np.ndarray, position: str) -> dict[str, Any]:
    key = str(row["player_id"])
    item = {
        "entityKey": key,
        "entityType": "defense" if position == "DST" else "player",
        "playerId": None if position == "DST" else key,
        "name": str(row.get("player_name") or key),
        "position": position,
        "team": str(row["team"]),
        "opponent": str(row["opponent"]),
        "draws": draws.tolist(),
    }
    availability = row.get("availability")
    if availability is not None and not pd.isna(availability):
        item["availability"] = str(availability)
    return item


def generate_live_forecasts(
    season: int,
    week: int,
    *,
    mode: ModelMode = "auto",
    refresh: bool = True,
    n_train_seasons: int = 3,
    n_draws: int = DEFAULT_DRAWS,
    trees: int = 200,
    min_samples_leaf: int = 20,
    seed: int = 0,
    prepared: dict[str, PreparedPosition] | None = None,
    tables: LiveTables | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Produce all six fitted forests and private seeded marginal draws.

    ``n_draws`` defaults to the production contract of 10,000.  A smaller
    explicit value is accepted only to keep focused unit tests cheap.
    """
    if n_draws < 1:
        raise ValueError("n_draws must be >= 1")
    if prepared is None and tables is None:
        seasons = list(range(season - n_train_seasons, season + 1))
        tables = load_live_tables(seasons, target_season=season, refresh=refresh)
    entities = []
    positions_meta = {}
    draw_root = SETTINGS.assert_local_write(SETTINGS.artifacts / "draws" / str(season) / f"w{week}")
    for pos_index, position in enumerate(POSITIONS):
        data = (prepared or {}).get(position) if prepared is not None else None
        data = data or prepare_position_data(
            season, week, position, n_train_seasons=n_train_seasons, refresh=False, tables=tables
        )
        fitted, metadata = fit_position(
            data,
            season=season,
            week=week,
            mode=mode,
            trees=trees,
            min_samples_leaf=min_samples_leaf,
            seed=seed,
        )
        samples = fitted.predict_samples(
            data.forecast_rows,
            n_draws=n_draws,
            rng=np.random.default_rng(np.random.SeedSequence([seed, pos_index])),
        )
        wall = HARD_WALLS.get(position)
        if wall is not None:
            samples = np.maximum(samples, wall)
        if not np.isfinite(samples).all():
            raise ValueError(f"non-finite {position} draws")
        draw_root.mkdir(parents=True, exist_ok=True)
        draw_path = draw_root / f"{position.lower()}.npz"
        tmp = draw_path.with_suffix(".tmp.npz")
        np.savez_compressed(
            tmp,
            draws=samples,
            entity_keys=np.asarray([str(x["player_id"]) for x in data.forecast_rows]),
        )
        tmp.replace(draw_path)
        entities.extend(
            _entity(row, samples[i], position) for i, row in enumerate(data.forecast_rows)
        )
        positions_meta[position] = {
            **metadata,
            "universe": data.universe,
            "drawRows": samples.shape[0],
            "drawCount": samples.shape[1],
            "drawSha256": hashlib.sha256(draw_path.read_bytes()).hexdigest(),
        }
    manifest = {
        "modelVersion": MODEL_VERSION,
        "sourceVersion": SOURCE_VERSION,
        "season": season,
        "week": week,
        "drawCount": n_draws,
        "seed": seed,
        "mode": mode,
        "refresh": refresh,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "positions": positions_meta,
        "rosterPolicy": "all scheduled roster entities with scoreable identity/team; availability preserved when supplied",
        "hardWalls": {"K": 0.0, "DST": -4.0},
        "historicalVegasFeatures": False,
        "sourceFingerprint": tables.source_metadata.get("sourceFingerprint")
        if tables is not None
        else None,
    }
    _atomic_json(manifest, draw_root / "manifest.json")
    return entities, manifest
