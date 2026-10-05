import numpy as np
from projection_ops.model import CRPSRandomForest, training_fingerprint


def test_forest_samples_and_fingerprint_are_deterministic():
    rows = [
        {"x": float(i), "cat": "a" if i % 2 else "b", "fantasy_points": float(i % 7)}
        for i in range(60)
    ]
    model = CRPSRandomForest(
        ("x", "cat"), tuple(range(-2, 12)), n_estimators=8, min_samples_leaf=2
    ).fit(rows)
    a = model.predict_samples([{"x": 4.0, "cat": "new"}], n_draws=30, rng=np.random.default_rng(3))
    b = model.predict_samples([{"x": 4.0, "cat": "new"}], n_draws=30, rng=np.random.default_rng(3))
    assert np.array_equal(a, b)
    assert training_fingerprint(rows, ("x", "cat"), {}) != training_fingerprint(
        rows[:-1], ("x", "cat"), {}
    )
