"""Frozen v1 Gaussian KDE, shared-grid serialization, and lookup math."""

from __future__ import annotations
from dataclasses import dataclass
import math
import numpy as np
from scipy.special import ndtr, ndtri


@dataclass(frozen=True)
class DrawSeries:
    entity_key: str
    position: str
    draws: np.ndarray


@dataclass(frozen=True)
class Distribution:
    expected_points: float
    pdf: list[float]
    cdf: list[float]
    y_max: float
    lower_bound: float | None
    bandwidth: float
    n_model_draws: int
    retained_mass: float
    kde_mean: float


def bandwidth(draws: np.ndarray) -> float:
    values = np.asarray(draws, float)
    if len(values) < 2:
        return 0.5
    sd = float(np.std(values, ddof=1))
    if not math.isfinite(sd) or sd < 1e-12:
        return 0.5
    return max(0.25, 1.06 * sd * len(values) ** (-0.2))


def _check(series: DrawSeries, minimum_draws: int) -> tuple[np.ndarray, float, float | None]:
    d = np.asarray(series.draws, float)
    if d.ndim != 1 or len(d) < minimum_draws:
        raise ValueError(f"{series.entity_key}: need at least {minimum_draws} draws")
    if not np.isfinite(d).all():
        raise ValueError(f"{series.entity_key}: non-finite draws")
    wall = {"K": 0.0, "DST": -4.0}.get(series.position)
    if wall is not None and np.any(d < wall - 1e-10):
        raise ValueError(f"{series.entity_key}: draws below hard wall {wall}")
    return d, bandwidth(d), wall


def shared_grid(
    series: list[DrawSeries], *, epsilon: float = 1e-5, minimum_draws: int = 2
) -> tuple[np.ndarray, dict[str, tuple[np.ndarray, float, float | None]]]:
    if not series:
        raise ValueError("at least one draw series is required")
    checked = {s.entity_key: _check(s, minimum_draws) for s in series}
    z = float(ndtri(1 - epsilon))
    lower = []
    upper = []
    min_h = min(v[1] for v in checked.values())
    for d, h, wall in checked.values():
        lower.append(wall if wall is not None else float(np.min(d) - z * h))
        upper.append(float(np.max(d) + z * h))
    lo = min(lower)
    hi = max(upper)
    step = min_h / 4
    base = np.linspace(lo, hi, max(2, int(math.ceil((hi - lo) / step)) + 1))
    knots = [w for w in (-4.0, 0.0) if lo <= w <= hi]
    grid = np.unique(np.concatenate([base, np.asarray(knots)]))
    return grid, checked


def _density(grid: np.ndarray, draws: np.ndarray, h: float, wall: float | None) -> np.ndarray:
    out = np.zeros(len(grid), float)
    norm = h * math.sqrt(2 * math.pi)
    for start in range(0, len(draws), 1000):
        d = draws[start : start + 1000]
        delta = (grid[:, None] - d[None, :]) / h
        chunk = np.exp(-0.5 * delta * delta).sum(axis=1)
        if wall is not None:
            reflected = (grid[:, None] - (2 * wall - d)[None, :]) / h
            chunk += np.exp(-0.5 * reflected * reflected).sum(axis=1)
        out += chunk
    out /= len(draws) * norm
    if wall is not None:
        out[grid < wall] = 0
    return out


def _cdf_from_pdf(grid: np.ndarray, pdf: np.ndarray, wall: float | None) -> np.ndarray:
    areas = (pdf[:-1] + pdf[1:]) * 0.5 * np.diff(grid)
    if wall is not None:
        areas[grid[:-1] < wall] = 0
    cdf = np.concatenate([[0.0], np.cumsum(areas)])
    return cdf


def build_distributions(
    series: list[DrawSeries], *, epsilon: float = 1e-5, minimum_draws: int = 2, precision: int = 8
) -> tuple[list[float], dict[str, Distribution]]:
    grid, checked = shared_grid(series, epsilon=epsilon, minimum_draws=minimum_draws)
    result = {}
    for s in series:
        d, h, wall = checked[s.entity_key]
        raw = _density(grid, d, h, wall)
        raw_cdf = _cdf_from_pdf(grid, raw, wall)
        retained = float(raw_cdf[-1])
        if not 0.99 <= retained <= 1.01:
            raise ValueError(f"{s.entity_key}: bad retained KDE mass {retained}")
        pdf = raw / retained
        # Serialize PDF first, then normalize and derive CDF from exactly those rounded values.
        pdf = np.round(pdf, precision)
        norm = float(_cdf_from_pdf(grid, pdf, wall)[-1])
        pdf = np.round(pdf / norm, precision + 2)
        cdf = _cdf_from_pdf(grid, pdf, wall)
        # One final exact normalization keeps trapezoids and endpoint consistent.
        pdf = pdf / float(cdf[-1])
        cdf = _cdf_from_pdf(grid, pdf, wall)
        cdf[-1] = 1.0
        pdf = np.asarray([float(f"{x:.10g}") for x in pdf])
        cdf = _cdf_from_pdf(grid, pdf, wall)
        pdf = pdf / float(cdf[-1])
        cdf = _cdf_from_pdf(grid, pdf, wall)
        cdf = np.clip(cdf, 0.0, 1.0)
        cdf[-1] = 1.0
        kde_mean = float(np.trapezoid(grid * pdf, grid))
        result[s.entity_key] = Distribution(
            float(np.mean(d)),
            pdf.tolist(),
            cdf.tolist(),
            float(np.max(pdf)),
            wall,
            h,
            len(d),
            retained,
            kde_mean,
        )
    return grid.tolist(), result


def cdf_at(
    x: float,
    grid: list[float],
    pdf: list[float],
    cdf: list[float],
    lower_bound: float | None = None,
) -> float:
    if not math.isfinite(x):
        raise ValueError("x must be finite")
    if (lower_bound is not None and x <= lower_bound) or x <= grid[0]:
        return 0.0
    if x >= grid[-1]:
        return 1.0
    i = int(np.searchsorted(grid, x, side="right") - 1)
    if x == grid[i]:
        return float(cdf[i])
    dx = x - grid[i]
    width = grid[i + 1] - grid[i]
    y = pdf[i] + (pdf[i + 1] - pdf[i]) * dx / width
    return min(1.0, max(0.0, float(cdf[i] + (pdf[i] + y) * dx / 2)))


def quantile(
    p: float,
    grid: list[float],
    pdf: list[float],
    cdf: list[float],
    lower_bound: float | None = None,
) -> float:
    if not math.isfinite(p) or not 0 <= p <= 1:
        raise ValueError("p must be in [0, 1]")
    if p == 0:
        return lower_bound if lower_bound is not None else grid[0]
    if p == 1:
        return grid[-1]
    j = int(np.searchsorted(cdf, p, side="left"))
    if cdf[j] == p:
        while j > 0 and cdf[j - 1] >= p:
            j -= 1
        return grid[j]
    i = max(0, j - 1)
    mass = p - cdf[i]
    width = grid[i + 1] - grid[i]
    y0 = pdf[i]
    slope = (pdf[i + 1] - y0) / width
    if abs(slope) < 1e-14:
        dx = mass / y0 if y0 > 0 else 0.0
    else:
        disc = max(0.0, y0 * y0 + 2 * slope * mass)
        dx = 2 * mass / (y0 + math.sqrt(disc)) if y0 + math.sqrt(disc) > 0 else 0.0
    return float(grid[i] + min(width, max(0.0, dx)))
