"""Quick sanity check on ingested local data."""

from __future__ import annotations

import sqlite3

import polars as pl

from knowball.config import DB_PATH, PLAYER_GAME_LOGS_PATH


def main() -> None:
    print(f"DB size:      {DB_PATH.stat().st_size / 1024:.1f} KB")
    print(f"Parquet size: {PLAYER_GAME_LOGS_PATH.stat().st_size / 1024:.1f} KB")

    conn = sqlite3.connect(DB_PATH)
    for table in ("players", "games", "stats", "league_distributions"):
        count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"{table}: {count:,} rows")

    print("\nSample players:", conn.execute(
        "SELECT gsis_id, display_name, position FROM players WHERE position = 'QB' LIMIT 3"
    ).fetchall())

    print("Sample stats:", conn.execute(
        "SELECT player_id, week, passing_epa FROM stats WHERE passing_epa IS NOT NULL LIMIT 3"
    ).fetchall())

    print("passing_epa bins (Current Season):")
    for row in conn.execute(
        """
        SELECT bin_start, bin_end, count
        FROM league_distributions
        WHERE metric = 'passing_epa' AND timeframe_context = 'Current Season'
        ORDER BY bin_start
        LIMIT 5
        """
    ):
        print(f"  [{row[0]:.2f}, {row[1]:.2f}): {row[2]}")

    logs = pl.read_parquet(PLAYER_GAME_LOGS_PATH)
    print(f"\nParquet: {logs.height:,} rows, {len(logs.columns)} columns")
    print(logs.select("player_name", "week", "passing_epa").filter(
        pl.col("passing_epa").is_not_null()
    ).head(3))


if __name__ == "__main__":
    main()
