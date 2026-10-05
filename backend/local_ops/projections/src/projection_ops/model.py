"""Persistable non-parametric CRPS random forest and cache metadata."""

from __future__ import annotations
from dataclasses import dataclass
from typing import Any
import hashlib, json
import numpy as np
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder
import sklearn

FIT_SCHEMA_VERSION = 1


def training_fingerprint(
    rows: list[dict[str, Any]], features: tuple[str, ...], config: dict[str, Any]
) -> str:
    payload = {
        "rows": rows,
        "features": features,
        "config": config,
        "fitSchemaVersion": FIT_SCHEMA_VERSION,
        "sklearn": sklearn.__version__,
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, default=str, separators=(",", ":")).encode()
    ).hexdigest()


@dataclass
class FittedCRPSForest:
    feature_columns: tuple[str, ...]
    n_estimators: int
    preprocessor: Any
    forest: RandomForestRegressor
    outcomes: np.ndarray
    train_leaves: np.ndarray
    fingerprint: str
    sklearn_version: str = sklearn.__version__
    fit_schema_version: int = FIT_SCHEMA_VERSION

    def predict_samples(
        self, rows: list[dict[str, Any]], *, n_draws: int, rng: np.random.Generator
    ) -> np.ndarray:
        if n_draws < 1:
            raise ValueError("n_draws must be >= 1")
        import pandas as pd

        x = self.preprocessor.transform(pd.DataFrame(rows)[list(self.feature_columns)])
        leaves = self.forest.apply(x)
        selected = rng.integers(self.n_estimators, size=(len(rows), n_draws))
        draws = np.empty((len(rows), n_draws), dtype=float)
        for r in range(len(rows)):
            for tree in np.unique(selected[r]):
                mask = selected[r] == tree
                pool = self.outcomes[self.train_leaves[:, tree] == leaves[r, tree]]
                if not pool.size:
                    pool = self.outcomes
                draws[r, mask] = rng.choice(pool, size=int(mask.sum()), replace=True)
        return draws


@dataclass(frozen=True)
class CRPSRandomForest:
    feature_columns: tuple[str, ...]
    thresholds: tuple[float, ...]
    n_estimators: int = 200
    min_samples_leaf: int = 20
    max_features: float = 0.7
    max_samples: float = 0.8
    random_state: int = 0

    def fit(self, rows: list[dict[str, Any]], target: str = "fantasy_points") -> FittedCRPSForest:
        import pandas as pd

        frame = pd.DataFrame(rows)
        y = frame[target].to_numpy(dtype=float)
        if not np.isfinite(y).all():
            raise ValueError("training target contains non-finite values")
        th = np.asarray(self.thresholds, float)
        if th.ndim != 1 or len(th) < 2 or np.any(np.diff(th) <= 0):
            raise ValueError("thresholds must be strictly increasing")
        categorical = [c for c in self.feature_columns if frame[c].dtype == object]
        numeric = [c for c in self.feature_columns if c not in categorical]
        pre = ColumnTransformer(
            [
                ("num", SimpleImputer(strategy="median"), numeric),
                (
                    "cat",
                    make_pipeline(
                        SimpleImputer(strategy="most_frequent"),
                        OneHotEncoder(handle_unknown="ignore"),
                    ),
                    categorical,
                ),
            ]
        )
        x = pre.fit_transform(frame[list(self.feature_columns)])
        forest = RandomForestRegressor(
            n_estimators=self.n_estimators,
            min_samples_leaf=self.min_samples_leaf,
            max_features=self.max_features,
            max_samples=self.max_samples,
            bootstrap=True,
            random_state=self.random_state,
            n_jobs=-1,
        )
        forest.fit(x, (y[:, None] <= th[None, :]).astype(np.float32))
        cfg = {
            k: getattr(self, k)
            for k in (
                "thresholds",
                "n_estimators",
                "min_samples_leaf",
                "max_features",
                "max_samples",
                "random_state",
            )
        }
        return FittedCRPSForest(
            self.feature_columns,
            self.n_estimators,
            pre,
            forest,
            y,
            forest.apply(x),
            training_fingerprint(rows, self.feature_columns, cfg),
        )
