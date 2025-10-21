"""
Debug script to test ESPN roster fetching
"""
import requests
import json
from config import Config

# Test fetching roster for one team
session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Sports Analytics Platform)"
})

espn_base = Config.get_espn_url("nfl", "")

# First get teams
print("Fetching teams...")
url = f"{espn_base}teams"
print(f"URL: {url}")
response = session.get(url)
teams_data = response.json()

# Get first team
teams = teams_data.get("sports", [{}])[0].get("leagues", [{}])[0].get("teams", [])
if teams:
    first_team = teams[0].get("team", {})
    team_id = str(first_team.get("id"))
    team_name = first_team.get("name")

    print(f"\nTesting roster for: {team_name} (ID: {team_id})")

    # Try fetching roster
    roster_url = f"{espn_base}teams/{team_id}/roster"
    print(f"Roster URL: {roster_url}")

    roster_response = session.get(roster_url)
    print(f"Status Code: {roster_response.status_code}")

    if roster_response.status_code == 200:
        roster_data = roster_response.json()

        # Save to file for inspection
        with open("roster_response.json", "w") as f:
            json.dump(roster_data, f, indent=2)

        print("\nRoster data structure:")
        print(f"Keys: {list(roster_data.keys())}")

        # Check different possible locations
        athletes = roster_data.get("athletes", [])
        print(f"\nAthletes (direct): {len(athletes)}")

        # Check if it's nested differently
        if "team" in roster_data:
            print(f"Has 'team' key: {list(roster_data['team'].keys())}")
            if "athletes" in roster_data["team"]:
                athletes = roster_data["team"]["athletes"]
                print(f"Athletes (team.athletes): {len(athletes)}")

        if athletes:
            print(f"\nFirst athlete structure:")
            print(json.dumps(athletes[0], indent=2))
        else:
            print("\n⚠️  No athletes found!")
            print("Full response saved to roster_response.json")
    else:
        print(f"Error: {roster_response.status_code}")
        print(roster_response.text)
else:
    print("No teams found!")
