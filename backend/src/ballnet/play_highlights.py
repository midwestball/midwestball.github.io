"""Play-level rarity boards (parallel to Stage H game highlights).

Reads play panels from `data/plays/`, scores each week's plays against all-time
peers within `(play_class, position_code)` (falling back to position_group then
class-only), and writes `data/highlights/plays/{season}/w{week}.json`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import polars as pl

from ballnet.jsonio import write_json
from ballnet.paths import PLAY_HIGHLIGHTS_DIR, ensure_data_dirs
from ballnet.play_panel import (
    PLAY_CLASSES,
    load_play_panel,
    max_week_in_play_panel,
    play_panel_path,
)
from ballnet.publish import default_as_of_week
from ballnet.scoring import MIN_PEER_N, snap_one_in_n

# Align with Stage H peer window; missing historical play panels are skipped.
PLAY_HIGHLIGHTS_START_YEAR = 2016

TOP_N = 25
PER_CLASS_N = 8
# Rare-event spam floors applied only when selecting board rows.
_MIN_VALUE: dict[str, float] = {
    "interception": 1.0,
    "sack": 1.0,
}

_METRIC_LABELS: dict[str, str] = {
    "receiving_yards": "receiving yards",
    "rushing_yards": "rushing yards",
    "passing_yards": "passing yards",
    "return_yards": "INT return yards",
    "sack_yards": "sack yards",
}


@dataclass(frozen=True)
class PlayHighlightsPublishResult:
    board: Path


def play_highlights_board_path(season: int, week: int) -> Path:
    return PLAY_HIGHLIGHTS_DIR / str(season) / f"w{week}.json"


def _fallback_keys(play_class: str, position_code: str | None, position_group: str | None) -> list[str]:
    """Try position code, then group, then class-wide."""
    keys: list[str] = []
    if position_code:
        keys.append(f"{play_class}|pos:{position_code}")
    if position_group:
        keys.append(f"{play_class}|group:{position_group}")
    keys.append(f"{play_class}|all")
    seen: set[str] = set()
    out: list[str] = []
    for k in keys:
        if k not in seen:
            seen.add(k)
            out.append(k)
    return out


def _with_peer_keys(plays: pl.DataFrame) -> pl.DataFrame:
    return plays.with_columns(
        pl.when(pl.col("position_code").is_not_null())
        .then(pl.concat_str([pl.col("play_class"), pl.lit("|pos:"), pl.col("position_code")]))
        .when(pl.col("position_group").is_not_null())
        .then(pl.concat_str([pl.col("play_class"), pl.lit("|group:"), pl.col("position_group")]))
        .otherwise(pl.concat_str([pl.col("play_class"), pl.lit("|all")]))
        .alias("_peer_key_primary"),
        pl.when(pl.col("position_group").is_not_null())
        .then(pl.concat_str([pl.col("play_class"), pl.lit("|group:"), pl.col("position_group")]))
        .otherwise(pl.concat_str([pl.col("play_class"), pl.lit("|all")]))
        .alias("_peer_key_group"),
        pl.concat_str([pl.col("play_class"), pl.lit("|all")]).alias("_peer_key_all"),
    )


def _load_all_time_play_peers(season: int, week: int) -> tuple[pl.DataFrame, list[int]]:
    if season < PLAY_HIGHLIGHTS_START_YEAR:
        raise ValueError(
            f"season {season} is before play highlights start {PLAY_HIGHLIGHTS_START_YEAR}"
        )
    current = play_panel_path(season)
    if not current.is_file():
        raise FileNotFoundError(
            f"missing play panel {current}; run `ballnet play-panel --season {season}` first"
        )

    frames: list[pl.DataFrame] = []
    missing: list[int] = []
    for y in range(PLAY_HIGHLIGHTS_START_YEAR, season):
        path = play_panel_path(y)
        if path.is_file():
            frames.append(pl.read_parquet(path))
        else:
            missing.append(y)
    frames.append(load_play_panel(season).filter(pl.col("week") <= week))
    peers = frames[0] if len(frames) == 1 else pl.concat(frames, how="diagonal_relaxed")
    return _with_peer_keys(peers), missing


def _peer_value_map(peers: pl.DataFrame) -> dict[str, np.ndarray]:
    """Sorted peer values for primary / group / all keys."""
    out: dict[str, np.ndarray] = {}
    for key_col in ("_peer_key_primary", "_peer_key_group", "_peer_key_all"):
        for key, group in peers.group_by(key_col):
            k = key[0] if isinstance(key, tuple) else key
            vals = group["value"].drop_nulls().to_numpy().astype(float)
            if vals.size:
                out[str(k)] = np.sort(vals)
    return out


def _score_play(
    rec: dict[str, Any],
    peer_map: dict[str, np.ndarray],
) -> dict[str, Any] | None:
    play_class = str(rec["play_class"])
    position_code = rec.get("position_code")
    position_group = rec.get("position_group")
    val = float(rec["value"])
    floor = _MIN_VALUE.get(play_class)
    if floor is not None and val < floor:
        return None

    chosen_key = None
    peers = None
    for key in _fallback_keys(play_class, position_code, position_group):
        arr = peer_map.get(key)
        if arr is not None and arr.size >= MIN_PEER_N:
            chosen_key = key
            peers = arr
            break
    if peers is None or chosen_key is None:
        return None

    favorable = int(peers.size - np.searchsorted(peers, val, side="left"))
    if not favorable:
        return None
    mean = float(peers.mean())
    std = float(peers.std())
    z = (val - mean) / std if std > 1e-12 else None
    one_in_n = peers.size / favorable
    metric_id = str(rec["metric_id"])
    desc = rec.get("desc")
    if isinstance(desc, str) and len(desc) > 220:
        desc = desc[:217] + "…"

    quarter = rec.get("quarter")
    clock = rec.get("clock")
    return {
        "playerId": rec["player_id"],
        "name": rec.get("player_display_name") or "",
        "position": position_code or "",
        "positionGroup": position_group or "",
        "team": rec.get("team") or "",
        "opponent": rec.get("opponent_team") or "",
        "playClass": play_class,
        "statId": metric_id,
        "statLabel": _METRIC_LABELS.get(metric_id, metric_id.replace("_", " ")),
        "value": val,
        "gameId": rec.get("game_id") or "",
        "playId": int(rec["play_id"]) if rec.get("play_id") is not None else None,
        "quarter": int(quarter) if quarter is not None else None,
        "clock": clock if isinstance(clock, str) else None,
        "gameClock": (
            f"Q{int(quarter)} {clock}" if quarter is not None and isinstance(clock, str) else None
        ),
        "gameSecondsRemaining": (
            float(rec["game_seconds_remaining"])
            if rec.get("game_seconds_remaining") is not None
            else None
        ),
        "touchdown": bool(rec.get("touchdown") or False),
        "description": desc,
        "zScore": round(z, 3) if z is not None else 0.0,
        "rarityScore": 1.0 - favorable / peers.size,
        "favorableCount": favorable,
        "rarityMethod": "empirical-inclusive-v2",
        "peerN": int(peers.size),
        "peerKey": chosen_key,
        "oneInN": one_in_n,
        "rarityTier": snap_one_in_n(one_in_n),
    }


def _collapse_by_player(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_player: dict[str, list[dict[str, Any]]] = {}
    order: list[str] = []
    for row in rows:
        pid = str(row["playerId"])
        if pid not in by_player:
            by_player[pid] = []
            order.append(pid)
        by_player[pid].append(row)

    out: list[dict[str, Any]] = []
    for pid in order:
        group_rows = by_player[pid]
        primary = dict(group_rows[0])
        also = []
        for secondary in group_rows[1:]:
            entry = dict(secondary)
            entry.pop("also", None)
            entry.pop("rank", None)
            also.append(entry)
        if also:
            primary["also"] = also
        out.append(primary)
    return out


def _board_from_peers(
    peers: pl.DataFrame,
    season: int,
    week: int,
    *,
    missing_peer_seasons: list[int] | None = None,
) -> dict[str, Any]:
    this_week = peers.filter((pl.col("season") == season) & (pl.col("week") == week))
    peer_map = _peer_value_map(peers)

    all_rows: list[dict[str, Any]] = []
    for rec in this_week.iter_rows(named=True):
        scored = _score_play(rec, peer_map)
        if scored is not None:
            all_rows.append(scored)

    all_rows.sort(
        key=lambda r: (-r["rarityScore"], r["favorableCount"], r["playerId"], r["playId"] or 0)
    )

    by_class: dict[str, list[dict[str, Any]]] = {c: [] for c in PLAY_CLASSES}
    balanced: list[dict[str, Any]] = []
    for play_class in PLAY_CLASSES:
        class_rows = [r for r in all_rows if r["playClass"] == play_class]
        collapsed = _collapse_by_player(class_rows)[:PER_CLASS_N]
        for i, row in enumerate(collapsed, start=1):
            entry = dict(row)
            entry["rank"] = i
            by_class[play_class].append(entry)
        balanced.extend(collapsed)

    balanced.sort(
        key=lambda r: (-r["rarityScore"], r["favorableCount"], r["playerId"], r["playId"] or 0)
    )
    top: list[dict[str, Any]] = []
    for i, row in enumerate(balanced[:TOP_N], start=1):
        entry = dict(row)
        entry["rank"] = i
        top.append(entry)

    payload: dict[str, Any] = {
        "schemaVersion": 1,
        "season": season,
        "week": week,
        "generatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "scope": "play_all_time",
        "peerWindowStartYear": PLAY_HIGHLIGHTS_START_YEAR,
        "top": top,
        "byClass": by_class,
    }
    if missing_peer_seasons:
        payload["missingPeerSeasons"] = list(missing_peer_seasons)
    return payload


def build_play_highlights_board(season: int, week: int) -> dict[str, Any]:
    peers, missing = _load_all_time_play_peers(season, week)
    return _board_from_peers(peers, season, week, missing_peer_seasons=missing)


def weeks_to_publish_plays(season: int) -> list[int]:
    cap = default_as_of_week(season)
    panel_max = max_week_in_play_panel(season)
    if panel_max is None:
        raise FileNotFoundError(
            f"missing play panel for {season}; run `ballnet play-panel --season {season}` first"
        )
    last = min(cap, panel_max)
    return list(range(1, last + 1))


def publish_play_highlights(season: int, week: int) -> PlayHighlightsPublishResult:
    ensure_data_dirs()
    payload = build_play_highlights_board(season, week)
    board = play_highlights_board_path(season, week)
    write_json(board, payload)
    return PlayHighlightsPublishResult(board=board)


def publish_play_highlights_range(
    start: int,
    end: int,
) -> list[PlayHighlightsPublishResult]:
    if end < start:
        raise ValueError("--end must be >= --start")
    results: list[PlayHighlightsPublishResult] = []
    for season in range(start, end + 1):
        for week in weeks_to_publish_plays(season):
            results.append(publish_play_highlights(season, week))
    return results
