import requests
import json
import os
from bs4 import BeautifulSoup
import time
from datetime import datetime

# For Vercel, we'll use a static JSON file that gets updated during build time
STATIC_PLAYERS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'data', 'players.json')

# Check if running in Vercel environment
if not os.environ.get('VERCEL'):
    # Use environment variable for cache directory
    CACHE_DIR = os.getenv('CACHE_DIR', 'cache')
    CACHE_PATH = os.path.join(CACHE_DIR, 'players.json')
    CACHE_TIMESTAMP_PATH = os.path.join(CACHE_DIR, 'last_cached.txt')
    # Ensure cache directory exists
    os.makedirs(CACHE_DIR, exist_ok=True)

def get_current_players():
    """Retrieve and process list of current NBA players."""
    url = "https://www.basketball-reference.com/players/"
    processed_players = []
    seen_names = set()

    for letter in "abcdefghijklmnopqrstuvwxyz":
        response = requests.get(url + letter + "/",
                                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"})
        if response.status_code == 429:
            print(f"Rate limit hit. Waiting before retrying {letter.upper()}...")
            time.sleep(10)
            response = requests.get(url + letter + "/",
                                    headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"})
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')
        players_table = soup.find('table', {'id': 'players'})
        rows = players_table.find('tbody').find_all('tr')

        for row in rows:
            columns = row.find_all('td')
            if not columns:
                continue

            full_name = row.find('th').text.strip()
            is_active = "*" in row.find('th').text

            name_parts = full_name.split(' ', 1)
            first_name = name_parts[0]
            last_name = name_parts[1] if len(name_parts) > 1 else ""

            if full_name not in seen_names:
                processed_players.append({
                    'name': full_name,
                    'first_name': first_name,
                    'last_name': last_name,
                    'is_active': is_active
                })
                seen_names.add(full_name)

        print(f"Finished scraping letter {letter.upper()}. Total players so far: {len(processed_players)}.")
        time.sleep(2)

    return processed_players

def cache_players():
    """Cache players to a JSON file."""
    players_data = get_current_players()

    os.makedirs('cache', exist_ok=True)

    # Write players to JSON
    with open(CACHE_PATH, 'w') as f:
        json.dump(players_data, f)

    # Record the current date as the last cached date
    with open(CACHE_TIMESTAMP_PATH, 'w') as f:
        f.write(datetime.now().strftime('%Y-%m-%d'))

    return players_data

def load_players():
    """Load players from cache or regenerate if needed."""
    try:
        # In production (Vercel), use the static file
        if os.environ.get('VERCEL'):
            with open(STATIC_PLAYERS_PATH, 'r') as f:
                return json.load(f)

        # In local development, check if the cache exists
        # Check if the cache exists and if the timestamp is valid
        with open(CACHE_PATH, 'r') as f:
            players_data = json.load(f)
        
        # Check the last cached date
        with open(CACHE_TIMESTAMP_PATH, 'r') as f:
            last_cached = f.read().strip()

        # Determine if the cache is outdated
        last_cached_date = datetime.strptime(last_cached, '%Y-%m-%d')
        current_date = datetime.now()

        # Check if the cache is older than a year
        if (current_date - last_cached_date).days > 365:
            print("Cache is outdated, updating...")
            return cache_players()

        return players_data

    except (FileNotFoundError, json.JSONDecodeError, ValueError):
        # Generate the player data
        players_data = get_current_players()
        
        # If we're in a build step on Vercel, save to static file
        if os.environ.get('VERCEL_BUILD'):
            os.makedirs(os.path.dirname(STATIC_PLAYERS_PATH), exist_ok = True)
            with open(STATIC_PLAYERS_PATH, 'w') as f:
                json.dump(players_data, f)
                
        return players_data