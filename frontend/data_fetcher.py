import requests
import json
import logging
import time
import os
import pandas as pd
from datetime import datetime, timedelta
import random
from bs4 import BeautifulSoup

# Configure logging
logging.basicConfig(
    level = logging.INFO,
    format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Constants
STATS_API_BASE_URL = "https://stats.nba.com/stats"
API_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Encoding": "gzip, deflate, br",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive",
    "Host": "stats.nba.com",
    "Origin": "https://www.nba.com",
    "Referer": "https://www.nba.com/",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "x-nba-stats-origin": "stats",
    "x-nba-stats-token": "true"
}

# NBA Stats API Endpoints
ENDPOINTS = {
    "players": "/playerindex",
    "player_game_logs": "/playergamelogs",
    "scoreboard": "/scoreboardv2",
    "box_score": "/boxscoretraditionalv2",
    "team_game_logs": "/teamgamelogs"
}

# Fallback data sources in case the NBA Stats API is unreachable
FALLBACK_SOURCES = {
    "basketball_reference": "https://www.basketball-reference.com",
    "data_nba": "https://data.nba.net"
}

def fetch_with_retry(url, headers = None, params = None, max_retries = 3, backoff_factor = 2):
    """
    Fetch data from an API with retry logic and random delays
    """
    retry_count = 0
    while retry_count < max_retries:
        try:
            # Add a random delay to avoid being blocked
            time.sleep(random.uniform(1.0, 3.0))
            
            response = requests.get(url, headers = headers, params = params, timeout = 30)
            
            # If we get rate limited, wait and try again
            if response.status_code == 429:
                retry_count += 1
                wait_time = backoff_factor ** retry_count
                logger.warning(f"Rate limited, retrying in {wait_time} seconds... ({retry_count}/{max_retries})")
                time.sleep(wait_time)
                continue
                
            # Handle other HTTP errors
            response.raise_for_status()
            
            return response.json()
            
        except requests.exceptions.RequestException as e:
            retry_count += 1
            wait_time = backoff_factor ** retry_count
            logger.warning(f"Request failed, retrying in {wait_time} seconds... ({retry_count}/{max_retries})")
            logger.error(f"Error: {e}")
            time.sleep(wait_time)
    
    # If we've exhausted our retries, return None
    logger.error(f"Failed to fetch data from {url} after {max_retries} attempts")
    return None

def fetch_active_players():
    """
    Fetch a list of all active NBA players
    """
    url = f"{STATS_API_BASE_URL}{ENDPOINTS['players']}"
    params = {
        "Historical": 0,  # 0 for active players only
        "LeagueID": "00",  # 00 is the NBA
        "Season": get_current_season(),
    }
    
    response_data = fetch_with_retry(url, headers = API_HEADERS, params = params)
    
    if not response_data:
        logger.warning("Failed to fetch players from NBA Stats API. Falling back to alternative source.")
        return fetch_players_from_basketball_reference()
        
    # Parse the response
    result_sets = response_data.get("resultSets", [])
    if not result_sets:
        logger.error("No result sets in response")
        return []
        
    headers = result_sets[0].get("headers", [])
    rows = result_sets[0].get("rowSet", [])
    
    # Find relevant column indices
    person_id_idx = headers.index("PERSON_ID") if "PERSON_ID" in headers else None
    first_name_idx = headers.index("FIRST_NAME") if "FIRST_NAME" in headers else None
    last_name_idx = headers.index("LAST_NAME") if "LAST_NAME" in headers else None
    
    if None in [person_id_idx, first_name_idx, last_name_idx]:
        logger.error("Missing required columns in player data")
        return []
    
    # Process player data
    players = []
    for row in rows:
        person_id = row[person_id_idx]
        first_name = row[first_name_idx]
        last_name = row[last_name_idx]
        
        # Create player slug based on Basketball Reference conventions
        # (first 5 of last name + first 2 of first name + 01)
        last_initial = last_name.lower()[:5]
        first_initial = first_name.lower()[:2]
        player_slug = f"{last_initial}{first_initial}01"
        
        players.append({
            "person_id": person_id,
            "first_name": first_name,
            "last_name": last_name,
            "full_name": f"{first_name} {last_name}",
            "player_slug": player_slug,
            "is_active": True
        })
    
    logger.info(f"Fetched {len(players)} active players")
    return players

