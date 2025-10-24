import asyncio
import logging
import sys
import argparse
from datetime import datetime
from typing import Optional

from config import Config
from database import Database
from local_database import LocalDatabase
from collectors.nfl_collector import NFLCollector

logging.basicConfig(
    level = logging.INFO,
    format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers = [
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(f"data_collection_{datetime.now().strftime('%Y%m%d')}.log")
    ]
)

logger = logging.getLogger(__name__)

async def seed_initial_data(supabase_db: Database, local_db: Optional[LocalDatabase] = None):
    logger.info("Starting initial data seeding...")

    nfl_collector = NFLCollector(supabase_db, local_db)
    await nfl_collector.seed_teams_and_players()

    logger.info("Initial seeding complete")

async def collect_weekly_nfl(
    supabase_db: Database,
    local_db: Optional[LocalDatabase] = None,
    season: int = None,
    week: int = None,
    local_stats: bool = False
):
    logger.info("Starting weekly NFL collection...")

    if not season:
        season = Config.SPORT_CONFIG["nfl"]["current_season"]

    nfl_collector = NFLCollector(supabase_db, local_db, local_stats_only=local_stats)

    if not week:
        season_id = await supabase_db.get_active_season("nfl")
        week = await supabase_db.get_current_week(season_id)

        if week == 0:
            week = 1

        logger.info(f"Auto-detected current week: {week}")

    games_collected = await nfl_collector.collect_weekly_data(season, week)

    logger.info(f"Weekly collection complete: {games_collected} games processed")
    return games_collected

# NOTE: The old calculate_percentiles_local and calculate_impressiveness_scores_local functions
# have been removed. They populated the weekly_percentiles and player_performance_scores tables,
# which have been deprecated in favor of the new aggregation tables.
#
# Aggregations are now automatically updated when stats are inserted (via refresh_aggregations).
# If you need to backfill aggregations for existing data, use the backfill_aggregations function below.

async def backfill_aggregations(
    supabase_db: Database,
    local_db: Optional[LocalDatabase] = None,
    local_stats_only: bool = False
):
    """
    Backfill aggregation tables for all existing games.

    Behavior matches collection modes:
    - Default (no flags): Backfill Supabase only
    - --use-local-db: Backfill Supabase AND local
    - --use-local-db --local-stats: Backfill local ONLY (skip Supabase)

    Args:
        supabase_db: Supabase database instance
        local_db: Optional local database instance
        local_stats_only: If True, only backfill local DB (matching --local-stats behavior)
    """
    logger.info("Starting aggregation backfill...")

    # Determine where stats are stored based on mode
    if local_stats_only:
        if not local_db:
            logger.error("Local-only backfill requires local database")
            return

        logger.info("Backfilling LOCAL database only (--local-stats mode)")

        # Backfill local database only
        async with local_db.acquire() as conn:
            season_id = await conn.fetchval("""
                SELECT season_id FROM seasons WHERE is_active = TRUE LIMIT 1
            """)

            if not season_id:
                logger.error("No active season found in local database")
                return

            games = await conn.fetch("""
                SELECT game_id FROM games
                WHERE season_id = $1
                ORDER BY game_date
            """, season_id)

            total_games = len(games)
            logger.info(f"Found {total_games} games in local database")

            for idx, game_record in enumerate(games, 1):
                game_id = game_record["game_id"]
                try:
                    await conn.execute("SELECT refresh_aggregations_for_game($1)", game_id)
                    if idx % 10 == 0:
                        logger.info(f"Processed {idx}/{total_games} games (LOCAL)")
                except Exception as e:
                    logger.error(f"Failed to refresh local aggregations for game {game_id}: {e}")

    else:
        # Default: Backfill Supabase (and optionally local if enabled)
        logger.info("Backfilling SUPABASE database" + (" and LOCAL database" if local_db else ""))

        # Get games from Supabase
        season_id = await supabase_db.get_active_season("nfl")
        if not season_id:
            logger.error("No active season found in Supabase")
            return

        # Get all games from Supabase
        result = supabase_db.client.table("games").select("game_id").eq("season_id", season_id).order("game_date").execute()
        games = result.data

        total_games = len(games)
        logger.info(f"Found {total_games} games in Supabase")

        # Backfill Supabase aggregations
        for idx, game_record in enumerate(games, 1):
            game_id = game_record["game_id"]
            try:
                await supabase_db.refresh_aggregations(game_id)
                if idx % 10 == 0:
                    logger.info(f"Processed {idx}/{total_games} games (SUPABASE)")
            except Exception as e:
                logger.error(f"Failed to refresh Supabase aggregations for game {game_id}: {e}")

        # Also backfill local DB if --use-local-db was specified
        if local_db:
            logger.info("Also backfilling local database...")
            async with local_db.acquire() as conn:
                local_season_id = await conn.fetchval("""
                    SELECT season_id FROM seasons WHERE is_active = TRUE LIMIT 1
                """)

                if not local_season_id:
                    logger.warning("No active season found in local database, skipping local backfill")
                else:
                    local_games = await conn.fetch("""
                        SELECT game_id FROM games
                        WHERE season_id = $1
                        ORDER BY game_date
                    """, local_season_id)

                    logger.info(f"Found {len(local_games)} games in local database")

                    for idx, game_record in enumerate(local_games, 1):
                        game_id = game_record["game_id"]
                        try:
                            await conn.execute("SELECT refresh_aggregations_for_game($1)", game_id)
                            if idx % 10 == 0:
                                logger.info(f"Processed {idx}/{len(local_games)} games (LOCAL)")
                        except Exception as e:
                            logger.error(f"Failed to refresh local aggregations for game {game_id}: {e}")

    logger.info("Aggregation backfill complete!")

