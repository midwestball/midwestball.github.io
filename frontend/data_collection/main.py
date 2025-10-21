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
    week: int = None
):
    logger.info("Starting weekly NFL collection...")

    if not season:
        season = Config.SPORT_CONFIG["nfl"]["current_season"]

    nfl_collector = NFLCollector(supabase_db, local_db)

    if not week:
        season_id = await supabase_db.get_active_season("nfl")
        week = await supabase_db.get_current_week(season_id)

        if week == 0:
            week = 1

        logger.info(f"Auto-detected current week: {week}")

    games_collected = await nfl_collector.collect_weekly_data(season, week)

    logger.info(f"Weekly collection complete: {games_collected} games processed")
    return games_collected

async def calculate_percentiles_local(local_db: LocalDatabase):
    """
    Calculate percentiles using local PostgreSQL database with raw SQL.
    This function requires a LocalDatabase instance.
    """
    logger.info("Calculating weekly percentiles on local database...")

    async with local_db.acquire() as conn:
        season_id = await conn.fetchval("""
            SELECT season_id FROM seasons WHERE is_active = TRUE LIMIT 1
        """)

        if not season_id:
            logger.error("No active season found")
            return

        current_week = await conn.fetchval("""
            SELECT MAX(game_week) FROM games WHERE season_id = $1
        """, season_id)

        if not current_week:
            logger.error("No games found for season")
            return

        positions = ["QB", "RB", "WR", "TE"]

        key_stats = {
            "QB": ["passing_yards", "passing_touchdowns", "passer_rating"],
            "RB": ["rushing_yards", "rushing_touchdowns", "rushing_yards_per_attempt"],
            "WR": ["receptions", "receiving_yards", "receiving_touchdowns"],
            "TE": ["receptions", "receiving_yards", "receiving_touchdowns"]
        }

        for position in positions:
            stats_to_calc = key_stats.get(position, [])

            for stat_category in stats_to_calc:
                percentiles = await conn.fetchrow("""
                    WITH position_stats AS (
                        SELECT
                            pgs.stat_value
                        FROM player_game_stats pgs
                        JOIN games g ON pgs.game_id = g.game_id
                        WHERE g.season_id = $1
                            AND g.game_week <= $2
                            AND pgs.position = $3
                            AND pgs.stat_category = $4
                            AND pgs.stat_value > 0
                    )
                    SELECT
                        percentile_cont(0.10) WITHIN GROUP (ORDER BY stat_value) as p10,
                        percentile_cont(0.25) WITHIN GROUP (ORDER BY stat_value) as p25,
                        percentile_cont(0.50) WITHIN GROUP (ORDER BY stat_value) as p50,
                        percentile_cont(0.75) WITHIN GROUP (ORDER BY stat_value) as p75,
                        percentile_cont(0.90) WITHIN GROUP (ORDER BY stat_value) as p90,
                        percentile_cont(0.95) WITHIN GROUP (ORDER BY stat_value) as p95,
                        percentile_cont(0.99) WITHIN GROUP (ORDER BY stat_value) as p99,
                        AVG(stat_value) as mean,
                        STDDEV(stat_value) as std_dev,
                        MIN(stat_value) as min_val,
                        MAX(stat_value) as max_val,
                        COUNT(*) as sample_size
                    FROM position_stats
                """, season_id, current_week, position, stat_category)

                if percentiles and percentiles["sample_size"] > 0:
                    percentile_data = {
                        "p10": float(percentiles["p10"]) if percentiles["p10"] else 0,
                        "p25": float(percentiles["p25"]) if percentiles["p25"] else 0,
                        "p50": float(percentiles["p50"]) if percentiles["p50"] else 0,
                        "p75": float(percentiles["p75"]) if percentiles["p75"] else 0,
                        "p90": float(percentiles["p90"]) if percentiles["p90"] else 0,
                        "p95": float(percentiles["p95"]) if percentiles["p95"] else 0,
                        "p99": float(percentiles["p99"]) if percentiles["p99"] else 0,
                        "mean": float(percentiles["mean"]) if percentiles["mean"] else 0,
                        "std_dev": float(percentiles["std_dev"]) if percentiles["std_dev"] else 0,
                        "min": float(percentiles["min_val"]) if percentiles["min_val"] else 0,
                        "max": float(percentiles["max_val"]) if percentiles["max_val"] else 0
                    }

                    import json
                    await conn.execute("""
                        INSERT INTO weekly_percentiles (
                            season_id,
                            week_number,
                            position,
                            stat_category,
                            calculation_date,
                            percentile_data,
                            sample_size
                        ) VALUES ($1, $2, $3, $4, NOW(), $5, $6)
                        ON CONFLICT (season_id, week_number, position, stat_category, calculation_date)
                        DO UPDATE SET
                            percentile_data = EXCLUDED.percentile_data,
                            sample_size = EXCLUDED.sample_size
                    """, season_id, current_week, position, stat_category, json.dumps(percentile_data), percentiles["sample_size"])

                    logger.info(f"Calculated percentiles for {position} {stat_category}: {percentiles['sample_size']} samples")

    logger.info("Percentile calculation complete")

