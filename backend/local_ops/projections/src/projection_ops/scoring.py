"""Immutable ppr-v1 fantasy scoring formulas."""

from __future__ import annotations
from collections.abc import Mapping
from typing import Any


def _n(row: Mapping[str, Any], key: str) -> float:
    value = row.get(key, 0.0)
    return 0.0 if value is None else float(value)


def score(position: str, row: Mapping[str, Any]) -> float:
    position = position.upper()
    if position == "QB":
        return (
            0.04 * _n(row, "passing_yards")
            + 4 * _n(row, "passing_tds")
            - 2 * _n(row, "interceptions")
            + 0.1 * _n(row, "rushing_yards")
            + 6 * _n(row, "rushing_tds")
        )
    if position in {"RB", "WR", "TE"}:
        return (
            _n(row, "receptions")
            + 0.1 * (_n(row, "receiving_yards") + _n(row, "rushing_yards"))
            + 6 * (_n(row, "receiving_tds") + _n(row, "rushing_tds"))
        )
    if position == "K":
        return (
            3 * sum(_n(row, k) for k in ("fg_made_0_19", "fg_made_20_29", "fg_made_30_39"))
            + 4 * _n(row, "fg_made_40_49")
            + 5 * _n(row, "fg_made_50_59")
            + 6 * _n(row, "fg_made_60_")
            + _n(row, "pat_made")
        )
    if position == "DST":
        pa = _n(row, "points_allowed")
        tier = (
            10
            if pa == 0
            else 7
            if pa <= 6
            else 4
            if pa <= 13
            else 1
            if pa <= 20
            else 0
            if pa <= 27
            else -1
            if pa <= 34
            else -4
        )
        return (
            _n(row, "def_sacks")
            + 2 * (_n(row, "def_interceptions") + _n(row, "def_fumbles"))
            + 6 * (_n(row, "def_tds") + _n(row, "special_teams_tds"))
            + 2 * (_n(row, "def_safeties") + _n(row, "blocked_kicks"))
            + tier
        )
    raise ValueError(f"unsupported position: {position}")