async def main():
    parser = argparse.ArgumentParser(description = "Sports Data Collection")
    parser.add_argument("--mode", choices = ["seed", "collect", "backfill", "full"], required = True,
                       help="Mode: seed (initial data), collect (weekly games), backfill (regenerate aggregations), full (collect + backfill)")
    parser.add_argument("--season", type = int, help = "NFL season year")
    parser.add_argument("--week", type = int, help = "NFL week number")
    parser.add_argument("--use-local-db", action = "store_true", help = "Also write to local database")
    parser.add_argument("--local-stats", action = "store_true", help = "Store stats only in local database (requires --use-local-db)")

    args = parser.parse_args()

    Config.validate_config()

    # Always initialize Supabase
    supabase_db = Database(Config.SUPABASE_URL, Config.SUPABASE_KEY)

    # Conditionally initialize local DB
    local_db = None
    use_local = args.use_local_db or Config.USE_LOCAL_DB

    if use_local:
        local_db = LocalDatabase(Config.LOCAL_DATABASE_URL)

    # Validate local-stats flag
    if args.local_stats and not use_local:
        logger.error("--local-stats requires --use-local-db or USE_LOCAL_DB=true in .env")
        sys.exit(1)

    try:
        await supabase_db.connect()
        if local_db:
            await local_db.connect()
            if args.local_stats:
                logger.info("Local database enabled - stats will be stored ONLY in local database")
            else:
                logger.info("Local database enabled - writing to both databases")

        # Pass both databases to functions
        if args.mode == "seed":
            await seed_initial_data(supabase_db, local_db)

        elif args.mode == "collect":
            await collect_weekly_nfl(supabase_db, local_db, args.season, args.week, args.local_stats)

        elif args.mode == "backfill":
            # Backfill aggregations
            await backfill_aggregations(supabase_db, local_db, args.local_stats)

        elif args.mode == "full":
            await collect_weekly_nfl(supabase_db, local_db, args.season, args.week, args.local_stats)
            # Note: Aggregations are now auto-updated during collection
            # Backfill is only needed if you want to regenerate all aggregations
            logger.info("Collection complete. Aggregations were automatically updated.")

        logger.info("All operations completed successfully")

    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info = True)
        sys.exit(1)

    finally:
        await supabase_db.close()
        if local_db:
            await local_db.close()

if __name__ == "__main__":
    asyncio.run(main())