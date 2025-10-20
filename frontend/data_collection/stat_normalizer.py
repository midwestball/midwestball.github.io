from typing import Dict, List, Any
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)

class StatNormalizer:
    
    @staticmethod
    def parse_fraction(value: str) -> tuple:
        if "/" in value:
            made, attempted = value.split("/")
            return int(made), int(attempted)
        return None, None
    
    @staticmethod
    def normalize_espn_stat(
        stat_name: str,
        stat_value: str,
        stat_category: str
    ) -> List[Dict[str, Any]]:
        normalized = []
        
        try:
            if stat_name == "C/ATT":
                completions, attempts = StatNormalizer.parse_fraction(stat_value)
                if completions is not None:
                    normalized.append({
                        "stat_category": "passing_completions",
                        "stat_value": Decimal(str(completions))
                    })
                    normalized.append({
                        "stat_category": "passing_attempts",
                        "stat_value": Decimal(str(attempts))
                    })
            
            elif stat_name == "FG":
                made, attempted = StatNormalizer.parse_fraction(stat_value)
                if made is not None:
                    normalized.append({
                        "stat_category": "field_goals_made",
                        "stat_value": Decimal(str(made))
                    })
                    normalized.append({
                        "stat_category": "field_goals_attempted",
                        "stat_value": Decimal(str(attempted))
                    })
            
            elif stat_name == "XP":
                made, attempted = StatNormalizer.parse_fraction(stat_value)
                if made is not None:
                    normalized.append({
                        "stat_category": "extra_points_made",
                        "stat_value": Decimal(str(made))
                    })
                    normalized.append({
                        "stat_category": "extra_points_attempted",
                        "stat_value": Decimal(str(attempted))
                    })
            
            else:
                clean_value = StatNormalizer._clean_stat_value(stat_value)
                if clean_value is not None:
                    normalized_name = StatNormalizer._normalize_stat_name(
                        stat_name,
                        stat_category
                    )
                    normalized.append({
                        "stat_category": normalized_name,
                        "stat_value": clean_value
                    })
        
        except Exception as e:
            logger.warning(f"Error normalizing stat {stat_name} = {stat_value}: {e}")
        
        return normalized
    
    @staticmethod
    def _clean_stat_value(value: str) -> Decimal:
        if value == "--" or value == "" or value is None:
            return None
        
        try:
            cleaned = value.replace(",", "").strip()
            return Decimal(cleaned)
        except:
            return None
    
    @staticmethod
    def _normalize_stat_name(stat_name: str, category: str) -> str:
        mapping = {
            "passing": {
                "YDS": "passing_yards",
                "AVG": "passing_yards_per_attempt",
                "TD": "passing_touchdowns",
                "INT": "passing_interceptions",
                "QBR": "qbr",
                "RTG": "passer_rating",
                "SACKS": "sacks_taken"
            },
            "rushing": {
                "CAR": "rushing_attempts",
                "YDS": "rushing_yards",
                "AVG": "rushing_yards_per_attempt",
                "TD": "rushing_touchdowns",
                "LONG": "rushing_longest"
            },
            "receiving": {
                "REC": "receptions",
                "TAR": "targets",
                "YDS": "receiving_yards",
                "AVG": "receiving_yards_per_reception",
                "TD": "receiving_touchdowns",
                "LONG": "receiving_longest"
            },
            "fumbles": {
                "FUM": "fumbles",
                "LOST": "fumbles_lost",
                "REC": "fumbles_recovered"
            },
            "defensive": {
                "TOT": "tackles_total",
                "SOLO": "tackles_solo",
                "SACKS": "sacks",
                "TFL": "tackles_for_loss",
                "PD": "passes_defended",
                "QB HTS": "qb_hits",
                "INT": "interceptions_defensive",
                "TD": "defensive_touchdowns"
            },
            "interceptions": {
                "INT": "interceptions_defensive",
                "YDS": "interception_yards",
                "TD": "interception_touchdowns"
            },
            "kickReturns": {
                "NO": "kick_returns",
                "YDS": "kick_return_yards",
                "AVG": "kick_return_yards_per_return",
                "LONG": "kick_return_longest",
                "TD": "kick_return_touchdowns"
            },
            "puntReturns": {
                "NO": "punt_returns",
                "YDS": "punt_return_yards",
                "AVG": "punt_return_yards_per_return",
                "LONG": "punt_return_longest",
                "TD": "punt_return_touchdowns"
            },
            "kicking": {
                "LONG": "field_goal_longest",
                "PCT": "field_goal_percentage",
                "PTS": "kicking_points"
            },
            "punting": {
                "NO": "punts",
                "YDS": "punt_yards",
                "AVG": "punt_yards_per_punt",
                "TB": "punt_touchbacks",
                "IN 20": "punts_inside_20",
                "LONG": "punt_longest"
            }
        }
        
        category_map = mapping.get(category, {})
        normalized = category_map.get(stat_name)
        
        if not normalized:
            normalized = f"{category}_{stat_name}".lower().replace(" ", "_").replace("/", "_")
        
        return normalized
    
    @staticmethod
    def parse_espn_player_stats(
        player_data: Dict[str, Any],
        team_id: int
    ) -> List[Dict[str, Any]]:
        all_stats = []
        
        athlete_info = player_data.get("athlete", {})
        player_external_id = str(athlete_info.get("id"))
        position = athlete_info.get("position", {}).get("abbreviation", "")
        
        for stat_line in player_data.get("stats", []):
            stat_value = stat_line
            
            for stat_name, stat_val in stat_value.items():
                if stat_name in ["name", "abbreviation", "displayValue"]:
                    continue
                
                category = StatNormalizer._infer_category(stat_name, position)
                
                normalized_stats = StatNormalizer.normalize_espn_stat(
                    stat_name,
                    str(stat_val),
                    category
                )
                
                for norm_stat in normalized_stats:
                    all_stats.append({
                        "player_external_id": player_external_id,
                        "team_id": team_id,
                        "position": position,
                        "stat_category": norm_stat["stat_category"],
                        "stat_value": norm_stat["stat_value"]
                    })
        
        return all_stats
    
    @staticmethod
    def _infer_category(stat_name: str, position: str) -> str:
        if stat_name in ["C/ATT", "YDS", "TD", "INT", "QBR", "RTG", "SACKS"]:
            if position in ["QB"]:
                return "passing"
        
        if stat_name in ["CAR", "YDS", "AVG", "TD", "LONG"]:
            if position in ["RB", "QB"]:
                return "rushing"
        
        if stat_name in ["REC", "TAR", "YDS", "AVG", "TD", "LONG"]:
            if position in ["WR", "TE", "RB"]:
                return "receiving"
        
        if stat_name in ["TOT", "SOLO", "SACKS", "TFL", "PD", "QB HTS"]:
            return "defensive"
        
        if stat_name in ["FG", "XP", "PCT", "LONG", "PTS"]:
            return "kicking"
        
        if stat_name in ["NO", "YDS", "AVG", "TB", "IN 20", "LONG"]:
            return "punting"
        
        return "unknown"