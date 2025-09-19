import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging
from db_config import execute_query, insert_returning_id, bulk_insert

# Configure logging
logging.basicConfig(
    level = logging.INFO,
    format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Constants
STAT_TYPES = [
    "points", "rebounds", "assists", "steals", "blocks",
    "field_goal_percentage", "three_point_percentage", "free_throw_percentage",
    "plus_minus", "minutes"
]

# Minimum games played to be included in statistical calculations
MIN_GAMES_PLAYED = 5

# Z-score display thresholds (how impressive a performance needs to be to stay visible)
Z_SCORE_THRESHOLDS = {
    "1_day": 1.5,    # Z-score needed to stay visible for 1 day
    "3_days": 2.0,   # Z-score needed to stay visible for 3 days
    "7_days": 2.5,   # Z-score needed to stay visible for 7 days
    "14_days": 3.0,  # Z-score needed to stay visible for 14 days
    "30_days": 3.5   # Z-score needed to stay visible for 30 days
}

# Weights for combining player-specific and league-wide z-scores
PLAYER_Z_SCORE_WEIGHT = 0.4
LEAGUE_Z_SCORE_WEIGHT = 0.6

def calculate_league_averages(season = None):
    """
    Calculate league-wide averages and standard deviations for all stat types
    
    Args:
        season (str, optional): Season to calculate stats for (e.g., "2023-24")
                               If None, uses current season
                               
    Returns:
        dict: Dictionary of statistical averages and standard deviations by stat type
    """
    # If no season provided, use current season from most recent game
    if not season:
        season_query = "SELECT season FROM games ORDER BY game_date DESC LIMIT 1"
        season_result = execute_query(season_query)
        if season_result:
            season = season_result[0]["season"]
        else:
            logger.error("No games found in database")
            return {}
    
    logger.info(f"Calculating league averages for {season} season")
    
    # Dictionary to store results
    league_stats = {}
    
    for stat_type in STAT_TYPES:
        # Query to get all values for this stat type where player has played enough games
        query = f"""
        SELECT pgs.{stat_type} 
        FROM player_game_stats pgs
        JOIN games g ON pgs.game_id = g.id
        JOIN (
            SELECT player_id, COUNT(*) as games_played
            FROM player_game_stats
            GROUP BY player_id
            HAVING COUNT(*) >= %s
        ) qualified_players ON pgs.player_id = qualified_players.player_id
        WHERE g.season = %s
        AND pgs.{stat_type} IS NOT NULL
        """
        
        results = execute_query(query, (MIN_GAMES_PLAYED, season))
        
        if not results:
            logger.warning(f"No data found for {stat_type} in {season} season")
            continue
            
        # Extract values
        values = [float(row[stat_type]) for row in results if row[stat_type] is not None]
        
        if not values:
            logger.warning(f"No valid values for {stat_type} in {season} season")
            continue
            
        # Calculate statistics
        mean = np.mean(values)
        std_dev = np.std(values)
        min_val = np.min(values)
        max_val = np.max(values)
        sample_size = len(values)
        
        # Store in results dictionary
        league_stats[stat_type] = {
            "mean": mean,
            "std_dev": std_dev,
            "min": min_val,
            "max": max_val,
            "sample_size": sample_size
        }
        
        # Store in database
        update_query = """
        INSERT INTO league_averages (season, stat_type, average_value, standard_deviation, 
                                    min_value, max_value, sample_size, last_updated)
        VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
        ON CONFLICT (season, stat_type) 
        DO UPDATE SET 
            average_value = EXCLUDED.average_value,
            standard_deviation = EXCLUDED.standard_deviation,
            min_value = EXCLUDED.min_value,
            max_value = EXCLUDED.max_value,
            sample_size = EXCLUDED.sample_size,
            last_updated = NOW()
        """
        
        execute_query(
            update_query, 
            (season, stat_type, mean, std_dev, min_val, max_val, sample_size),
            fetch = False
        )
        
        logger.info(f"Updated league averages for {stat_type} in {season} season")
    
    return league_stats

def calculate_player_averages(player_id, season = None):
    """
    Calculate averages and standard deviations for a specific player
    
    Args:
        player_id (int): Database ID of the player
        season (str, optional): Season to calculate stats for
        
    Returns:
        dict: Dictionary of player's statistical averages by stat type
    """
    # If no season provided, use current season from most recent game
    if not season:
        season_query = "SELECT season FROM games ORDER BY game_date DESC LIMIT 1"
        season_result = execute_query(season_query)
        if season_result:
            season = season_result[0]["season"]
        else:
            logger.error("No games found in database")
            return {}
    
    logger.info(f"Calculating averages for player {player_id} in {season} season")
    
    # Dictionary to store results
    player_stats = {}
    
    for stat_type in STAT_TYPES:
        # Query to get all values for this stat type
        query = f"""
        SELECT pgs.{stat_type} 
        FROM player_game_stats pgs
        JOIN games g ON pgs.game_id = g.id
        WHERE pgs.player_id = %s
        AND g.season = %s
        AND pgs.{stat_type} IS NOT NULL
        """
        
        results = execute_query(query, (player_id, season))
        
        if not results:
            logger.warning(f"No data found for player {player_id} for {stat_type} in {season} season")
            continue
            
        # Extract values
        values = [float(row[stat_type]) for row in results if row[stat_type] is not None]
        
        if not values:
            logger.warning(f"No valid values for player {player_id} for {stat_type} in {season} season")
            continue
            
        # Calculate statistics
        mean = np.mean(values)
        median = np.median(values)
        std_dev = np.std(values)
        min_val = np.min(values)
        max_val = np.max(values)
        percentile_25 = np.percentile(values, 25)
        percentile_75 = np.percentile(values, 75)
        sample_size = len(values)
        
        # Store in results dictionary
        player_stats[stat_type] = {
            "mean": mean,
            "median": median,
            "std_dev": std_dev,
            "min": min_val,
            "max": max_val,
            "percentile_25": percentile_25,
            "percentile_75": percentile_75,
            "sample_size": sample_size
        }
        
        # Store in database
        update_query = """
        INSERT INTO player_stat_distributions (
            player_id, season, stat_type, mean, median, std_dev, 
            min_value, max_value, percentile_25, percentile_75, 
            sample_size, last_updated
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
        ON CONFLICT (player_id, season, stat_type) 
        DO UPDATE SET 
            mean = EXCLUDED.mean,
            median = EXCLUDED.median,
            std_dev = EXCLUDED.std_dev,
            min_value = EXCLUDED.min_value,
            max_value = EXCLUDED.max_value,
            percentile_25 = EXCLUDED.percentile_25,
            percentile_75 = EXCLUDED.percentile_75,
            sample_size = EXCLUDED.sample_size,
            last_updated = NOW()
        """
        
        execute_query(
            update_query, 
            (
                player_id, season, stat_type, mean, median, std_dev, 
                min_val, max_val, percentile_25, percentile_75, sample_size
            ),
            fetch = False
        )
        
        logger.info(f"Updated distribution stats for player {player_id}, {stat_type} in {season} season")
    
    return player_stats

def analyze_game_performance(game_id):
    """
    Analyze performances from a specific game, calculating z-scores and identifying
    impressive performances
    
    Args:
        game_id (int): Database ID of the game
        
    Returns:
        list: List of impressive performances with z-scores
    """
    logger.info(f"Analyzing performances for game {game_id}")
    
    # Get game info
    game_query = "SELECT * FROM games WHERE id = %s"
    game_info = execute_query(game_query, (game_id,))
    
    if not game_info:
        logger.error(f"Game {game_id} not found in database")
        return []
        
    game_info = game_info[0]
    season = game_info["season"]
    
    # Get all player performances from this game
    stats_query = """
    SELECT 
        pgs.*, 
        p.id as player_id, 
        p.full_name as player_name
    FROM 
        player_game_stats pgs
    JOIN 
        players p ON pgs.player_id = p.id
    WHERE 
        pgs.game_id = %s
    """
    
    performances = execute_query(stats_query, (game_id,))
    
    if not performances:
        logger.warning(f"No performances found for game {game_id}")
        return []
    
    # Get league averages for this season
    league_stats_query = """
    SELECT 
        stat_type, 
        average_value, 
        standard_deviation
    FROM 
        league_averages
    WHERE 
        season = %s
    """
    
    league_stats_results = execute_query(league_stats_query, (season,))
    
    if not league_stats_results:
        logger.warning(f"No league averages found for {season} season. Calculating now...")
        calculate_league_averages(season)
        league_stats_results = execute_query(league_stats_query, (season,))
        
    # Convert to dictionary for easier lookup
    league_stats = {}
    for row in league_stats_results:
        league_stats[row["stat_type"]] = {
            "mean": float(row["average_value"]),
            "std_dev": float(row["standard_deviation"])
        }
    
    # Analyze each performance
    impressive_performances = []
    
    for performance in performances:
        player_id = performance["player_id"]
        
        # Get player's personal averages
        player_stats_query = """
        SELECT 
            stat_type, 
            mean, 
            std_dev
        FROM 
            player_stat_distributions
        WHERE 
            player_id = %s
            AND season = %s
        """
        
        player_stats_results = execute_query(player_stats_query, (player_id, season))
        
        if not player_stats_results:
            logger.info(f"No player stats found for player {player_id}. Calculating now...")
            calculate_player_averages(player_id, season)
            player_stats_results = execute_query(player_stats_query, (player_id, season))
        
        # Convert to dictionary for easier lookup
        player_stats = {}
        for row in player_stats_results:
            player_stats[row["stat_type"]] = {
                "mean": float(row["mean"]),
                "std_dev": float(row["std_dev"])
            }
        
        # Calculate z-scores for each stat
        for stat_type in STAT_TYPES:
            if stat_type not in performance or performance[stat_type] is None:
                continue
                
            value = float(performance[stat_type])
            
            # Calculate league z-score
            if stat_type in league_stats and league_stats[stat_type]["std_dev"] > 0:
                league_mean = league_stats[stat_type]["mean"]
                league_std = league_stats[stat_type]["std_dev"]
                league_z_score = (value - league_mean) / league_std
            else:
                league_z_score = 0
            
            # Calculate player-specific z-score
            if stat_type in player_stats and player_stats[stat_type]["std_dev"] > 0:
                player_mean = player_stats[stat_type]["mean"]
                player_std = player_stats[stat_type]["std_dev"]
                player_z_score = (value - player_mean) / player_std
            else:
                player_z_score = 0
            
            # Combined weighted z-score
            combined_z_score = (
                PLAYER_Z_SCORE_WEIGHT * player_z_score + 
                LEAGUE_Z_SCORE_WEIGHT * league_z_score
            )
            
            # Only consider positive z-scores (better than average performances)
            if combined_z_score > Z_SCORE_THRESHOLDS["1_day"]:
                # Calculate display duration based on how impressive the performance is
                display_until = datetime.now()
                
                if combined_z_score >= Z_SCORE_THRESHOLDS["30_days"]:
                    display_until += timedelta(days = 30)
                elif combined_z_score >= Z_SCORE_THRESHOLDS["14_days"]:
                    display_until += timedelta(days = 14)
                elif combined_z_score >= Z_SCORE_THRESHOLDS["7_days"]:
                    display_until += timedelta(days = 7)
                elif combined_z_score >= Z_SCORE_THRESHOLDS["3_days"]:
                    display_until += timedelta(days = 3)
                else:
                    display_until += timedelta(days = 1)
                
                # Add to impressive performances
                impressive_performances.append({
                    "player_id": player_id,
                    "game_id": game_id,
                    "stat_type": stat_type,
                    "value": value,
                    "league_z_score": league_z_score,
                    "player_z_score": player_z_score,
                    "z_score": combined_z_score,
                    "display_until": display_until.strftime("%Y-%m-%d")
                })
    
    # If we found any impressive performances, store them in the database
    if impressive_performances:
        # Start with ranking within this game's impressive performances
        for stat_type in STAT_TYPES:
            # Filter performances for this stat type
            stat_performances = [p for p in impressive_performances if p["stat_type"] == stat_type]
            
            # Sort by z-score descending
            stat_performances.sort(key = lambda x: x["z_score"], reverse = True)
            
            # Add rank
            for i, performance in enumerate(stat_performances):
                performance["league_rank"] = i + 1
        
        # Store in database
        for performance in impressive_performances:
            # Get current rankings for this stat
            rank_query = """
            SELECT COUNT(*) + 1 as player_rank
            FROM impressive_performances
            WHERE 
                stat_type = %s
                AND z_score > %s
                AND display_until >= CURRENT_DATE
            """
            
            rank_result = execute_query(
                rank_query, 
                (performance["stat_type"], performance["z_score"])
            )
            
            player_rank = rank_result[0]["player_rank"] if rank_result else 1
            
            # Insert into database
            insert_query = """
            INSERT INTO impressive_performances (
                player_id, game_id, stat_type, value, z_score,
                league_rank, player_rank, combined_score, display_until
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """
            
            insert_returning_id(
                "impressive_performances",
                {
                    "player_id": performance["player_id"],
                    "game_id": performance["game_id"],
                    "stat_type": performance["stat_type"],
                    "value": performance["value"],
                    "z_score": performance["z_score"],
                    "league_rank": performance["league_rank"],
                    "player_rank": player_rank,
                    "combined_score": performance["z_score"],
                    "display_until": performance["display_until"]
                }
            )
    
    return impressive_performances

def get_recent_impressive_performances(limit = 10):
    """
    Get recent impressive performances to display on the homepage
    
    Args:
        limit (int): Maximum number of performances to return
        
    Returns:
        list: List of impressive performances with player and game details
    """
    query = """
    SELECT 
        ip.*, 
        p.full_name as player_name,
        g.game_date,
        g.season,
        g.home_team,
        g.away_team
    FROM 
        impressive_performances ip
    JOIN 
        players p ON ip.player_id = p.id
    JOIN 
        games g ON ip.game_id = g.id
    WHERE 
        ip.display_until >= CURRENT_DATE
    ORDER BY 
        ip.z_score DESC
    LIMIT %s
    """
    
    performances = execute_query(query, (limit,))
    return performances

def calculate_player_distributions(player_id, season = None):
    """
    Calculate detailed statistical distributions for a player's performance
    
    Args:
        player_id (int): Database ID of the player
        season (str, optional): Season to analyze
        
    Returns:
        dict: Dictionary of distribution data by stat type
    """
    # If no season provided, use current season
    if not season:
        season_query = "SELECT season FROM games ORDER BY game_date DESC LIMIT 1"
        season_result = execute_query(season_query)
        if season_result:
            season = season_result[0]["season"]
        else:
            logger.error("No games found in database")
            return {}
    
    # Get player stats for the season
    query = f"""
    SELECT 
        pgs.*,
        g.game_date
    FROM 
        player_game_stats pgs
    JOIN 
        games g ON pgs.game_id = g.id
    WHERE 
        pgs.player_id = %s
        AND g.season = %s
    ORDER BY 
        g.game_date
    """
    
    results = execute_query(query, (player_id, season))
    
    if not results:
        logger.warning(f"No stats found for player {player_id} in season {season}")
        return {}
    
    # Convert to DataFrame for analysis
    df = pd.DataFrame(results)
    
    # Calculate histograms and distribution data for each stat type
    distributions = {}
    
    for stat_type in STAT_TYPES:
        if stat_type not in df.columns or df[stat_type].isna().all():
            continue
            
        # Basic statistics
        values = df[stat_type].dropna().astype(float)
        
        if len(values) < MIN_GAMES_PLAYED:
            continue
            
        # Create histogram data
        hist, bin_edges = np.histogram(values, bins = 'auto')
        
        # Calculate cumulative distribution
        sorted_values = np.sort(values)
        cumulative_prob = np.arange(1, len(sorted_values) + 1) / len(sorted_values)
        
        # Store distribution data
        distributions[stat_type] = {
            "histogram": {
                "counts": hist.tolist(),
                "bin_edges": bin_edges.tolist()
            },
            "cumulative_distribution": {
                "values": sorted_values.tolist(),
                "probabilities": cumulative_prob.tolist()
            },
            "time_series": {
                "dates": df["game_date"].astype(str).tolist(),
                "values": df[stat_type].tolist()
            }
        }
    
    return distributions

def calculate_league_distributions(season = None):
    """
    Calculate detailed statistical distributions for league-wide performance
    
    Args:
        season (str, optional): Season to analyze
        
    Returns:
        dict: Dictionary of distribution data by stat type
    """
    # If no season provided, use current season
    if not season:
        season_query = "SELECT season FROM games ORDER BY game_date DESC LIMIT 1"
        season_result = execute_query(season_query)
        if season_result:
            season = season_result[0]["season"]
        else:
            logger.error("No games found in database")
            return {}
    
    # Dictionary to store results
    distributions = {}
    
    for stat_type in STAT_TYPES:
        # Query to get all values for this stat type from players with enough games
        query = f"""
        SELECT pgs.{stat_type} 
        FROM player_game_stats pgs
        JOIN games g ON pgs.game_id = g.id
        JOIN (
            SELECT player_id, COUNT(*) as games_played
            FROM player_game_stats
            GROUP BY player_id
            HAVING COUNT(*) >= %s
        ) qualified_players ON pgs.player_id = qualified_players.player_id
        WHERE g.season = %s
        AND pgs.{stat_type} IS NOT NULL
        """
        
        results = execute_query(query, (MIN_GAMES_PLAYED, season))
        
        if not results:
            logger.warning(f"No data found for {stat_type} in {season} season")
            continue
            
        # Extract values
        values = np.array([float(row[stat_type]) for row in results if row[stat_type] is not None])
        
        if len(values) == 0:
            continue
            
        # Create histogram data
        hist, bin_edges = np.histogram(values, bins = 'auto')
        
        # Calculate cumulative distribution
        sorted_values = np.sort(values)
        cumulative_prob = np.arange(1, len(sorted_values) + 1) / len(sorted_values)
        
        # Store distribution data
        distributions[stat_type] = {
            "histogram": {
                "counts": hist.tolist(),
                "bin_edges": bin_edges.tolist()
            },
            "cumulative_distribution": {
                "values": sorted_values.tolist(),
                "probabilities": cumulative_prob.tolist()
            }
        }
    
    return distributions