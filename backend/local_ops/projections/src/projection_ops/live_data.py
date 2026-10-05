"""Deletion-safe nflverse inputs and leakage-safe six-position model frames.

This module owns its cache below ``projection_ops``' local root.  It has no
runtime dependency on the former research tree.  Callers may pass ``tables``
for deterministic/no-network tests.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd

from .config import POSITIONS, SETTINGS
from .scoring import score

SOURCE_SCHEMA_VERSION = 1
TARGET = "fantasy_points"
POSITION_LAG_SOURCES: dict[str, tuple[str, ...]] = {
    "WR": (
        "targets",
        "target_share",
        "air_yards_share",
        "wopr",
        "offense_snaps",
        "offense_snap_pct",
        "receptions",
        "receiving_yards",
        "receiving_tds",
        "rushing_yards",
        "rushing_tds",
        TARGET,
    ),
    "TE": (
        "targets",
        "target_share",
        "air_yards_share",
        "wopr",
        "offense_snaps",
        "offense_snap_pct",
        "receptions",
        "receiving_yards",
        "receiving_tds",
        "rushing_yards",
        "rushing_tds",
        TARGET,
    ),
    "RB": (
        "carries",
        "rushing_yards",
        "rushing_tds",
        "targets",
        "target_share",
        "air_yards_share",
        "wopr",
        "offense_snaps",
        "offense_snap_pct",
        "receptions",
        "receiving_yards",
        "receiving_tds",
        TARGET,
    ),
    "QB": (
        "attempts",
        "completions",
        "passing_yards",
        "passing_tds",
        "interceptions",
        "carries",
        "rushing_yards",
        "rushing_tds",
        "offense_snaps",
        "offense_snap_pct",
        TARGET,
    ),
    "K": (
        "fg_att",
        "fg_made",
        "fg_made_40_49",
        "fg_made_50_59",
        "fg_made_60_",
        "pat_att",
        "pat_made",
        TARGET,
    ),
    "DST": (
        "def_sacks",
        "def_interceptions",
        "def_fumbles",
        "def_tds",
        "def_safeties",
        "blocked_kicks",
        "special_teams_tds",
        "points_allowed",
        TARGET,
    ),
}
_HORIZONS = ("last", "ewma_short", "ewma_med", "last16", "season_1", "season_2", "season_3")
_CONTEXT = ("player_id", "team", "opponent", "roof", "surface", "is_home", "week")
# Historical nflverse lines are mutable closing values, not archived Wednesday as-of values.
# They remain metadata but are deliberately excluded from every model feature set.
_POSITION_ALIASES = {"FB": "RB", "HB": "RB"}


@dataclass(frozen=True)
class LiveTables:
    schedules: pd.DataFrame
    weekly: pd.DataFrame
    rosters: pd.DataFrame
    snaps: pd.DataFrame
    player_ids: pd.DataFrame
    source_metadata: dict[str, Any]


@dataclass(frozen=True)
class PreparedPosition:
    position: str
    train_rows: list[dict[str, Any]]
    forecast_rows: list[dict[str, Any]]
    feature_columns: tuple[str, ...]
    source_metadata: dict[str, Any]
    universe: dict[str, int]


def _pandas(value: Any) -> pd.DataFrame:
    if isinstance(value, pd.DataFrame):
        return value.copy()
    if hasattr(value, "to_pandas"):
        return value.to_pandas()
    return pd.DataFrame(value)


def _canonical_frame_hash(frame: pd.DataFrame) -> str:
    if frame.empty:
        return hashlib.sha256(b"empty").hexdigest()
    work = frame.copy()
    work.columns = work.columns.map(str)
    work = work.reindex(sorted(work.columns), axis=1)
    keys = [c for c in ("season", "week", "game_id", "player_id", "gsis_id", "team") if c in work]
    if keys:
        work = work.sort_values(keys, kind="stable", na_position="last")
    payload = work.to_json(orient="records", date_format="iso", date_unit="us", default_handler=str)
    return hashlib.sha256(payload.encode()).hexdigest()


def _cache_path(table: str, season: int) -> Path:
    path = SETTINGS.cache / "nflverse" / table / f"season={season}" / "part.parquet"
    return SETTINGS.assert_local_write(path)


def _download(table: str, season: int) -> pd.DataFrame:
    import nflreadpy as nfl

    if table == "schedules":
        raw = nfl.load_schedules([season])
    elif table == "weekly":
        raw = nfl.load_player_stats(season, summary_level="week")
    elif table == "rosters":
        raw = nfl.load_rosters_weekly(season)
    elif table == "snaps":
        raw = nfl.load_snap_counts(season)
    elif table == "player_ids":
        raw = nfl.load_ff_playerids()
    else:  # pragma: no cover - internal misuse
        raise ValueError(f"unknown nflverse table: {table}")
    return _pandas(raw)


def load_cached_table(
    table: str,
    seasons: list[int],
    *,
    refresh_seasons: set[int] | None = None,
    loader: Callable[[str, int], Any] | None = None,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Load season partitions, refreshing only requested/missing partitions.

    Downloads are atomically persisted below ``cache/nflverse``.  Therefore a
    later ``refresh=False`` run is independent of any other repository tree.
    """
    refresh = refresh_seasons or set()
    frames: list[pd.DataFrame] = []
    partitions: list[dict[str, Any]] = []
    for season in seasons:
        path = _cache_path(table, season)
        fetched = season in refresh or not path.exists()
        if fetched:
            frame = _pandas((loader or _download)(table, season))
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(".tmp.parquet")
            import polars as pl

            pl.from_pandas(frame).write_parquet(tmp)
            tmp.replace(path)
        else:
            import polars as pl

            frame = pd.DataFrame(pl.read_parquet(path).to_dicts())
        frames.append(frame)
        partitions.append(
            {"season": season, "sha256": _canonical_frame_hash(frame), "refreshed": fetched}
        )
    combined = pd.concat(frames, ignore_index=True, sort=False) if frames else pd.DataFrame()
    return combined, {"table": table, "partitions": partitions, "rows": len(combined)}