async def calculate_impressiveness_scores(db: Database):
    logger.info("Calculating impressiveness scores...")

    # Get active season
    season_result = db.client.table("seasons").select("season_id").eq("is_active", True).execute()
    if not season_result.data:
        logger.error("No active season found")
        return
    season_id = season_result.data[0]["season_id"]

    # Get current week
    week_result = db.client.table("games").select("game_week").eq("season_id", season_id).order("game_week", desc=True).limit(1).execute()
    if not week_result.data:
        logger.error("No games found for season")
        return
    current_week = week_result.data[0]["game_week"]

    # Get recent games
    games_result = db.client.table("games").select("game_id").eq("season_id", season_id).eq("game_week", current_week).execute()

    for game_record in games_result.data:
        game_id = game_record["game_id"]

        # Get all stats for this game
        stats_result = db.client.table("player_game_stats").select("stat_id, player_id, position, stat_category, stat_value").eq("game_id", game_id).execute()

        for stat in stats_result.data:
            # Get percentile data for this stat
            percentile_result = db.client.table("weekly_percentiles").select("percentile_data").eq("season_id", season_id).eq("week_number", current_week).eq("position", stat["position"]).eq("stat_category", stat["stat_category"]).order("calculation_date", desc=True).limit(1).execute()

            if not percentile_result.data:
                continue

            percentiles = percentile_result.data[0]["percentile_data"]
            stat_value = float(stat["stat_value"])

            if stat_value >= percentiles.get("p99", 0):
                percentile_rank = 99
            elif stat_value >= percentiles.get("p95", 0):
                percentile_rank = 95
            elif stat_value >= percentiles.get("p90", 0):
                percentile_rank = 90
            elif stat_value >= percentiles.get("p75", 0):
                percentile_rank = 75
            elif stat_value >= percentiles.get("p50", 0):
                percentile_rank = 50
            else:
                percentile_rank = 25

            impressiveness = percentile_rank * (stat_value / max(percentiles.get("mean", 1), 1))

            # Insert performance score
            db.client.table("player_performance_scores").upsert({
                "game_id": game_id,
                "player_id": stat["player_id"],
                "stat_category": stat["stat_category"],
                "raw_value": stat["stat_value"],
                "percentile_rank": percentile_rank,
                "impressiveness_score": impressiveness,
                "score_version": "v1"
            }).execute()

    logger.info("Impressiveness score calculation complete")

async def main():
    parser = argparse.ArgumentParser(description = "Sports Data Collection")
    parser.add_argument("--mode", choices = ["seed", "collect", "percentiles", "scores", "full"], required = True)
    parser.add_argument("--season", type = int, help = "NFL season year")
    parser.add_argument("--week", type = int, help = "NFL week number")
    parser.add_argument("--use-local-db", action = "store_true", help = "Also write to local database")

    args = parser.parse_args()

    Config.validate_config()

    # Always initialize Supabase
    supabase_db = Database(Config.SUPABASE_URL, Config.SUPABASE_KEY)

    # Conditionally initialize local DB
    local_db = None
    use_local = args.use_local_db or Config.USE_LOCAL_DB

    if use_local:
        local_db = LocalDatabase(Config.LOCAL_DATABASE_URL)

    try:
        await supabase_db.connect()
        if local_db:
            await local_db.connect()
            logger.info("Local database enabled - writing to both databases")

        # Pass both databases to functions
        if args.mode == "seed":
            await seed_initial_data(supabase_db, local_db)

        elif args.mode == "collect":
            await collect_weekly_nfl(supabase_db, local_db, args.season, args.week)

        elif args.mode == "percentiles":
            # Always use local DB for percentiles (if available)
            if local_db:
                await calculate_percentiles_local(local_db)
            else:
                logger.error("Percentile calculation requires local database. Use --use-local-db flag or set USE_LOCAL_DB=true in .env")

        elif args.mode == "scores":
            # Use local DB if available, otherwise Supabase
            db_for_scores = local_db if local_db else supabase_db
            await calculate_impressiveness_scores(db_for_scores)

        elif args.mode == "full":
            await collect_weekly_nfl(supabase_db, local_db, args.season, args.week)
            if local_db:
                await calculate_percentiles_local(local_db)
                await calculate_impressiveness_scores(local_db)
            else:
                logger.warning("Skipping percentiles and scores - requires local database")

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