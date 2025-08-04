import sqlite3
import csv
import requests
import time
from datetime import datetime

def get_nba_players():
    """Fetch all NBA players from the stats API"""
    url = "https://stats.nba.com/stats/commonallplayers"
    headers = {
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Connection": "keep-alive",
        "Host": "stats.nba.com",
        "Referer": "https://stats.nba.com/",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "x-nba-stats-origin": "stats",
        "x-nba-stats-token": "true"
    }
    
    params = {
        "IsOnlyCurrentSeason": "1",
        "LeagueID": "00",
        "Season": "2024-25"
    }
    
    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()
        return data["resultSets"][0]["rowSet"]
    except Exception as e:
        print(f"Error fetching players: {e}")
        return []

def get_player_info(player_id):
    """Fetch detailed player information"""
    url = "https://stats.nba.com/stats/commonplayerinfo"
    headers = {
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Connection": "keep-alive",
        "Host": "stats.nba.com",
        "Referer": "https://stats.nba.com/",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "x-nba-stats-origin": "stats",
        "x-nba-stats-token": "true"
    }
    
    params = {
        "PlayerID": player_id
    }
    
    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()
        
        # Player info is in the first result set
        player_info = data["resultSets"][0]["rowSet"][0]
        return player_info
    except Exception as e:
        print(f"Error fetching player {player_id} info: {e}")
        return None

def calculate_age(birthdate_str):
    """Calculate age from birthdate string"""
    if not birthdate_str:
        return None
    try:
        birth_date = datetime.strptime(birthdate_str, "%Y-%m-%dT%H:%M:%S")
        today = datetime.now()
        age = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
        return age
    except:
        return None

def main():
    # Connect to database
    conn = sqlite3.connect('experiments/databases/players.db')
    c = conn.cursor()
    
    # Create table if not exists
    c.execute('''CREATE TABLE IF NOT EXISTS players (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        active BOOLEAN NOT NULL,
        twitter_handle TEXT UNIQUE,
        team TEXT NOT NULL,
        position TEXT NOT NULL,
        age INTEGER NOT NULL,
        height TEXT NOT NULL,
        weight INTEGER NOT NULL,
        college TEXT,
        experience INTEGER NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    conn.commit()

    # Load Twitter handles from CSV
    twitter_handles = {}
    try:
        with open("experiments/x.csv", mode='r') as file:
            reader = csv.reader(file)
            next(reader)  # Skip header
            for row in reader:
                if len(row) >= 3:
                    twitter_handles[row[1]] = row[2] if row[2] else None
    except FileNotFoundError:
        print("x.csv not found. Continuing without Twitter handles.")

    # Fetch NBA players
    print("Fetching NBA players...")
    players = get_nba_players()
    print(f"Found {len(players)} players")

    successful_inserts = 0
    errors = 0

    for i, player in enumerate(players):
        try:
            player_id = player[0]
            player_name = player[2]
            is_active = player[4] == 1  # Convert to boolean
            
            print(f"Processing {i+1}/{len(players)}: {player_name}")
            
            # Get detailed player info
            player_info = get_player_info(player_id)
            if not player_info:
                print(f"  Could not fetch details for {player_name}")
                errors += 1
                continue
            
            # Extract player details from API response
            # player_info indices based on NBA stats API response structure
            team_name = player_info[18] if player_info[18] else "Free Agent"
            position = player_info[15] if player_info[15] else "Unknown"
            height = player_info[11] if player_info[11] else "Unknown"
            weight = int(player_info[12]) if player_info[12] else 0
            college = player_info[8] if player_info[8] else None
            experience = int(player_info[13]) if player_info[13] else 0
            birthdate = player_info[7]
            
            # Calculate age
            age = calculate_age(birthdate)
            if age is None:
                age = 0
            
            # Get Twitter handle if available
            twitter_handle = twitter_handles.get(player_name)
            
            # Insert or update player in database
            c.execute('''INSERT OR REPLACE INTO players 
                        (name, active, twitter_handle, team, position, age, height, weight, college, experience, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)''',
                     (player_name, is_active, twitter_handle, team_name, position, age, height, weight, college, experience))
            
            successful_inserts += 1
            print(f"  ✓ Added {player_name} ({team_name})")
            
            # Be respectful to the API - add small delay
            time.sleep(0.1)
            
        except Exception as e:
            print(f"  Error processing {player_name}: {e}")
            errors += 1
            continue

    # Commit all changes
    conn.commit()
    conn.close()
    
    print(f"\nCompleted!")
    print(f"Successfully processed: {successful_inserts} players")
    print(f"Errors: {errors} players")

if __name__ == "__main__":
    main()