def load_live_tables(
    seasons: list[int],
    *,
    target_season: int,
    refresh: bool = True,
    loader: Callable[[str, int], Any] | None = None,
) -> LiveTables:
    refresh_set = {target_season} if refresh else set()
    schedules, sm = load_cached_table(
        "schedules", seasons, refresh_seasons=refresh_set, loader=loader
    )
    weekly, wm = load_cached_table("weekly", seasons, refresh_seasons=refresh_set, loader=loader)
    # Only the target roster is needed and prevents stale historical roster downloads.
    rosters, rm = load_cached_table(
        "rosters", [target_season], refresh_seasons=refresh_set, loader=loader
    )
    snaps, nm = load_cached_table("snaps", seasons, refresh_seasons=refresh_set, loader=loader)
    # The crosswalk is static but gets a local fingerprinted cache partition.
    player_ids, im = load_cached_table(
        "player_ids", [0], refresh_seasons={0} if refresh else set(), loader=loader
    )
    meta = {
        "sourceSchemaVersion": SOURCE_SCHEMA_VERSION,
        "provider": "nflverse/nflreadpy",
        "tables": {"schedules": sm, "weekly": wm, "rosters": rm, "snaps": nm, "player_ids": im},
    }
    meta["sourceFingerprint"] = hashlib.sha256(
        json.dumps(meta, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return LiveTables(schedules, weekly, rosters, snaps, player_ids, meta)


def detect_target_week(season: int, *, refresh: bool = True, today: datetime | None = None) -> int:
    tables = load_live_tables([season], target_season=season, refresh=refresh)
    schedule = tables.schedules.copy()
    if "game_type" in schedule:
        schedule = schedule[schedule.game_type.astype(str).str.upper().eq("REG")]
    if schedule.empty:
        raise ValueError(f"no regular-season schedule for {season}")
    dates = pd.to_datetime(schedule.get("gameday"), errors="coerce", utc=True)
    now = pd.Timestamp(today or datetime.now(timezone.utc))
    pending = schedule[
        schedule.get("home_score").isna() | schedule.get("away_score").isna() | (dates >= now)
    ]
    return int(
        (pending if not pending.empty else schedule)["week"].min()
        if not pending.empty
        else schedule["week"].max()
    )


def _schedule_team_rows(schedules: pd.DataFrame) -> pd.DataFrame:
    s = schedules.copy()
    if "game_type" in s:
        s = s[s.game_type.astype(str).str.upper().eq("REG")]
    required = {"season", "week", "home_team", "away_team"}
    if not required <= set(s):
        raise ValueError(f"schedule missing columns: {sorted(required - set(s))}")
    gametime = s["gametime"].fillna("13:00") if "gametime" in s else "13:00"
    kickoff = pd.to_datetime(s["gameday"].astype(str) + " " + gametime.astype(str), errors="coerce")
    prediction = kickoff.dt.normalize() - pd.to_timedelta((kickoff.dt.dayofweek - 2) % 7, unit="D")

    def side(home: bool) -> pd.DataFrame:
        out = pd.DataFrame(index=s.index)
        for c in ("season", "week", "game_id", "roof", "surface", "spread_line", "total_line"):
            out[c] = s[c] if c in s else None
        out["team"] = s["home_team" if home else "away_team"]
        out["opponent"] = s["away_team" if home else "home_team"]
        out["is_home"] = home
        spread = pd.to_numeric(s.get("spread_line"), errors="coerce")
        total = pd.to_numeric(s.get("total_line"), errors="coerce")
        out["spread_line"] = spread if home else -spread
        out["vegas_implied_team_pts"] = (total - spread) / 2 if home else (total + spread) / 2
        out["points_allowed"] = s.get("away_score") if home else s.get("home_score")
        out["kickoff"] = kickoff
        out["prediction_timestamp"] = prediction
        return out

    return pd.concat([side(True), side(False)], ignore_index=True)


def _normalize_weekly(weekly: pd.DataFrame) -> pd.DataFrame:
    w = weekly.copy()
    rename = {}
    if "player_id" not in w and "gsis_id" in w:
        rename["gsis_id"] = "player_id"
    if "player_name" not in w and "player_display_name" in w:
        rename["player_display_name"] = "player_name"
    if "interceptions" not in w and "passing_interceptions" in w:
        rename["passing_interceptions"] = "interceptions"
    w = w.rename(columns=rename)
    if "position" in w:
        w["position"] = w.position.astype(str).str.upper().replace(_POSITION_ALIASES)
    return w


def _availability_column(frame: pd.DataFrame) -> str | None:
    # status_description_abbr is the official compact weekly-roster field.
    return next(
        (c for c in ("status_description_abbr", "status", "report_status") if c in frame), None
    )


def _forecast_slate(
    tables: LiveTables, season: int, week: int, position: str
) -> tuple[pd.DataFrame, dict[str, int]]:
    schedule = _schedule_team_rows(tables.schedules)
    schedule = schedule[(schedule.season == season) & (schedule.week == week)].copy()
    if schedule.empty:
        raise ValueError(f"no regular-season schedule for {season} week {week}")
    if position == "DST":
        slate = schedule.copy()
        slate["player_id"] = slate.team.astype(str) + "_DST"
        slate["player_name"] = slate.team.astype(str) + " DST"
        slate["position"] = "DST"
        slate["availability"] = None
        return slate, {"scheduled": len(schedule), "included": len(slate), "excluded": 0}

    r = tables.rosters.copy()
    if "game_type" in r:
        r = r[r.game_type.astype(str).str.upper().eq("REG")]
    rename = {}
    if "player_id" not in r and "gsis_id" in r:
        rename["gsis_id"] = "player_id"
    if "player_name" not in r:
        for c in ("full_name", "player_display_name"):
            if c in r:
                rename[c] = "player_name"
                break
    r = r.rename(columns=rename)
    if not {"player_id", "team", "position"} <= set(r):
        raise ValueError("weekly roster lacks player identity/team/position")
    r["position"] = r.position.astype(str).str.upper().replace(_POSITION_ALIASES)
    if "season" in r:
        r = r[r.season == season]
    if "week" in r:
        weeks = pd.to_numeric(r.week, errors="coerce")
        chosen = week if (weeks == week).any() else weeks[weeks <= week].max()
        r = r[weeks == chosen] if pd.notna(chosen) else r.iloc[0:0]
    r = r[(r.position == position) & r.player_id.notna() & r.team.notna()].copy()
    avail = _availability_column(r)
    r["availability"] = r[avail].where(r[avail].notna(), None) if avail else None
    if "player_name" not in r:
        r["player_name"] = r.player_id
    r = r.sort_values(["player_id", "team"]).drop_duplicates("player_id", keep="last")
    scheduled_count = len(r)
    slate = r[["player_id", "player_name", "team", "position", "availability"]].merge(
        schedule, on="team", how="inner"
    )
    return slate, {
        "scheduled": scheduled_count,
        "included": len(slate),
        "excluded": scheduled_count - len(slate),
    }


def _attach_snaps(
    weekly: pd.DataFrame, snaps: pd.DataFrame, player_ids: pd.DataFrame
) -> pd.DataFrame:
    if snaps.empty:
        raise ValueError("snap_counts is required for audited feature parity")
    sn = snaps.copy()
    if "offense_pct" in sn and "offense_snap_pct" not in sn:
        sn = sn.rename(columns={"offense_pct": "offense_snap_pct"})
    if "player_id" not in sn:
        if "gsis_id" in sn:
            sn = sn.rename(columns={"gsis_id": "player_id"})
        elif "pfr_player_id" in sn and {"pfr_id", "gsis_id"} <= set(player_ids):
            cross = (
                player_ids[["pfr_id", "gsis_id"]]
                .dropna()
                .drop_duplicates("pfr_id")
                .rename(columns={"pfr_id": "pfr_player_id", "gsis_id": "player_id"})
            )
            sn = sn.merge(cross, on="pfr_player_id", how="left")
    required = {"player_id", "season", "week"}
    if not required <= set(sn):
        raise ValueError("snap_counts cannot be mapped to GSIS player ids")
    keep = [
        c for c in ("player_id", "season", "week", "offense_snaps", "offense_snap_pct") if c in sn
    ]
    if len(keep) == 3:
        raise ValueError("snap_counts lacks offense snap measures")
    sn = sn[keep].dropna(subset=["player_id"]).drop_duplicates(["player_id", "season", "week"])
    return weekly.merge(sn, on=["player_id", "season", "week"], how="left", suffixes=("", "_snap"))


def _historical_panel(tables: LiveTables, position: str) -> pd.DataFrame:
    w = _normalize_weekly(tables.weekly)
    if position in {"QB", "RB", "WR", "TE"}:
        w = _attach_snaps(w, tables.snaps, tables.player_ids)
    schedule = _schedule_team_rows(tables.schedules)
    if "season_type" in w:
        w = w[w.season_type.astype(str).str.upper().eq("REG")]
    if position == "DST":
        components = (
            "def_sacks",
            "def_interceptions",
            "def_fumbles",
            "def_tds",
            "def_safeties",
            "def_fg_blocks",
            "def_pat_blocks",
            "def_punt_blocks",
            "special_teams_tds",
        )
        for c in components:
            if c not in w:
                w[c] = 0.0
        agg = w.groupby(["season", "week", "team"], as_index=False)[list(components)].sum(
            min_count=1
        )
        panel = schedule.merge(agg, on=["season", "week", "team"], how="left")
        panel["blocked_kicks"] = sum(
            pd.to_numeric(panel[c], errors="coerce").fillna(0)
            for c in ("def_fg_blocks", "def_pat_blocks", "def_punt_blocks")
        )
        panel["player_id"] = panel.team.astype(str) + "_DST"
        panel["player_name"] = panel.team.astype(str) + " DST"
        panel["position"] = "DST"
    else:
        panel = w[w.position.eq(position)].merge(
            schedule, on=["season", "week", "team"], how="inner", suffixes=("", "_schedule")
        )
    panel[TARGET] = panel.apply(lambda row: score(position, row), axis=1)
    # Deliberately do not censor negative QB/RB/WR/TE outcomes.
    return panel[panel.player_id.notna() & panel.team.notna() & panel.opponent.notna()].copy()


def _ewma(values: np.ndarray, half_life: float) -> float:
    finite = np.isfinite(values)
    if not finite.any():
        return np.nan
    ages = np.arange(len(values) - 1, -1, -1, dtype=float)
    weights = (0.5 ** (ages / half_life))[finite]
    return float(np.dot(weights, values[finite]) / weights.sum())


def _add_lags(frame: pd.DataFrame, sources: tuple[str, ...]) -> pd.DataFrame:
    out = frame.copy()
    for src in sources:
        if src not in out:
            out[src] = np.nan
        for h in _HORIZONS:
            out[f"{src}_{h}"] = np.nan
    out["n_prior_games"] = 0.0
    out["days_since_last_game"] = np.nan
    out["kickoff"] = pd.to_datetime(out.kickoff, errors="coerce")
    out["prediction_timestamp"] = pd.to_datetime(out.prediction_timestamp, errors="coerce")
    for _, idx in out.groupby("player_id", sort=False).groups.items():
        ids = list(idx)
        for i in ids:
            ts = out.at[i, "prediction_timestamp"]
            eligible = [
                j
                for j in ids
                if j != i
                and pd.notna(out.at[j, "kickoff"])
                and pd.notna(ts)
                and out.at[j, "kickoff"] + timedelta(hours=4) < ts
            ]
            eligible.sort(key=lambda j: out.at[j, "kickoff"])
            out.at[i, "n_prior_games"] = len(eligible)
            if not eligible:
                continue
            if pd.notna(out.at[i, "kickoff"]):
                out.at[i, "days_since_last_game"] = (
                    out.at[i, "kickoff"] - out.at[eligible[-1], "kickoff"]
                ).total_seconds() / 86400
            row_season = out.at[i, "season"]
            for src in sources:
                vals = pd.to_numeric(out.loc[eligible, src], errors="coerce").to_numpy(float)
                out.at[i, f"{src}_last"] = vals[-1]
                out.at[i, f"{src}_ewma_short"] = _ewma(vals, 4)
                out.at[i, f"{src}_ewma_med"] = _ewma(vals, 16)
                out.at[i, f"{src}_last16"] = (
                    np.nanmean(vals[-16:]) if np.isfinite(vals[-16:]).any() else np.nan
                )
                seasons = pd.to_numeric(out.loc[eligible, "season"], errors="coerce").to_numpy(
                    float
                )
                for n in (1, 2, 3):
                    mask = (
                        (seasons >= row_season - n)
                        & (seasons <= row_season - 1)
                        & np.isfinite(vals)
                    )
                    if mask.any():
                        out.at[i, f"{src}_season_{n}"] = float(vals[mask].mean())
    return out


def prepare_position_data(
    season: int,
    week: int,
    position: str,
    *,
    n_train_seasons: int = 3,
    refresh: bool = True,
    tables: LiveTables | None = None,
) -> PreparedPosition:
    position = position.upper()
    if position not in POSITIONS:
        raise ValueError(f"unsupported position: {position}")
    if n_train_seasons < 1:
        raise ValueError("n_train_seasons must be >= 1")
    seasons = list(range(season - n_train_seasons, season + 1))
    tables = tables or load_live_tables(seasons, target_season=season, refresh=refresh)
    history = _historical_panel(tables, position)
    history = history[
        (history.season < season) | ((history.season == season) & (history.week < week))
    ].copy()
    if history.empty:
        raise ValueError(f"no completed training rows for {position}")
    slate, universe = _forecast_slate(tables, season, week, position)
    slate[TARGET] = np.nan
    slate["_forecast_row"] = True
    history["_forecast_row"] = False
    combined = pd.concat([history, slate], ignore_index=True, sort=False)
    combined = _add_lags(combined, POSITION_LAG_SOURCES[position])
    train = combined[~combined._forecast_row & combined[TARGET].notna()].copy()
    forecast = combined[combined._forecast_row].copy()
    candidates = [
        *(f"{s}_{h}" for s in POSITION_LAG_SOURCES[position] for h in _HORIZONS),
        "n_prior_games",
        "days_since_last_game",
        *_CONTEXT,
    ]
    features = []
    for c in dict.fromkeys(candidates):
        if c not in train or c not in forecast:
            continue
        # Skip columns which cannot be imputed by the frozen model preprocessor.
        if train[c].notna().any():
            features.append(c)
    for frame in (train, forecast):
        frame.replace({pd.NA: None}, inplace=True)
    meta = dict(tables.source_metadata)
    meta["positionSourceFingerprint"] = hashlib.sha256(
        (meta.get("sourceFingerprint", "") + position + str(season) + str(week)).encode()
    ).hexdigest()
    return PreparedPosition(
        position,
        train.to_dict("records"),
        forecast.to_dict("records"),
        tuple(features),
        meta,
        universe,
    )


def historical_position_frame(
    tables: LiveTables, position: str
) -> tuple[pd.DataFrame, tuple[str, ...]]:
    """Return one fully lagged REG history frame for frozen rolling validation."""
    position = position.upper()
    panel = _historical_panel(tables, position)
    panel["_forecast_row"] = False
    frame = _add_lags(panel, POSITION_LAG_SOURCES[position])
    candidates = [
        *(f"{source}_{h}" for source in POSITION_LAG_SOURCES[position] for h in _HORIZONS),
        "n_prior_games",
        "days_since_last_game",
        *_CONTEXT,
    ]
    features = tuple(
        column
        for column in dict.fromkeys(candidates)
        if column in frame and frame[column].notna().any()
    )
    if "vegas_implied_team_pts" in features:
        raise RuntimeError("historical closing lines must not enter the model feature set")
    return frame, features


def resolve_finalized_and_target(schedules: pd.DataFrame, season: int, finalized_week: int) -> int:
    regular = schedules.copy()
    if "game_type" in regular:
        regular = regular[regular.game_type.astype(str).str.upper().eq("REG")]
    completed = regular[(regular.season == season) & (regular.week == finalized_week)]
    if completed.empty or completed.home_score.isna().any() or completed.away_score.isna().any():
        raise RuntimeError(f"week {finalized_week} is not schedule-final")
    later = regular[(regular.season == season) & (regular.week > finalized_week)].sort_values(
        ["week", "gameday"]
    )
    if later.empty:
        raise RuntimeError("no next scheduled regular-season target week")
    return int(later.week.iloc[0])
