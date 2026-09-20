"""Stage H — weekly highlight boards from the Stage B spine (not Stage G)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import numpy as np
import polars as pl

from ballnet.catalog.registry import stats_for_group
from ballnet.catalog.types import StatDefinition
from ballnet.density import build_league_density
from ballnet.fantasy_rank import FantasyPosRank, attach_fantasy_pos_rank, fantasy_pos_ranks
from ballnet.paths import HIGHLIGHTS_DIR, LEAGUE_WEEKLY_DIR, SPINE_DIR, ensure_data_dirs
from ballnet.publish import PUBLISHABLE_GROUPS, default_as_of_week
from ballnet.scoring import MIN_PEER_N, gaussian_tail_one_in_n, oriented_z_score, snap_one_in_n

_JSON_DUMP_KW: dict[str, Any] = {"separators": (",", ":"), "ensure_ascii": False}

TOP_N = 25
PER_GROUP_N = 8
# NGS-era spine coverage; all-time peers start here.
HIGHLIGHTS_START_YEAR = 2016

# OL / punter / returner: sparse or unusable weekly box columns for curated z-scores.
HIGHLIGHT_GROUPS: tuple[str, ...] = tuple(
    g for g in PUBLISHABLE_GROUPS if g not in ("ol", "punter")
)


@dataclass(frozen=True)
class HighlightsPublishResult:
    board: Path
    dist_paths: list[Path] = field(default_factory=list)


@dataclass(frozen=True)
class HighlightStat:
    """One catalog id scored from a single spine week."""

    stat_id: str
    label: str
    higher_is_better: bool
    # Build a numeric column named `_value` (and optional `_volume` for floors).
    build: Callable[[pl.DataFrame], pl.DataFrame]
    volume_floor: float | None = None
    # Rare event counts (FF, INT) need a floor so a single fluke does not dominate.
    min_value: float | None = None


def _allowlist_for_group(group: str) -> list[HighlightStat]:
    """Curated single-game stats — volumes + clear rates; skip snap%/cushion noise."""

    def meta(stat_id: str) -> tuple[str, bool]:
        for s in stats_for_group(group):
            if s.id == stat_id:
                return s.id.replace("_", " "), s.higher_is_better
        return stat_id.replace("_", " "), True

    def simple(
        stat_id: str,
        spine_col: str,
        *,
        volume_col: str | None = None,
        floor: float | None = None,
        min_value: float | None = None,
    ) -> HighlightStat:
        label, hib = meta(stat_id)

        def build(df: pl.DataFrame) -> pl.DataFrame:
            out = df.with_columns(pl.col(spine_col).cast(pl.Float64).alias("_value"))
            if volume_col and volume_col in df.columns:
                out = out.with_columns(pl.col(volume_col).cast(pl.Float64).alias("_volume"))
            else:
                out = out.with_columns(pl.lit(None).cast(pl.Float64).alias("_volume"))
            return out

        return HighlightStat(stat_id, label, hib, build, floor, min_value)

    def ratio(
        stat_id: str,
        num: str,
        den: str,
        *,
        floor: float,
    ) -> HighlightStat:
        label, hib = meta(stat_id)

        def build(df: pl.DataFrame) -> pl.DataFrame:
            return df.with_columns(
                pl.when(pl.col(den).cast(pl.Float64) > 0)
                .then(pl.col(num).cast(pl.Float64) / pl.col(den).cast(pl.Float64))
                .otherwise(None)
                .alias("_value"),
                pl.col(den).cast(pl.Float64).alias("_volume"),
            )

        return HighlightStat(stat_id, label, hib, build, floor)

    def combined_tackles(stat_id: str = "tackles_combined") -> HighlightStat:
        label, hib = meta(stat_id)

        def build(df: pl.DataFrame) -> pl.DataFrame:
            return df.with_columns(
                (
                    pl.col("def_tackles_solo").fill_null(0).cast(pl.Float64)
                    + pl.col("def_tackle_assists").fill_null(0).cast(pl.Float64)
                ).alias("_value"),
                pl.lit(None).cast(pl.Float64).alias("_volume"),
            )

        return HighlightStat(stat_id, label, hib, build, None)

    def cpoe() -> HighlightStat:
        label, hib = meta("cpoe")

        def build(df: pl.DataFrame) -> pl.DataFrame:
            ngs = "ngs_pass_completion_percentage_above_expectation"
            exprs = []
            if ngs in df.columns:
                exprs.append(pl.col(ngs).cast(pl.Float64))
            exprs.append(pl.col("passing_cpoe").cast(pl.Float64))
            return df.with_columns(
                pl.coalesce(exprs).alias("_value"),
                pl.col("attempts").cast(pl.Float64).alias("_volume"),
            )

        return HighlightStat("cpoe", label, hib, build, 10.0)

    if group == "qb":
        return [
            simple("passing_yards", "passing_yards", volume_col="attempts", floor=10),
            simple("passing_tds", "passing_tds", volume_col="attempts", floor=10),
            simple("passing_epa", "passing_epa", volume_col="attempts", floor=10),
            cpoe(),
            ratio("completion_pct", "completions", "attempts", floor=15),
            simple("rushing_yards", "rushing_yards", volume_col="carries", floor=3),
        ]
    if group == "backfield":
        return [
            simple("rushing_yards", "rushing_yards", volume_col="carries", floor=8),
            simple("rushing_tds", "rushing_tds", volume_col="carries", floor=5),
            simple("rushing_epa", "rushing_epa", volume_col="carries", floor=8),
            ratio("yards_per_carry", "rushing_yards", "carries", floor=8),
            simple("receptions", "receptions", volume_col="targets", floor=2),
            simple("receiving_yards", "receiving_yards", volume_col="targets", floor=2),
        ]
    if group == "pass_catcher":
        return [
            simple("receiving_yards", "receiving_yards", volume_col="targets", floor=3),
            simple("receptions", "receptions", volume_col="targets", floor=3),
            simple("receiving_tds", "receiving_tds", volume_col="targets", floor=2),
            simple("receiving_epa", "receiving_epa", volume_col="targets", floor=3),
            simple("targets", "targets", volume_col="targets", floor=4),
        ]
    if group == "def_front":
        return [
            combined_tackles(),
            simple("sacks", "def_sacks", min_value=1.5),
            simple("tackles_for_loss", "def_tackles_for_loss", min_value=2),
            simple("qb_hits", "def_qb_hits", min_value=3),
            simple("forced_fumbles", "def_fumbles_forced", min_value=2),
            simple("interceptions", "def_interceptions", min_value=2),
        ]
    if group == "secondary":
        return [
            simple("interceptions", "def_interceptions", min_value=2),
            simple("passes_defended", "def_pass_defended", min_value=2),
            combined_tackles(),
            simple("forced_fumbles", "def_fumbles_forced", min_value=2),
        ]
    if group == "kicker":
        return [
            simple("fg_made", "fg_made", volume_col="fg_att", floor=1),
            ratio("fg_pct", "fg_made", "fg_att", floor=2),
            simple("fg_long", "fg_long", volume_col="fg_att", floor=1),
        ]
    return []


def _catalog_stat(group: str, stat_id: str) -> StatDefinition | None:
    for s in stats_for_group(group):
        if s.id == stat_id:
            return s
    return None


def _resolve_spec(group: str, spec: HighlightStat) -> HighlightStat:
    cat = _catalog_stat(group, spec.stat_id)
    if cat is None:
        return spec
    return HighlightStat(
        spec.stat_id,
        cat.id.replace("_", " "),
        cat.higher_is_better,
        spec.build,
        spec.volume_floor,
        spec.min_value,
    )


def _qualified_values(df: pl.DataFrame, spec: HighlightStat) -> pl.DataFrame:
    """Volume-qualified finite values. Does not apply `min_value` (board-only)."""
    if df.is_empty():
        return df
    built = spec.build(df)
    built = built.filter(pl.col("_value").is_not_null() & pl.col("_value").is_finite())
    if spec.volume_floor is not None:
        built = built.filter(
            pl.col("_volume").is_not_null() & (pl.col("_volume") >= spec.volume_floor)
        )
    return built


def _score_stat(
    peer_df: pl.DataFrame,
    week_df: pl.DataFrame,
    group: str,
    spec: HighlightStat,
) -> list[dict[str, Any]]:
    """Z vs all-time qualified player-weeks; board rows are this week's games only."""
    peer_vals = _qualified_values(peer_df, spec)
    if peer_vals.height < MIN_PEER_N:
        return []
    peers = peer_vals["_value"].to_list()
    week_vals = _qualified_values(week_df, spec)
    if week_vals.is_empty():
        return []

    rows: list[dict[str, Any]] = []
    for rec in week_vals.iter_rows(named=True):
        val = float(rec["_value"])
        if spec.min_value is not None and val < spec.min_value:
            continue
        z = oriented_z_score(val, peers, higher_is_better=spec.higher_is_better)
        if z is None:
            continue
        one_in_n = gaussian_tail_one_in_n(z)
        rows.append(
            {
                "playerId": rec["player_id"],
                "name": rec.get("player_display_name") or "",
                "position": rec.get("position_code") or rec.get("position") or "",
                "team": rec.get("team") or "",
                "opponent": rec.get("opponent_team") or "",
                "positionGroup": group,
                "statId": spec.stat_id,
                "statLabel": spec.label,
                "value": val,
                "zScore": round(z, 3),
                "peerN": len(peers),
                "oneInN": one_in_n,
                "rarityTier": snap_one_in_n(one_in_n),
            }
        )
    return rows


