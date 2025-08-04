import os
import sys
import logging
from datetime import datetime, timedelta
import time
import json

# Add parent directory to path to import modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data_fetcher import (
    fetch_active_players,
    fetch_recent_games,
    fetch_game_stats,
    get_current_season
)
from stats_analyzer import (
    calculate_league_averages,
    calculate_player_averages,
    analyze_game_performance
)
from db_config import (
    execute_query,
    insert_returning_id,
    bulk_insert
)

# Configure logging
logging.basicConfig(
    level = logging.INFO,
    format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers = [
        logging.FileHandler("data_collector.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def update_players():
    """
    Update the players table with active NBA players
    """
    logger.info("Updating players database...")
    
    try:
        # Fetch active players
        players = fetch_active_players()
        
        if not players:
            logger.error("Failed to fetch players")
            return
        
        logger.info(f"Fetched {len(players)} active players")
        
        # Update database
        for player in players:
            # Check if player already exists
            query = """
            SELECT id FROM players 
            WHERE full_name = %s OR player_slug = %s
            """
            existing = execute_query(query, (player["full_name"], player["player_slug"]))
            
            if existing:
                # Update existing player
                player_id = existing[0]["id"]
                update_query = """
                UPDATE players
                SET is_active = TRUE, last_updated = NOW()
                WHERE id = %s
                """
                execute_query(update_query, (player_id,), fetch = False)
                logger.info(f"Updated existing player: {player['full_name']}")
            else:
                # Insert new player
                insert_query = """
                INSERT INTO players (first_name, last_name, full_name, player_slug, is_active)
                VALUES (%s, %s, %s, %s, %s)
                """
                execute_query(
                    insert_query, 
                    (
                        player["first_name"], 
                        player["last_name"], 
                        player["full_name"], 
                        player["player_slug"], 
                        True
                    ),
                    fetch = False
                )
                logger.info(f"Inserted new player: {player['full_name']}")
        
        logger.info("Players database updated successfully")
        
    except Exception as e:
        logger.error(f"Error updating players: {e}")
        raise

def update_recent_games(days = 3):
    """
    Update the database with recent NBA games and stats
    
    Args:
        days (int): Number of days in the past to fetch
    """
    logger.info(f"Updating games database for the past {days} days...")
    
    try:
        # Fetch recent games
        games = fetch_recent_games(days)
        
        if not games:
            logger.warning("No recent games found or fetching failed")
            return
        
        logger.info(f"Fetched {len(games)} recent games")
        
        # Process games
        for game in games:
            # Check if game already exists
            query = "SELECT id FROM games WHERE game_id = %s"
            existing = execute_query(query, (game["game_id"],))
            
            game_db_id = None
            
            if existing:
                # Game exists, use its ID
                game_db_id = existing[0]["id"]
                logger.info(f"Game {game['game_id']} already exists with ID {game_db_id}")
            else:
                # Insert new game
                game_db_id = insert_returning_id(
                    "games",
                    {
                        "game_id": game["game_id"],
                        "game_date": game["game_date"],
                        "season": game["season"],
                        "home_team": game["home_team"],
                        "away_team": game["away_team"]
                    }
                )
                
                logger.info(f"Inserted new game {game['game_id']} with ID {game_db_id}")
            
            # Skip stats if game already exists (we don't update stats for existing games)
            if existing:
                continue
            
            # Fetch game stats
            player_stats = fetch_game_stats(game["game_id"])
            
            if not player_stats:
                logger.warning(f"No stats found for game {game['game_id']}")
                continue
            
            logger.info(f"Fetched stats for {len(player_stats)} players in game {game['game_id']}")
            
            # Process each player's stats
            for stats in player_stats:
                # Find player in database
                player_query = "SELECT id FROM players WHERE full_name = %s"
                player_result = execute_query(player_query, (stats["player_name"],))
                
                if not player_result:
                    logger.warning(f"Player {stats['player_name']} not found in database, skipping stats")
                    continue
                    
                player_id = player_result[0]["id"]
                
                # Insert player game stats
                insert_query = """
                INSERT INTO player_game_stats (
                    player_id, game_id, points, rebounds, assists, 
                    steals, blocks, minutes, field_goal_percentage,
                    three_point_percentage, free_throw_percentage,
                    turnovers, plus_minus
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (player_id, game_id) DO NOTHING
                """
                
                execute_query(
                    insert_query, 
                    (
                        player_id, game_db_id, 
                        stats.get("points", 0),
                        stats.get("rebounds", 0),
                        stats.get("assists", 0),
                        stats.get("steals", 0),
                        stats.get("blocks", 0),
                        stats.get("minutes", 0),
                        stats.get("field_goal_percentage"),
                        stats.get("three_point_percentage"),
                        stats.get("free_throw_percentage"),
                        stats.get("turnovers", 0),
                        stats.get("plus_minus", 0)
                    ),
                    fetch = False
                )
                
                logger.info(f"Inserted stats for player {stats['player_name']} in game {game['game_id']}")
            
            # Now analyze the game performance
            if game_db_id:
                analyze_game_performance(game_db_id)
        
        logger.info("Game and stats update completed")
        
    except Exception as e:
        logger.error(f"Error updating games: {e}")
        raise

def update_statistical_distributions():
    """
    Update statistical distributions for players and the league
    """
    logger.info("Updating statistical distributions...")
    
    try:
        # Get current season
        season = get_current_season()
        
        # Update league averages
        league_stats = calculate_league_averages(season)
        logger.info("League averages updated successfully")
        
        # Update player averages for active players with enough games
        player_query = """
        SELECT DISTINCT p.id 
        FROM players p
        JOIN player_game_stats pgs ON p.id = pgs.player_id
        JOIN games g ON pgs.game_id = g.id
        WHERE g.season = %s
        AND p.is_active = TRUE
        GROUP BY p.id
        HAVING COUNT(pgs.id) >= 5
        """
        
        players = execute_query(player_query, (season,))
        
        if players:
            for player in players:
                player_id = player["id"]
                calculate_player_averages(player_id, season)
                logger.info(f"Updated player averages for player {player_id}")
        
        logger.info("Statistical distributions update completed")
        
    except Exception as e:
        logger.error(f"Error updating statistical distributions: {e}")
        raise

def run_daily_update():
    """
    Run a complete daily update of the database
    """
    logger.info("Starting daily data update...")
    
    try:
        # Update players
        update_players()
        
        # Update recent games (last 3 days to catch any missing data)
        update_recent_games(3)
        
        # Update statistical distributions
        update_statistical_distributions()
        
        logger.info("Daily update completed successfully")
        
    except Exception as e:
        logger.error(f"Error during daily update: {e}")
        raise

if __name__ == "__main__":
    # Get command line arguments
    import argparse
    
    parser = argparse.ArgumentParser(description = "NBA data collection script")
    parser.add_argument("--players", action = "store_true", help = "Update players only")
    parser.add_argument("--games", action = "store_true", help = "Update games only")
    parser.add_argument("--stats", action = "store_true", help = "Update statistics only")
    parser.add_argument("--days", type = int, default = 3, help = "Number of days to fetch (default: 3)")
    parser.add_argument("--full", action = "store_true", help = "Run full update")
    
    args = parser.parse_args()
    
    try:
        if args.players:
            update_players()
        elif args.games:
            update_recent_games(args.days)
        elif args.stats:
            update_statistical_distributions()
        elif args.full:
            run_daily_update()
        else:
            # Default: run daily update
            run_daily_update()
    except Exception as e:
        logger.error(f"Script failed: {e}")
        sys.exit(1)