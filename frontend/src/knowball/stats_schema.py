"""Canonical stats table columns (nflverse ``load_player_stats``)."""

from __future__ import annotations

import polars as pl

STAT_CONTEXT_COLUMNS = [
    "player_id",
    "game_id",
    "season",
    "week",
    "season_type",
    "team",
    "opponent_team",
    "position",
    "position_group",
]

PARQUET_DISPLAY_COLUMNS = ["player_name", "player_display_name"]

EXCLUDE_FROM_STATS = frozenset(
    {
        *PARQUET_DISPLAY_COLUMNS,
        "headshot_url",
    }
)

STAT_CONTEXT_DTYPES: dict[str, pl.DataType] = {
    "player_id": pl.Utf8,
    "game_id": pl.Utf8,
    "season": pl.Int64,
    "week": pl.Int64,
    "season_type": pl.Utf8,
    "team": pl.Utf8,
    "opponent_team": pl.Utf8,
    "position": pl.Utf8,
    "position_group": pl.Utf8,
}

# Metric columns from nflverse load_player_stats (2010+ weekly), excluding context/display.
STAT_COLUMN_DTYPES: dict[str, pl.DataType] = {
    "air_yards_share": pl.Float64,
    "attempts": pl.Int64,
    "carries": pl.Int64,
    "completions": pl.Int64,
    "def_fumbles": pl.Int64,
    "def_fumbles_forced": pl.Int64,
    "def_interception_yards": pl.Int64,
    "def_interceptions": pl.Int64,
    "def_pass_defended": pl.Int64,
    "def_qb_hits": pl.Int64,
    "def_sack_yards": pl.Float64,
    "def_sacks": pl.Float64,
    "def_safeties": pl.Int64,
    "def_tackle_assists": pl.Int64,
    "def_tackles_for_loss": pl.Int64,
    "def_tackles_for_loss_yards": pl.Int64,
    "def_tackles_solo": pl.Int64,
    "def_tackles_with_assist": pl.Int64,
    "def_tds": pl.Int64,
    "fantasy_points": pl.Float64,
    "fantasy_points_ppr": pl.Float64,
    "fg_att": pl.Int64,
    "fg_blocked": pl.Int64,
    "fg_blocked_distance": pl.Int64,
    "fg_blocked_list": pl.Utf8,
    "fg_long": pl.Int64,
    "fg_made": pl.Int64,
    "fg_made_0_19": pl.Int64,
    "fg_made_20_29": pl.Int64,
    "fg_made_30_39": pl.Int64,
    "fg_made_40_49": pl.Int64,
    "fg_made_50_59": pl.Int64,
    "fg_made_60_": pl.Int64,
    "fg_made_distance": pl.Int64,
    "fg_made_list": pl.Utf8,
    "fg_missed": pl.Int64,
    "fg_missed_0_19": pl.Int64,
    "fg_missed_20_29": pl.Int64,
    "fg_missed_30_39": pl.Int64,
    "fg_missed_40_49": pl.Int64,
    "fg_missed_50_59": pl.Int64,
    "fg_missed_60_": pl.Int64,
    "fg_missed_distance": pl.Int64,
    "fg_missed_list": pl.Utf8,
    "fg_pct": pl.Float64,
    "fumble_recovery_opp": pl.Int64,
    "fumble_recovery_own": pl.Int64,
    "fumble_recovery_tds": pl.Int64,
    "fumble_recovery_yards_opp": pl.Int64,
    "fumble_recovery_yards_own": pl.Int64,
    "gwfg_att": pl.Int64,
    "gwfg_blocked": pl.Int64,
    "gwfg_distance": pl.Int64,
    "gwfg_made": pl.Int64,
    "gwfg_missed": pl.Int64,
    "kickoff_return_yards": pl.Int64,
    "kickoff_returns": pl.Int64,
    "misc_yards": pl.Int64,
    "pacr": pl.Float64,
    "passing_2pt_conversions": pl.Int64,
    "passing_air_yards": pl.Int64,
    "passing_cpoe": pl.Float64,
    "passing_epa": pl.Float64,
    "passing_first_downs": pl.Int64,
    "passing_interceptions": pl.Int64,
    "passing_tds": pl.Int64,
    "passing_yards": pl.Int64,
    "passing_yards_after_catch": pl.Int64,
    "pat_att": pl.Int64,
    "pat_blocked": pl.Int64,
    "pat_made": pl.Int64,
    "pat_missed": pl.Int64,
    "pat_pct": pl.Float64,
    "penalties": pl.Int64,
    "penalty_yards": pl.Int64,
    "punt_return_yards": pl.Int64,
    "punt_returns": pl.Int64,
    "racr": pl.Float64,
    "receiving_2pt_conversions": pl.Int64,
    "receiving_air_yards": pl.Int64,
    "receiving_epa": pl.Float64,
    "receiving_first_downs": pl.Int64,
    "receiving_fumbles": pl.Int64,
    "receiving_fumbles_lost": pl.Int64,
    "receiving_tds": pl.Int64,
    "receiving_yards": pl.Int64,
    "receiving_yards_after_catch": pl.Int64,
    "receptions": pl.Int64,
    "rushing_2pt_conversions": pl.Int64,
    "rushing_epa": pl.Float64,
    "rushing_first_downs": pl.Int64,
    "rushing_fumbles": pl.Int64,
    "rushing_fumbles_lost": pl.Int64,
    "rushing_tds": pl.Int64,
    "rushing_yards": pl.Int64,
    "sack_fumbles": pl.Int64,
    "sack_fumbles_lost": pl.Int64,
    "sack_yards_lost": pl.Int64,
    "sacks_suffered": pl.Int64,
    "special_teams_tds": pl.Int64,
    "target_share": pl.Float64,
    "targets": pl.Int64,
    "wopr": pl.Float64,
}

STATS_TABLE_SCHEMA: dict[str, pl.DataType] = {
    **STAT_CONTEXT_DTYPES,
    **STAT_COLUMN_DTYPES,
}

PARQUET_LOGS_SCHEMA: dict[str, pl.DataType] = {
    **STATS_TABLE_SCHEMA,
    **{col: pl.Utf8 for col in PARQUET_DISPLAY_COLUMNS},
}

STAT_METRIC_COLUMNS = list(STAT_COLUMN_DTYPES.keys())


def _sql_type(dtype: pl.DataType) -> str:
    if dtype == pl.Int64:
        return "INTEGER"
    if dtype == pl.Float64:
        return "REAL"
    return "TEXT"


def stats_ddl() -> str:
    """Build SQLite/Postgres DDL for the stats table."""
    col_lines = [
        f"    {name} {_sql_type(dtype)}"
        for name, dtype in STATS_TABLE_SCHEMA.items()
    ]
    body = ",\n".join(col_lines)
    return f"""
CREATE TABLE IF NOT EXISTS stats (
{body},
    PRIMARY KEY (player_id, game_id),
    FOREIGN KEY (player_id) REFERENCES players(gsis_id),
    FOREIGN KEY (game_id) REFERENCES games(game_id)
);
"""
