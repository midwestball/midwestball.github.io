import os
from typing import Dict
from dotenv import load_dotenv

load_dotenv()

class Config:
    DATABASE_URL = os.getenv("DATABASE_URL")
    
    ESPN_BASE_URL = "https://site.api.espn.com/apis/site/v2/sports"
    
    SPORT_CONFIG = {
        "nfl": {
            "espn_path": "football/nfl",
            "season_type": 2,
            "current_season": 2024,
            "positions": ["QB", "RB", "WR", "TE", "K", "DEF"]
        }
    }
    
    STAT_MAPPINGS = {
        "passing": {
            "C/ATT": "passing_completions_attempts",
            "YDS": "passing_yards",
            "AVG": "passing_yards_per_attempt",
            "TD": "passing_touchdowns",
            "INT": "passing_interceptions",
            "QBR": "qbr",
            "RTG": "passer_rating"
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
            "INT": "interceptions"
        },
        "kicking": {
            "FG": "field_goals_made_attempted",
            "PCT": "field_goal_percentage",
            "LONG": "field_goal_longest",
            "XP": "extra_points_made_attempted"
        }
    }
    
    RATE_LIMITS = {
        "espn": 1.0,
        "nfl_official": 2.0
    }
    
    @classmethod
    def get_espn_url(cls, sport: str, endpoint: str = "scoreboard") -> str:
        sport_path = cls.SPORT_CONFIG[sport]["espn_path"]
        return f"{cls.ESPN_BASE_URL}/{sport_path}/{endpoint}"
    
    @classmethod
    def normalize_stat_name(cls, stat_category: str, stat_label: str) -> str:
        mapping = cls.STAT_MAPPINGS.get(stat_category, {})
        return mapping.get(stat_label, f"{stat_category}_{stat_label}".lower().replace(" ", "_"))
    
    @classmethod
    def validate_config(cls):
        if not cls.DATABASE_URL:
            raise ValueError("DATABASE_URL environment variable not set")
        return True