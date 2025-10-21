"""
Debug version of seed to see what's happening with roster fetching
"""
import asyncio
import requests
import time
import logging
import sys
from config import Config
from local_database import LocalDatabase
from database import Database

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)

logger = logging.getLogger(__name__)

async def debug_seed():
    """Debug version of seed that shows detailed info"""

    local_db = LocalDatabase(Config.LOCAL_DATABASE_URL)
    supabase_db = Database(Config.SUPABASE_URL, Config.SUPABASE_KEY)

    await local_db.connect()
    await supabase_db.connect()

    try:
        sport_id = await local_db.get_sport_id("nfl")
        logger.info(f"Sport ID: {sport_id}")

        session = requests.Session()
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Sports Analytics Platform)"
        })

        espn_base = Config.get_espn_url("nfl", "")

        # Get teams
        url = f"{espn_base}teams"
        response = session.get(url)
        teams_data = response.json()

        teams = teams_data.get("sports", [{}])[0].get("leagues", [{}])[0].get("teams", [])
        logger.info(f"Found {len(teams)} teams")

        # Just test the first team
        team = teams[0]
        team_info = team.get("team", {})
        team_external_id = str(team_info.get("id"))
        team_name = team_info.get("name")

        logger.info(f"\n{'='*60}")
        logger.info(f"Testing team: {team_name} (ID: {team_external_id})")
        logger.info(f"{'='*60}")

        team_record = {
            "name": team_info.get("name"),
            "abbreviation": team_info.get("abbreviation"),
            "displayName": team_info.get("displayName"),
            "location": team_info.get("location"),
            "color": team_info.get("color"),
            "logo": team_info.get("logos", [{}])[0].get("href") if team_info.get("logos") else None,
            "metadata": {}
        }

        team_id = await local_db.get_or_create_team(
            sport_id,
            team_external_id,
            team_record
        )
        logger.info(f"Team ID in database: {team_id}")

        # Fetch roster
        roster_url = f"{espn_base}teams/{team_external_id}/roster"
        logger.info(f"Fetching roster from: {roster_url}")

        roster_response = session.get(roster_url)
        logger.info(f"Response status: {roster_response.status_code}")

        roster_data = roster_response.json()

        # Debug: show the structure
        logger.info(f"\nRoster data keys: {list(roster_data.keys())}")

        # ESPN API returns athletes grouped by position
        athlete_groups = roster_data.get("athletes", [])
        logger.info(f"Athlete groups: {len(athlete_groups)}")

        # Flatten all athletes from all groups
        all_athletes = []
        for group in athlete_groups:
            group_name = group.get("position", "unknown")
            items = group.get("items", [])
            logger.info(f"  - {group_name}: {len(items)} players")
            all_athletes.extend(items)

        logger.info(f"\n{'='*60}")
        logger.info(f"Processing {len(all_athletes)} total athletes")
        logger.info(f"{'='*60}")

        # Process first 3 athletes
        for i, athlete in enumerate(all_athletes[:3]):
            logger.info(f"\n--- Athlete {i+1} ---")
            logger.info(f"Athlete keys: {list(athlete.keys())}")
            logger.info(f"ID: {athlete.get('id')}")
            logger.info(f"Name: {athlete.get('displayName')} / {athlete.get('name')}")
            logger.info(f"Position (raw): {athlete.get('position')}")
            logger.info(f"Position type: {type(athlete.get('position'))}")

            if isinstance(athlete.get('position'), dict):
                logger.info(f"Position.abbreviation: {athlete.get('position', {}).get('abbreviation')}")

            logger.info(f"Jersey: {athlete.get('jersey')}")

            player_external_id = str(athlete.get("id"))

            # Build player record
            player_record = {
                "displayName": athlete.get("displayName") or athlete.get("name") or f"Player {athlete.get('id', 'Unknown')}",
                "position": athlete.get("position", {}).get("abbreviation") if isinstance(athlete.get("position"), dict) else athlete.get("position"),
                "jersey": athlete.get("jersey"),
                "team_id": team_id,
                "metadata": {
                    "height": athlete.get("height"),
                    "weight": athlete.get("weight"),
                    "age": athlete.get("age"),
                    "experience": athlete.get("experience", {}).get("years") if isinstance(athlete.get("experience"), dict) else None
                }
            }

            logger.info(f"Player record to insert: {player_record}")

            # Insert player
            try:
                player_id = await local_db.get_or_create_player(
                    sport_id,
                    player_external_id,
                    player_record
                )
                logger.info(f"✓ Created player ID: {player_id}")
            except Exception as e:
                logger.error(f"✗ Error creating player: {e}", exc_info=True)

        # Check final count
        players_count = await local_db.fetch_one("SELECT COUNT(*) as count FROM players WHERE current_team_id = $1", team_id)
        logger.info(f"\nTotal players for {team_name}: {players_count['count']}")

    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)

    finally:
        await local_db.close()
        await supabase_db.close()

if __name__ == "__main__":
    asyncio.run(debug_seed())
