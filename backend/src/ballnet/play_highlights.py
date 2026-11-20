"""Play-level rarity boards (parallel to Stage H game highlights).

Reads play panels from `data/plays/`, scores each week's plays against all-time
peers within `(play_class, position_code)` (falling back to position_group then
class-only), and writes `data/highlights/plays/{season}/w{week}.json`.
"""

from __future__ import annotations

import json
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
ScoreMode = str  # "raw" | "epa"
SCORE_MODES: tuple[str, ...] = ("raw", "epa")
# Actor benefits when offense EPA falls — rank with -epa.
_EPA_FLIP_CLASSES: frozenset[str] = frozenset(
    {
        "interception",
        "sack",
        "tackle_for_loss",
        "fumble_recovery",
        "forced_fumble",
        "punt_return",
    }
)
_EPA_STAT = StatDefinition(
    "epa", "continuous", True, "one_decimal", -10, 10, None, "plays", 2016
)
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
    board_epa: Path | None = None
    dist_epa: Path | None = None


def play_highlights_board_path(season: int, week: int, *, mode: ScoreMode = "raw") -> Path:
    suffix = ".epa" if mode == "epa" else ""
    return PLAY_HIGHLIGHTS_DIR / str(season) / f"w{week}{suffix}.json"


def play_highlights_dist_path(season: int, week: int, *, mode: ScoreMode = "raw") -> Path:
    suffix = ".epa" if mode == "epa" else ""
    return LEAGUE_PLAYS_DIR / str(season) / f"w{week}{suffix}.json"


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


