from supabase import create_client, Client
from typing import Optional, List, Dict, Any
import logging
import json

logger = logging.getLogger(__name__)

class Database:
    def __init__(self, supabase_url: str, supabase_key: str):
        self.supabase_url = supabase_url
        self.supabase_key = supabase_key
        self.client: Optional[Client] = None

    async def connect(self):
        """Initialize the Supabase client"""
        self.client = create_client(self.supabase_url, self.supabase_key)
        logger.info("Supabase client initialized")

    async def close(self):
        """Close is not needed for Supabase client, but kept for compatibility"""
        logger.info("Supabase client session ended")

    async def get_or_create_team(
        self,
        sport_id: int,
        team_external_id: str,
        team_data: Dict[str, Any]
    ) -> int:
        # Check if team exists
        result = self.client.table("teams").select("team_id").eq("sport_id", sport_id).eq("team_external_id", team_external_id).execute()

        if result.data:
            return result.data[0]["team_id"]

        # Insert or update team
        team_record = {
            "sport_id": sport_id,
            "team_external_id": team_external_id,
            "team_name": team_data.get("name"),
            "team_abbreviation": team_data.get("abbreviation"),
            "team_display_name": team_data.get("displayName"),
            "team_location": team_data.get("location"),
            "team_color": team_data.get("color"),
            "team_logo_url": team_data.get("logo"),
            "metadata": team_data.get("metadata", {})
        }

        result = self.client.table("teams").upsert(team_record, on_conflict="sport_id,team_external_id").execute()

        team_id = result.data[0]["team_id"]
        logger.info(f"Created/updated team: {team_data.get('name')} (ID: {team_id})")
        return team_id

    async def get_or_create_player(
        self,
        sport_id: int,
        player_external_id: str,
        player_data: Dict[str, Any]
    ) -> int:
        # Check if player exists
        result = self.client.table("players").select("player_id").eq("sport_id", sport_id).eq("player_external_id", player_external_id).execute()

        if result.data:
            return result.data[0]["player_id"]

        # Insert or update player
        # Convert birth_date from date object to ISO string for Supabase
        birth_date = player_data.get("birth_date")
        if birth_date and hasattr(birth_date, 'isoformat'):
            birth_date = birth_date.isoformat()

        player_record = {
            "sport_id": sport_id,
            "player_external_id": player_external_id,
            "player_name": player_data.get("displayName"),
            "player_display_name": player_data.get("displayName"),
            "position": player_data.get("position"),
            "jersey_number": player_data.get("jersey"),
            "current_team_id": player_data.get("team_id"),
            "birth_date": birth_date,
            "height_inches": player_data.get("height_inches"),
            "weight_pounds": player_data.get("weight_pounds"),
            "metadata": player_data.get("metadata", {})
        }

        result = self.client.table("players").upsert(player_record, on_conflict="sport_id,player_external_id").execute()

        player_id = result.data[0]["player_id"]
        logger.info(f"Created/updated player: {player_data.get('displayName')} (ID: {player_id})")
        return player_id

    async def insert_game(
        self,
        season_id: int,
        game_external_id: str,
        game_data: Dict[str, Any]
    ) -> Optional[int]:
        # Check if game already exists
        result = self.client.table("games").select("game_id").eq("season_id", season_id).eq("game_external_id", game_external_id).execute()

        if result.data:
            logger.info(f"Game {game_external_id} already exists")
            return None

        # Insert game
        game_record = {
            "season_id": season_id,
            "game_external_id": game_external_id,
            "game_date": game_data["game_date"].isoformat(),
            "game_week": game_data.get("game_week"),
            "home_team_id": game_data["home_team_id"],
            "away_team_id": game_data["away_team_id"],
            "home_score": game_data.get("home_score"),
            "away_score": game_data.get("away_score"),
            "game_status": game_data.get("status", "completed"),
            "venue_name": game_data.get("venue"),
            "metadata": game_data.get("metadata", {})
        }

        result = self.client.table("games").insert(game_record).execute()

        game_id = result.data[0]["game_id"]
        logger.info(f"Inserted game {game_external_id} (ID: {game_id})")
        return game_id

    async def insert_player_stats_batch(
        self,
        game_id: int,
        stats: List[Dict[str, Any]]
    ):
        # Prepare stats for upsert
        stat_records = []
        for stat in stats:
            try:
                stat_record = {
                    "game_id": game_id,
                    "player_id": stat["player_id"],
                    "team_id": stat["team_id"],
                    "position": stat["position"],
                    "stat_category": stat["stat_category"],
                    "stat_value": stat["stat_value"]
                }
                stat_records.append(stat_record)
            except Exception as e:
                logger.error(f"Error preparing stat: {stat}, error: {e}")
                continue

        if stat_records:
            # Upsert all stats
            self.client.table("player_game_stats").upsert(
                stat_records,
                on_conflict="game_id,player_id,stat_category"
            ).execute()

            logger.info(f"Inserted {len(stat_records)} stats for game {game_id}")

    async def refresh_aggregations(self, game_id: int):
        """
        Refresh aggregation tables for a specific game.
        This should be called after stats are inserted to Supabase.
        Uses the RPC function to trigger aggregation updates.
        """
        try:
            result = self.client.rpc('rpc_refresh_aggregations_for_game', {'game_id_param': game_id}).execute()
            logger.info(f"Refreshed aggregations for game {game_id}")
        except Exception as e:
            logger.error(f"Failed to refresh aggregations for game {game_id}: {e}")
            # Don't raise - aggregations can be backfilled later

    async def get_active_season(self, sport_code: str) -> Optional[int]:
        # Get sport_id first
        sport_result = self.client.table("sports").select("sport_id").eq("sport_code", sport_code).execute()
        if not sport_result.data:
            return None

        sport_id = sport_result.data[0]["sport_id"]

        # Get active season for this sport
        season_result = self.client.table("seasons").select("season_id").eq("sport_id", sport_id).eq("is_active", True).limit(1).execute()

        if season_result.data:
            return season_result.data[0]["season_id"]

        return None

    async def get_sport_id(self, sport_code: str) -> Optional[int]:
        result = self.client.table("sports").select("sport_id").eq("sport_code", sport_code).execute()

        if result.data:
            return result.data[0]["sport_id"]

        return None

    async def get_current_week(self, season_id: int) -> int:
        result = self.client.table("games").select("game_week").eq("season_id", season_id).order("game_week", desc=True).limit(1).execute()

        if result.data and result.data[0]["game_week"]:
            return result.data[0]["game_week"]

        return 1

    async def execute_query(self, query: str, *args):
        """
        Execute a raw SQL query using Supabase RPC
        This is a compatibility method for complex queries
        """
        # Note: For complex queries, you'll need to create RPC functions in Supabase
        # This is a placeholder for compatibility
        logger.warning("Direct SQL execution not supported with Supabase client. Use RPC functions instead.")
        raise NotImplementedError("Direct SQL queries require RPC functions in Supabase")

    async def fetch_one(self, query: str, *args):
        """Compatibility method - not directly supported"""
        raise NotImplementedError("Use Supabase table queries or RPC functions")

    async def fetch_many(self, query: str, *args):
        """Compatibility method - not directly supported"""
        raise NotImplementedError("Use Supabase table queries or RPC functions")
