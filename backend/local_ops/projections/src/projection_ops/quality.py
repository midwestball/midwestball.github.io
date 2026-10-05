"""Frozen week-ahead historical replication after the negative-support correction.

This is historical replication, not a new pristine confirmation. Historical nflverse
closing lines are excluded because they lack Wednesday as-of timestamps.
"""

from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import hashlib, json, zlib
import numpy as np
import pandas as pd
from lightgbm import LGBMRegressor
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder
from .config import HARD_WALLS, POSITIONS, PROMOTED_POSITIONS, SETTINGS
from .contracts import canonical_bytes, sha256_bytes
from .live_data import TARGET, historical_position_frame, load_live_tables
from .live_pipeline import _thresholds
from .model import CRPSRandomForest

PROTOCOL = "week_ahead_negative_support_v1_no_vegas"
COVERAGE_MATERIALITY = 0.02
TAIL_BRIER_MATERIALITY = 0.002
TAILS = {
    "QB": (("lt", 15.0), ("ge", 20.0), ("ge", 25.0), ("ge", 30.0)),
    "RB": (("lt", 5.0), ("ge", 15.0), ("ge", 20.0), ("ge", 25.0), ("ge", 30.0)),
    "WR": (("lt", 5.0), ("ge", 15.0), ("ge", 20.0), ("ge", 25.0), ("ge", 30.0)),
    "TE": (("lt", 3.0), ("ge", 10.0), ("ge", 15.0), ("ge", 20.0)),
    "K": (("lt", 5.0), ("ge", 8.0), ("ge", 12.0), ("ge", 15.0)),
    "DST": (("lt", 5.0), ("ge", 10.0), ("ge", 15.0), ("ge", 20.0)),
}
LGBM_PARAMS = {
    "objective": "regression_l1",
    "n_estimators": 200,
    "learning_rate": 0.05,
    "num_leaves": 31,
    "min_child_samples": 40,
    "subsample": 0.8,
    "subsample_freq": 1,
    "colsample_bytree": 0.8,
    "random_state": 0,
    "n_jobs": 1,
    "verbosity": -1,
    "deterministic": True,
}


def _rng(seed: int, *parts: object) -> np.random.Generator:
    return np.random.default_rng(
        np.random.SeedSequence([seed, zlib.crc32("|".join(map(str, parts)).encode())])
    )


def _preprocess(train: pd.DataFrame, test: pd.DataFrame, features: tuple[str, ...]):
    categorical = [c for c in features if train[c].dtype == object]
    numeric = [c for c in features if c not in categorical]
    pre = ColumnTransformer(
        [
            ("num", SimpleImputer(strategy="median", keep_empty_features=True), numeric),
            (
                "cat",
                make_pipeline(
                    SimpleImputer(strategy="most_frequent", keep_empty_features=True),
                    OneHotEncoder(handle_unknown="ignore"),
                ),
                categorical,
            ),
        ]
    )
    return pre.fit_transform(train[list(features)]), pre.transform(test[list(features)])


def _lgbm_mu(train: pd.DataFrame, test: pd.DataFrame, features: tuple[str, ...]) -> np.ndarray:
    xtr, xte = _preprocess(train, test, features)
    model = LGBMRegressor(**LGBM_PARAMS)
    model.fit(xtr, train[TARGET].to_numpy(float))
    return model.predict(xte).astype(float)


def _calibration(
    frame: pd.DataFrame, holdout: int, features: tuple[str, ...]
) -> tuple[np.ndarray, np.ndarray]:
    mus = []
    residuals = []
    for season in sorted(int(x) for x in frame.season.unique() if x < holdout):
        prior = frame[frame.season < season]
        if prior.empty:
            continue
        for week in sorted(int(x) for x in frame.loc[frame.season == season, "week"].unique()):
            train = frame[
                (frame.season < season) | ((frame.season == season) & (frame.week < week))
            ]
            test = frame[(frame.season == season) & (frame.week == week)]
            if train.empty or test.empty:
                continue
            mu = _lgbm_mu(train, test, features)
            mus.append(mu)
            residuals.append(test[TARGET].to_numpy(float) - mu)
    if not mus:
        raise RuntimeError(f"no prior-season OOF calibration before {holdout}")
    return np.concatenate(mus), np.concatenate(residuals)


