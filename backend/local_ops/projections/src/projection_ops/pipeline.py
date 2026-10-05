"""Snapshot orchestration. Live model input and deterministic no-network fixtures share one builder."""

from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
import hashlib, json, shutil
import numpy as np
from .config import SETTINGS, SCORING_DESCRIPTIONS, MODEL_STATUS, POSITIONS
from .contracts import (
    canonical_bytes,
    object_name,
    sha256_bytes,
    validate_snapshot,
    verify_schema_copy,
)
from .distribution import DrawSeries, build_distributions

MODEL_VERSION = "crps-forest-ppr-v1"


def _utc(value: datetime | None = None) -> datetime:
    out = value or datetime.now(timezone.utc)
    if out.tzinfo is None:
        out = out.replace(tzinfo=timezone.utc)
    return out.astimezone(timezone.utc).replace(microsecond=0)


def _snapshot_id(generated: datetime, season: int, week: int, entities: list[dict]) -> str:
    identity = [
        (x["entityKey"], x["position"], float(np.mean(x["draws"])), len(x["draws"]))
        for x in entities
    ]
    suffix = hashlib.sha256(
        canonical_bytes(
            {"season": season, "week": week, "model": MODEL_VERSION, "entities": identity}
        )
    ).hexdigest()[:8]
    return generated.strftime("%Y-%m-%dT%H%M%SZ-") + suffix


def fixture_entities(seed: int = 20260929, n_draws: int = 10000) -> list[dict]:
    rng = np.random.default_rng(seed)
    out = []
    specs = [
        ("QB", "00-fixture-qb", "Fixture QB", "CHI", "GB", 19, 6, None),
        ("RB", "00-fixture-rb", "Fixture RB", "DET", "MIN", 14, 6, None),
        ("WR", "00-fixture-wr", "Fixture WR", "GB", "CHI", 13, 7, None),
        ("TE", "00-fixture-te", "Fixture TE", "MIN", "DET", 9, 5, None),
        ("K", "00-fixture-k", "Fixture K", "KC", "LV", 8, 3, 0),
        ("DST", "BUF_DST", "BUF DST", "BUF", "MIA", 7, 4, -4),
    ]
    for pos, key, name, team, opp, mu, sd, wall in specs:
        draws = rng.normal(mu, sd, n_draws)
        if wall is not None:
            draws = np.maximum(draws, wall)
        out.append(
            {
                "entityKey": key,
                "entityType": "defense" if pos == "DST" else "player",
                "playerId": None if pos == "DST" else key,
                "name": name,
                "position": pos,
                "team": team,
                "opponent": opp,
                "availability": "ACT",
                "draws": draws.tolist(),
            }
        )
    return out


