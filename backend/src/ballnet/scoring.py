"""Shared scoring primitives for highlights / rarity (not Stage G)."""

from __future__ import annotations

import math
from typing import Sequence

import numpy as np

# Peer sample must be large enough that z is not dominated by tiny groups (e.g. week-1 kickers).
MIN_PEER_N = 16

# Order-of-magnitude display ladder (10^k). Geometric nearest snap for UI chips.
RARITY_TIERS: tuple[int, ...] = tuple(10**k for k in range(1, 10))  # 10 .. 1_000_000_000


def snap_one_in_n(n: int | None) -> int | None:
    """Snap a raw 1-in-N to the nearest RARITY_TIERS rung in log space."""
    if n is None or not math.isfinite(n) or n < 1:
        return None
    n = max(1, int(n))
    best = RARITY_TIERS[0]
    best_dist = abs(math.log(n) - math.log(best))
    for tier in RARITY_TIERS[1:]:
        dist = abs(math.log(n) - math.log(tier))
        if dist < best_dist:
            best = tier
            best_dist = dist
    return best


def z_score(
    value: float,
    peer_values: Sequence[float],
    *,
    min_n: int = MIN_PEER_N,
) -> float | None:
    """Population z vs peers. Returns None if n < min_n or std is non-finite / ~0."""
    peers = [float(v) for v in peer_values if v is not None and math.isfinite(float(v))]
    if len(peers) < min_n:
        return None
    arr = np.asarray(peers, dtype=float)
    mu = float(arr.mean())
    sigma = float(arr.std(ddof=0))
    if not math.isfinite(sigma) or sigma < 1e-12:
        return None
    z = (float(value) - mu) / sigma
    if not math.isfinite(z):
        return None
    return z


def oriented_z_score(
    value: float,
    peer_values: Sequence[float],
    *,
    higher_is_better: bool,
    min_n: int = MIN_PEER_N,
) -> float | None:
    """Z-score oriented so larger is always 'better' for ranking."""
    z = z_score(value, peer_values, min_n=min_n)
    if z is None:
        return None
    return z if higher_is_better else -z


def one_in_n_from_tail(p: float) -> int | None:
    """
    Map a one-sided tail probability to an integer rarity (Gaussian approximation).

    `p` is P(Z >= z) for the oriented z (already flipped for lower-is-better).
    Clamped to [2, 1_000_000_000] for display; None if p is not in (0, 1).
    """
    if p is None or not math.isfinite(p) or p <= 0 or p >= 1:
        return None
    # Avoid overflow on tiny tails.
    p = max(p, 1e-12)
    n = int(round(1.0 / p))
    return max(2, min(n, 1_000_000_000))


def gaussian_tail_one_in_n(oriented_z: float) -> int | None:
    """Rarity from standard-normal upper tail of an oriented z-score."""
    if oriented_z is None or not math.isfinite(oriented_z):
        return None
    # Survival function Φ̄(z) via erfc for stability.
    p = 0.5 * math.erfc(oriented_z / math.sqrt(2.0))
    return one_in_n_from_tail(p)


def rarity_tier_from_z(oriented_z: float) -> int | None:
    """Display tier (10^k) from oriented z via Gaussian-tail oneInN."""
    return snap_one_in_n(gaussian_tail_one_in_n(oriented_z))