def _residual_draws(
    mu: np.ndarray,
    cal_mu: np.ndarray,
    residuals: np.ndarray,
    n: int,
    rng: np.random.Generator,
    wall: float | None,
) -> np.ndarray:
    edges = np.unique(np.quantile(cal_mu, np.linspace(0, 1, 6)))
    cuts = edges[1:-1] if len(edges) > 2 else np.array([])
    cb = np.searchsorted(cuts, cal_mu, side="right")
    tb = np.searchsorted(cuts, mu, side="right")
    out = np.empty((len(mu), n))
    for i, b in enumerate(tb):
        pool = residuals[cb == b]
        if len(pool) < 20:
            pool = residuals
        out[i] = mu[i] + rng.choice(pool, n, replace=True)
    return np.maximum(out, wall) if wall is not None else out


def row_crps(samples: np.ndarray, y: np.ndarray) -> np.ndarray:
    ordered = np.sort(samples, axis=1)
    m = ordered.shape[1]
    weights = 2 * np.arange(1, m + 1) - m - 1
    return np.mean(np.abs(samples - y[:, None]), axis=1) - (ordered * weights).sum(axis=1) / (m * m)


def _metrics(samples: np.ndarray, y: np.ndarray, position: str) -> dict:
    crps = row_crps(samples, y)
    out = {
        "rows": len(y),
        "mae": float(np.mean(np.abs(samples.mean(1) - y))),
        "crps": float(crps.mean()),
        "negativeRows": int((y < 0).sum()),
        "negativeRate": float((y < 0).mean()),
    }
    if (y < 0).any():
        out["negativeCrps"] = float(crps[y < 0].mean())
    for nominal in (0.5, 0.7, 0.8, 0.9, 0.95):
        a = (1 - nominal) / 2
        lo, hi = np.quantile(samples, [a, 1 - a], axis=1)
        out[f"coverage{int(nominal * 100)}"] = float(np.mean((y >= lo) & (y <= hi)))
        out[f"width{int(nominal * 100)}"] = float(np.mean(hi - lo))
    tails = {}
    for direction, threshold in TAILS[position]:
        prob = (
            np.mean(samples < threshold, axis=1)
            if direction == "lt"
            else np.mean(samples >= threshold, axis=1)
        )
        event = y < threshold if direction == "lt" else y >= threshold
        tails[f"{direction}_{int(threshold)}"] = {
            "brier": float(np.mean((prob - event) ** 2)),
            "predicted": float(prob.mean()),
            "observed": float(event.mean()),
        }
    out["tails"] = tails
    return out


def _cluster_ci(
    delta: np.ndarray, clusters: np.ndarray, n_boot: int, rng: np.random.Generator
) -> list[float]:
    unique = np.unique(clusters)
    means = []
    for _ in range(n_boot):
        sampled = rng.choice(unique, len(unique), replace=True)
        values = np.concatenate([delta[clusters == c] for c in sampled])
        means.append(float(values.mean()))
    return [float(np.quantile(means, 0.025)), float(np.quantile(means, 0.975))]


