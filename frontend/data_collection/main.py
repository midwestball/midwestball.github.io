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
    
    async with db.acquire() as conn:
        season_id = await conn.fetchval("""
            SELECT season_id FROM seasons WHERE is_active = TRUE
        """)
        
        current_week = await conn.fetchval("""
            SELECT MAX(game_week) FROM games WHERE season_id = $1
        """, season_id)
        
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
                    """, season_id, current_week, position, stat_category, percentile_data, percentiles["sample_size"])
                    
                    logger.info(f"Calculated percentiles for {position} {stat_category}: {percentiles['sample_size']} samples")
    
    logger.info("Percentile calculation complete")

async def calculate_impressiveness_scores(db: Database):
    logger.info("Calculating impressiveness scores...")
    
    async with db.acquire() as conn:
        season_id = await conn.fetchval("""
            SELECT season_id FROM seasons WHERE is_active = TRUE
        """)
        
        current_week = await conn.fetchval("""
            SELECT MAX(game_week) FROM games WHERE season_id = $1
        """, season_id)
        
        recent_games = await conn.fetch("""
            SELECT game_id FROM games 
            WHERE season_id = $1 AND game_week = $2
        """, season_id, current_week)
        
        for game_record in recent_games:
            game_id = game_record["game_id"]
            
            stats = await conn.fetch("""
                SELECT 
                    pgs.stat_id,
                    pgs.player_id,
                    pgs.position,
                    pgs.stat_category,
                    pgs.stat_value
                FROM player_game_stats pgs
                WHERE pgs.game_id = $1
            """, game_id)
            
            for stat in stats:
                percentile_record = await conn.fetchrow("""
                    SELECT percentile_data 
                    FROM weekly_percentiles 
                    WHERE season_id = $1 
                        AND week_number = $2
                        AND position = $3
                        AND stat_category = $4
                    ORDER BY calculation_date DESC 
                    LIMIT 1
                """, season_id, current_week, stat["position"], stat["stat_category"])
                
                if not percentile_record:
                    continue
                
                percentiles = percentile_record["percentile_data"]
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
                
                await conn.execute("""
                    INSERT INTO player_performance_scores (
                        game_id,
                        player_id,
                        stat_category,
                        raw_value,
                        percentile_rank,
                        impressiveness_score,
                        score_version
                    ) VALUES ($1, $2, $3, $4, $5, $6, 'v1')
                    ON CONFLICT (game_id, player_id, stat_category, score_version) 
                    DO UPDATE SET
                        raw_value = EXCLUDED.raw_value,
                        percentile_rank = EXCLUDED.percentile_rank,
                        impressiveness_score = EXCLUDED.impressiveness_score,
                        calculated_at = NOW()
                """, game_id, stat["player_id"], stat["stat_category"], stat["stat_value"], percentile_rank, impressiveness)
    
    logger.info("Impressiveness score calculation complete")

async def main():
    parser = argparse.ArgumentParser(description = "Sports Data Collection")
    parser.add_argument("--mode", choices = ["seed", "collect", "percentiles", "scores", "full"], required = True)
    parser.add_argument("--season", type = int, help = "NFL season year")
    parser.add_argument("--week", type = int, help = "NFL week number")
    
    args = parser.parse_args()
    
    Config.validate_config()
    
    db = Database(Config.DATABASE_URL)
    
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