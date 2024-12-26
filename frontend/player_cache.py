from nba_api.stats.static import players
import json
import os

def get_current_players():
    """
    Retrieve and process list of current NBA players
    """
    # Get all players
    player_list = players.get_players()
    
    # Process and clean player names
    processed_players = []
    seen_names = set()
    
    for player in player_list:
        # Clean and standardize player name
        full_name = player['full_name']
        
        # Remove duplicates and standardize
        if full_name not in seen_names:
            processed_players.append({
                'name': full_name,
                'first_name': player['first_name'],
                'last_name': player['last_name'],
                'is_active': player['is_active']
            })
            seen_names.add(full_name)
    
    return processed_players

def cache_players():
    """
    Cache players to a JSON file to reduce API calls
    """
    players_data = get_current_players()
    
    # Ensure the cache directory exists
    os.makedirs('cache', exist_ok=True)
    
    # Write to JSON file
    with open('cache/players.json', 'w') as f:
        json.dump(players_data, f)
    
    return players_data

def load_players():
    """
    Load players from cache or regenerate
    """
    cache_path = 'cache/players.json'
    
    # Try to load from cache
    try:
        with open(cache_path, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        # If cache doesn't exist or is invalid, regenerate
        return cache_players()