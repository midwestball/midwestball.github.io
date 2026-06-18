"""Phase 1.1: Pull nflverse data into local SQLite + Parquet."""

from __future__ import annotations

import argparse
import json

import nflreadpy as nfl

from knowball.config import DB_PATH, PLAYER_GAME_LOGS_PATH
from knowball.ingest import ingest_seasons


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest nflverse data for knowball")
    parser.add_argument(
        "--seasons",
        type=int,
        nargs="+",
        default=None,
        help="Seasons to load (default: current NFL season)",
    )
    args = parser.parse_args()

    seasons = args.seasons or [nfl.get_current_season()]
    print(f"Ingesting seasons: {seasons}")
    print(f"Database: {DB_PATH}")
    print(f"Parquet:  {PLAYER_GAME_LOGS_PATH}")

    counts = ingest_seasons(seasons)

    print("\nIngestion complete:")
    print(json.dumps(counts, indent=2, default=str))


if __name__ == "__main__":
    main()