def _with_score_column(plays: pl.DataFrame, mode: ScoreMode) -> pl.DataFrame:
    """Attach `_score` used for rarity: raw yards/etc. or actor-oriented EPA."""
    if "epa" not in plays.columns:
        plays = plays.with_columns(pl.lit(None).cast(pl.Float64).alias("epa"))
    if mode == "raw":
        return plays.with_columns(pl.col("value").cast(pl.Float64).alias("_score"))
    # Actor-oriented EPA: flip for defense / punt returner.
    return plays.with_columns(
        pl.when(pl.col("epa").is_null() | ~pl.col("epa").is_finite())
        .then(None)
        .when(pl.col("play_class").is_in(sorted(_EPA_FLIP_CLASSES)))
        .then(-pl.col("epa"))
        .otherwise(pl.col("epa"))
        .alias("_score")
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
    """Sorted peer `_score` values for primary / group / all keys."""
    out: dict[str, np.ndarray] = {}
    score_col = "_score" if "_score" in peers.columns else "value"
    for key_col in ("_peer_key_primary", "_peer_key_group", "_peer_key_all"):
        for key, group in peers.group_by(key_col):
            k = key[0] if isinstance(key, tuple) else key
            vals = group[score_col].drop_nulls().to_numpy().astype(float)
            if vals.size:
                out[str(k)] = np.sort(vals)
    return out


def _score_play(
    rec: dict[str, Any],
    peer_map: dict[str, np.ndarray],
    *,
    mode: ScoreMode = "raw",
) -> dict[str, Any] | None:
    play_class = str(rec["play_class"])
    position_code = rec.get("position_code")
    position_group = rec.get("position_group")
    score = rec.get("_score", rec.get("value"))
    if score is None:
        return None
    val = float(score)
    if not np.isfinite(val):
        return None
    if mode == "raw":
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
    if mode == "epa":
        metric_id = "epa"
        stat_label = "EPA"
    else:
        metric_id = str(rec["metric_id"])
        stat_label = _METRIC_LABELS.get(metric_id, metric_id.replace("_", " "))
    quarter = rec.get("quarter")
    clock = rec.get("clock")
    raw_value = rec.get("value")
    down = rec.get("down")
    ydstogo = rec.get("ydstogo")
    yardline_100 = rec.get("yardline_100")
    yrdln = rec.get("yrdln")
    air_yards = rec.get("air_yards")
    yards_after_catch = rec.get("yards_after_catch")
    return {
        "playerId": rec["player_id"],
        "name": rec.get("player_display_name") or "",
        "position": position_code or "",
        "positionGroup": position_group or "",
        "team": rec.get("team") or "",
        "opponent": rec.get("opponent_team") or "",
        "playClass": play_class,
        "statId": metric_id,
        "statLabel": stat_label,
        "value": val,
        "rawValue": float(raw_value) if raw_value is not None else None,
        "metricMode": mode,
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
        "down": int(down) if down is not None else None,
        "distance": float(ydstogo) if ydstogo is not None else None,
        "yardline100": float(yardline_100) if yardline_100 is not None else None,
        "yardline": yrdln.strip() if isinstance(yrdln, str) and yrdln.strip() else None,
        "airYards": float(air_yards) if air_yards is not None else None,
        "yardsAfterCatch": (
            float(yards_after_catch) if yards_after_catch is not None else None
        ),
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

    mode = str(pas.get("metricMode") or rec.get("metricMode") or "raw")
    # Same play → same scored value in both modes (yards or oriented EPA).
    scored = float(pas["value"])
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
            "statId": "epa" if mode == "epa" else "completion_yards",
            "statLabel": "EPA" if mode == "epa" else "yard pass",
            "value": scored,
            "rawValue": (
                float(pas["rawValue"])
                if pas.get("rawValue") is not None
                else float(rec["rawValue"])
                if rec.get("rawValue") is not None
                else None
            ),
            "metricMode": mode,
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
            "down": pas.get("down") if pas.get("down") is not None else rec.get("down"),
            "distance": (
                pas.get("distance")
                if pas.get("distance") is not None
                else rec.get("distance")
            ),
            "yardline100": (
                pas.get("yardline100")
                if pas.get("yardline100") is not None
                else rec.get("yardline100")
            ),
            "yardline": pas.get("yardline") or rec.get("yardline"),
            "airYards": (
                pas.get("airYards")
                if pas.get("airYards") is not None
                else rec.get("airYards")
            ),
            "yardsAfterCatch": (
                pas.get("yardsAfterCatch")
                if pas.get("yardsAfterCatch") is not None
                else rec.get("yardsAfterCatch")
            ),
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
    mode: ScoreMode = "raw",
    missing_peer_seasons: list[int] | None = None,
) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    scored_peers = _with_score_column(peers, mode)
    this_week = scored_peers.filter((pl.col("season") == season) & (pl.col("week") == week))
    peer_map = _peer_value_map(scored_peers)

    all_rows: list[dict[str, Any]] = []
    for rec in this_week.iter_rows(named=True):
        scored = _score_play(rec, peer_map, mode=mode)
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
        "metricMode": mode,
        "peerWindowStartYear": PLAY_HIGHLIGHTS_START_YEAR,
        "top": top,
        "byClass": by_class,
    }
    if missing_peer_seasons:
        payload["missingPeerSeasons"] = list(missing_peer_seasons)
    return payload, peer_map


def _shape_payload(dens: dict[str, Any]) -> dict[str, Any]:
    """Compact play peer shapes for Storage.

    Play expand charts only render ``bins`` (see PlayHighlightList). Exact
    ``valueCounts`` dominate EPA file size and are omitted here; Stage G YTD
    league files still publish counts for player-page KDE reconstruction.
    """
    out: dict[str, Any] = {
        "kind": dens["kind"],
        "xMin": dens["x_min"],
        "xMax": dens["x_max"],
        "yMax": dens["y_max"],
    }
    if dens.get("representation") == "histogram":
        out.update(
            {
                "representation": "histogram",
                "bins": dens["bins"],
            }
        )
    else:
        # Legacy continuous shapes (if any) keep a curve; prefer bins when present.
        curve = dens.get("curve") or []
        if curve:
            out["curve"] = curve
    if dens.get("n_sample") is not None:
        out["nSample"] = int(dens["n_sample"])
    return out