def fetch_players_from_basketball_reference():
    """
    Fallback method to fetch players from Basketball Reference
    """
    players = []
    url = f"{FALLBACK_SOURCES['basketball_reference']}/players"
    seen_names = set()
    
    for letter in "abcdefghijklmnopqrstuvwxyz":
        letter_url = f"{url}/{letter}/"
        
        try:
            response = requests.get(
                letter_url,
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
                }
            )
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, "html.parser")
            players_table = soup.find("table", {"id": "players"})
            
            if not players_table:
                continue
                
            rows = players_table.find("tbody").find_all("tr")
            
            for row in rows:
                # Check for active players (marked with *)
                name_element = row.find("th")
                if not name_element:
                    continue
                    
                full_name = name_element.text.strip()
                is_active = "*" in full_name
                
                # Skip inactive players
                if not is_active:
                    continue
                    
                # Clean up the name
                full_name = full_name.replace("*", "").strip()
                
                # Skip already processed names
                if full_name in seen_names:
                    continue
                    
                seen_names.add(full_name)
                
                # Split name into first and last
                name_parts = full_name.split(" ", 1)
                first_name = name_parts[0]
                last_name = name_parts[1] if len(name_parts) > 1 else ""
                
                # Create player slug
                last_initial = last_name.lower()[:5] if last_name else ""
                first_initial = first_name.lower()[:2]
                player_slug = f"{last_initial}{first_initial}01"
                
                players.append({
                    "person_id": None,  # Not available from Basketball Reference
                    "first_name": first_name,
                    "last_name": last_name,
                    "full_name": full_name,
                    "player_slug": player_slug,
                    "is_active": True
                })
                
            # Be respectful to the website
            time.sleep(1)
            
        except Exception as e:
            logger.error(f"Error fetching players for letter {letter}: {e}")
    
    logger.info(f"Fetched {len(players)} active players from Basketball Reference")
    return players

def fetch_recent_games(days = 1):
    """
    Fetch recent NBA games
    
    Args:
        days (int): Number of days in the past to fetch
        
    Returns:
        list: List of game data dictionaries
    """
    games = []
    date = datetime.now()
    
    for _ in range(days):
        date_str = date.strftime("%Y-%m-%d")
        
        url = f"{STATS_API_BASE_URL}{ENDPOINTS['scoreboard']}"
        params = {
            "GameDate": date_str,
            "LeagueID": "00",
            "DayOffset": 0
        }
        
        response_data = fetch_with_retry(url, headers = API_HEADERS, params = params)
        
        if response_data:
            result_sets = response_data.get("resultSets", [])
            if result_sets and len(result_sets) > 0:
                headers = result_sets[0].get("headers", [])
                rows = result_sets[0].get("rowSet", [])
                
                # Find relevant column indices
                game_id_idx = headers.index("GAME_ID") if "GAME_ID" in headers else None
                game_date_idx = headers.index("GAME_DATE_EST") if "GAME_DATE_EST" in headers else None
                home_team_idx = headers.index("HOME_TEAM_ID") if "HOME_TEAM_ID" in headers else None
                visitor_team_idx = headers.index("VISITOR_TEAM_ID") if "VISITOR_TEAM_ID" in headers else None
                season_idx = headers.index("SEASON") if "SEASON" in headers else None
                
                if None not in [game_id_idx, game_date_idx, home_team_idx, visitor_team_idx, season_idx]:
                    for row in rows:
                        game_data = {
                            "game_id": row[game_id_idx],
                            "game_date": row[game_date_idx],
                            "home_team": row[home_team_idx],
                            "away_team": row[visitor_team_idx],
                            "season": row[season_idx]
                        }
                        games.append(game_data)
        
        # Move to previous day
        date = date - timedelta(days = 1)
    
    logger.info(f"Fetched {len(games)} games from the past {days} days")
    return games

