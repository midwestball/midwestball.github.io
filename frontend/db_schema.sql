-- NBA Stats Database Schema for Supabase
-- Drop existing tables if they exist (for development)
DROP TABLE IF EXISTS impressive_performances CASCADE;
DROP TABLE IF EXISTS player_stat_distributions CASCADE;
DROP TABLE IF EXISTS league_averages CASCADE;
DROP TABLE IF EXISTS player_game_stats CASCADE;
DROP TABLE IF EXISTS games CASCADE;
DROP TABLE IF EXISTS players CASCADE;

-- Players table
CREATE TABLE players (
    id SERIAL PRIMARY KEY,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    full_name TEXT NOT NULL,
    player_slug TEXT NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_updated TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create index on player names for fast search
CREATE INDEX idx_players_full_name ON players (full_name);
CREATE INDEX idx_players_slug ON players (player_slug);

-- Games table
CREATE TABLE games (
    id SERIAL PRIMARY KEY,
    game_id TEXT UNIQUE NOT NULL,
    game_date DATE NOT NULL,
    season TEXT NOT NULL,
    home_team TEXT NOT NULL,
    away_team TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create index on game_date for performance queries
CREATE INDEX idx_games_date ON games (game_date);
CREATE INDEX idx_games_season ON games (season);

-- Player game stats table
CREATE TABLE player_game_stats (
    id SERIAL PRIMARY KEY,
    player_id INTEGER REFERENCES players(id),
    game_id INTEGER REFERENCES games(id),
    points INTEGER,
    rebounds INTEGER,
    assists INTEGER,
    steals INTEGER,
    blocks INTEGER,
    minutes INTEGER,
    field_goals_made INTEGER,
    field_goals_attempted INTEGER,
    field_goal_percentage NUMERIC(5,2),
    three_pointers_made INTEGER,
    three_pointers_attempted INTEGER, 
    three_point_percentage NUMERIC(5,2),
    free_throws_made INTEGER,
    free_throws_attempted INTEGER,
    free_throw_percentage NUMERIC(5,2),
    turnovers INTEGER,
    plus_minus INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(player_id, game_id)
);

-- League averages table
CREATE TABLE league_averages (
    id SERIAL PRIMARY KEY,
    season TEXT NOT NULL,
    stat_type TEXT NOT NULL,
    average_value NUMERIC(8,3) NOT NULL,
    standard_deviation NUMERIC(8,3) NOT NULL,
    min_value NUMERIC(8,3) NOT NULL,
    max_value NUMERIC(8,3) NOT NULL,
    sample_size INTEGER NOT NULL,
    last_updated TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(season, stat_type)
);

-- Impressive performances table
CREATE TABLE impressive_performances (
    id SERIAL PRIMARY KEY,
    player_id INTEGER REFERENCES players(id),
    game_id INTEGER REFERENCES games(id),
    stat_type TEXT NOT NULL,
    value NUMERIC(8,2) NOT NULL,
    z_score NUMERIC(6,3) NOT NULL,
    league_rank INTEGER,
    player_rank INTEGER,
    combined_score NUMERIC(6,3), -- weighted combination of league and player z-scores
    display_until DATE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create index for efficient retrieval of impressive performances
CREATE INDEX idx_impressive_performances_scores ON impressive_performances (combined_score DESC);
CREATE INDEX idx_impressive_performances_date ON impressive_performances (display_until);

-- Player statistical distributions
CREATE TABLE player_stat_distributions (
    id SERIAL PRIMARY KEY,
    player_id INTEGER REFERENCES players(id),
    season TEXT NOT NULL,
    stat_type TEXT NOT NULL,
    mean NUMERIC(8,3) NOT NULL,
    median NUMERIC(8,3) NOT NULL,
    std_dev NUMERIC(8,3) NOT NULL,
    min_value NUMERIC(8,3) NOT NULL,
    max_value NUMERIC(8,3) NOT NULL,
    percentile_25 NUMERIC(8,3) NOT NULL,
    percentile_75 NUMERIC(8,3) NOT NULL,
    sample_size INTEGER NOT NULL,
    last_updated TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(player_id, season, stat_type)
);

-- Enable Row Level Security (RLS) for Supabase
ALTER TABLE players ENABLE ROW LEVEL SECURITY;
ALTER TABLE games ENABLE ROW LEVEL SECURITY;
ALTER TABLE player_game_stats ENABLE ROW LEVEL SECURITY;
ALTER TABLE league_averages ENABLE ROW LEVEL SECURITY;
ALTER TABLE impressive_performances ENABLE ROW LEVEL SECURITY;
ALTER TABLE player_stat_distributions ENABLE ROW LEVEL SECURITY;

-- Create policies for public read access (since this is stats data)
CREATE POLICY "Public read access" ON players FOR SELECT USING (true);
CREATE POLICY "Public read access" ON games FOR SELECT USING (true);
CREATE POLICY "Public read access" ON player_game_stats FOR SELECT USING (true);
CREATE POLICY "Public read access" ON league_averages FOR SELECT USING (true);
CREATE POLICY "Public read access" ON impressive_performances FOR SELECT USING (true);
CREATE POLICY "Public read access" ON player_stat_distributions FOR SELECT USING (true);

-- For data collection scripts, you'll need to create service role policies
-- These should be configured in the Supabase dashboard for your service role