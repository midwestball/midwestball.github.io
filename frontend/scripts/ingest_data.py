"""Phase 1.1: Pull nflverse data into local SQLite + Parquet."""

from __future__ import annotations

import argparse
import json

import nflreadpy as nfl

from knowball.config import DB_PATH, PLAYER_GAME_LOGS_PATH, get_supabase_db_url
from knowball.ingest import ingest_seasons


def _seasons_from_args(args: argparse.Namespace) -> list[int]:
    if args.seasons is not None:
        return args.seasons
    if args.from_season is not None:
        current = nfl.get_current_season()
        return list(range(args.from_season, current + 1))
    return [nfl.get_current_season()]


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest nflverse data for knowball")
    parser.add_argument(
        "--seasons",
        type=int,
        nargs="+",
        default=None,
        help="Seasons to load (default: current NFL season)",
    )
    parser.add_argument(
        "--from-season",
        type=int,
        default=None,
        metavar="YEAR",
        help="Load from YEAR through the current season (e.g. 2010)",
    )
    parser.add_argument(
        "--db-url",
        default=None,
        help="Explicit PostgreSQL URL (overrides secrets when using --remote)",
    )
    parser.add_argument(
        "--remote",
        action="store_true",
        help="Write to Supabase/PostgreSQL (from secrets.toml or env)",
    )
    args = parser.parse_args()

    if args.seasons is not None and args.from_season is not None:
        parser.error("Use either --seasons or --from-season, not both")

    seasons = _seasons_from_args(args)
    db_url = args.db_url or (get_supabase_db_url() if args.remote else None)
    using_postgres = bool(db_url and db_url.startswith("postgresql"))

    print(f"Ingesting seasons: {seasons[0]}–{seasons[-1]} ({len(seasons)} seasons)")
    print("Note: ingest replaces all stored data for the seasons listed above.")
    if using_postgres:
        print("Database: Supabase/PostgreSQL (remote)")
    else:
        print(f"Database: {DB_PATH}")
    print(f"Parquet:  {PLAYER_GAME_LOGS_PATH}")

    counts = ingest_seasons(
        seasons,
        db_url=db_url if using_postgres else None,
        db_path=None if using_postgres else DB_PATH,
    )

    print("\nIngestion complete:")
    print(json.dumps(counts, indent=2, default=str))


if __name__ == "__main__":
    main()
