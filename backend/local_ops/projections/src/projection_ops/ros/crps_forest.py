"""Baseline B: direct ROS CRPS forest (§5).

Same model family as the existing weekly ``CRPSRandomForest`` (multi-output
squared-error splits on ``I(Y <= z)``, then empirical training outcomes from the
fitted leaves), retargeted to ``ros_points`` with a training-only threshold grid.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import polars as pl

from . import config as C
from .design import dense_design
from .features import CATEGORICAL_FEATURES, FEATURE_COLUMNS


def threshold_grid(values: np.ndarray, *, n_quantiles: int = 40, n_low: int = 15) -> np.ndarray:
    """Position-aware ROS threshold grid from training targets only (§5.2).

    Fixed zero, a dense low-end grid, training-target quantiles 0.02-0.98, and a
    small upper-tail set.  Deduplicated and sorted; saved in each fit manifest.
    """
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    if values.size == 0:
        raise ValueError("no finite training targets for the threshold grid")
    quantiles = np.quantile(values, np.linspace(0.02, 0.98, n_quantiles))
    low = np.linspace(0.0, float(np.quantile(values, 0.5)), n_low)
    upper = np.quantile(values, [0.95, 0.99])
    grid = np.unique(np.round(np.concatenate([[0.0], low, quantiles, upper]), 2))
    return grid


@dataclass
class FittedROSForest:
    feature_columns: tuple[str, ...]
    target: str
    forest: Any
    train_frame: pl.DataFrame
    outcomes: np.ndarray
    train_leaves: np.ndarray
    n_estimators: int
    leaf_pools: list[dict[int, np.ndarray]] | None = None

    def _ensure_pools(self) -> None:
        """Leaf -> training-outcome arrays, built once for fast sampling (§5.4)."""
        if self.leaf_pools is not None:
            return
        pools: list[dict[int, np.ndarray]] = []
        for tree_idx in range(self.n_estimators):
            leaves = self.train_leaves[:, tree_idx]
            pools.append({int(leaf): self.outcomes[leaves == leaf] for leaf in np.unique(leaves)})
        self.leaf_pools = pools

    def predict_samples(
        self, test: pl.DataFrame, *, n_draws: int, rng: np.random.Generator
    ) -> np.ndarray:
        if n_draws < 1:
            raise ValueError("n_draws must be >= 1")
        self._ensure_pools()
        _, x_test = dense_design(
            self.train_frame, test, self.feature_columns, categorical=CATEGORICAL_FEATURES
        )
        test_leaves = self.forest.apply(x_test)
        draws = np.empty((test.height, n_draws), dtype=float)
        selected = rng.integers(self.n_estimators, size=(test.height, n_draws))
        for row in range(test.height):
            for tree_idx in np.unique(selected[row]):
                mask = selected[row] == tree_idx
                pool = self.leaf_pools[tree_idx].get(int(test_leaves[row, tree_idx]))
                if pool is None or pool.size == 0:
                    pool = self.outcomes
                draws[row, mask] = rng.choice(pool, size=int(mask.sum()), replace=True)
        return draws


@dataclass
class ROSForest:
    """Direct conditional-CDF forest for ROS points."""

    feature_columns: tuple[str, ...] = FEATURE_COLUMNS
    target: str = "ros_points"
    params: dict[str, Any] = field(default_factory=lambda: dict(C.FOREST_PARAMS))
    thresholds: np.ndarray | None = None  # None -> derive from training targets
    representation: str = "direct"  # "direct" (F0) or "per_game" (F1)

    def _y(self, train: pl.DataFrame) -> np.ndarray:
        y = train[self.target].cast(pl.Float64).to_numpy()
        if self.representation == "per_game":
            remaining = train["remaining_team_games"].cast(pl.Float64).to_numpy()
            y = np.divide(y, remaining, out=np.zeros_like(y), where=remaining > 0)
        return y

    def fit(self, train: pl.DataFrame) -> FittedROSForest:
        from sklearn.ensemble import RandomForestRegressor  # noqa: PLC0415

        y = self._y(train)
        thresholds = self.thresholds
        if thresholds is None:
            thresholds = threshold_grid(y)
        thresholds = np.asarray(thresholds, dtype=float)
        x_train, _ = dense_design(
            train, train.head(0), self.feature_columns, categorical=CATEGORICAL_FEATURES
        )
        cdf_targets = (y[:, None] <= thresholds[None, :]).astype(np.float32)
        forest = RandomForestRegressor(
            criterion="squared_error",
            bootstrap=True,
            **self.params,
        )
        forest.fit(x_train, cdf_targets)
        return FittedROSForest(
            feature_columns=self.feature_columns,
            target=self.target,
            forest=forest,
            train_frame=train.select(*self.feature_columns),
            outcomes=y,
            train_leaves=forest.apply(x_train),
            n_estimators=self.params.get("n_estimators", 200),
        )
