"""Position-aware stat groupings for analytics and UI filtering."""

from __future__ import annotations

import polars as pl

from knowball.stats_schema import STAT_COLUMN_DTYPES

PASSING_COLUMNS = [
    "passing_epa",
    "completions",
    "attempts",
    "passing_yards",
    "passing_tds",
    "passing_interceptions",
    "sacks_suffered",
    "sack_yards_lost",
    "sack_fumbles",
    "sack_fumbles_lost",
    "passing_air_yards",
    "passing_yards_after_catch",
    "passing_first_downs",
    "passing_cpoe",
    "passing_2pt_conversions",
    "pacr",
]

RUSHING_COLUMNS = [
    "rushing_epa",
    "carries",
    "rushing_yards",
    "rushing_tds",
    "rushing_fumbles",
    "rushing_fumbles_lost",
    "rushing_first_downs",
    "rushing_2pt_conversions",
]

RECEIVING_COLUMNS = [
    "receiving_epa",
    "receptions",
    "targets",
    "receiving_yards",
    "receiving_tds",
    "receiving_fumbles",
    "receiving_fumbles_lost",
    "receiving_air_yards",
    "receiving_yards_after_catch",
    "receiving_first_downs",
    "receiving_2pt_conversions",
    "racr",
    "target_share",
    "air_yards_share",
    "wopr",
]

DEFENSE_COLUMNS = [
    "def_tackles_solo",
    "def_tackles_with_assist",
    "def_tackle_assists",
    "def_tackles_for_loss",
    "def_tackles_for_loss_yards",
    "def_sacks",
    "def_sack_yards",
    "def_qb_hits",
    "def_interceptions",
    "def_interception_yards",
    "def_pass_defended",
    "def_tds",
    "def_fumbles",
    "def_fumbles_forced",
    "def_safeties",
]

KICKING_COLUMNS = [
    "fg_made",
    "fg_att",
    "fg_missed",
    "fg_blocked",
    "fg_long",
    "fg_pct",
    "fg_made_0_19",
    "fg_made_20_29",
    "fg_made_30_39",
    "fg_made_40_49",
    "fg_made_50_59",
    "fg_made_60_",
    "fg_missed_0_19",
    "fg_missed_20_29",
    "fg_missed_30_39",
    "fg_missed_40_49",
    "fg_missed_50_59",
    "fg_missed_60_",
    "fg_made_distance",
    "fg_missed_distance",
    "fg_blocked_distance",
    "fg_made_list",
    "fg_missed_list",
    "fg_blocked_list",
    "pat_made",
    "pat_att",
    "pat_missed",
    "pat_blocked",
    "pat_pct",
    "gwfg_made",
    "gwfg_att",
    "gwfg_missed",
    "gwfg_blocked",
    "gwfg_distance",
]

RETURNS_MISC_COLUMNS = [
    "punt_returns",
    "punt_return_yards",
    "kickoff_returns",
    "kickoff_return_yards",
    "penalties",
    "penalty_yards",
    "fumble_recovery_own",
    "fumble_recovery_opp",
    "fumble_recovery_yards_own",
    "fumble_recovery_yards_opp",
    "fumble_recovery_tds",
    "special_teams_tds",
    "misc_yards",
]

FANTASY_COLUMNS = ["fantasy_points", "fantasy_points_ppr"]

STAT_GROUPS: dict[str, dict[str, frozenset[str] | list[str]]] = {
    "passing": {
        "positions": frozenset({"QB"}),
        "columns": PASSING_COLUMNS,
    },
    "rushing": {
        "position_groups": frozenset({"RB", "QB", "WR", "TE", "FB"}),
        "columns": RUSHING_COLUMNS,
    },
    "receiving": {
        "position_groups": frozenset({"WR", "TE", "RB", "FB"}),
        "columns": RECEIVING_COLUMNS,
    },
    "defense": {
        "position_groups": frozenset({"DL", "LB", "DB"}),
        "columns": DEFENSE_COLUMNS,
    },
    "kicking": {
        "positions": frozenset({"K"}),
        "columns": KICKING_COLUMNS,
    },
    "returns_misc": {
        "position_groups": frozenset({"WR", "RB", "DB", "CB", "S", "FS", "SS"}),
        "columns": RETURNS_MISC_COLUMNS,
    },
    "fantasy": {
        "position_groups": frozenset({"QB", "RB", "WR", "TE", "K", "FB"}),
        "columns": FANTASY_COLUMNS,
    },
}

# Primary role filter for coverage reports and percentile denominators.
METRIC_ROLE_FILTERS: dict[str, pl.Expr] = {
    "passing_epa": pl.col("position") == "QB",
    "rushing_epa": pl.col("position") == "RB",
    "receiving_epa": pl.col("position").is_in(["WR", "TE"]),
}


def _group_applies(group: dict[str, frozenset[str] | list[str]], position: str, position_group: str) -> bool:
    positions = group.get("positions")
    if isinstance(positions, frozenset) and position in positions:
        return True
    groups = group.get("position_groups")
    return isinstance(groups, frozenset) and position_group in groups


def applicable_metrics(position: str, position_group: str) -> list[str]:
    """Return stat columns meaningful for a player's role."""
    metrics: list[str] = []
    for group in STAT_GROUPS.values():
        if _group_applies(group, position, position_group):
            metrics.extend(group["columns"])  # type: ignore[arg-type]
    seen: set[str] = set()
    ordered: list[str] = []
    for metric in metrics:
        if metric not in seen and metric in STAT_COLUMN_DTYPES:
            seen.add(metric)
            ordered.append(metric)
    return ordered


def filter_logs_for_metric(logs: pl.DataFrame, metric: str) -> pl.DataFrame:
    """Subset game logs to players for whom *metric* is role-appropriate."""
    if metric in METRIC_ROLE_FILTERS:
        return logs.filter(METRIC_ROLE_FILTERS[metric])

    for group in STAT_GROUPS.values():
        columns = group["columns"]
        if metric not in columns:  # type: ignore[operator]
            continue
        positions = group.get("positions")
        if isinstance(positions, frozenset):
            return logs.filter(pl.col("position").is_in(list(positions)))
        groups = group.get("position_groups")
        if isinstance(groups, frozenset):
            return logs.filter(pl.col("position_group").is_in(list(groups)))

    return logs


def coverage_groups() -> dict[str, tuple[list[str], pl.Expr]]:
    """Named stat groups with role filters for coverage_report.py."""
    return {
        "passing": (PASSING_COLUMNS, pl.col("position") == "QB"),
        "rushing": (RUSHING_COLUMNS, pl.col("position") == "RB"),
        "receiving": (RECEIVING_COLUMNS, pl.col("position").is_in(["WR", "TE"])),
        "defense": (DEFENSE_COLUMNS, pl.col("position_group").is_in(["DL", "LB", "DB"])),
        "kicking": (KICKING_COLUMNS, pl.col("position") == "K"),
    }