def build_snapshot(
    *,
    season: int,
    week: int,
    trained_through_week: int,
    entities: list[dict],
    generated_at: datetime | None = None,
    epsilon: float = 1e-5,
    minimum_draws: int = 10000,
) -> Path:
    verify_schema_copy()
    generated = _utc(generated_at)
    if not 1 <= week <= 22 or not 0 <= trained_through_week < week:
        raise ValueError("trained-through week must precede target week")
    positions = {x.get("position") for x in entities}
    if positions != set(POSITIONS):
        raise ValueError(f"snapshot must include all six positions; got {sorted(positions)}")
    keys = [x["entityKey"] for x in entities]
    if len(keys) != len(set(keys)):
        raise ValueError("duplicate entityKey")
    snapshot_id = _snapshot_id(generated, season, week, entities)
    draw_series = [
        DrawSeries(x["entityKey"], x["position"], np.asarray(x["draws"], float)) for x in entities
    ]
    grid, dists = build_distributions(draw_series, epsilon=epsilon, minimum_draws=minimum_draws)
    target = SETTINGS.artifacts / "public" / str(season) / f"w{week}" / snapshot_id
    SETTINGS.assert_local_write(target)
    tmp = target.parent / f".tmp-{snapshot_id}"
    if target.exists():
        return target
    if tmp.exists():
        shutil.rmtree(tmp)
    (tmp / "entities").mkdir(parents=True)
    index_entities = []
    file_inventory = []
    diagnostics = {}
    for item in sorted(entities, key=lambda x: x["entityKey"]):
        dist = dists[item["entityKey"]]
        rel = "entities/" + object_name(item["entityKey"])
        public = {
            "schemaVersion": 1,
            "snapshotId": snapshot_id,
            "entityKey": item["entityKey"],
            "expectedPoints": dist.expected_points,
            "yMax": dist.y_max,
            "pdf": dist.pdf,
            "cdf": dist.cdf,
            "lowerBound": dist.lower_bound,
            "bandwidth": dist.bandwidth,
            "nModelDraws": dist.n_model_draws,
        }
        data = canonical_bytes(public)
        (tmp / rel).write_bytes(data)
        file_inventory.append({"path": rel, "bytes": len(data), "sha256": sha256_bytes(data)})
        # Defense entities carry no official roster status, so `availability` is omitted rather
        # than published as null: the contract types it as a string when present.
        row = {
            k: item[k]
            for k in ("entityKey", "entityType", "playerId", "name", "position", "team", "opponent")
            if k in item
        }
        if item.get("availability") is not None:
            row["availability"] = item["availability"]
        index_entities.append(row | {"expectedPoints": dist.expected_points, "path": rel})
        diagnostics[item["entityKey"]] = {
            "retainedMass": dist.retained_mass,
            "drawMean": dist.expected_points,
            "kdeMean": dist.kde_mean,
            "meanGap": dist.kde_mean - dist.expected_points,
        }
    generated_text = generated.isoformat().replace("+00:00", "Z")
    index = {
        "schemaVersion": 1,
        "season": season,
        "week": week,
        "snapshotId": snapshot_id,
        "generatedAt": generated_text,
        "trainedThrough": {"season": season, "week": trained_through_week},
        "modelFamily": "crps_forest",
        "modelVersion": MODEL_VERSION,
        "scoringProfile": "ppr-v1",
        "scoringDescriptions": SCORING_DESCRIPTIONS,
        "positionModelStatus": MODEL_STATUS,
        "manifestPath": "manifest.json",
        "xGrid": grid,
        "entities": index_entities,
    }
    data = canonical_bytes(index)
    (tmp / "index.json").write_bytes(data)
    file_inventory.append({"path": "index.json", "bytes": len(data), "sha256": sha256_bytes(data)})
    manifest = {
        "schemaVersion": 1,
        "snapshotId": snapshot_id,
        "generatedAt": generated_text,
        "model": {"family": "crps_forest", "version": MODEL_VERSION, "seed": 20260929},
        "distribution": {
            "drawCount": minimum_draws,
            "epsilonPerTail": epsilon,
            "bandwidth": "max(0.25, 1.06 * sample_sd * n^-1/5)",
            "boundaryRule": {"K": 0, "DST": -4},
            "gridRule": "shared; hard-wall knots; max spacing <= min bandwidth / 4",
            "precision": "10 significant digits",
        },
        "diagnostics": diagnostics,
        "scoringDescriptions": SCORING_DESCRIPTIONS,
        "knownCaveats": [
            "TE validation was conservatively calibrated.",
            "QB has weaker evidence in a small high-projection segment.",
            "K and DST are initial CRPS-forest deployments.",
        ],
        "contractSha256": verify_schema_copy(),
        "files": sorted(file_inventory, key=lambda x: x["path"]),
        "validation": {
            "passed": True,
            "warnings": ["Fixture/offline snapshots are not production forecasts."]
            if all(str(x["entityKey"]).startswith(("00-fixture", "BUF_DST")) for x in entities)
            else [],
        },
    }
    (tmp / "manifest.json").write_bytes(canonical_bytes(manifest))
    validate_snapshot(tmp)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp.rename(target)
    report = SETTINGS.artifacts / "reports" / str(season) / f"w{week}"
    report.mkdir(parents=True, exist_ok=True)
    (report / f"{snapshot_id}.json").write_bytes(canonical_bytes(validate_snapshot(target)))
    return target


def pointer_for(directory: Path) -> dict:
    index = json.loads((directory / "index.json").read_text())
    base = f"projections/{index['season']}/w{index['week']}/{index['snapshotId']}"
    return {
        "schemaVersion": 1,
        "season": index["season"],
        "week": index["week"],
        "snapshotId": index["snapshotId"],
        "indexPath": base + "/index.json",
        "manifestPath": base + "/manifest.json",
        "generatedAt": index["generatedAt"],
    }
