"""Print stat coverage for ingested game logs."""

from __future__ import annotations

import polars as pl

from knowball.config import DB_PATH, DISTRIBUTION_METRICS, PLAYER_GAME_LOGS_PATH
from knowball.stat_registry import METRIC_ROLE_FILTERS, coverage_groups


def _report_group_coverage(logs: pl.DataFrame, name: str, columns: list[str], filt: pl.Expr) -> None:
    subset = logs.filter(filt)
    total = subset.height
    if total == 0:
        print(f"  {name}: no rows for role filter")
        return

    print(f"--- {name} ({total:,} role rows) ---")
    for metric in columns:
        if metric not in logs.columns:
            continue
        non_null = subset.filter(pl.col(metric).is_not_null()).height
        pct = 100 * non_null / total if total else 0
        if non_null > 0:
            print(f"  {metric:32s} {non_null:7,}/{total:7,}  ({pct:5.1f}%)")


def main() -> None:
    logs = pl.read_parquet(PLAYER_GAME_LOGS_PATH)

    print("=== Dataset summary ===")
    print(
        f"Seasons: {logs['season'].min()} - {logs['season'].max()} "
        f"({logs['season'].n_unique()} seasons)"
    )
    print(f"Game log rows: {logs.height:,}")
    print(f"Stat columns: {len([c for c in logs.columns if c not in {'player_id', 'game_id', 'player_name', 'player_display_name'}])}")
    print(f"Unique players: {logs['player_id'].n_unique():,}")
    print(f"Parquet size: {PLAYER_GAME_LOGS_PATH.stat().st_size / 1024 / 1024:.2f} MB")
    print(f"SQLite size: {DB_PATH.stat().st_size / 1024 / 1024:.2f} MB")
    print()

    print("=== EPA non-null rate by season ===")
    by_season = (
        logs.group_by("season")
        .agg(
            pl.len().alias("rows"),
            *[
                pl.col(metric).is_not_null().sum().alias(metric)
                for metric in DISTRIBUTION_METRICS
            ],
        )
        .sort("season")
    )
    for row in by_season.iter_rows(named=True):
        parts = [f"{row['season']}: {row['rows']:,} rows"]
        for metric in DISTRIBUTION_METRICS:
            pct = 100 * row[metric] / row["rows"] if row["rows"] else 0
            parts.append(f"{metric} {row[metric]:,} ({pct:.1f}%)")
        print(" | ".join(parts))

    print()
    print("=== Role-appropriate EPA coverage ===")
    for metric, filt in METRIC_ROLE_FILTERS.items():
        subset = logs.filter(filt)
        non_null = subset.filter(pl.col(metric).is_not_null()).height
        total = subset.height
        pct = 100 * non_null / total if total else 0
        print(f"  {metric}: {non_null:,}/{total:,} ({pct:.1f}%)")

    print()
    print("=== Role-appropriate coverage by stat group ===")
    for name, (columns, filt) in coverage_groups().items():
        _report_group_coverage(logs, name, columns, filt)
        print()


if __name__ == "__main__":
    main()
