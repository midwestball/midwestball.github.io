# data_collection.py - NFL Data Collection and Database Population

import sqlite3
import json
import requests
import time
from datetime import datetime, timedelta
import random
import logging
from typing import Dict, List, Any

logging.basicConfig(level = logging.INFO)
logger = logging.getLogger(__name__)

DATABASE_PATH = "nfl_analytics.db"

class NFLDataCollector:
    """
    Collects and processes NFL data for the analytics platform.
    Includes both real API integration and synthetic data generation capabilities.
    """
    
    def __init__(self, use_synthetic_data: bool = True):
        self.use_synthetic_data = use_synthetic_data
        self.db_path = DATABASE_PATH
        
    def initialize_database(self):
        """Initialize the database with schema and basic data"""
        logger.info("Initializing database...")
        
        with sqlite3.connect(self.db_path) as conn:
            # Read and execute schema from the SQL file we created earlier
            # For now, we'll recreate the essential tables
            
            # Teams table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS teams (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name VARCHAR(100) NOT NULL,
                    city VARCHAR(100) NOT NULL,
                    abbreviation VARCHAR(5) NOT NULL UNIQUE,
                    conference VARCHAR(3) CHECK(conference IN ('AFC', 'NFC')),
                    division VARCHAR(10) CHECK(division IN ('North', 'South', 'East', 'West')),
                    primary_color VARCHAR(7),
                    secondary_color VARCHAR(7),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Players table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS players (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    team_id INTEGER REFERENCES teams(id),
                    name VARCHAR(100) NOT NULL,
                    position VARCHAR(5) NOT NULL,
                    jersey_number INTEGER,
                    height_inches INTEGER,
                    weight_lbs INTEGER,
                    birth_date DATE,
                    years_pro INTEGER DEFAULT 0,
                    active BOOLEAN DEFAULT 1,
                    statistical_baseline TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Games table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS games (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    home_team_id INTEGER REFERENCES teams(id),
                    away_team_id INTEGER REFERENCES teams(id),
                    game_date DATE NOT NULL,
                    season INTEGER NOT NULL,
                    week INTEGER NOT NULL,
                    game_type VARCHAR(20) DEFAULT 'regular',
                    venue VARCHAR(100),
                    attendance INTEGER,
                    weather_conditions TEXT,
                    status VARCHAR(20) DEFAULT 'completed',
                    home_score INTEGER DEFAULT 0,
                    away_score INTEGER DEFAULT 0,
                    game_context TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Player game stats table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS player_game_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    player_id INTEGER REFERENCES players(id),
                    game_id INTEGER REFERENCES games(id),
                    stats TEXT NOT NULL,
                    minutes_played INTEGER,
                    game_situation TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(player_id, game_id)
                )
            """)
            
            # Performance analysis table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS performance_analysis (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    player_id INTEGER REFERENCES players(id),
                    game_id INTEGER REFERENCES games(id),
                    personal_z_scores TEXT NOT NULL,
                    personal_percentile REAL,
                    comparative_rankings TEXT NOT NULL,
                    comparative_percentile REAL,
                    impressiveness_score REAL NOT NULL,
                    confidence_score REAL,
                    performance_context TEXT,
                    historical_rank INTEGER,
                    peer_rank INTEGER,
                    analyzer_version VARCHAR(20),
                    baseline_games_count INTEGER,
                    comparison_pool_size INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            conn.commit()
            logger.info("Database initialized successfully")
    
    def populate_teams(self):
        """Populate the teams table with NFL teams"""
        logger.info("Populating teams...")
        
        nfl_teams = [
            # AFC East
            ("Bills", "Buffalo", "BUF", "AFC", "East", "#00338D"),
            ("Dolphins", "Miami", "MIA", "AFC", "East", "#008E97"),
            ("Patriots", "New England", "NE", "AFC", "East", "#002244"),
            ("Jets", "New York", "NYJ", "AFC", "East", "#125740"),
            
            # AFC North
            ("Ravens", "Baltimore", "BAL", "AFC", "North", "#241773"),
            ("Bengals", "Cincinnati", "CIN", "AFC", "North", "#FB4F14"),
            ("Browns", "Cleveland", "CLE", "AFC", "North", "#311D00"),
            ("Steelers", "Pittsburgh", "PIT", "AFC", "North", "#FFB612"),
            
            # AFC South
            ("Texans", "Houston", "HOU", "AFC", "South", "#03202F"),
            ("Colts", "Indianapolis", "IND", "AFC", "South", "#002C5F"),
            ("Jaguars", "Jacksonville", "JAX", "AFC", "South", "#006778"),
            ("Titans", "Tennessee", "TEN", "AFC", "South", "#0C2340"),
            
            # AFC West
            ("Broncos", "Denver", "DEN", "AFC", "West", "#FB4F14"),
            ("Chiefs", "Kansas City", "KC", "AFC", "West", "#E31837"),
            ("Raiders", "Las Vegas", "LV", "AFC", "West", "#000000"),
            ("Chargers", "Los Angeles", "LAC", "AFC", "West", "#0080C6"),
            
            # NFC East
            ("Cowboys", "Dallas", "DAL", "NFC", "East", "#003594"),
            ("Giants", "New York", "NYG", "NFC", "East", "#0B2265"),
            ("Eagles", "Philadelphia", "PHI", "NFC", "East", "#004C54"),
            ("Commanders", "Washington", "WAS", "NFC", "East", "#5A1414"),
            
            # NFC North
            ("Bears", "Chicago", "CHI", "NFC", "North", "#0B162A"),
            ("Lions", "Detroit", "DET", "NFC", "North", "#0076B6"),
            ("Packers", "Green Bay", "GB", "NFC", "North", "#203731"),
            ("Vikings", "Minnesota", "MIN", "NFC", "North", "#4F2683"),
            
            # NFC South
            ("Falcons", "Atlanta", "ATL", "NFC", "South", "#A71930"),
            ("Panthers", "Carolina", "CAR", "NFC", "South", "#0085CA"),
            ("Saints", "New Orleans", "NO", "NFC", "South", "#D3BC8D"),
            ("Buccaneers", "Tampa Bay", "TB", "NFC", "South", "#D50A0A"),
            
            # NFC West
            ("Cardinals", "Arizona", "ARI", "NFC", "West", "#97233F"),
            ("Rams", "Los Angeles", "LAR", "NFC", "West", "#003594"),
            ("49ers", "San Francisco", "SF", "NFC", "West", "#AA0000"),
            ("Seahawks", "Seattle", "SEA", "NFC", "West", "#002244")
        ]
        
        with sqlite3.connect(self.db_path) as conn:
            conn.executemany("""
                INSERT OR IGNORE INTO teams (name, city, abbreviation, conference, division, primary_color)
                VALUES (?, ?, ?, ?, ?, ?)
            """, nfl_teams)
            conn.commit()
            
        logger.info(f"Populated {len(nfl_teams)} teams")
    
    def generate_synthetic_players(self, num_players_per_team: int = 8):
        """Generate synthetic player data for testing"""
        logger.info("Generating synthetic players...")
        
        first_names = ["Aaron", "Tom", "Josh", "Patrick", "Lamar", "Russell", "Dak", "Derek", 
                      "Kyler", "Tua", "Mac", "Zach", "Trevor", "Davis", "Justin", "Joe"]
        last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", 
                     "Davis", "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez"]
        
        positions = [
            ("QB", 2), ("RB", 3), ("WR", 4), ("TE", 2), ("K", 1), ("DEF", 1)
        ]
        
        with sqlite3.connect(self.db_path) as conn:
            # Get all team IDs
            cursor = conn.execute("SELECT id FROM teams")
            team_ids = [row[0] for row in cursor.fetchall()]
            
            players_added = 0
            
            for team_id in team_ids:
                jersey_num = 1
                
                for position, count in positions:
                    for _ in range(count):
                        name = f"{random.choice(first_names)} {random.choice(last_names)}"
                        
                        # Position-specific attributes
                        if position == "QB":
                            height = random.randint(72, 78)  # 6'0" to 6'6"
                            weight = random.randint(200, 250)
                        elif position == "RB":
                            height = random.randint(68, 74)  # 5'8" to 6'2"
                            weight = random.randint(190, 230)
                        elif position in ["WR", "TE"]:
                            height = random.randint(70, 77)  # 5'10" to 6'5"
                            weight = random.randint(180, 260)
                        else:
                            height = random.randint(70, 76)
                            weight = random.randint(180, 220)
                        
                        years_pro = random.randint(1, 12)
                        
                        conn.execute("""
                            INSERT INTO players 
                            (team_id, name, position, jersey_number, height_inches, weight_lbs, years_pro)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        """, (team_id, name, position, jersey_num, height, weight, years_pro))
                        
                        jersey_num += 1
                        players_added += 1
                        
                        if jersey_num > 99:  # Reset jersey numbers if needed
                            jersey_num = 1
            
            conn.commit()
            
        logger.info(f"Generated {players_added} synthetic players")
    
    def generate_synthetic_games(self, weeks: int = 18):
        """Generate synthetic game schedule"""
        logger.info("Generating synthetic games...")
        
        with sqlite3.connect(self.db_path) as conn:
            # Get all teams
            cursor = conn.execute("SELECT id, abbreviation FROM teams")
            teams = list(cursor.fetchall())
            
            season = 2024
            game_id = 1
            games_added = 0
            
            # Generate games for each week
            for week in range(1, weeks + 1):
                # Create matchups (simplified random pairing)
                team_ids = [team[0] for team in teams]
                random.shuffle(team_ids)
                
                # Pair teams for games
                for i in range(0, len(team_ids), 2):
                    if i + 1 < len(team_ids):
                        home_team = team_ids[i]
                        away_team = team_ids[i + 1]
                        
                        # Generate game date (Sunday of the week)
                        base_date = datetime(2024, 9, 8)  # First Sunday of season
                        game_date = base_date + timedelta(weeks = week - 1)
                        
                        # Generate realistic scores
                        home_score = random.randint(10, 35)
                        away_score = random.randint(10, 35)
                        
                        conn.execute("""
                            INSERT INTO games 
                            (home_team_id, away_team_id, game_date, season, week, 
                             home_score, away_score, status)
                            VALUES (?, ?, ?, ?, ?, ?, ?, 'completed')
                        """, (home_team, away_team, game_date.strftime("%Y-%m-%d"), 
                             season, week, home_score, away_score))
                        
                        games_added += 1
            
            conn.commit()
            
        logger.info(f"Generated {games_added} synthetic games")
    
    def generate_synthetic_player_stats(self):
        """Generate realistic player statistics for games"""
        logger.info("Generating synthetic player statistics...")
        
        with sqlite3.connect(self.db_path) as conn:
            # Get all games and players
            cursor = conn.execute("""
                SELECT g.id as game_id, g.home_team_id, g.away_team_id, g.week
                FROM games g 
                ORDER BY g.game_date
            """)
            games = cursor.fetchall()
            
            stats_added = 0
            
            for game in games:
                game_id, home_team_id, away_team_id, week = game
                
                # Get players for both teams
                for team_id in [home_team_id, away_team_id]:
                    cursor = conn.execute("""
                        SELECT id, position FROM players 
                        WHERE team_id = ? AND active = 1
                    """, (team_id,))
                    
                    players = cursor.fetchall()
                    
                    for player_id, position in players:
                        stats = self._generate_position_stats(position, week)
                        
                        if stats:  # Only insert if player has stats for this game
                            conn.execute("""
                                INSERT OR IGNORE INTO player_game_stats 
                                (player_id, game_id, stats, minutes_played)
                                VALUES (?, ?, ?, ?)
                            """, (player_id, game_id, json.dumps(stats), 
                                 random.randint(30, 60) if position in ["QB", "RB", "WR", "TE"] else 0))
                            
                            stats_added += 1
            
            conn.commit()
            
        logger.info(f"Generated {stats_added} player stat records")
    
    def _generate_position_stats(self, position: str, week: int) -> Dict[str, int]:
        """Generate realistic statistics based on position"""
        # Add some week-to-week variation and season progression
        week_factor = 1.0 + (week - 9) * 0.02  # Slight improvement over season
        injury_chance = random.random() < 0.05  # 5% chance player doesn't play
        
        if injury_chance:
            return None
        
        if position == "QB":
            base_attempts = random.randint(25, 45)
            completion_rate = random.uniform(0.55, 0.75)
            completions = int(base_attempts * completion_rate)
            
            return {
                "passing_attempts": int(base_attempts * week_factor),
                "passing_completions": int(completions * week_factor),
                "passing_yards": int(random.randint(180, 350) * week_factor),
                "passing_touchdowns": random.randint(0, 4),
                "interceptions": random.randint(0, 2),
                "rushing_yards": random.randint(-5, 40),
                "rushing_touchdowns": random.randint(0, 1)
            }
        
        elif position == "RB":
            carries = random.randint(8, 25)
            return {
                "rushing_attempts": int(carries * week_factor),
                "rushing_yards": int(random.randint(30, 150) * week_factor),
                "rushing_touchdowns": random.randint(0, 2),
                "receiving_targets": random.randint(2, 8),
                "receptions": random.randint(1, 6),
                "receiving_yards": random.randint(10, 80),
                "receiving_touchdowns": random.randint(0, 1)
            }
        
        elif position == "WR":
            targets = random.randint(4, 12)
            catch_rate = random.uniform(0.5, 0.8)
            
            return {
                "receiving_targets": int(targets * week_factor),
                "receptions": int(targets * catch_rate * week_factor),
                "receiving_yards": int(random.randint(30, 120) * week_factor),
                "receiving_touchdowns": random.randint(0, 2),
                "rushing_attempts": random.randint(0, 2),
                "rushing_yards": random.randint(0, 20)
            }
        
        elif position == "TE":
            targets = random.randint(3, 8)
            catch_rate = random.uniform(0.6, 0.85)
            
            return {
                "receiving_targets": int(targets * week_factor),
                "receptions": int(targets * catch_rate * week_factor),
                "receiving_yards": int(random.randint(20, 90) * week_factor),
                "receiving_touchdowns": random.randint(0, 1)
            }
        
        return None
    
    def run_full_data_generation(self):
        """Run the complete data generation pipeline"""
        logger.info("Starting full data generation pipeline...")
        
        self.initialize_database()
        self.populate_teams()
        self.generate_synthetic_players()
        self.generate_synthetic_games()
        self.generate_synthetic_player_stats()
        
        logger.info("Data generation pipeline completed successfully!")
        
        # Print summary statistics
        with sqlite3.connect(self.db_path) as conn:
            team_count = conn.execute("SELECT COUNT(*) FROM teams").fetchone()[0]
            player_count = conn.execute("SELECT COUNT(*) FROM players").fetchone()[0]
            game_count = conn.execute("SELECT COUNT(*) FROM games").fetchone()[0]
            stats_count = conn.execute("SELECT COUNT(*) FROM player_game_stats").fetchone()[0]
            
            logger.info(f"Database Summary:")
            logger.info(f"  Teams: {team_count}")
            logger.info(f"  Players: {player_count}")
            logger.info(f"  Games: {game_count}")
            logger.info(f"  Player Game Stats: {stats_count}")

def main():
    """Main execution function"""
    collector = NFLDataCollector(use_synthetic_data = True)
    collector.run_full_data_generation()

if __name__ == "__main__":
    main()