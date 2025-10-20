import asyncio
import logging
import sys
import argparse
from datetime import datetime

from config import Config
from database import Database
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

async def seed_initial_data(db: Database):
    logger.info("Starting initial data seeding...")
    
    nfl_collector = NFLCollector(db)
    await nfl_collector.seed_teams_and_players()
    
    logger.info("Initial seeding complete")

async def collect_weekly_nfl(
    db: Database,
    season: int = None,
    week: int = None
):
    logger.info("Starting weekly NFL collection...")
    
    if not season:
        season = Config.SPORT_CONFIG["nfl"]["current_season"]
    
    nfl_collector = NFLCollector(db)
    
    if not week:
        season_id = await db.get_active_season("nfl")
        week = await db.get_current_week(season_id)
        
        if week == 0:
            week = 1
        
        logger.info(f"Auto-detected current week: {week}")
    
    games_collected = await nfl_collector.collect_weekly_data(season, week)
    
    logger.info(f"Weekly collection complete: {games_collected} games processed")
    return games_collected

async def calculate_percentiles(db: Database):
    logger.info("Calculating weekly percentiles...")

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

    positions = ["QB", "RB", "WR", "TE"]

    key_stats = {
        "QB": ["passing_yards", "passing_touchdowns", "passer_rating"],
        "RB": ["rushing_yards", "rushing_touchdowns", "rushing_yards_per_attempt"],
        "WR": ["receptions", "receiving_yards", "receiving_touchdowns"],
        "TE": ["receptions", "receiving_yards", "receiving_touchdowns"]
    }

    logger.warning("NOTE: Percentile calculation requires creating RPC functions in Supabase")
    logger.info("You need to create a Supabase RPC function called 'calculate_percentiles' that accepts:")
    logger.info("  - p_season_id, p_week_number, p_position, p_stat_category")
    logger.info("And returns percentile data (p10, p25, p50, p75, p90, p95, p99, mean, std_dev, min, max, sample_size)")

    # For now, use RPC function approach
    for position in positions:
        stats_to_calc = key_stats.get(position, [])

        for stat_category in stats_to_calc:
            try:
                # Call Supabase RPC function for percentile calculation
                # You'll need to create this function in your Supabase database
                result = db.client.rpc(
                    "calculate_stat_percentiles",
                    {
                        "p_season_id": season_id,
                        "p_week_number": current_week,
                        "p_position": position,
                        "p_stat_category": stat_category
                    }
                ).execute()

                if result.data:
                    percentiles = result.data[0] if isinstance(result.data, list) else result.data

                    if percentiles and percentiles.get("sample_size", 0) > 0:
                        percentile_data = {
                            "p10": float(percentiles.get("p10", 0)) if percentiles.get("p10") else 0,
                            "p25": float(percentiles.get("p25", 0)) if percentiles.get("p25") else 0,
                            "p50": float(percentiles.get("p50", 0)) if percentiles.get("p50") else 0,
                            "p75": float(percentiles.get("p75", 0)) if percentiles.get("p75") else 0,
                            "p90": float(percentiles.get("p90", 0)) if percentiles.get("p90") else 0,
                            "p95": float(percentiles.get("p95", 0)) if percentiles.get("p95") else 0,
                            "p99": float(percentiles.get("p99", 0)) if percentiles.get("p99") else 0,
                            "mean": float(percentiles.get("mean", 0)) if percentiles.get("mean") else 0,
                            "std_dev": float(percentiles.get("std_dev", 0)) if percentiles.get("std_dev") else 0,
                            "min": float(percentiles.get("min_val", 0)) if percentiles.get("min_val") else 0,
                            "max": float(percentiles.get("max_val", 0)) if percentiles.get("max_val") else 0
                        }

                        # Insert percentile record
                        db.client.table("weekly_percentiles").upsert({
                            "season_id": season_id,
                            "week_number": current_week,
                            "position": position,
                            "stat_category": stat_category,
                            "percentile_data": percentile_data,
                            "sample_size": percentiles["sample_size"]
                        }).execute()

                        logger.info(f"Calculated percentiles for {position} {stat_category}: {percentiles['sample_size']} samples")

            except Exception as e:
                logger.error(f"Error calculating percentiles for {position} {stat_category}: {e}")
                logger.info("Make sure you've created the 'calculate_stat_percentiles' RPC function in Supabase")
                continue

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
    
    args = parser.parse_args()
    
    Config.validate_config()

    db = Database(Config.SUPABASE_URL, Config.SUPABASE_KEY)
    
    try:
        await db.connect()
        
        if args.mode == "seed":
            await seed_initial_data(db)
        
        elif args.mode == "collect":
            await collect_weekly_nfl(db, args.season, args.week)
        
        elif args.mode == "percentiles":
            await calculate_percentiles(db)
        
        elif args.mode == "scores":
            await calculate_impressiveness_scores(db)
        
        elif args.mode == "full":
            await collect_weekly_nfl(db, args.season, args.week)
            await calculate_percentiles(db)
            await calculate_impressiveness_scores(db)
        
        logger.info("All operations completed successfully")
    
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info = True)
        sys.exit(1)
    
    finally:
        await db.close()

if __name__ == "__main__":
    asyncio.run(main())