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

from ballnet.catalog.types import StatDefinition
from ballnet.density import build_league_density
from ballnet.jsonio import write_json
from ballnet.paths import LEAGUE_PLAYS_DIR, PLAY_HIGHLIGHTS_DIR, ensure_data_dirs
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
# Board sections after pass+reception are paired into one completion card.
BOARD_CLASSES: tuple[str, ...] = (
    "completion",
    "rush",
    "interception",
    "sack",
    "kick_return",
    "punt_return",
    "field_goal",
    "punt",
    "tackle_for_loss",
    "fumble_recovery",
    "forced_fumble",
)
# Rare-event spam floors applied only when selecting board rows.
_MIN_VALUE: dict[str, float] = {
    "interception": 1.0,
    "sack": 1.0,
    "punt_return": 5.0,
    "tackle_for_loss": 1.0,
    "fumble_recovery": 1.0,
}

_METRIC_LABELS: dict[str, str] = {
    "receiving_yards": "receiving yards",
    "rushing_yards": "rushing yards",
    "passing_yards": "passing yards",
    "return_yards": "INT return yards",
    "sack_yards": "sack yards",
    "completion_yards": "yard pass",
    "kick_return_yards": "yard kick return",
    "punt_return_yards": "yard punt return",
    "field_goal_distance": "yard field goal",
    "punt_distance": "yard punt",
    "tfl_yards": "yard TFL",
    "fumble_recovery_yards": "yard fumble return",
    "forced_fumble_epa": "EPA forced fumble",
}

# Synthetic defs for histogram binning only — not frontend catalog ids.
_PLAY_STATS: dict[str, StatDefinition] = {
    "reception": StatDefinition(
        "receiving_yards", "discrete", True, "count", 0, 100, None, "plays", 2016, bin_width=1
    ),
    "rush": StatDefinition(
        "rushing_yards", "discrete", True, "count", -20, 100, None, "plays", 2016, bin_width=1
    ),
    "pass": StatDefinition(
        "passing_yards", "discrete", True, "count", 0, 100, None, "plays", 2016, bin_width=1
    ),
    "interception": StatDefinition(
        "return_yards", "discrete", True, "count", 0, 100, None, "plays", 2016, bin_width=1
    ),
    "sack": StatDefinition(
        "sack_yards", "discrete", True, "count", 0, 40, None, "plays", 2016, bin_width=1
    ),
    "kick_return": StatDefinition(
        "kick_return_yards", "discrete", True, "count", 0, 110, None, "plays", 2016, bin_width=1
    ),
    "punt_return": StatDefinition(
        "punt_return_yards", "discrete", True, "count", -10, 100, None, "plays", 2016, bin_width=1
    ),
    "field_goal": StatDefinition(
        "field_goal_distance", "discrete", True, "count", 15, 70, None, "plays", 2016, bin_width=1
    ),
    "punt": StatDefinition(
        "punt_distance", "discrete", True, "count", 0, 90, None, "plays", 2016, bin_width=1
    ),
    "tackle_for_loss": StatDefinition(
        "tfl_yards", "discrete", True, "count", 0, 25, None, "plays", 2016, bin_width=1
    ),
    "fumble_recovery": StatDefinition(
        "fumble_recovery_yards", "discrete", True, "count", 0, 100, None, "plays", 2016, bin_width=1
    ),
    "forced_fumble": StatDefinition(
        "forced_fumble_epa",
        "continuous",
        True,
        "one_decimal",
        -5,
        15,
        None,
        "plays",
        2016,
    ),
}


@dataclass(frozen=True)
class PlayHighlightsPublishResult:
    board: Path
    dist: Path | None = None


def play_highlights_board_path(season: int, week: int) -> Path:
    return PLAY_HIGHLIGHTS_DIR / str(season) / f"w{week}.json"


def play_highlights_dist_path(season: int, week: int) -> Path:
    return LEAGUE_PLAYS_DIR / str(season) / f"w{week}.json"


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


def _collapse_key(row: dict[str, Any]) -> str:
    """Completions stay one card per play; other classes nest by player."""
    if row.get("playClass") == "completion":
        game_id = row.get("gameId") or ""
        play_id = row.get("playId")
        if game_id and play_id is not None:
            return f"play:{game_id}:{play_id}"
    return f"player:{row.get('playerId')}"