def fetch_game_stats(game_id):
    """
    Fetch box score stats for a specific game
    
    Args:
        game_id (str): NBA game ID
        
    Returns:
        list: List of player stats for the game
    """
    url = f"{STATS_API_BASE_URL}{ENDPOINTS['box_score']}"
    params = {
        "GameID": game_id,
        "StartPeriod": 0,
        "EndPeriod": 0,
        "StartRange": 0,
        "EndRange": 0,
        "RangeType": 0
    }
    
    response_data = fetch_with_retry(url, headers = API_HEADERS, params = params)
    
    if not response_data:
        logger.warning(f"Failed to fetch box score for game {game_id}")
        return []
        
    # Parse the player stats
    player_stats = []
    result_sets = response_data.get("resultSets", [])
    
    for result_set in result_sets:
        if result_set.get("name") == "PlayerStats":
            headers = result_set.get("headers", [])
            rows = result_set.get("rowSet", [])
            
            # Find relevant column indices
            player_id_idx = headers.index("PLAYER_ID") if "PLAYER_ID" in headers else None
            player_name_idx = headers.index("PLAYER_NAME") if "PLAYER_NAME" in headers else None
            min_idx = headers.index("MIN") if "MIN" in headers else None
            pts_idx = headers.index("PTS") if "PTS" in headers else None
            reb_idx = headers.index("REB") if "REB" in headers else None
            ast_idx = headers.index("AST") if "AST" in headers else None
            stl_idx = headers.index("STL") if "STL" in headers else None
            blk_idx = headers.index("BLK") if "BLK" in headers else None
            fg_pct_idx = headers.index("FG_PCT") if "FG_PCT" in headers else None
            fg3_pct_idx = headers.index("FG3_PCT") if "FG3_PCT" in headers else None
            ft_pct_idx = headers.index("FT_PCT") if "FT_PCT" in headers else None
            tov_idx = headers.index("TO") if "TO" in headers else None
            plus_minus_idx = headers.index("PLUS_MINUS") if "PLUS_MINUS" in headers else None
            
            if None in [player_id_idx, min_idx, pts_idx]:
                logger.error("Missing required columns in game stats")
                return []
            
            for row in rows:
                minutes_str = row[min_idx]
                minutes = 0
                
                # Handle minutes formatting (convert "12:34" to numeric minutes)
                if minutes_str and ":" in minutes_str:
                    try:
                        mins, secs = minutes_str.split(":")
                        minutes = int(mins) + (int(secs) / 60)
                    except (ValueError, TypeError):
                        minutes = 0
                        
                player_stat = {
                    "player_id": row[player_id_idx],
                    "player_name": row[player_name_idx] if player_name_idx is not None else "",
                    "minutes": minutes,
                    "points": row[pts_idx] if pts_idx is not None else 0,
                    "rebounds": row[reb_idx] if reb_idx is not None else 0,
                    "assists": row[ast_idx] if ast_idx is not None else 0,
                    "steals": row[stl_idx] if stl_idx is not None else 0,
                    "blocks": row[blk_idx] if blk_idx is not None else 0,
                    "field_goal_percentage": row[fg_pct_idx] if fg_pct_idx is not None else None,
                    "three_point_percentage": row[fg3_pct_idx] if fg3_pct_idx is not None else None,
                    "free_throw_percentage": row[ft_pct_idx] if ft_pct_idx is not None else None,
                    "turnovers": row[tov_idx] if tov_idx is not None else 0,
                    "plus_minus": row[plus_minus_idx] if plus_minus_idx is not None else 0,
                }
                
                player_stats.append(player_stat)
    
    return player_stats

def fetch_player_season_stats(player_id, season):
    """
    Fetch a player's game-by-game stats for a season
    
    Args:
        player_id (int): NBA player ID
        season (str): Season in format "2023-24"
        
    Returns:
        list: List of game stats for the player
    """
    url = f"{STATS_API_BASE_URL}{ENDPOINTS['player_game_logs']}"
    params = {
        "PlayerID": player_id,
        "Season": season,
        "SeasonType": "Regular Season"
    }
    
    response_data = fetch_with_retry(url, headers = API_HEADERS, params = params)
    
    if not response_data:
        logger.warning(f"Failed to fetch season stats for player {player_id}")
        return []
        
    # Process the game logs
    game_logs = []
    result_sets = response_data.get("resultSets", [])
    
    if result_sets and len(result_sets) > 0:
        headers = result_sets[0].get("headers", [])
        rows = result_sets[0].get("rowSet", [])
        
        # Convert to DataFrame for easier processing
        df = pd.DataFrame(rows, columns = headers)
        
        # Convert to list of dictionaries
        if not df.empty:
            game_logs = df.to_dict("records")
    
    return game_logs

def get_current_season():
    """
    Get the current NBA season in the format "2023-24"
    """
    today = datetime.now()
    year = today.year
    
    # NBA season starts in October and ends in June
    # If we're in July, August, or September, we're between seasons
    if today.month >= 7 and today.month <= 9:
        # Use the next season (e.g., in September 2023, use "2023-24")
        return f"{year}-{str(year + 1)[-2:]}"
    elif today.month >= 10:
        # October to December of year X is part of season "X-(X+1)"
        return f"{year}-{str(year + 1)[-2:]}"
    else:
        # January to June of year X is part of season "(X-1)-X"
        return f"{year - 1}-{str(year)[-2:]}"