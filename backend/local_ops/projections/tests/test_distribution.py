import numpy as np
import pytest
from projection_ops.distribution import DrawSeries, build_distributions, cdf_at, quantile


def test_shared_grid_walls_normalization_and_round_trip():
    rng = np.random.default_rng(2)
    series = [
        DrawSeries("wr", "WR", rng.normal(9, 5, 2000)),
        DrawSeries("k", "K", np.maximum(0, rng.normal(7, 3, 2000))),
        DrawSeries("d", "DST", np.maximum(-4, rng.normal(6, 4, 2000))),
    ]
    grid, out = build_distributions(series, minimum_draws=2000)
    assert -4 in grid and 0 in grid
    for key, d in out.items():
        assert d.cdf[0] == 0 and d.cdf[-1] == 1
        assert all(b >= a for a, b in zip(d.cdf, d.cdf[1:]))
        for p in (0.1, 0.5, 0.9):
            x = quantile(p, grid, d.pdf, d.cdf, d.lower_bound)
            assert cdf_at(x, grid, d.pdf, d.cdf, d.lower_bound) == pytest.approx(p, abs=2e-6)
    k = out["k"]
    assert cdf_at(-1, grid, k.pdf, k.cdf, k.lower_bound) == 0
    assert quantile(0, grid, k.pdf, k.cdf, k.lower_bound) == 0


def test_degenerate_draws():
    grid, out = build_distributions([DrawSeries("x", "QB", np.ones(100) * 3)], minimum_draws=100)
    assert out["x"].bandwidth == 0.5