def _collapse_by_player(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_key: dict[str, list[dict[str, Any]]] = {}
    order: list[str] = []
    for row in rows:
        key = _collapse_key(row)
        if key not in by_key:
            by_key[key] = []
            order.append(key)
        by_key[key].append(row)

    out: list[dict[str, Any]] = []
    for key in order:
        group_rows = by_key[key]
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


def _combine_completion(pas: dict[str, Any], rec: dict[str, Any]) -> dict[str, Any]:
    """One board card for a completed pass: passer → receiver."""
    # Rank / primary histogram from the rarer of the two peer perspectives.
    if float(pas.get("rarityScore") or 0) >= float(rec.get("rarityScore") or 0):
        primary, secondary = pas, rec
        secondary_role = "reception"
    else:
        primary, secondary = rec, pas
        secondary_role = "pass"

    yards = float(pas["value"])
    out = dict(primary)
    out.update(
        {
            "playerId": pas["playerId"],
            "name": f"{pas.get('name') or ''} → {rec.get('name') or ''}".strip(),
            "position": rec.get("position") or pas.get("position") or "",
            "positionGroup": rec.get("positionGroup") or pas.get("positionGroup") or "",
            "team": pas.get("team") or rec.get("team") or "",
            "opponent": pas.get("opponent") or rec.get("opponent") or "",
            "playClass": "completion",
            "statId": "completion_yards",
            "statLabel": "yard pass",
            "value": yards,
            "passerId": pas["playerId"],
            "passerName": pas.get("name") or "",
            "passerPosition": pas.get("position") or "",
            "receiverId": rec["playerId"],
            "receiverName": rec.get("name") or "",
            "receiverPosition": rec.get("position") or "",
            "peerKey": primary.get("peerKey"),
            "secondaryPeerKey": secondary.get("peerKey"),
            "secondaryRole": secondary_role,
            "secondaryFavorableCount": secondary.get("favorableCount"),
            "secondaryPeerN": secondary.get("peerN"),
            "secondaryOneInN": secondary.get("oneInN"),
            "secondaryRarityTier": secondary.get("rarityTier"),
            "secondaryRarityScore": secondary.get("rarityScore"),
            "zScore": primary.get("zScore") or 0.0,
            "rarityScore": primary.get("rarityScore"),
            "favorableCount": primary.get("favorableCount"),
            "peerN": primary.get("peerN"),
            "oneInN": primary.get("oneInN"),
            "rarityTier": primary.get("rarityTier"),
            "rarityMethod": primary.get("rarityMethod"),
            "touchdown": bool(pas.get("touchdown") or rec.get("touchdown")),
            "description": pas.get("description") or rec.get("description"),
            "gameId": pas.get("gameId") or rec.get("gameId") or "",
            "playId": pas.get("playId") if pas.get("playId") is not None else rec.get("playId"),
            "quarter": pas.get("quarter") if pas.get("quarter") is not None else rec.get("quarter"),
            "clock": pas.get("clock") or rec.get("clock"),
            "gameClock": pas.get("gameClock") or rec.get("gameClock"),
            "gameSecondsRemaining": pas.get("gameSecondsRemaining")
            if pas.get("gameSecondsRemaining") is not None
            else rec.get("gameSecondsRemaining"),
        }
    )
    out.pop("also", None)
    return out


def _merge_pass_reception_pairs(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Collapse same-play pass + reception actor rows into completion cards."""
    paired: dict[tuple[str, int], dict[str, dict[str, Any]]] = {}
    others: list[dict[str, Any]] = []
    for row in rows:
        play_class = row.get("playClass")
        game_id = row.get("gameId") or ""
        play_id = row.get("playId")
        if play_class in ("pass", "reception") and game_id and play_id is not None:
            key = (str(game_id), int(play_id))
            bucket = paired.setdefault(key, {})
            # First win keeps the highest-rarity row if duplicates appear.
            prior = bucket.get(str(play_class))
            if prior is None or float(row.get("rarityScore") or 0) > float(
                prior.get("rarityScore") or 0
            ):
                bucket[str(play_class)] = row
        else:
            others.append(row)

    merged: list[dict[str, Any]] = list(others)
    for parts in paired.values():
        pas = parts.get("pass")
        rec = parts.get("reception")
        if pas is not None and rec is not None:
            merged.append(_combine_completion(pas, rec))
        else:
            merged.extend(parts.values())
    return merged


def _rows_for_board_class(rows: list[dict[str, Any]], board_class: str) -> list[dict[str, Any]]:
    if board_class == "completion":
        return [
            r
            for r in rows
            if r.get("playClass") in ("completion", "pass", "reception")
        ]
    return [r for r in rows if r.get("playClass") == board_class]


def _board_from_peers(
    peers: pl.DataFrame,
    season: int,
    week: int,
    *,
    missing_peer_seasons: list[int] | None = None,
) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    this_week = peers.filter((pl.col("season") == season) & (pl.col("week") == week))
    peer_map = _peer_value_map(peers)

    all_rows: list[dict[str, Any]] = []
    for rec in this_week.iter_rows(named=True):
        scored = _score_play(rec, peer_map)
        if scored is not None:
            all_rows.append(scored)

    all_rows = _merge_pass_reception_pairs(all_rows)
    all_rows.sort(
        key=lambda r: (-r["rarityScore"], r["favorableCount"], r["playerId"], r["playId"] or 0)
    )

    by_class: dict[str, list[dict[str, Any]]] = {c: [] for c in BOARD_CLASSES}
    balanced: list[dict[str, Any]] = []
    for board_class in BOARD_CLASSES:
        class_rows = _rows_for_board_class(all_rows, board_class)
        collapsed = _collapse_by_player(class_rows)[:PER_CLASS_N]
        for i, row in enumerate(collapsed, start=1):
            entry = dict(row)
            entry["rank"] = i
            by_class[board_class].append(entry)
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
    return payload, peer_map


def _shape_payload(dens: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {
        "kind": dens["kind"],
        "xMin": dens["x_min"],
        "xMax": dens["x_max"],
        "yMax": dens["y_max"],
        "curve": dens.get("curve") or [],
    }
    if dens.get("representation") == "histogram":
        out.update(
            {
                "representation": "histogram",
                "bins": dens["bins"],
                "valueCounts": dens["value_counts"],
            }
        )
    if dens.get("n_sample") is not None:
        out["nSample"] = int(dens["n_sample"])
    return out


def _peer_keys_on_board(payload: dict[str, Any]) -> set[str]:
    keys: set[str] = set()

    def walk(rows: list[dict[str, Any]]) -> None:
        for row in rows:
            for field in ("peerKey", "secondaryPeerKey"):
                key = row.get(field)
                if isinstance(key, str) and key:
                    keys.add(key)
            also = row.get("also") or []
            if isinstance(also, list):
                walk(also)

    walk(list(payload.get("top") or []))
    for rows in (payload.get("byClass") or {}).values():
        walk(list(rows or []))
    return keys


def _play_class_from_peer_key(peer_key: str) -> str:
    return peer_key.split("|", 1)[0]


def build_play_league_shapes(
    season: int,
    week: int,
    peer_map: dict[str, np.ndarray],
    peer_keys: set[str],
) -> dict[str, Any]:
    """Observed histograms for peer keys present on the board (expand charts)."""
    stats: dict[str, Any] = {}
    for key in sorted(peer_keys):
        sample = peer_map.get(key)
        if sample is None or sample.size < MIN_PEER_N:
            continue
        play_class = _play_class_from_peer_key(key)
        cat = _PLAY_STATS.get(play_class)
        if cat is None:
            continue
        dens = build_league_density(np.asarray(sample, dtype=float), cat)
        stats[key] = _shape_payload(dens)
    return {
        "schemaVersion": 1,
        "season": season,
        "asOfWeek": week,
        "scope": "play_all_time",
        "peerWindowStartYear": PLAY_HIGHLIGHTS_START_YEAR,
        "stats": stats,
    }


def build_play_highlights_board(season: int, week: int) -> dict[str, Any]:
    peers, missing = _load_all_time_play_peers(season, week)
    payload, _peer_map = _board_from_peers(
        peers, season, week, missing_peer_seasons=missing
    )
    return payload


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
    peers, missing = _load_all_time_play_peers(season, week)
    payload, peer_map = _board_from_peers(
        peers, season, week, missing_peer_seasons=missing
    )
    board = play_highlights_board_path(season, week)
    write_json(board, payload)

    shapes = build_play_league_shapes(
        season, week, peer_map, _peer_keys_on_board(payload)
    )
    dist = play_highlights_dist_path(season, week)
    write_json(dist, shapes)
    return PlayHighlightsPublishResult(board=board, dist=dist)


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