def compact_play_league_shapes_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Strip unused bulk fields from an already-published play league shapes JSON."""
    stats_in = payload.get("stats")
    if not isinstance(stats_in, dict):
        return payload
    stats: dict[str, Any] = {}
    for key, shape in stats_in.items():
        if not isinstance(shape, dict):
            continue
        compact = {
            k: shape[k]
            for k in ("kind", "xMin", "xMax", "yMax", "representation", "bins", "nSample")
            if k in shape
        }
        # Drop empty curves; keep a non-empty curve only when bins are absent.
        curve = shape.get("curve")
        if isinstance(curve, list) and curve and not compact.get("bins"):
            compact["curve"] = curve
        stats[key] = compact
    out = dict(payload)
    out["stats"] = stats
    return out


def compact_local_play_league_shapes(*, root: Path | None = None) -> dict[str, int]:
    """Rewrite local ``dists/league_plays/**/*.json`` without valueCounts bloat."""
    from ballnet.paths import LEAGUE_PLAYS_DIR

    base = root or LEAGUE_PLAYS_DIR
    if not base.is_dir():
        raise FileNotFoundError(f"missing play league shapes dir {base}")
    rewritten = 0
    bytes_before = 0
    bytes_after = 0
    for path in sorted(base.rglob("*.json")):
        raw = path.read_bytes()
        bytes_before += len(raw)
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            continue
        compact = compact_play_league_shapes_payload(payload)
        data = (json.dumps(compact, separators=(",", ":"), ensure_ascii=False) + "\n").encode(
            "utf-8"
        )
        if data == raw:
            bytes_after += len(raw)
            continue
        path.write_bytes(data)
        rewritten += 1
        bytes_after += len(data)
    return {
        "files": rewritten,
        "bytesBefore": bytes_before,
        "bytesAfter": bytes_after,
        "bytesFreed": max(0, bytes_before - bytes_after),
    }


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
    *,
    mode: ScoreMode = "raw",
) -> dict[str, Any]:
    """Observed histograms for peer keys present on the board (expand charts)."""
    stats: dict[str, Any] = {}
    for key in sorted(peer_keys):
        sample = peer_map.get(key)
        if sample is None or sample.size < MIN_PEER_N:
            continue
        play_class = _play_class_from_peer_key(key)
        cat = _EPA_STAT if mode == "epa" else _PLAY_STATS.get(play_class)
        if cat is None:
            continue
        dens = build_league_density(np.asarray(sample, dtype=float), cat)
        stats[key] = _shape_payload(dens)
    return {
        "schemaVersion": 1,
        "season": season,
        "asOfWeek": week,
        "scope": "play_all_time",
        "metricMode": mode,
        "peerWindowStartYear": PLAY_HIGHLIGHTS_START_YEAR,
        "stats": stats,
    }


def build_play_highlights_board(
    season: int, week: int, *, mode: ScoreMode = "raw"
) -> dict[str, Any]:
    peers, missing = _load_all_time_play_peers(season, week)
    payload, _peer_map = _board_from_peers(
        peers, season, week, mode=mode, missing_peer_seasons=missing
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

    paths: dict[str, Path] = {}
    for mode in SCORE_MODES:
        payload, peer_map = _board_from_peers(
            peers, season, week, mode=mode, missing_peer_seasons=missing
        )
        board = play_highlights_board_path(season, week, mode=mode)
        write_json(board, payload)
        shapes = build_play_league_shapes(
            season,
            week,
            peer_map,
            _peer_keys_on_board(payload),
            mode=mode,
        )
        dist = play_highlights_dist_path(season, week, mode=mode)
        write_json(dist, shapes)
        paths[mode] = board
        paths[f"{mode}_dist"] = dist

    return PlayHighlightsPublishResult(
        board=paths["raw"],
        dist=paths["raw_dist"],
        board_epa=paths["epa"],
        dist_epa=paths["epa_dist"],
    )


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
