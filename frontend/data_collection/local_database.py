import asyncpg
from typing import Optional, List, Dict, Any
from contextlib import asynccontextmanager
import logging
import json

logger = logging.getLogger(__name__)

class LocalDatabase:
    """
    Local PostgreSQL database client using asyncpg.
    Provides the same interface as the Supabase Database class for dual-write compatibility.
    """

    def __init__(self, connection_string: str):
        self.connection_string = connection_string
        self.pool: Optional[asyncpg.Pool] = None

    async def connect(self):
        """Initialize the asyncpg connection pool"""
        try:
            self.pool = await asyncpg.create_pool(
                self.connection_string,
                min_size=2,
                max_size=10,
                command_timeout=60
            )
            logger.info("Local database connection pool created")
        except Exception as e:
            logger.error(f"Failed to connect to local database: {e}")
            raise

    async def close(self):
        """Close the connection pool"""
        if self.pool:
            await self.pool.close()
            logger.info("Local database connection pool closed")

    @asynccontextmanager
    async def acquire(self):
        """Context manager for acquiring a connection from the pool"""
        if not self.pool:
            raise RuntimeError("Database pool not initialized. Call connect() first.")

        async with self.pool.acquire() as conn:
            yield conn

    async def get_or_create_team(
        self,
        sport_id: int,
        team_external_id: str,
        team_data: Dict[str, Any]
    ) -> int:
        """
        Get existing team or create new team.
        Returns the team_id.
        """
        async with self.acquire() as conn:
            # Check if team exists
            team_id = await conn.fetchval("""
                SELECT team_id FROM teams
                WHERE sport_id = $1 AND team_external_id = $2
            """, sport_id, team_external_id)

            if team_id:
                return team_id

            # Convert metadata dict to JSON string for insertion
            metadata_json = json.dumps(team_data.get("metadata", {}))

            # Insert new team
            team_id = await conn.fetchval("""
                INSERT INTO teams (
                    sport_id, team_external_id, team_name, team_abbreviation,
                    team_display_name, team_location, team_color, team_logo_url, metadata
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                ON CONFLICT (sport_id, team_external_id)
                DO UPDATE SET
                    team_name = EXCLUDED.team_name,
                    team_abbreviation = EXCLUDED.team_abbreviation,
                    team_display_name = EXCLUDED.team_display_name,
                    team_location = EXCLUDED.team_location,
                    team_color = EXCLUDED.team_color,
                    team_logo_url = EXCLUDED.team_logo_url,
                    metadata = EXCLUDED.metadata,
                    updated_at = NOW()
                RETURNING team_id
            """, sport_id, team_external_id, team_data.get("name"),
                team_data.get("abbreviation"), team_data.get("displayName"),
                team_data.get("location"), team_data.get("color"),
                team_data.get("logo"), metadata_json)

            logger.info(f"Created/updated team: {team_data.get('name')} (ID: {team_id})")
            return team_id

    async def get_or_create_player(
        self,
        sport_id: int,
        player_external_id: str,
        player_data: Dict[str, Any]
    ) -> int:
        """
        Get existing player or create new player.
        Returns the player_id.
        """
        async with self.acquire() as conn:
            # Check if player exists
            player_id = await conn.fetchval("""
                SELECT player_id FROM players
                WHERE sport_id = $1 AND player_external_id = $2
            """, sport_id, player_external_id)

            if player_id:
                return player_id

            # Convert metadata dict to JSON string for insertion
            metadata_json = json.dumps(player_data.get("metadata", {}))

            # Insert new player
            player_id = await conn.fetchval("""
                INSERT INTO players (
                    sport_id, player_external_id, player_name, player_display_name,
                    position, jersey_number, current_team_id, birth_date,
                    height_inches, weight_pounds, metadata
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                ON CONFLICT (sport_id, player_external_id)
                DO UPDATE SET
                    player_name = EXCLUDED.player_name,
                    player_display_name = EXCLUDED.player_display_name,
                    position = EXCLUDED.position,
                    jersey_number = EXCLUDED.jersey_number,
                    current_team_id = EXCLUDED.current_team_id,
                    birth_date = EXCLUDED.birth_date,
                    height_inches = EXCLUDED.height_inches,
                    weight_pounds = EXCLUDED.weight_pounds,
                    metadata = EXCLUDED.metadata,
                    updated_at = NOW()
                RETURNING player_id
            """, sport_id, player_external_id, player_data.get("displayName"),
                player_data.get("displayName"), player_data.get("position"),
                player_data.get("jersey"), player_data.get("team_id"),
                player_data.get("birth_date"), player_data.get("height_inches"),
                player_data.get("weight_pounds"), metadata_json)

            logger.info(f"Created/updated player: {player_data.get('displayName')} (ID: {player_id})")
            return player_id

    async def insert_game(
        self,
        season_id: int,
        game_external_id: str,
        game_data: Dict[str, Any]
    ) -> Optional[int]:
        """
        Insert a new game if it doesn't exist.
        Returns the game_id or None if game already exists.
        """
        async with self.acquire() as conn:
            # Check if game already exists
            existing_game = await conn.fetchval("""
                SELECT game_id FROM games
                WHERE season_id = $1 AND game_external_id = $2
            """, season_id, game_external_id)

            if existing_game:
                logger.info(f"Game {game_external_id} already exists")
                return None

            # Convert metadata dict to JSON string for insertion
            metadata_json = json.dumps(game_data.get("metadata", {}))

            # Insert game
            game_id = await conn.fetchval("""
                INSERT INTO games (
                    season_id, game_external_id, game_date, game_week,
                    home_team_id, away_team_id, home_score, away_score,
                    game_status, venue_name, metadata
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                RETURNING game_id
            """, season_id, game_external_id, game_data["game_date"],
                game_data.get("game_week"), game_data["home_team_id"],
                game_data["away_team_id"], game_data.get("home_score"),
                game_data.get("away_score"), game_data.get("status", "completed"),
                game_data.get("venue"), metadata_json)

            logger.info(f"Inserted game {game_external_id} (ID: {game_id})")
            return game_id

    async def insert_player_stats_batch(
        self,
        game_id: int,
        stats: List[Dict[str, Any]]
    ):
        """
        Insert multiple player stats in a batch.
        Uses INSERT ... ON CONFLICT for upsert behavior.
        """
        if not stats:
            return

        async with self.acquire() as conn:
            # Prepare values for batch insert
            stat_records = []
            for stat in stats:
                try:
                    stat_records.append((
                        game_id,
                        stat["player_id"],
                        stat["team_id"],
                        stat["position"],
                        stat["stat_category"],
                        stat["stat_value"]
                    ))
                except Exception as e:
                    logger.error(f"Error preparing stat: {stat}, error: {e}")
                    continue

            if stat_records:
                # Use executemany for batch insert
                await conn.executemany("""
                    INSERT INTO player_game_stats (
                        game_id, player_id, team_id, position, stat_category, stat_value
                    ) VALUES ($1, $2, $3, $4, $5, $6)
                    ON CONFLICT (game_id, player_id, stat_category)
                    DO UPDATE SET
                        stat_value = EXCLUDED.stat_value,
                        updated_at = NOW()
                """, stat_records)

                logger.info(f"Inserted {len(stat_records)} stats for game {game_id}")

    async def get_active_season(self, sport_code: str) -> Optional[int]:
        """Get the active season_id for a given sport code"""
        async with self.acquire() as conn:
            season_id = await conn.fetchval("""
                SELECT s.season_id
                FROM seasons s
                JOIN sports sp ON s.sport_id = sp.sport_id
                WHERE sp.sport_code = $1 AND s.is_active = TRUE
                LIMIT 1
            """, sport_code)

            return season_id

    async def get_sport_id(self, sport_code: str) -> Optional[int]:
        """Get the sport_id for a given sport code"""
        async with self.acquire() as conn:
            sport_id = await conn.fetchval("""
                SELECT sport_id FROM sports WHERE sport_code = $1
            """, sport_code)

            return sport_id

    async def get_current_week(self, season_id: int) -> int:
        """Get the current week number for a given season"""
        async with self.acquire() as conn:
            current_week = await conn.fetchval("""
                SELECT COALESCE(MAX(game_week), 1) FROM games
                WHERE season_id = $1
            """, season_id)

            return current_week or 1

    async def execute_query(self, query: str, *args):
        """
        Execute a raw SQL query.
        Returns no result (for INSERT, UPDATE, DELETE, etc.)
        """
        async with self.acquire() as conn:
            await conn.execute(query, *args)

    async def fetch_one(self, query: str, *args) -> Optional[Dict[str, Any]]:
        """
        Execute a query and return a single row as a dict.
        """
        async with self.acquire() as conn:
            row = await conn.fetchrow(query, *args)
            return dict(row) if row else None

    async def fetch_many(self, query: str, *args) -> List[Dict[str, Any]]:
        """
        Execute a query and return multiple rows as a list of dicts.
        """
        async with self.acquire() as conn:
            rows = await conn.fetch(query, *args)
            return [dict(row) for row in rows]

    async def get_games_for_week(self, season_id: int, week: int) -> List[Dict[str, Any]]:
        """Get all games for a specific week"""
        async with self.acquire() as conn:
            games = await conn.fetch("""
                SELECT game_id, game_external_id, game_date, home_team_id, away_team_id
                FROM games
                WHERE season_id = $1 AND game_week = $2
                ORDER BY game_date
            """, season_id, week)

            return [dict(game) for game in games]

    async def get_recent_weeks_games(self, season_id: int, num_weeks: int = 1) -> List[Dict[str, Any]]:
        """Get games from the most recent N weeks"""
        async with self.acquire() as conn:
            games = await conn.fetch("""
                WITH recent_weeks AS (
                    SELECT DISTINCT game_week
                    FROM games
                    WHERE season_id = $1
                    ORDER BY game_week DESC
                    LIMIT $2
                )
                SELECT g.game_id, g.game_external_id, g.game_date, g.game_week,
                       g.home_team_id, g.away_team_id, g.home_score, g.away_score
                FROM games g
                JOIN recent_weeks rw ON g.game_week = rw.game_week
                WHERE g.season_id = $1
                ORDER BY g.game_date DESC
            """, season_id, num_weeks)

            return [dict(game) for game in games]

    async def get_stats_for_game(self, game_id: int) -> List[Dict[str, Any]]:
        """Get all stats for a specific game"""
        async with self.acquire() as conn:
            stats = await conn.fetch("""
                SELECT pgs.stat_id, pgs.game_id, pgs.player_id, pgs.team_id,
                       pgs.position, pgs.stat_category, pgs.stat_value,
                       p.player_name, p.player_external_id
                FROM player_game_stats pgs
                JOIN players p ON pgs.player_id = p.player_id
                WHERE pgs.game_id = $1
            """, game_id)

            return [dict(stat) for stat in stats]

    async def get_weekly_percentiles(self, season_id: int, week: int) -> List[Dict[str, Any]]:
        """Get all percentile records for a specific week"""
        async with self.acquire() as conn:
            percentiles = await conn.fetch("""
                SELECT percentile_id, season_id, week_number, position, stat_category,
                       calculation_date, percentile_data, sample_size
                FROM weekly_percentiles
                WHERE season_id = $1 AND week_number = $2
                ORDER BY calculation_date DESC
            """, season_id, week)

            return [dict(p) for p in percentiles]

    async def get_performance_scores_for_game(self, game_id: int) -> List[Dict[str, Any]]:
        """Get all performance scores for a specific game"""
        async with self.acquire() as conn:
            scores = await conn.fetch("""
                SELECT pps.score_id, pps.game_id, pps.player_id, pps.stat_category,
                       pps.raw_value, pps.percentile_rank, pps.impressiveness_score,
                       pps.context_factors, pps.score_version, pps.calculated_at,
                       p.player_name, p.player_external_id
                FROM player_performance_scores pps
                JOIN players p ON pps.player_id = p.player_id
                WHERE pps.game_id = $1
                ORDER BY pps.impressiveness_score DESC
            """, game_id)

            return [dict(score) for score in scores]
