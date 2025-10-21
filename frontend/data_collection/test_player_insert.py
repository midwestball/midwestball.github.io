"""
Test script to verify player insertion works
"""
import asyncio
import logging
from config import Config
from local_database import LocalDatabase
from database import Database

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_player_insert():
    """Test inserting a player into both databases"""

    # Initialize databases
    local_db = LocalDatabase(Config.LOCAL_DATABASE_URL)
    supabase_db = Database(Config.SUPABASE_URL, Config.SUPABASE_KEY)

    await local_db.connect()
    await supabase_db.connect()

    try:
        # Get sport_id
        sport_id = await local_db.get_sport_id("nfl")
        logger.info(f"Sport ID: {sport_id}")

        # Check if we have teams
        teams_count = await local_db.fetch_one("SELECT COUNT(*) as count FROM teams")
        logger.info(f"Teams in local DB: {teams_count['count']}")

        # Get a team to use
        team = await local_db.fetch_one("SELECT team_id FROM teams LIMIT 1")
        if not team:
            logger.error("No teams found! Run seed command for teams first.")
            return

        team_id = team['team_id']
        logger.info(f"Using team_id: {team_id}")

        # Test player data
        test_player = {
            "displayName": "Test Player",
            "position": "WR",
            "jersey": "99",
            "team_id": team_id,
            "metadata": {
                "height": "6-2",
                "weight": "200",
                "age": 25
            }
        }

        # Insert into local DB
        logger.info("Inserting test player into local DB...")
        local_player_id = await local_db.get_or_create_player(
            sport_id,
            "test_player_123",
            test_player
        )
        logger.info(f"Local DB player_id: {local_player_id}")

        # Insert into Supabase
        logger.info("Inserting test player into Supabase...")
        supabase_player_id = await supabase_db.get_or_create_player(
            sport_id,
            "test_player_123",
            test_player
        )
        logger.info(f"Supabase player_id: {supabase_player_id}")

        # Check player count in local DB
        players_count = await local_db.fetch_one("SELECT COUNT(*) as count FROM players")
        logger.info(f"Total players in local DB: {players_count['count']}")

        # Check player count in Supabase
        supabase_count = supabase_db.client.table("players").select("player_id", count="exact").execute()
        logger.info(f"Total players in Supabase: {supabase_count.count}")

        logger.info("\n✓ Test completed successfully!")

    except Exception as e:
        logger.error(f"Error during test: {e}", exc_info=True)

    finally:
        await local_db.close()
        await supabase_db.close()

if __name__ == "__main__":
    asyncio.run(test_player_insert())