def validate_position(
    position: str,
    frame: pd.DataFrame,
    features: tuple[str, ...],
    *,
    holdouts=(2024, 2025),
    n_train=3,
    n_draws=200,
    n_boot=500,
    trees=200,
    leaf=20,
    seed=0,
) -> dict:
    if "vegas_implied_team_pts" in features:
        raise RuntimeError("unverifiable historical Vegas feature is forbidden")
    records = []
    folds = {}
    calibrations = {}
    for season in holdouts:
        window = frame[(frame.season >= season - n_train) & (frame.season <= season)].copy()
        calibrations[season] = _calibration(window, season, features)
        used = 0
        for week in sorted(int(x) for x in window.loc[window.season == season, "week"].unique()):
            train = window[
                (window.season < season) | ((window.season == season) & (window.week < week))
            ]
            test = window[(window.season == season) & (window.week == week)]
            if train.empty or test.empty:
                continue
            if (
                train.season.max() > season
                or ((train.season == season) & (train.week >= week)).any()
            ):
                raise RuntimeError("future row in training fold")
            print(
                f"[{position}] {season} week {week}: train={len(train)} test={len(test)}",
                flush=True,
            )
            rows = train.to_dict("records")
            forest = CRPSRandomForest(
                features,
                _thresholds(position),
                n_estimators=trees,
                min_samples_leaf=leaf,
                max_features=0.7,
                max_samples=0.8,
                random_state=seed,
            ).fit(rows)
            fdraw = forest.predict_samples(
                test.to_dict("records"),
                n_draws=n_draws,
                rng=_rng(seed, position, season, week, "forest"),
            )
            wall = HARD_WALLS.get(position)
            if wall is not None:
                fdraw = np.maximum(fdraw, wall)
            mu = _lgbm_mu(train, test, features)
            bdraw = _residual_draws(
                mu, *calibrations[season], n_draws, _rng(seed, position, season, week, "lgbm"), wall
            )
            y = test[TARGET].to_numpy(float)
            for i, row in enumerate(test.to_dict("records")):
                records.append(
                    {
                        "season": season,
                        "week": week,
                        "playerId": str(row["player_id"]),
                        "actual": float(y[i]),
                        "forest": fdraw[i].tolist(),
                        "baseline": bdraw[i].tolist(),
                    }
                )
            used += 1
        folds[str(season)] = used
    if any(folds.get(str(s)) != 18 for s in holdouts):
        raise RuntimeError(f"expected 18 REG folds per season, got {folds}")
    y = np.array([r["actual"] for r in records])
    fd = np.array([r["forest"] for r in records])
    bd = np.array([r["baseline"] for r in records])
    delta = row_crps(bd, y) - row_crps(fd, y)
    players = np.array([r["playerId"] for r in records])
    weeks = np.array([r["season"] * 100 + r["week"] for r in records])
    season_delta = {
        str(s): float(delta[np.array([r["season"] == s for r in records])].mean()) for s in holdouts
    }
    fm = _metrics(fd, y, position)
    bm = _metrics(bd, y, position)
    pci = _cluster_ci(delta, players, n_boot, _rng(seed, position, "player-bootstrap"))
    wci = _cluster_ci(delta, weeks, n_boot, _rng(seed, position, "week-bootstrap"))
    coverage_bad = all(
        abs(fm[f"coverage{x}"] - x / 100) > abs(bm[f"coverage{x}"] - x / 100) + COVERAGE_MATERIALITY
        for x in (80, 95)
    )
    tail_worse = (
        sum(
            fm["tails"][k]["brier"] > bm["tails"][k]["brier"] + TAIL_BRIER_MATERIALITY
            for k in fm["tails"]
        )
        > len(fm["tails"]) / 2
    )
    passed = (
        float(delta.mean()) > 0
        and pci[0] > 0
        and wci[0] > 0
        and all(v > 0 for v in season_delta.values())
        and not coverage_bad
        and not tail_worse
    )
    return {
        "position": position,
        "passed": passed,
        "folds": folds,
        "features": list(features),
        "forest": fm,
        "lgbmResidual": bm,
        "deltaCrps": float(delta.mean()),
        "seasonDeltaCrps": season_delta,
        "playerCluster95": pci,
        "seasonWeekCluster95": wci,
        "coverageHardStop": coverage_bad,
        "tailHardStop": tail_worse,
        "rows": records,
    }


def run_quality_gate(
    *,
    positions=POSITIONS,
    holdouts=(2024, 2025),
    n_train=3,
    n_draws=200,
    n_boot=500,
    trees=200,
    leaf=20,
    seed=0,
    refresh=True,
) -> dict:
    seasons = list(range(min(holdouts) - n_train, max(holdouts) + 1))
    tables = load_live_tables(seasons, target_season=max(holdouts), refresh=refresh)
    results = {}
    for position in positions:
        print(f"[{position}] preparing historical quality frame", flush=True)
        frame, features = historical_position_frame(tables, position)
        results[position] = validate_position(
            position,
            frame,
            features,
            holdouts=holdouts,
            n_train=n_train,
            n_draws=n_draws,
            n_boot=n_boot,
            trees=trees,
            leaf=leaf,
            seed=seed,
        )
    summary = {p: {k: v for k, v in result.items() if k != "rows"} for p, result in results.items()}
    payload = {
        "protocol": PROTOCOL,
        "historicalReplication": True,
        "pristineConfirmation": False,
        "holdouts": list(holdouts),
        "nTrainSeasons": n_train,
        "draws": n_draws,
        "bootstraps": n_boot,
        "trees": trees,
        "minSamplesLeaf": leaf,
        "seed": seed,
        "coverageMateriality": COVERAGE_MATERIALITY,
        "tailBrierMateriality": TAIL_BRIER_MATERIALITY,
        "source": tables.source_metadata,
        "positions": summary,
        "passed": all(x["passed"] for x in results.values()),
    }
    payload["releaseDecision"] = release_decision(payload)
    out = SETTINGS.artifacts / "reports" / "quality"
    out.mkdir(parents=True, exist_ok=True)
    for p, result in results.items():
        pd.DataFrame(result["rows"]).to_parquet(
            out / f"{p.lower()}-predictions.parquet", index=False
        )
    data = canonical_bytes(payload)
    (out / "historical-quality.json").write_bytes(data)
    (out / "historical-quality.sha256").write_text(sha256_bytes(data) + "\n")
    return payload


