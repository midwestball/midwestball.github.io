"""
Sync script to push recent data from local PostgreSQL database to Supabase.
Use this to sync the most recent weeks, percentiles, and ML model results.
"""

import asyncio
import logging
import sys
import argparse
from datetime import datetime
from typing import Optional

from config import Config
from database import Database
from local_database import LocalDatabase

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(f"sync_{datetime.now().strftime('%Y%m%d')}.log")
    ]
)

logger = logging.getLogger(__name__)


async def sync_recent_weeks(local_db: LocalDatabase, supabase_db: Database, num_weeks: int = 1):
    """
    Sync the most recent N weeks of games and stats to Supabase.
    """
    logger.info(f"Syncing the most recent {num_weeks} week(s) of data to Supabase...")

    # Get active season
    season_id = await local_db.get_active_season("nfl")
    if not season_id:
        logger.error("No active season found in local database")
        return

    # Get recent weeks' games
    games = await local_db.get_recent_weeks_games(season_id, num_weeks)
    logger.info(f"Found {len(games)} games to sync")

    synced_games = 0
    synced_stats = 0

    for game in games:
        game_id = game["game_id"]
        game_external_id = game["game_external_id"]

        # Check if game exists in Supabase
        existing = supabase_db.client.table("games").select("game_id").eq("game_external_id", game_external_id).execute()

        if not existing.data:
            # Insert game into Supabase
            game_record = {
                "season_id": season_id,
                "game_external_id": game_external_id,
                "game_date": game["game_date"].isoformat() if hasattr(game["game_date"], 'isoformat') else game["game_date"],
                "game_week": game["game_week"],
                "home_team_id": game["home_team_id"],
                "away_team_id": game["away_team_id"],
                "home_score": game["home_score"],
                "away_score": game["away_score"]
            }

            try:
                supabase_db.client.table("games").insert(game_record).execute()
                synced_games += 1
                logger.info(f"Synced game {game_external_id}")
            except Exception as e:
                logger.error(f"Failed to sync game {game_external_id}: {e}")
                continue

        # Sync stats for this game
        stats = await local_db.get_stats_for_game(game_id)

        for stat in stats:
            try:
                stat_record = {
                    "game_id": game_id,
                    "player_id": stat["player_id"],
                    "team_id": stat["team_id"],
                    "position": stat["position"],
                    "stat_category": stat["stat_category"],
                    "stat_value": float(stat["stat_value"])
                }

                supabase_db.client.table("player_game_stats").upsert(stat_record, on_conflict="game_id,player_id,stat_category").execute()
                synced_stats += 1
            except Exception as e:
                logger.error(f"Failed to sync stat for player {stat['player_id']}: {e}")
                continue

    logger.info(f"Synced {synced_games} games and {synced_stats} stats to Supabase")


async def sync_percentiles(local_db: LocalDatabase, supabase_db: Database, num_weeks: int = 1):
    """
    Sync percentile calculations from local database to Supabase.
    """
    logger.info(f"Syncing percentiles for the most recent {num_weeks} week(s) to Supabase...")

    # Get active season
    season_id = await local_db.get_active_season("nfl")
    if not season_id:
        logger.error("No active season found in local database")
        return

    # Get current week
    current_week = await local_db.get_current_week(season_id)

    synced_count = 0

    # Sync percentiles for recent weeks
    for week in range(max(1, current_week - num_weeks + 1), current_week + 1):
        percentiles = await local_db.get_weekly_percentiles(season_id, week)

        for percentile in percentiles:
            try:
                percentile_record = {
                    "season_id": season_id,
                    "week_number": week,
                    "position": percentile["position"],
                    "stat_category": percentile["stat_category"],
                    "percentile_data": percentile["percentile_data"],
                    "sample_size": percentile["sample_size"]
                }

                supabase_db.client.table("weekly_percentiles").upsert(
                    percentile_record,
                    on_conflict="season_id,week_number,position,stat_category,calculation_date"
                ).execute()

                synced_count += 1
                logger.info(f"Synced percentile: Week {week}, {percentile['position']}, {percentile['stat_category']}")
            except Exception as e:
                logger.error(f"Failed to sync percentile: {e}")
                continue

    logger.info(f"Synced {synced_count} percentile records to Supabase")


async def sync_performance_scores(local_db: LocalDatabase, supabase_db: Database, num_weeks: int = 1):
    """
    Sync performance scores from local database to Supabase.
    """
    logger.info(f"Syncing performance scores for the most recent {num_weeks} week(s) to Supabase...")

    # Get active season
    season_id = await local_db.get_active_season("nfl")
    if not season_id:
        logger.error("No active season found in local database")
        return

    # Get recent weeks' games
    games = await local_db.get_recent_weeks_games(season_id, num_weeks)

    synced_count = 0

    for game in games:
        game_id = game["game_id"]

        # Get performance scores for this game
        scores = await local_db.get_performance_scores_for_game(game_id)

        for score in scores:
            try:
                score_record = {
                    "game_id": game_id,
                    "player_id": score["player_id"],
                    "stat_category": score["stat_category"],
                    "raw_value": float(score["raw_value"]),
                    "percentile_rank": float(score["percentile_rank"]),
                    "impressiveness_score": float(score["impressiveness_score"]),
                    "context_factors": score["context_factors"],
                    "score_version": score["score_version"]
                }

                supabase_db.client.table("player_performance_scores").upsert(
                    score_record,
                    on_conflict="game_id,player_id,stat_category,score_version"
                ).execute()

                synced_count += 1
            except Exception as e:
                logger.error(f"Failed to sync performance score: {e}")
                continue

    logger.info(f"Synced {synced_count} performance scores to Supabase")


async def main():
    parser = argparse.ArgumentParser(description="Sync data from local PostgreSQL to Supabase")
    parser.add_argument(
        "--mode",
        choices=["games", "percentiles", "scores", "all"],
        required=True,
        help="What to sync: games (recent weeks), percentiles, scores, or all"
    )
    parser.add_argument(
        "--weeks",
        type=int,
        default=1,
        help="Number of recent weeks to sync (default: 1)"
    )

    args = parser.parse_args()

    Config.validate_config()

    if not Config.LOCAL_DATABASE_URL:
        logger.error("LOCAL_DATABASE_URL not set in configuration")
        sys.exit(1)

    # Initialize both databases
    local_db = LocalDatabase(Config.LOCAL_DATABASE_URL)
    supabase_db = Database(Config.SUPABASE_URL, Config.SUPABASE_KEY)

    try:
        await local_db.connect()
        await supabase_db.connect()

        logger.info(f"Connected to both databases. Mode: {args.mode}, Weeks: {args.weeks}")

        if args.mode == "games":
            await sync_recent_weeks(local_db, supabase_db, args.weeks)

        elif args.mode == "percentiles":
            await sync_percentiles(local_db, supabase_db, args.weeks)

        elif args.mode == "scores":
            await sync_performance_scores(local_db, supabase_db, args.weeks)

        elif args.mode == "all":
            await sync_recent_weeks(local_db, supabase_db, args.weeks)
            await sync_percentiles(local_db, supabase_db, args.weeks)
            await sync_performance_scores(local_db, supabase_db, args.weeks)

        logger.info("Sync completed successfully")

    except Exception as e:
        logger.error(f"Fatal error during sync: {e}", exc_info=True)
        sys.exit(1)

    finally:
        await local_db.close()
        await supabase_db.close()


if __name__ == "__main__":
    asyncio.run(main())
