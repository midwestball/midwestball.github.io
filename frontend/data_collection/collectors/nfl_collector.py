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

logger = logging.getLogger(__name__)

class NFLCollector:
    def __init__(self, db: Database):
        self.db = db
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Sports Analytics Platform)"
        })
        self.espn_base = Config.get_espn_url("nfl", "")
    
    async def collect_weekly_data(self, season: int, week: int):
        logger.info(f"Starting NFL Week {week} collection for season {season}")
        
        season_id = await self.db.get_active_season("nfl")
        if not season_id:
            raise ValueError("No active NFL season found in database")
        
        sport_id = await self.db.get_sport_id("nfl")
        
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
        
        db_game_id = await self.db.insert_game(
            season_id,
            game_id,
            game_record
        )
        
        if not db_game_id:
            logger.info(f"Game {game_id} already exists, updating stats")
            async with self.db.acquire() as conn:
                db_game_id = await conn.fetchval("""
                    SELECT game_id FROM games 
                    WHERE season_id = $1 AND game_external_id = $2
                """, season_id, game_id)
        
        summary = self._fetch_game_summary(game_id)
        
        boxscore = summary.get("boxscore", {})
        players_data = boxscore.get("players", [])
        
        all_stats = []
        for team_stats in players_data:
            team_external_id = str(team_stats["team"]["id"])
            
            async with self.db.acquire() as conn:
                team_id = await conn.fetchval("""
                    SELECT team_id FROM teams 
                    WHERE sport_id = $1 AND team_external_id = $2
                """, sport_id, team_external_id)
            
            for stat_group in team_stats.get("statistics", []):
                for athlete_stats in stat_group.get("athletes", []):
                    player_stats = await self._parse_player_stats(
                        athlete_stats,
                        team_id,
                        sport_id
                    )
                    all_stats.extend(player_stats)
        
        prepared_stats = []
        for stat in all_stats:
            if stat["stat_value"] is not None:
                prepared_stats.append({
                    "player_id": stat["player_id"],
                    "team_id": stat["team_id"],
                    "position": stat["position"],
                    "stat_category": stat["stat_category"],
                    "stat_value": stat["stat_value"]
                })
        
        if prepared_stats:
            await self.db.insert_player_stats_batch(db_game_id, prepared_stats)
        
        logger.info(f"Successfully processed game {game_id} with {len(prepared_stats)} stats")
        return True
    
    async def _ensure_team(self, sport_id: int, team_data: Dict) -> int:
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
        
        return await self.db.get_or_create_team(
            sport_id,
            team_external_id,
            team_record
        )
    
    async def _parse_player_stats(
        self,
        athlete_data: Dict,
        team_id: int,
        sport_id: int
    ) -> List[Dict]:
        athlete_info = athlete_data.get("athlete", {})
        player_external_id = str(athlete_info.get("id"))
        
        player_record = {
            "displayName": athlete_info.get("displayName"),
            "position": athlete_info.get("position", {}).get("abbreviation"),
            "jersey": athlete_info.get("jersey"),
            "team_id": team_id,
            "metadata": {
                "headshot": athlete_info.get("headshot", {}).get("href"),
                "links": athlete_info.get("links", [])
            }
        }
        
        player_id = await self.db.get_or_create_player(
            sport_id,
            player_external_id,
            player_record
        )
        
        stats = []
        stat_lines = athlete_data.get("stats", [])
        
        for stat_value in stat_lines:
            for stat_name, stat_val in stat_value.items():
                if stat_name in ["name", "abbreviation", "displayValue"]:
                    continue
                
                position = player_record["position"]
                category = StatNormalizer._infer_category(stat_name, position)
                
                normalized = StatNormalizer.normalize_espn_stat(
                    stat_name,
                    str(stat_val),
                    category
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
        
        sport_id = await self.db.get_sport_id("nfl")
        
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
            
            team_id = await self.db.get_or_create_team(
                sport_id,
                team_external_id,
                team_record
            )
            
            time.sleep(0.5)
            
            roster_url = f"{self.espn_base}teams/{team_external_id}/roster"
            roster_response = self.session.get(roster_url)
            roster_data = roster_response.json()
            
            athletes = roster_data.get("athletes", [])
            for athlete in athletes:
                player_external_id = str(athlete.get("id"))
                
                player_record = {
                    "displayName": athlete.get("displayName") or athlete.get("name") or f"Player {athlete.get('id', 'Unknown')}",
                    "position": athlete.get("position", {}).get("abbreviation") if isinstance(athlete.get("position"), dict) else athlete.get("position"),
                    "jersey": athlete.get("jersey"),
                    "team_id": team_id,
                    "metadata": {
                        "height": athlete.get("height"),
                        "weight": athlete.get("weight"),
                        "age": athlete.get("age"),
                        "experience": athlete.get("experience", {}).get("years")
                    }
                }
                
                await self.db.get_or_create_player(
                    sport_id,
                    player_external_id,
                    player_record
                )
            
            logger.info(f"Seeded team {team_info.get('name')} with {len(athletes)} players")
            time.sleep(1)
        
        logger.info("Seeding complete!")