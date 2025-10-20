import asyncpg
from typing import Optional, List, Dict, Any
from contextlib import asynccontextmanager
import logging
import json

logger = logging.getLogger(__name__)

class Database:
    def __init__(self, connection_string: str):
        self.connection_string = connection_string
        self.pool = None
    
    async def connect(self):
        self.pool = await asyncpg.create_pool(
            self.connection_string,
            min_size = 2,
            max_size = 10,
            command_timeout = 60
        )
        logger.info("Database connection pool created")
    
    async def close(self):
        if self.pool:
            await self.pool.close()
            logger.info("Database connection pool closed")
    
    @asynccontextmanager
    async def acquire(self):
        async with self.pool.acquire() as conn:
            yield conn
    
    async def get_or_create_team(
        self,
        sport_id: int,
        team_external_id: str,
        team_data: Dict[str, Any]
    ) -> int:
        async with self.acquire() as conn:
            team_id = await conn.fetchval("""
                SELECT team_id FROM teams 
                WHERE sport_id = $1 AND team_external_id = $2
            """, sport_id, team_external_id)
            
            if team_id:
                return team_id
            
            team_id = await conn.fetchval("""
                INSERT INTO teams (
                    sport_id,
                    team_external_id,
                    team_name,
                    team_abbreviation,
                    team_display_name,
                    team_location,
                    team_color,
                    team_logo_url,
                    metadata
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                ON CONFLICT (sport_id, team_external_id) 
                DO UPDATE SET
                    team_name = EXCLUDED.team_name,
                    updated_at = NOW()
                RETURNING team_id
            """,
                sport_id,
                team_external_id,
                team_data.get("name"),
                team_data.get("abbreviation"),
                team_data.get("displayName"),
                team_data.get("location"),
                team_data.get("color"),
                team_data.get("logo"),
                json.dumps(team_data.get("metadata", {}))
            )
            
            logger.info(f"Created/updated team: {team_data.get('name')} (ID: {team_id})")
            return team_id
    
    async def get_or_create_player(
        self,
        sport_id: int,
        player_external_id: str,
        player_data: Dict[str, Any]
    ) -> int:
        async with self.acquire() as conn:
            player_id = await conn.fetchval("""
                SELECT player_id FROM players 
                WHERE sport_id = $1 AND player_external_id = $2
            """, sport_id, player_external_id)
            
            if player_id:
                return player_id
            
            player_id = await conn.fetchval("""
                INSERT INTO players (
                    sport_id,
                    player_external_id,
                    player_name,
                    player_display_name,
                    position,
                    jersey_number,
                    current_team_id,
                    metadata
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                ON CONFLICT (sport_id, player_external_id) 
                DO UPDATE SET
                    player_name = EXCLUDED.player_name,
                    position = EXCLUDED.position,
                    updated_at = NOW()
                RETURNING player_id
            """,
                sport_id,
                player_external_id,
                player_data.get("displayName"),
                player_data.get("displayName"),
                player_data.get("position"),
                player_data.get("jersey"),
                player_data.get("team_id"),
                json.dumps(player_data.get("metadata", {}))
            )
            
            logger.info(f"Created/updated player: {player_data.get('displayName')} (ID: {player_id})")
            return player_id
    
    async def insert_game(
        self,
        season_id: int,
        game_external_id: str,
        game_data: Dict[str, Any]
    ) -> Optional[int]:
        async with self.acquire() as conn:
            existing = await conn.fetchval("""
                SELECT game_id FROM games 
                WHERE season_id = $1 AND game_external_id = $2
            """, season_id, game_external_id)
            
            if existing:
                logger.info(f"Game {game_external_id} already exists")
                return None
            
            game_id = await conn.fetchval("""
                INSERT INTO games (
                    season_id,
                    game_external_id,
                    game_date,
                    game_week,
                    home_team_id,
                    away_team_id,
                    home_score,
                    away_score,
                    game_status,
                    venue_name,
                    metadata
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                RETURNING game_id
            """,
                season_id,
                game_external_id,
                game_data["game_date"],
                game_data.get("game_week"),
                game_data["home_team_id"],
                game_data["away_team_id"],
                game_data.get("home_score"),
                game_data.get("away_score"),
                game_data.get("status", "completed"),
                game_data.get("venue"),
                json.dumps(game_data.get("metadata", {}))
            )
            
            logger.info(f"Inserted game {game_external_id} (ID: {game_id})")
            return game_id
    
    async def insert_player_stats_batch(
        self,
        game_id: int,
        stats: List[Dict[str, Any]]
    ):
        async with self.acquire() as conn:
            async with conn.transaction():
                for stat in stats:
                    try:
                        await conn.execute("""
                            INSERT INTO player_game_stats (
                                game_id,
                                player_id,
                                team_id,
                                position,
                                stat_category,
                                stat_value
                            ) VALUES ($1, $2, $3, $4, $5, $6)
                            ON CONFLICT (game_id, player_id, stat_category) 
                            DO UPDATE SET
                                stat_value = EXCLUDED.stat_value,
                                updated_at = NOW()
                        """,
                            game_id,
                            stat["player_id"],
                            stat["team_id"],
                            stat["position"],
                            stat["stat_category"],
                            stat["stat_value"]
                        )
                    except Exception as e:
                        logger.error(f"Error inserting stat: {stat}, error: {e}")
                        continue
                
                logger.info(f"Inserted {len(stats)} stats for game {game_id}")
    
    async def get_active_season(self, sport_code: str) -> Optional[int]:
        async with self.acquire() as conn:
            season_id = await conn.fetchval("""
                SELECT s.season_id 
                FROM seasons s
                JOIN sports sp ON s.sport_id = sp.sport_id
                WHERE sp.sport_code = $1 AND s.is_active = TRUE
            """, sport_code)
            return season_id
    
    async def get_sport_id(self, sport_code: str) -> Optional[int]:
        async with self.acquire() as conn:
            sport_id = await conn.fetchval("""
                SELECT sport_id FROM sports WHERE sport_code = $1
            """, sport_code)
            return sport_id
    
    async def get_current_week(self, season_id: int) -> int:
        async with self.acquire() as conn:
            week = await conn.fetchval("""
                SELECT COALESCE(MAX(game_week), 0) 
                FROM games 
                WHERE season_id = $1
            """, season_id)
            return week or 1