def _shape_payload(dens: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {
        "kind": dens["kind"],
        "xMin": dens["x_min"],
        "xMax": dens["x_max"],
        "yMax": dens["y_max"],
        "curve": dens.get("curve") or [],
    }
    if dens.get("n_sample") is not None:
        out["nSample"] = int(dens["n_sample"])
    if dens.get("lower_bound") is not None:
        out["lowerBound"] = dens["lower_bound"]
    if dens.get("upper_bound") is not None:
        out["upperBound"] = dens["upper_bound"]
    return out


def _league_weekly_group_payload(
    season: int,
    week: int,
    group: str,
    peer_df: pl.DataFrame,
    specs: list[HighlightStat],
) -> dict[str, Any]:
    stats: dict[str, Any] = {}
    for spec in specs:
        cat = _catalog_stat(group, spec.stat_id)
        if cat is None:
            continue
        sample_df = _qualified_values(peer_df, spec)
        if sample_df.is_empty():
            continue
        sample = sample_df["_value"].to_numpy().astype(float)
        dens = build_league_density(np.asarray(sample, dtype=float), cat)
        stats[spec.stat_id] = _shape_payload(dens)
    return {
        "schemaVersion": 1,
        "season": season,
        "asOfWeek": week,
        "positionGroup": group,
        "scope": "league_game_all_time",
        "stats": stats,
    }


def _load_spine(season: int) -> pl.DataFrame:
    path = SPINE_DIR / f"player_week_{season}.parquet"
    if not path.is_file():
        raise FileNotFoundError(f"missing spine {path}")
    return pl.read_parquet(path)


def _load_all_time_peers(season: int, week: int) -> pl.DataFrame:
    """Prior full seasons (HIGHLIGHTS_START_YEAR..S-1) + current season weeks <= W."""
    if season < HIGHLIGHTS_START_YEAR:
        raise ValueError(f"season {season} is before highlights start {HIGHLIGHTS_START_YEAR}")
    frames: list[pl.DataFrame] = []
    for y in range(HIGHLIGHTS_START_YEAR, season):
        frames.append(
            _load_spine(y).filter(pl.col("position_group").is_not_null())
        )
    frames.append(
        _load_spine(season).filter(
            (pl.col("week") <= week) & pl.col("position_group").is_not_null()
        )
    )
    if len(frames) == 1:
        return frames[0]
    return pl.concat(frames, how="diagonal_relaxed")


def _collapse_by_player(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One primary per player (highest zScore); nest the rest as `also`."""
    # Caller must pass rows sorted by zScore desc so first sighting is the primary.
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
        also: list[dict[str, Any]] = []
        for secondary in group_rows[1:]:
            entry = dict(secondary)
            entry.pop("also", None)
            entry.pop("rank", None)
            also.append(entry)
        if also:
            primary["also"] = also
        else:
            primary.pop("also", None)
        out.append(primary)
    return out


def _board_from_peers(
    peers: pl.DataFrame,
    season: int,
    week: int,
    *,
    ranks: dict[str, FantasyPosRank] | None = None,
) -> dict[str, Any]:
    this_week = peers.filter(
        (pl.col("season") == season) & (pl.col("week") == week)
    )

    all_rows: list[dict[str, Any]] = []
    by_group: dict[str, list[dict[str, Any]]] = {g: [] for g in HIGHLIGHT_GROUPS}

    for group in HIGHLIGHT_GROUPS:
        peer_g = peers.filter(pl.col("position_group") == group)
        week_g = this_week.filter(pl.col("position_group") == group)
        for spec in _allowlist_for_group(group):
            spec = _resolve_spec(group, spec)
            all_rows.extend(_score_stat(peer_g, week_g, group, spec))

    all_rows.sort(key=lambda r: r["zScore"], reverse=True)

    # Cap per-group contribution so sparse defensive events cannot crowd out offense.
    balanced: list[dict[str, Any]] = []
    for group in HIGHLIGHT_GROUPS:
        group_rows = [r for r in all_rows if r["positionGroup"] == group]
        collapsed = _collapse_by_player(group_rows)[:PER_GROUP_N]
        balanced.extend(collapsed)
    balanced.sort(key=lambda r: r["zScore"], reverse=True)

    top: list[dict[str, Any]] = []
    for i, row in enumerate(balanced[:TOP_N], start=1):
        entry = dict(row)
        entry["rank"] = i
        attach_fantasy_pos_rank(entry, entry["playerId"], ranks)
        top.append(entry)

    for group in HIGHLIGHT_GROUPS:
        group_rows = [r for r in all_rows if r["positionGroup"] == group]
        collapsed = _collapse_by_player(group_rows)[:PER_GROUP_N]
        for i, row in enumerate(collapsed, start=1):
            entry = dict(row)
            entry["rank"] = i
            attach_fantasy_pos_rank(entry, entry["playerId"], ranks)
            by_group[group].append(entry)

    return {
        "schemaVersion": 1,
        "season": season,
        "week": week,
        "generatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "top": top,
        "byGroup": by_group,
    }


def build_highlights_board(season: int, week: int) -> dict[str, Any]:
    """Compute weekly board payload from spines (does not write)."""
    ranks = fantasy_pos_ranks(season, week)
    peers = _load_all_time_peers(season, week)
    return _board_from_peers(peers, season, week, ranks=ranks)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, **_JSON_DUMP_KW)


def max_week_in_spine(season: int) -> int | None:
    """Highest REG week present in the spine, or None if the file is missing."""
    path = SPINE_DIR / f"player_week_{season}.parquet"
    if not path.is_file():
        return None
    week = pl.read_parquet(path, columns=["week"]).select(pl.col("week").max()).item()
    return int(week) if week is not None else None


def weeks_to_publish(season: int) -> list[int]:
    """Weeks 1..N for a season (spine max, capped at the season's REG length)."""
    cap = default_as_of_week(season)
    spine_max = max_week_in_spine(season)
    if spine_max is None:
        raise FileNotFoundError(
            f"missing spine for {season}; run `ballnet spine --season {season}` first"
        )
    last = min(cap, spine_max)
    return list(range(1, last + 1))


def publish_highlights(season: int, week: int) -> HighlightsPublishResult:
    """Write board + allowlist all-time game KDEs for the same week."""
    ensure_data_dirs()
    peers = _load_all_time_peers(season, week)
    ranks = fantasy_pos_ranks(season, week)
    payload = _board_from_peers(peers, season, week, ranks=ranks)
    board = HIGHLIGHTS_DIR / str(season) / f"w{week}.json"
    _write_json(board, payload)

    dist_paths: list[Path] = []
    for group in HIGHLIGHT_GROUPS:
        peer_g = peers.filter(pl.col("position_group") == group)
        specs = [_resolve_spec(group, spec) for spec in _allowlist_for_group(group)]
        dist = _league_weekly_group_payload(season, week, group, peer_g, specs)
        out = LEAGUE_WEEKLY_DIR / str(season) / f"w{week}" / f"{group}.json"
        _write_json(out, dist)
        dist_paths.append(out)
    return HighlightsPublishResult(board=board, dist_paths=dist_paths)


def publish_highlights_range(
    start: int,
    end: int,
) -> list[HighlightsPublishResult]:
    """Publish every available week for seasons start..end (inclusive), ascending."""
    if end < start:
        raise ValueError("--end must be >= --start")
    results: list[HighlightsPublishResult] = []
    for season in range(start, end + 1):
        for week in weeks_to_publish(season):
            results.append(publish_highlights(season, week))
    return results
