"""Play-grain panel from cached nflverse PBP (parallel to Stage B spine).

Does not widen Stage B. Reads `data/raw/pbp_{season}.parquet` + weekly rosters,
classifies actor-centric plays, and writes `data/plays/plays_{season}.parquet`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import polars as pl

from ballnet.paths import PLAYS_DIR, RAW_DIR, ensure_data_dirs
from ballnet.positions import map_position

PLAY_CLASSES: tuple[str, ...] = (
    "reception",
    "rush",
    "pass",
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

_CLASSIFIED_COLS: list[str] = [
    "season",
    "week",
    "game_id",
    "play_id",
    "play_class",
    "metric_id",
    "value",
    "epa",
    "player_id",
    "player_display_name",
    "team",
    "opponent_team",
    "quarter",
    "clock",
    "game_seconds_remaining",
    "touchdown",
    "desc",
]

_PANEL_COLS: list[str] = [
    "season",
    "week",
    "game_id",
    "play_id",
    "play_class",
    "metric_id",
    "value",
    "epa",
    "player_id",
    "player_display_name",
    "team",
    "opponent_team",
    "position_code",
    "position_group",
    "quarter",
    "clock",
    "game_seconds_remaining",
    "touchdown",
    "desc",
]


def play_panel_path(season: int) -> Path:
    return PLAYS_DIR / f"plays_{season}.parquet"


def _require_cols(df: pl.DataFrame, cols: list[str], *, label: str) -> None:
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise ValueError(f"{label} missing columns: {missing}")


def _load_pbp(season: int) -> pl.DataFrame:
    path = RAW_DIR / f"pbp_{season}.parquet"
    if not path.is_file():
        raise FileNotFoundError(
            f"missing PBP cache {path}; run `ballnet fetch --season {season}` first"
        )
    return pl.read_parquet(path)


def _roster_positions(season: int) -> pl.DataFrame:
    """Weekly GSIS → position_code / position_group from rosterson disk."""
    path = RAW_DIR / f"rosters_{season}.parquet"
    if not path.is_file():
        raise FileNotFoundError(
            f"missing rosters cache {path}; run `ballnet fetch --season {season}` first"
        )
    rost = pl.read_parquet(path)
    _require_cols(rost, ["gsis_id", "week", "position"], label="rosters")
    codes = [map_position(p) for p in rost.get_column("position").to_list()]
    return (
        rost.with_columns(
            pl.col("gsis_id").cast(pl.Utf8).alias("player_id"),
            pl.col("week").cast(pl.Int32),
            pl.Series("position_code", [c[0] for c in codes]),
            pl.Series("position_group", [c[1] for c in codes]),
        )
        .filter(pl.col("player_id").is_not_null() & (pl.col("player_id") != ""))
        .select(["player_id", "week", "position_code", "position_group"])
        .unique(subset=["player_id", "week"], keep="last")
    )


def _flag_true(col: str) -> pl.Expr:
    """nflverse flags arrive as 0/1 floats (or bool)."""
    return pl.col(col).fill_null(0).cast(pl.Float64) > 0.5


def _base_context(df: pl.DataFrame) -> pl.DataFrame:
    qtr = pl.col("qtr").cast(pl.Int32, strict=False) if "qtr" in df.columns else pl.lit(None).cast(pl.Int32)
    clock = pl.col("time").cast(pl.Utf8) if "time" in df.columns else pl.lit(None).cast(pl.Utf8)
    gsr = (
        pl.col("game_seconds_remaining").cast(pl.Float64)
        if "game_seconds_remaining" in df.columns
        else pl.lit(None).cast(pl.Float64)
    )
    td = _flag_true("touchdown") if "touchdown" in df.columns else pl.lit(False)
    desc = pl.col("desc").cast(pl.Utf8) if "desc" in df.columns else pl.lit(None).cast(pl.Utf8)
    epa = pl.col("epa").cast(pl.Float64) if "epa" in df.columns else pl.lit(None).cast(pl.Float64)
    return df.with_columns(
        pl.col("season").cast(pl.Int32),
        pl.col("week").cast(pl.Int32),
        pl.col("game_id").cast(pl.Utf8),
        pl.col("play_id").cast(pl.Int64, strict=False),
        qtr.alias("quarter"),
        clock.alias("clock"),
        gsr.alias("game_seconds_remaining"),
        td.alias("touchdown"),
        desc.alias("desc"),
        epa.alias("epa"),
        pl.col("posteam").cast(pl.Utf8).alias("team"),
        pl.col("defteam").cast(pl.Utf8).alias("opponent_team"),
    )


def _actor_frame(
    df: pl.DataFrame,
    *,
    play_class: str,
    metric_id: str,
    player_id_col: str,
    name_col: str,
    value_expr: pl.Expr,
    team_col: str = "team",
    opponent_col: str = "opponent_team",
) -> pl.DataFrame:
    return (
        df.filter(pl.col(player_id_col).is_not_null() & (pl.col(player_id_col).cast(pl.Utf8) != ""))
        .with_columns(
            pl.lit(play_class).alias("play_class"),
            pl.lit(metric_id).alias("metric_id"),
            value_expr.cast(pl.Float64).alias("value"),
            pl.col(player_id_col).cast(pl.Utf8).alias("player_id"),
            pl.col(name_col).cast(pl.Utf8).alias("player_display_name"),
            pl.col(team_col).cast(pl.Utf8).alias("team"),
            pl.col(opponent_col).cast(pl.Utf8).alias("opponent_team"),
        )
        .filter(pl.col("value").is_not_null() & pl.col("value").is_finite())
        .select(_CLASSIFIED_COLS)
    )


def _classify_plays(pbp: pl.DataFrame) -> pl.DataFrame:
    _require_cols(
        pbp,
        ["season", "week", "game_id", "play_id", "posteam", "defteam"],
        label="pbp",
    )
    base = _base_context(pbp)
    frames: list[pl.DataFrame] = []

    if "complete_pass" in base.columns and "receiver_player_id" in base.columns:
        rec = base.filter(_flag_true("complete_pass"))
        yards = (
            pl.col("receiving_yards")
            if "receiving_yards" in rec.columns
            else pl.col("yards_gained")
        )
        name = "receiver_player_name" if "receiver_player_name" in rec.columns else "receiver_player_id"
        frames.append(
            _actor_frame(
                rec,
                play_class="reception",
                metric_id="receiving_yards",
                player_id_col="receiver_player_id",
                name_col=name,
                value_expr=yards,
            )
        )

    if "complete_pass" in base.columns and "passer_player_id" in base.columns:
        pas = base.filter(_flag_true("complete_pass"))
        yards = (
            pl.col("passing_yards")
            if "passing_yards" in pas.columns
            else pl.col("yards_gained")
        )
        name = "passer_player_name" if "passer_player_name" in pas.columns else "passer_player_id"
        frames.append(
            _actor_frame(
                pas,
                play_class="pass",
                metric_id="passing_yards",
                player_id_col="passer_player_id",
                name_col=name,
                value_expr=yards,
            )
        )

    rush_mask = pl.lit(False)
    if "play_type" in base.columns:
        rush_mask = rush_mask | (pl.col("play_type") == "run")
    if "rush_attempt" in base.columns:
        rush_mask = rush_mask | _flag_true("rush_attempt")
    if "play_type" in base.columns:
        rush_mask = rush_mask & ~pl.col("play_type").is_in(["qb_kneel", "qb_spike"])
    if "rusher_player_id" in base.columns:
        rush = base.filter(rush_mask)
        yards = (
            pl.col("rushing_yards")
            if "rushing_yards" in rush.columns
            else pl.col("yards_gained")
        )
        name = "rusher_player_name" if "rusher_player_name" in rush.columns else "rusher_player_id"
        frames.append(
            _actor_frame(
                rush,
                play_class="rush",
                metric_id="rushing_yards",
                player_id_col="rusher_player_id",
                name_col=name,
                value_expr=yards,
            )
        )

    if "interception" in base.columns and "interception_player_id" in base.columns:
        ints = base.filter(_flag_true("interception"))
        ret = (
            pl.col("return_yards").fill_null(0.0)
            if "return_yards" in ints.columns
            else pl.lit(0.0)
        )
        name = (
            "interception_player_name"
            if "interception_player_name" in ints.columns
            else "interception_player_id"
        )
        # Defender's team is the defense of the play.
        frames.append(
            _actor_frame(
                ints,
                play_class="interception",
                metric_id="return_yards",
                player_id_col="interception_player_id",
                name_col=name,
                value_expr=ret,
                team_col="opponent_team",
                opponent_col="team",
            )
        )

    if "sack" in base.columns:
        sacks = base.filter(_flag_true("sack"))
        # Prefer credited sack_player_id; fall back to half_sack_1.
        player_col = None
        name_col = None
        if "sack_player_id" in sacks.columns:
            player_col = "sack_player_id"
            name_col = "sack_player_name" if "sack_player_name" in sacks.columns else player_col
        elif "half_sack_1_player_id" in sacks.columns:
            player_col = "half_sack_1_player_id"
            name_col = (
                "half_sack_1_player_name"
                if "half_sack_1_player_name" in sacks.columns
                else player_col
            )
        if player_col is not None:
            lost = (
                (-pl.col("yards_gained").fill_null(0.0)).clip(lower_bound=0.0)
                if "yards_gained" in sacks.columns
                else pl.lit(0.0)
            )
            frames.append(
                _actor_frame(
                    sacks,
                    play_class="sack",
                    metric_id="sack_yards",
                    player_id_col=player_col,
                    name_col=name_col or player_col,
                    value_expr=lost,
                    team_col="opponent_team",
                    opponent_col="team",
                )
            )

    # Special teams / returns / kicking — continuous metrics only.
    if "return_team" in base.columns:
        return_opp = (
            pl.when(pl.col("return_team") == pl.col("posteam"))
            .then(pl.col("defteam"))
            .otherwise(pl.col("posteam"))
            .alias("_return_opp")
        )
    else:
        return_opp = pl.col("opponent_team").alias("_return_opp")

    if "kickoff_returner_player_id" in base.columns:
        kr = base.filter(pl.col("kickoff_returner_player_id").is_not_null()).with_columns(
            return_opp
        )
        if "return_team" in kr.columns:
            kr = kr.with_columns(pl.col("return_team").cast(pl.Utf8).alias("_return_team"))
        else:
            kr = kr.with_columns(pl.col("team").alias("_return_team"))
        ret_yards = (
            pl.col("return_yards").fill_null(0.0)
            if "return_yards" in kr.columns
            else pl.lit(0.0)
        )
        name = (
            "kickoff_returner_player_name"
            if "kickoff_returner_player_name" in kr.columns
            else "kickoff_returner_player_id"
        )
        frames.append(
            _actor_frame(
                kr,
                play_class="kick_return",
                metric_id="kick_return_yards",
                player_id_col="kickoff_returner_player_id",
                name_col=name,
                value_expr=ret_yards,
                team_col="_return_team",
                opponent_col="_return_opp",
            )
        )

    if "punt_returner_player_id" in base.columns:
        pr = base.filter(pl.col("punt_returner_player_id").is_not_null()).with_columns(
            return_opp
        )
        if "return_team" in pr.columns:
            pr = pr.with_columns(pl.col("return_team").cast(pl.Utf8).alias("_return_team"))
        else:
            pr = pr.with_columns(pl.col("opponent_team").alias("_return_team"))
        ret_yards = (
            pl.col("return_yards").fill_null(0.0)
            if "return_yards" in pr.columns
            else pl.lit(0.0)
        )
        name = (
            "punt_returner_player_name"
            if "punt_returner_player_name" in pr.columns
            else "punt_returner_player_id"
        )
        frames.append(
            _actor_frame(
                pr,
                play_class="punt_return",
                metric_id="punt_return_yards",
                player_id_col="punt_returner_player_id",
                name_col=name,
                value_expr=ret_yards,
                team_col="_return_team",
                opponent_col="_return_opp",
            )
        )

    if (
        "field_goal_attempt" in base.columns
        and "field_goal_result" in base.columns
        and "kicker_player_id" in base.columns
    ):
        fg = base.filter(
            _flag_true("field_goal_attempt") & (pl.col("field_goal_result") == "made")
        )
        dist = (
            pl.col("kick_distance")
            if "kick_distance" in fg.columns
            else pl.lit(None).cast(pl.Float64)
        )
        name = "kicker_player_name" if "kicker_player_name" in fg.columns else "kicker_player_id"
        frames.append(
            _actor_frame(
                fg,
                play_class="field_goal",
                metric_id="field_goal_distance",
                player_id_col="kicker_player_id",
                name_col=name,
                value_expr=dist,
            )
        )

    if "punt_attempt" in base.columns and "punter_player_id" in base.columns:
        punts = base.filter(_flag_true("punt_attempt"))
        dist = (
            pl.col("kick_distance")
            if "kick_distance" in punts.columns
            else pl.lit(None).cast(pl.Float64)
        )
        name = "punter_player_name" if "punter_player_name" in punts.columns else "punter_player_id"
        frames.append(
            _actor_frame(
                punts,
                play_class="punt",
                metric_id="punt_distance",
                player_id_col="punter_player_id",
                name_col=name,
                value_expr=dist,
            )
        )

    if "tackle_for_loss_1_player_id" in base.columns:
        tfl = base.filter(pl.col("tackle_for_loss_1_player_id").is_not_null())
        lost = (
            (-pl.col("yards_gained").fill_null(0.0)).clip(lower_bound=0.0)
            if "yards_gained" in tfl.columns
            else pl.lit(0.0)
        )
        name = (
            "tackle_for_loss_1_player_name"
            if "tackle_for_loss_1_player_name" in tfl.columns
            else "tackle_for_loss_1_player_id"
        )
        frames.append(
            _actor_frame(
                tfl,
                play_class="tackle_for_loss",
                metric_id="tfl_yards",
                player_id_col="tackle_for_loss_1_player_id",
                name_col=name,
                value_expr=lost,
                team_col="opponent_team",
                opponent_col="team",
            )
        )

    if (
        "fumble_recovery_1_player_id" in base.columns
        and "fumble_recovery_1_team" in base.columns
        and "fumbled_1_team" in base.columns
    ):
        # Defensive / change-of-possession recoveries only.
        fr = base.filter(
            pl.col("fumble_recovery_1_player_id").is_not_null()
            & pl.col("fumble_recovery_1_team").is_not_null()
            & pl.col("fumbled_1_team").is_not_null()
            & (pl.col("fumble_recovery_1_team") != pl.col("fumbled_1_team"))
        ).with_columns(
            pl.col("fumble_recovery_1_team").cast(pl.Utf8).alias("_fr_team"),
            pl.col("fumbled_1_team").cast(pl.Utf8).alias("_fr_opp"),
        )
        yards = (
            pl.col("fumble_recovery_1_yards").fill_null(0.0)
            if "fumble_recovery_1_yards" in fr.columns
            else pl.lit(0.0)
        )
        name = (
            "fumble_recovery_1_player_name"
            if "fumble_recovery_1_player_name" in fr.columns
            else "fumble_recovery_1_player_id"
        )
        frames.append(
            _actor_frame(
                fr,
                play_class="fumble_recovery",
                metric_id="fumble_recovery_yards",
                player_id_col="fumble_recovery_1_player_id",
                name_col=name,
                value_expr=yards,
                team_col="_fr_team",
                opponent_col="_fr_opp",
            )
        )

    if "forced_fumble_player_1_player_id" in base.columns:
        ff = base.filter(pl.col("forced_fumble_player_1_player_id").is_not_null())
        if "forced_fumble_player_1_team" in ff.columns:
            ff = ff.with_columns(
                pl.col("forced_fumble_player_1_team").cast(pl.Utf8).alias("_ff_team"),
                pl.when(pl.col("forced_fumble_player_1_team") == pl.col("posteam"))
                .then(pl.col("defteam"))
                .otherwise(pl.col("posteam"))
                .alias("_ff_opp"),
            )
            team_col, opp_col = "_ff_team", "_ff_opp"
        else:
            team_col, opp_col = "opponent_team", "team"
        # Continuous proxy: damage done to the offense (higher better for defense).
        value = (-pl.col("epa")) if "epa" in ff.columns else pl.lit(0.0)
        name = (
            "forced_fumble_player_1_player_name"
            if "forced_fumble_player_1_player_name" in ff.columns
            else "forced_fumble_player_1_player_id"
        )
        frames.append(
            _actor_frame(
                ff,
                play_class="forced_fumble",
                metric_id="forced_fumble_epa",
                player_id_col="forced_fumble_player_1_player_id",
                name_col=name,
                value_expr=value,
                team_col=team_col,
                opponent_col=opp_col,
            )
        )

    if not frames:
        empty_schema: dict[str, pl.DataType] = {
            "season": pl.Int32,
            "week": pl.Int32,
            "game_id": pl.Utf8,
            "play_id": pl.Int64,
            "play_class": pl.Utf8,
            "metric_id": pl.Utf8,
            "value": pl.Float64,
            "epa": pl.Float64,
            "player_id": pl.Utf8,
            "player_display_name": pl.Utf8,
            "team": pl.Utf8,
            "opponent_team": pl.Utf8,
            "quarter": pl.Int32,
            "clock": pl.Utf8,
            "game_seconds_remaining": pl.Float64,
            "touchdown": pl.Boolean,
            "desc": pl.Utf8,
        }
        return pl.DataFrame(schema=empty_schema)

    return pl.concat(frames, how="vertical_relaxed")


def _attach_positions(plays: pl.DataFrame, season: int) -> pl.DataFrame:
    if plays.is_empty():
        return plays.with_columns(
            pl.lit(None).cast(pl.Utf8).alias("position_code"),
            pl.lit(None).cast(pl.Utf8).alias("position_group"),
        ).select(_PANEL_COLS)
    rost = _roster_positions(season)
    joined = plays.join(rost, on=["player_id", "week"], how="left")
    # Season-level fallback when a week roster row is missing.
    season_pos = (
        rost.filter(pl.col("position_code").is_not_null())
        .sort("week")
        .unique(subset=["player_id"], keep="last")
        .select(
            [
                "player_id",
                pl.col("position_code").alias("_season_code"),
                pl.col("position_group").alias("_season_group"),
            ]
        )
    )
    joined = joined.join(season_pos, on="player_id", how="left").with_columns(
        pl.coalesce(["position_code", "_season_code"]).alias("position_code"),
        pl.coalesce(["position_group", "_season_group"]).alias("position_group"),
    ).drop(["_season_code", "_season_group"])
    return joined.select(_PANEL_COLS)


def build_play_panel(season: int) -> tuple[pl.DataFrame, dict[str, Any]]:
    """Build and persist the play panel for one season. Returns (frame, summary)."""
    ensure_data_dirs()
    pbp = _load_pbp(season)
    classified = _classify_plays(pbp)
    panel = _attach_positions(classified, season)
    out = play_panel_path(season)
    panel.write_parquet(out)
    by_class = (
        panel.group_by("play_class")
        .len()
        .sort("play_class")
        .to_dicts()
        if not panel.is_empty()
        else []
    )
    summary = {
        "path": str(out),
        "season": season,
        "rows": panel.height,
        "byClass": {r["play_class"]: r["len"] for r in by_class},
        "withPosition": int(panel.filter(pl.col("position_code").is_not_null()).height),
        "maxWeek": int(panel["week"].max()) if panel.height else None,
    }
    return panel, summary


def load_play_panel(season: int) -> pl.DataFrame:
    path = play_panel_path(season)
    if not path.is_file():
        raise FileNotFoundError(
            f"missing play panel {path}; run `ballnet play-panel --season {season}` first"
        )
    return pl.read_parquet(path)


def max_week_in_play_panel(season: int) -> int | None:
    path = play_panel_path(season)
    if not path.is_file():
        return None
    week = pl.read_parquet(path, columns=["week"]).select(pl.col("week").max()).item()
    return int(week) if week is not None else None
