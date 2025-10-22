import asyncio
import requests
from typing import Dict, List, Any, Optional
from datetime import datetime
import time
import logging
from decimal import Decimal

from config import Config
from database import Database
from stat_normalizer import StatNormalizer
from player_parser import parse_player_data

logger = logging.getLogger(__name__)

class NFLCollector:
    def __init__(self, supabase_db: Database, local_db = None):
        self.supabase_db = supabase_db
        self.local_db = local_db
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Sports Analytics Platform)"
        })
        self.espn_base = Config.get_espn_url("nfl", "")
    
    async def collect_weekly_data(self, season: int, week: int):
        logger.info(f"Starting NFL Week {week} collection for season {season}")

        season_id = await self.supabase_db.get_active_season("nfl")
        if not season_id:
            raise ValueError("No active NFL season found in database")

        sport_id = await self.supabase_db.get_sport_id("nfl")
        
        games = self._fetch_weekly_scoreboard(season, week)
        
        collected_count = 0
        for game_data in games:
            if not game_data["status"]["type"]["completed"]:
                logger.info(f"Game {game_data['id']} not completed, skipping")
                continue
            
            try:
                success = await self._process_game(
                    game_data,
                    season_id,
                    sport_id
                )
                if success:
                    collected_count += 1
                
                time.sleep(Config.RATE_LIMITS["espn"])
            
            except Exception as e:
                logger.error(f"Error processing game {game_data['id']}: {e}")
                continue
        
        logger.info(f"Collected {collected_count} games for Week {week}")
        return collected_count
    
    def _fetch_weekly_scoreboard(self, season: int, week: int) -> List[Dict]:
        url = f"{self.espn_base}scoreboard"
        params = {
            "dates": season,
            "seasontype": 2,
            "week": week,
            "limit": 100
        }
        
        logger.info(f"Fetching scoreboard: {url} with params {params}")
        response = self.session.get(url, params = params)
        response.raise_for_status()
        
        data = response.json()
        events = data.get("events", [])
        logger.info(f"Found {len(events)} games for week {week}")
        
        return events
    
    def _fetch_game_summary(self, game_id: str) -> Dict:
        url = f"{self.espn_base}summary"
        params = {"event": game_id}
        
        logger.info(f"Fetching game summary for {game_id}")
        response = self.session.get(url, params = params)
        response.raise_for_status()
        
        return response.json()
    
    async def _process_game(
        self,
        game_data: Dict,
        season_id: int,
        sport_id: int
    ) -> bool:
        game_id = game_data["id"]
        logger.info(f"Processing game {game_id}")
        
        competition = game_data["competitions"][0]
        competitors = competition["competitors"]
        
        home_team = next(c for c in competitors if c["homeAway"] == "home")
        away_team = next(c for c in competitors if c["homeAway"] == "away")
        
        home_team_id = await self._ensure_team(sport_id, home_team)
        away_team_id = await self._ensure_team(sport_id, away_team)
        
        game_date = datetime.fromisoformat(
            competition["date"].replace("Z", "+00:00")
        )
        
        game_record = {
            "game_date": game_date,
            "game_week": game_data.get("week", {}).get("number"),
            "home_team_id": home_team_id,
            "away_team_id": away_team_id,
            "home_score": int(home_team["score"]),
            "away_score": int(away_team["score"]),
            "status": "completed",
            "venue": competition.get("venue", {}).get("fullName"),
            "metadata": {
                "attendance": competition.get("attendance"),
                "broadcast": competition.get("broadcasts", [])
            }
        }
        
        # Insert game into Supabase
        db_game_id = await self.supabase_db.insert_game(
            season_id,
            game_id,
            game_record
        )

        if not db_game_id:
            logger.info(f"Game {game_id} already exists, updating stats")
            result = self.supabase_db.client.table("games").select("game_id").eq("season_id", season_id).eq("game_external_id", game_id).execute()
            if result.data:
                db_game_id = result.data[0]["game_id"]

        # Insert game into local DB if enabled, using Supabase game_id for parity
        if self.local_db and db_game_id:
            await self.local_db.insert_game(
                season_id,
                game_id,
                game_record,
                supabase_game_id=db_game_id
            )
        
        summary = self._fetch_game_summary(game_id)
        
        boxscore = summary.get("boxscore", {})
        players_data = boxscore.get("players", [])
        
        all_stats = []
        for team_stats in players_data:
            team_external_id = str(team_stats["team"]["id"])

            # Get team_id using Supabase
            team_result = self.supabase_db.client.table("teams").select("team_id").eq("sport_id", sport_id).eq("team_external_id", team_external_id).execute()
            team_id = team_result.data[0]["team_id"] if team_result.data else None

            if not team_id:
                logger.warning(f"Team not found: {team_external_id}")
                continue
            
            for stat_group in team_stats.get("statistics", []):
                # Get stat labels and keys for this group
                stat_keys = stat_group.get("keys", [])
                stat_labels = stat_group.get("labels", [])
                stat_category = stat_group.get("name", "")

                for athlete_stats in stat_group.get("athletes", []):
                    player_stats = await self._parse_player_stats(
                        athlete_stats,
                        team_id,
                        sport_id,
                        stat_keys,
                        stat_labels,
                        stat_category
                    )
                    all_stats.extend(player_stats)
        
        prepared_stats = []
        for stat in all_stats:
            if stat["stat_value"] is not None:
                # Convert Decimal to float for JSON serialization
                stat_value = stat["stat_value"]
                if isinstance(stat_value, Decimal):
                    stat_value = float(stat_value)

                prepared_stats.append({
                    "player_id": stat["player_id"],
                    "team_id": stat["team_id"],
                    "position": stat["position"],
                    "stat_category": stat["stat_category"],
                    "stat_value": stat_value
                })
        
        if prepared_stats:
            # Insert stats into Supabase
            await self.supabase_db.insert_player_stats_batch(db_game_id, prepared_stats)

            # Insert stats into local DB if enabled (using same game_id for parity)
            if self.local_db and db_game_id:
                await self.local_db.insert_player_stats_batch(db_game_id, prepared_stats)

        logger.info(f"Successfully processed game {game_id} with {len(prepared_stats)} stats")
        return True
    
    async def _ensure_team(self, sport_id: int, team_data: Dict) -> int:
        """
        Ensure team exists in both databases.
        Returns the Supabase team_id (used for foreign keys).
        """
        team_external_id = str(team_data["team"]["id"])
        team_info = team_data["team"]

        team_record = {
            "name": team_info.get("name"),
            "abbreviation": team_info.get("abbreviation"),
            "displayName": team_info.get("displayName"),
            "location": team_info.get("location"),
            "color": team_info.get("color"),
            "logo": team_info.get("logo"),
            "metadata": {
                "alternateColor": team_info.get("alternateColor"),
                "links": team_info.get("links", [])
            }
        }

        # Always create in Supabase
        supabase_team_id = await self.supabase_db.get_or_create_team(
            sport_id,
            team_external_id,
            team_record
        )

        # Optionally create in local DB
        if self.local_db:
            await self.local_db.get_or_create_team(
                sport_id,
                team_external_id,
                team_record
            )

        return supabase_team_id
    
    async def _parse_player_stats(
        self,
        athlete_data: Dict,
        team_id: int,
        sport_id: int,
        stat_keys: List[str],
        stat_labels: List[str],
        stat_category: str
    ) -> List[Dict]:
        athlete_info = athlete_data.get("athlete", {})

        # Handle case where athlete might not be a dict
        if not isinstance(athlete_info, dict):
            logger.warning(f"Invalid athlete data: {athlete_info}")
            return []

        player_external_id = str(athlete_info.get("id"))
        if not player_external_id or player_external_id == "None":
            logger.warning(f"No player ID found in athlete data")
            return []

        # Parse player data with proper field extraction
        try:
            player_record = parse_player_data(athlete_info, team_id)
        except Exception as e:
            logger.error(f"Error parsing player data for player {player_external_id}: {e}")
            return []

        # Create player in Supabase
        player_id = await self.supabase_db.get_or_create_player(
            sport_id,
            player_external_id,
            player_record
        )

        # Create player in local DB if enabled, using Supabase player_id for parity
        if self.local_db:
            await self.local_db.get_or_create_player(
                sport_id,
                player_external_id,
                player_record,
                supabase_player_id=player_id
            )

        stats = []
        stat_values = athlete_data.get("stats", [])

        # Stats is a list of string values that map to the keys/labels
        # Example: stats=['13/21', '167', '8.0', ...] maps to keys=['completions/passingAttempts', 'passingYards', ...]
        for stat_key, stat_label, stat_value in zip(stat_keys, stat_labels, stat_values):
            if not stat_value or stat_value == "0":
                continue

            position = player_record.get("position", "")

            # Normalize the stat using the label (which matches our config mappings)
            normalized = StatNormalizer.normalize_espn_stat(
                stat_label,
                str(stat_value),
                stat_category
            )

            for norm_stat in normalized:
                stats.append({
                    "player_id": player_id,
                    "team_id": team_id,
                    "position": position,
                    "stat_category": norm_stat["stat_category"],
                    "stat_value": norm_stat["stat_value"]
                })

        return stats
    
    async def seed_teams_and_players(self):
        logger.info("Seeding NFL teams and players...")

        sport_id = await self.supabase_db.get_sport_id("nfl")
        
        url = f"{self.espn_base}teams"
        response = self.session.get(url)
        teams_data = response.json()
        
        for team in teams_data.get("sports", [{}])[0].get("leagues", [{}])[0].get("teams", []):
            team_info = team.get("team", {})
            team_external_id = str(team_info.get("id"))
            
            team_record = {
                "name": team_info.get("name"),
                "abbreviation": team_info.get("abbreviation"),
                "displayName": team_info.get("displayName"),
                "location": team_info.get("location"),
                "color": team_info.get("color"),
                "logo": team_info.get("logos", [{}])[0].get("href") if team_info.get("logos") else None,
                "metadata": {}
            }
            
            # Create team in Supabase
            team_id = await self.supabase_db.get_or_create_team(
                sport_id,
                team_external_id,
                team_record
            )

            # Create team in local DB if enabled
            if self.local_db:
                await self.local_db.get_or_create_team(
                    sport_id,
                    team_external_id,
                    team_record
                )
            
            time.sleep(0.5)
            
            roster_url = f"{self.espn_base}teams/{team_external_id}/roster"
            roster_response = self.session.get(roster_url)
            roster_data = roster_response.json()

            # ESPN API returns athletes grouped by position
            # Structure: athletes: [{position: "offense", items: [...]}, {position: "defense", items: [...]}]
            athlete_groups = roster_data.get("athletes", [])

            total_players = 0
            for group in athlete_groups:
                athletes = group.get("items", [])

                for athlete in athletes:
                    player_external_id = str(athlete.get("id"))

                    # Parse player data with proper field extraction
                    player_record = parse_player_data(athlete, team_id)

                    # Create player in Supabase
                    player_id = await self.supabase_db.get_or_create_player(
                        sport_id,
                        player_external_id,
                        player_record
                    )

                    # Create player in local DB if enabled, using Supabase player_id for parity
                    if self.local_db:
                        await self.local_db.get_or_create_player(
                            sport_id,
                            player_external_id,
                            player_record,
                            supabase_player_id=player_id
                        )

                    total_players += 1

            logger.info(f"Seeded team {team_info.get('name')} with {total_players} players")
            time.sleep(1)
        
        logger.info("Seeding complete!")