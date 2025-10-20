-- Migration 001: Initial Schema
-- Created for sports analytics platform

-- Enable extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================
-- CORE METADATA TABLES
-- ============================================

CREATE TABLE sports (
    sport_id SERIAL PRIMARY KEY,
    sport_name VARCHAR(50) UNIQUE NOT NULL,
    sport_code VARCHAR(10) UNIQUE NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE seasons (
    season_id SERIAL PRIMARY KEY,
    sport_id INTEGER REFERENCES sports(sport_id) ON DELETE CASCADE,
    season_year INTEGER NOT NULL,
    season_type VARCHAR(20) NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    is_active BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(sport_id, season_year, season_type)
);

CREATE INDEX idx_seasons_active ON seasons(sport_id, is_active) WHERE is_active = TRUE;
CREATE INDEX idx_seasons_year ON seasons(sport_id, season_year);

-- ============================================
-- TEAMS AND PLAYERS
-- ============================================

CREATE TABLE teams (
    team_id SERIAL PRIMARY KEY,
    sport_id INTEGER REFERENCES sports(sport_id) ON DELETE CASCADE,
    team_external_id VARCHAR(50) NOT NULL,
    team_name VARCHAR(100) NOT NULL,
    team_abbreviation VARCHAR(10),
    team_display_name VARCHAR(100),
    team_location VARCHAR(100),
    team_color VARCHAR(7),
    team_logo_url TEXT,
    metadata JSONB DEFAULT '{}',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(sport_id, team_external_id)
);

CREATE INDEX idx_teams_sport ON teams(sport_id, is_active);
CREATE INDEX idx_teams_abbrev ON teams(sport_id, team_abbreviation);

CREATE TABLE players (
    player_id SERIAL PRIMARY KEY,
    sport_id INTEGER REFERENCES sports(sport_id) ON DELETE CASCADE,
    player_external_id VARCHAR(50) NOT NULL,
    player_name VARCHAR(100) NOT NULL,
    player_display_name VARCHAR(100),
    position VARCHAR(20),
    jersey_number VARCHAR(10),
    current_team_id INTEGER REFERENCES teams(team_id),
    birth_date DATE,
    height_inches INTEGER,
    weight_pounds INTEGER,
    metadata JSONB DEFAULT '{}',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(sport_id, player_external_id)
);

CREATE INDEX idx_players_sport_position ON players(sport_id, position, is_active);
CREATE INDEX idx_players_team ON players(current_team_id);
CREATE INDEX idx_players_name ON players(player_name);

-- ============================================
-- GAMES
-- ============================================

CREATE TABLE games (
    game_id SERIAL PRIMARY KEY,
    season_id INTEGER REFERENCES seasons(season_id) ON DELETE CASCADE,
    game_external_id VARCHAR(50) NOT NULL,
    game_date TIMESTAMPTZ NOT NULL,
    game_week INTEGER,
    home_team_id INTEGER REFERENCES teams(team_id),
    away_team_id INTEGER REFERENCES teams(team_id),
    home_score INTEGER,
    away_score INTEGER,
    game_status VARCHAR(20) NOT NULL DEFAULT 'scheduled',
    venue_name VARCHAR(200),
    attendance INTEGER,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(season_id, game_external_id)
);

CREATE INDEX idx_games_date ON games(season_id, game_date);
CREATE INDEX idx_games_week ON games(season_id, game_week);
CREATE INDEX idx_games_teams ON games(home_team_id, away_team_id);
CREATE INDEX idx_games_status ON games(game_status, game_date);

-- ============================================
-- RAW STATS (Narrow Table Design)
-- ============================================

CREATE TABLE player_game_stats (
    stat_id BIGSERIAL PRIMARY KEY,
    game_id INTEGER REFERENCES games(game_id) ON DELETE CASCADE,
    player_id INTEGER REFERENCES players(player_id) ON DELETE CASCADE,
    team_id INTEGER REFERENCES teams(team_id) ON DELETE CASCADE,
    position VARCHAR(20),
    stat_category VARCHAR(50) NOT NULL,
    stat_value DECIMAL(10, 2) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(game_id, player_id, stat_category)
);

CREATE INDEX idx_stats_player_category ON player_game_stats(player_id, stat_category, game_id DESC);
CREATE INDEX idx_stats_game ON player_game_stats(game_id);
CREATE INDEX idx_stats_position_category ON player_game_stats(position, stat_category);
CREATE INDEX idx_stats_category_value ON player_game_stats(stat_category, stat_value DESC);

-- ============================================
-- COMPUTED PERCENTILES
-- ============================================

CREATE TABLE weekly_percentiles (
    percentile_id BIGSERIAL PRIMARY KEY,
    season_id INTEGER REFERENCES seasons(season_id) ON DELETE CASCADE,
    week_number INTEGER NOT NULL,
    position VARCHAR(20) NOT NULL,
    stat_category VARCHAR(50) NOT NULL,
    calculation_date TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    percentile_data JSONB NOT NULL,
    sample_size INTEGER NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(season_id, week_number, position, stat_category, calculation_date)
);

CREATE INDEX idx_percentiles_lookup ON weekly_percentiles(season_id, week_number, position, stat_category);

-- ============================================
-- PERFORMANCE SCORES
-- ============================================

CREATE TABLE player_performance_scores (
    score_id BIGSERIAL PRIMARY KEY,
    game_id INTEGER REFERENCES games(game_id) ON DELETE CASCADE,
    player_id INTEGER REFERENCES players(player_id) ON DELETE CASCADE,
    stat_category VARCHAR(50) NOT NULL,
    raw_value DECIMAL(10, 2) NOT NULL,
    percentile_rank DECIMAL(5, 2) NOT NULL,
    impressiveness_score DECIMAL(10, 4) NOT NULL,
    context_factors JSONB DEFAULT '{}',
    score_version VARCHAR(20) NOT NULL DEFAULT 'v1',
    calculated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(game_id, player_id, stat_category, score_version)
);

CREATE INDEX idx_performance_impressive ON player_performance_scores(impressiveness_score DESC, calculated_at DESC);
CREATE INDEX idx_performance_player ON player_performance_scores(player_id, stat_category);
CREATE INDEX idx_performance_game ON player_performance_scores(game_id);

-- ============================================
-- ML INFRASTRUCTURE
-- ============================================

CREATE TABLE ml_models (
    model_id SERIAL PRIMARY KEY,
    model_name VARCHAR(100) NOT NULL,
    model_version VARCHAR(50) NOT NULL,
    model_type VARCHAR(50) NOT NULL,
    sport_id INTEGER REFERENCES sports(sport_id),
    training_start_date DATE NOT NULL,
    training_end_date DATE NOT NULL,
    model_metrics JSONB DEFAULT '{}',
    model_config JSONB DEFAULT '{}',
    is_active BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(model_name, model_version)
);

CREATE TABLE ml_feature_store (
    feature_id BIGSERIAL PRIMARY KEY,
    player_id INTEGER REFERENCES players(player_id) ON DELETE CASCADE,
    game_id INTEGER REFERENCES games(game_id) ON DELETE CASCADE,
    feature_set_version VARCHAR(50) NOT NULL,
    features JSONB NOT NULL,
    target_variables JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_features_player_game ON ml_feature_store(player_id, game_id);
CREATE INDEX idx_features_version ON ml_feature_store(feature_set_version, created_at);

CREATE TABLE ml_predictions (
    prediction_id BIGSERIAL PRIMARY KEY,
    model_id INTEGER REFERENCES ml_models(model_id) ON DELETE CASCADE,
    game_id INTEGER REFERENCES games(game_id) ON DELETE CASCADE,
    player_id INTEGER REFERENCES players(player_id) ON DELETE CASCADE,
    prediction_type VARCHAR(50) NOT NULL,
    predicted_value JSONB NOT NULL,
    confidence_score DECIMAL(5, 4),
    actual_value JSONB,
    prediction_error DECIMAL(10, 4),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_predictions_game ON ml_predictions(game_id, prediction_type);
CREATE INDEX idx_predictions_evaluation ON ml_predictions(model_id, prediction_error);

-- ============================================
-- HELPER FUNCTIONS
-- ============================================

-- Auto-update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Add triggers to all tables with updated_at
CREATE TRIGGER update_sports_updated_at BEFORE UPDATE ON sports FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_seasons_updated_at BEFORE UPDATE ON seasons FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_teams_updated_at BEFORE UPDATE ON teams FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_players_updated_at BEFORE UPDATE ON players FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_games_updated_at BEFORE UPDATE ON games FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_stats_updated_at BEFORE UPDATE ON player_game_stats FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================
-- INITIAL DATA SEED
-- ============================================

-- Insert NFL as the first sport
INSERT INTO sports (sport_name, sport_code) VALUES ('NFL', 'nfl');

-- Insert current NFL season
INSERT INTO seasons (sport_id, season_year, season_type, start_date, end_date, is_active)
VALUES (
    (SELECT sport_id FROM sports WHERE sport_code = 'nfl'),
    2024,
    'regular',
    '2024-09-05',
    '2025-01-05',
    TRUE
);