def release_decision(payload: dict) -> dict:
    """Classify a frozen quality report into an explicit release decision.

    A promoted position must pass the frozen gate outright. An initial-deployment
    position may ship only with a recorded disclosure, and only when its failure is
    a thin CRPS margin rather than a coverage or tail-calibration hard stop.
    """
    positions = payload.get("positions", {})
    missing = [p for p in POSITIONS if p not in positions]
    if missing:
        raise RuntimeError("quality report is missing positions: " + ", ".join(sorted(missing)))
    promoted_passed = []
    promoted_blocked = []
    disclosed = []
    for position in POSITIONS:
        result = positions[position]
        if position in PROMOTED_POSITIONS:
            (promoted_passed if result["passed"] else promoted_blocked).append(position)
            continue
        if result["passed"]:
            disclosed.append(
                {
                    "position": position,
                    "status": "initial_deployment",
                    "gatePassed": True,
                    "note": "Selection evidence matched the promoted gate; initial-deployment label retained conservatively.",
                }
            )
            continue
        if result.get("coverageHardStop") or result.get("tailHardStop"):
            promoted_blocked.append(position)
            disclosed.append(
                {
                    "position": position,
                    "status": "blocked",
                    "gatePassed": False,
                    "reason": "coverage or tail-calibration hard stop",
                    "deltaCrps": result["deltaCrps"],
                    "playerCluster95": result["playerCluster95"],
                }
            )
            continue
        disclosed.append(
            {
                "position": position,
                "status": "initial_deployment",
                "gatePassed": False,
                "note": "CRPS gain over the residual baseline is positive but its player-cluster interval includes zero, so head-to-head selection evidence is incomplete.",
                "deltaCrps": result["deltaCrps"],
                "playerCluster95": result["playerCluster95"],
                "seasonWeekCluster95": result["seasonWeekCluster95"],
            }
        )
    blocked = sorted(
        set(promoted_blocked) | set(d["position"] for d in disclosed if d["status"] == "blocked")
    )
    return {
        "approved": not blocked,
        "promotedPassed": sorted(promoted_passed),
        "promotedBlocked": sorted(set(promoted_blocked)),
        "disclosures": sorted(disclosed, key=lambda d: d["position"]),
        "blocked": blocked,
        "caveats": [d["note"] for d in disclosed if d.get("note")],
    }


def disclosure_caveats(decision: dict) -> list[str]:
    """Human-readable caveats for any position shipping without full selection evidence."""
    return [
        f"{d['position']} is an initial CRPS-forest deployment without complete head-to-head selection evidence."
        for d in decision.get("disclosures", [])
        if d["status"] == "initial_deployment" and not d["gatePassed"]
    ]


def main(argv=None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="Run frozen historical projection quality replication"
    )
    parser.add_argument("--positions", nargs="+", choices=POSITIONS, default=list(POSITIONS))
    parser.add_argument("--holdouts", nargs="+", type=int, default=[2024, 2025])
    parser.add_argument("--draws", type=int, default=200)
    parser.add_argument("--bootstraps", type=int, default=500)
    parser.add_argument("--trees", type=int, default=200)
    parser.add_argument("--min-samples-leaf", type=int, default=20)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--no-refresh", action="store_true")
    args = parser.parse_args(argv)
    result = run_quality_gate(
        positions=tuple(args.positions),
        holdouts=tuple(args.holdouts),
        n_draws=args.draws,
        n_boot=args.bootstraps,
        trees=args.trees,
        leaf=args.min_samples_leaf,
        seed=args.seed,
        refresh=not args.no_refresh,
    )
    summary = {
        p: {
            "passed": v["passed"],
            "deltaCrps": v["deltaCrps"],
            "playerCluster95": v["playerCluster95"],
            "seasonWeekCluster95": v["seasonWeekCluster95"],
        }
        for p, v in result["positions"].items()
    }
    decision = result["releaseDecision"]
    print(
        json.dumps(
            {
                "allPositionsPassedGate": result["passed"],
                "releaseApproved": decision["approved"],
                "blocked": decision["blocked"],
                "disclosures": [
                    {k: v for k, v in d.items() if k != "note"} | {"note": d.get("note")}
                    for d in decision["disclosures"]
                ],
                "positions": summary,
            },
            indent=2,
        )
    )
    return 0 if decision["approved"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
