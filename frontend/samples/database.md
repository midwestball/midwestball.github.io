```sql
-- NFL Analytics Platform - SQLite Database Schema

-- Teams table with essential NFL team information
CREATE TABLE teams (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(100) NOT NULL,
    city VARCHAR(100) NOT NULL,
    abbreviation VARCHAR(5) NOT NULL UNIQUE,
    conference VARCHAR(3) CHECK(conference IN ('AFC', 'NFC')),
    division VARCHAR(10) CHECK(division IN ('North', 'South', 'East', 'West')),
    primary_color VARCHAR(7),
    secondary_color VARCHAR(7),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Players table with NFL player information
CREATE TABLE players (
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
    -- Cached baseline statistics for z-score calculations (JSON as TEXT)
    statistical_baseline TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Games table for NFL game tracking
CREATE TABLE games (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    home_team_id INTEGER REFERENCES teams(id),
    away_team_id INTEGER REFERENCES teams(id),
    game_date DATE NOT NULL,
    season INTEGER NOT NULL,
    week INTEGER NOT NULL,
    game_type VARCHAR(20) DEFAULT 'regular', -- regular, wildcard, divisional, conference, superbowl
    venue VARCHAR(100),
    attendance INTEGER,
    -- Weather conditions stored as JSON text
    weather_conditions TEXT,
    status VARCHAR(20) DEFAULT 'scheduled',
    home_score INTEGER DEFAULT 0,
    away_score INTEGER DEFAULT 0,
    -- Game context (prime time, division rival, etc.) as JSON
    game_context TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Player game statistics with flexible JSON storage
CREATE TABLE player_game_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id INTEGER REFERENCES players(id),
    game_id INTEGER REFERENCES games(id),
    -- Flexible statistics storage as JSON text
    stats TEXT NOT NULL,
    minutes_played INTEGER,
    -- Game situation context as JSON
    game_situation TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(player_id, game_id)
);

-- Mathematical impressiveness analysis results
CREATE TABLE performance_analysis (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id INTEGER REFERENCES players(id),
    game_id INTEGER REFERENCES games(id),
    
    -- Personal improvement component
    -- Z-scores for each statistic as JSON
    personal_z_scores TEXT NOT NULL,
    personal_percentile REAL CHECK(personal_percentile BETWEEN 0.0 AND 100.0),
    
    -- Comparative ranking component
    -- Percentile rankings vs peers as JSON
    comparative_rankings TEXT NOT NULL,
    comparative_percentile REAL CHECK(comparative_percentile BETWEEN 0.0 AND 100.0),
    
    -- Combined final score
    impressiveness_score REAL NOT NULL CHECK(impressiveness_score BETWEEN 0.0 AND 100.0),
    confidence_score REAL CHECK(confidence_score BETWEEN 0.0 AND 1.0),
    
    -- Context and explanation
    performance_context TEXT,
    historical_rank INTEGER,
    peer_rank INTEGER,
    
    -- Analysis metadata
    analyzer_version VARCHAR(20),
    baseline_games_count INTEGER,
    comparison_pool_size INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Position-specific analyzer configurations
CREATE TABLE analyzer_configs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    position VARCHAR(5) NOT NULL,
    config_name VARCHAR(50) NOT NULL,
    -- Weights, timeframes, normalization settings as JSON
    parameters TEXT NOT NULL,
    version VARCHAR(20) NOT NULL,
    active BOOLEAN DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Model performance tracking
CREATE TABLE model_performance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    position VARCHAR(5) NOT NULL,
    model_type VARCHAR(50) NOT NULL,
    version VARCHAR(20) NOT NULL,
    
    -- Validation metrics
    mae REAL,
    rmse REAL,
    correlation REAL,
    
    -- Training details
    training_start_date DATE,
    training_end_date DATE,
    training_samples INTEGER,
    validation_samples INTEGER,
    
    deployed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    retired_at TIMESTAMP,
    active BOOLEAN DEFAULT 1
);

-- Indexes for optimal query performance
CREATE INDEX idx_players_position ON players(position);
CREATE INDEX idx_players_team ON players(team_id);
CREATE INDEX idx_games_date ON games(game_date);
CREATE INDEX idx_games_season_week ON games(season, week);
CREATE INDEX idx_player_stats_player ON player_game_stats(player_id);
CREATE INDEX idx_player_stats_game ON player_game_stats(game_id);
CREATE INDEX idx_analysis_player ON performance_analysis(player_id);
CREATE INDEX idx_analysis_score ON performance_analysis(impressiveness_score DESC);
CREATE INDEX idx_analysis_date ON performance_analysis(created_at);

-- Sample data inserts for development
INSERT INTO teams (name, city, abbreviation, conference, division, primary_color) VALUES
('Patriots', 'New England', 'NE', 'AFC', 'East', '#002244'),
('Chiefs', 'Kansas City', 'KC', 'AFC', 'West', '#E31837'),
('Cowboys', 'Dallas', 'DAL', 'NFC', 'East', '#003594'),
('Packers', 'Green Bay', 'GB', 'NFC', 'North', '#203731');

INSERT INTO players (team_id, name, position, jersey_number, height_inches, weight_lbs, years_pro) VALUES
(1, 'Mac Jones', 'QB', 10, 75, 214, 3),
(2, 'Patrick Mahomes', 'QB', 15, 75, 225, 7),
(3, 'Dak Prescott', 'QB', 4, 74, 238, 8),
(4, 'Jordan Love', 'QB', 10, 76, 224, 4);
```