"""Create Supabase schema and ingest the same data as local SQLite."""

from __future__ import annotations

import argparse
import json
import sys

import nflreadpy as nfl
from sqlalchemy import create_engine, text

from knowball.config import PLAYER_GAME_LOGS_PATH, get_supabase_db_url
from knowball.ingest import ingest_seasons
from knowball.storage import init_remote_db
from knowball.supabase_check import supabase_is_reachable

EXPECTED_TABLES = ("players", "games", "stats", "league_distributions")


def _print_table_counts(db_url: str) -> None:
    engine = create_engine(db_url)
    try:
        with engine.connect() as conn:
            for table in EXPECTED_TABLES:
                count = conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
                print(f"  {table}: {count:,} rows")
    finally:
        engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Initialize Supabase tables and ingest nflverse data"
    )
    parser.add_argument(
        "--seasons",
        type=int,
        nargs="+",
        default=None,
        help="Seasons to load (default: current NFL season)",
    )
    parser.add_argument(
        "--skip-ingest",
        action="store_true",
        help="Only create empty tables, do not pull nflverse data",
    )
    args = parser.parse_args()

    db_url = get_supabase_db_url()
    if not db_url:
        print(
            "No Supabase URL found. Add [connections.knowball_db] to "
            ".streamlit/secrets.toml (see secrets.toml.example).",
            file=sys.stderr,
        )
        sys.exit(1)

    if "db." in db_url and ".supabase.co" in db_url and "pooler" not in db_url:
        print(
            "Your URL uses the Direct host (db.*.supabase.co), which is often "
            "IPv6-only and will not connect from this network.\n"
            "In Supabase: Connect -> Session pooler -> URI. Copy that full string "
            "into secrets.toml (user should be postgres.[project-ref], host "
            "aws-N-[region].pooler.supabase.com).",
            file=sys.stderr,
        )
        sys.exit(1)

    print("Testing Supabase connection...")
    if not supabase_is_reachable():
        print(
            "Cannot reach Supabase. Check password, pooler host, and region in "
            "secrets.toml, then run: uv run python scripts/test_supabase_connection.py",
            file=sys.stderr,
        )
        sys.exit(1)
    print("Connection OK.")

    print("Creating tables (same schema as local SQLite)...")
    init_remote_db(db_url)
    print("Schema ready.")

    if args.skip_ingest:
        return

    seasons = args.seasons or [nfl.get_current_season()]
    print(f"Ingesting seasons {seasons} into Supabase...")
    print(f"Parquet cache (local): {PLAYER_GAME_LOGS_PATH}")

    counts = ingest_seasons(seasons, db_url=db_url)
    print("\nIngestion complete:")
    print(json.dumps(counts, indent=2, default=str))

    print("\nSupabase row counts:")
    _print_table_counts(db_url)


if __name__ == "__main__":
    main()
