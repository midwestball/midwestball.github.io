"""
Debug script to investigate game collection errors
"""
import requests
import json
from config import Config

# Test fetching a specific game that's failing
session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Sports Analytics Platform)"
})

espn_base = Config.get_espn_url("nfl", "")

# The game that's failing
game_id = "401671696"

print(f"Fetching game summary for: {game_id}")
url = f"{espn_base}summary"
params = {"event": game_id}

response = session.get(url, params=params)
print(f"Status: {response.status_code}")

if response.status_code == 200:
    data = response.json()

    # Save full response
    with open("game_debug.json", "w") as f:
        json.dump(data, f, indent=2)
    print("Saved full response to game_debug.json")

    # Check boxscore structure
    boxscore = data.get("boxscore", {})
    print(f"\nBoxscore keys: {boxscore.keys()}")

    players_data = boxscore.get("players", [])
    print(f"Number of teams: {len(players_data)}")

    if players_data:
        first_team = players_data[0]
        print(f"\nFirst team keys: {first_team.keys()}")
        print(f"Team ID: {first_team.get('team', {}).get('id')}")

        statistics = first_team.get("statistics", [])
        print(f"Number of stat groups: {len(statistics)}")

        if statistics:
            first_group = statistics[0]
            print(f"\nFirst stat group keys: {first_group.keys()}")
            print(f"Stat group name: {first_group.get('name')}")

            athletes = first_group.get("athletes", [])
            print(f"Number of athletes: {len(athletes)}")

            if athletes:
                first_athlete = athletes[0]
                print(f"\nFirst athlete keys: {list(first_athlete.keys())}")

                athlete_info = first_athlete.get("athlete", {})
                print(f"Athlete info type: {type(athlete_info)}")
                print(f"Athlete info: {athlete_info}")

                if isinstance(athlete_info, dict):
                    print(f"Athlete ID: {athlete_info.get('id')}")
                    print(f"Athlete name: {athlete_info.get('displayName')}")
                    print(f"Athlete keys: {list(athlete_info.keys())}")
                else:
                    print(f"⚠️  Athlete info is not a dict! It's: {type(athlete_info)}")
                    print(f"Value: {athlete_info}")

                # Check stats
                stats = first_athlete.get("stats", [])
                print(f"\nStats type: {type(stats)}")
                print(f"Stats: {stats}")

                if isinstance(stats, list) and stats:
                    print(f"First stat: {stats[0]}")
                    print(f"First stat type: {type(stats[0])}")

                # Check the stat group labels
                labels = first_group.get("labels", [])
                keys = first_group.get("keys", [])
                print(f"\nStat labels: {labels}")
                print(f"Stat keys: {keys}")
                print(f"\nMapping stats to labels:")
                for i, (label, key, value) in enumerate(zip(labels, keys, stats)):
                    print(f"  {key}: {label} = {value}")
else:
    print(f"Error: {response.status_code}")
    print(response.text)
