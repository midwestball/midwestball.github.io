-- Migration 002: Player Stats Aggregation Tables
-- Created to optimize Recharts histogram queries
-- This migration adds pre-aggregated tables for efficient chart rendering

-- ============================================
-- PLAYER STATS AGGREGATIONS
-- ============================================

-- Table to store pre-aggregated player career stats by stat type
-- This allows O(1) lookup for player historical data needed for charts
CREATE TABLE player_stat_history_agg (
    agg_id BIGSERIAL PRIMARY KEY,
    player_id INTEGER REFERENCES players(player_id) ON DELETE CASCADE,
    season_id INTEGER REFERENCES seasons(season_id) ON DELETE CASCADE,
    stat_category VARCHAR(50) NOT NULL,
    stat_values DECIMAL(10, 2)[] NOT NULL,  -- Array of all historical values
    game_ids INTEGER[] NOT NULL,            -- Corresponding game IDs for context
    game_count INTEGER NOT NULL,            -- Number of games in the sample
    min_value DECIMAL(10, 2) NOT NULL,      -- Min for quick range checks
    max_value DECIMAL(10, 2) NOT NULL,      -- Max for quick range checks
    avg_value DECIMAL(10, 2) NOT NULL,      -- Average for reference
    last_updated TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(player_id, season_id, stat_category)
);

CREATE INDEX idx_player_history_lookup ON player_stat_history_agg(player_id, stat_category, season_id);
CREATE INDEX idx_player_history_season ON player_stat_history_agg(season_id);

-- Table to store pre-aggregated positional stats for peer comparison
-- This allows O(1) lookup for positional distribution data
CREATE TABLE position_stat_distribution_agg (
    agg_id BIGSERIAL PRIMARY KEY,
    season_id INTEGER REFERENCES seasons(season_id) ON DELETE CASCADE,
    position VARCHAR(20) NOT NULL,
    stat_category VARCHAR(50) NOT NULL,
    week_number INTEGER,                     -- NULL means season-to-date
    stat_values DECIMAL(10, 2)[] NOT NULL,   -- Array of all values from all players
    player_count INTEGER NOT NULL,           -- Number of unique players in sample
    game_count INTEGER NOT NULL,             -- Total number of games in sample
    min_value DECIMAL(10, 2) NOT NULL,
    max_value DECIMAL(10, 2) NOT NULL,
    avg_value DECIMAL(10, 2) NOT NULL,
    median_value DECIMAL(10, 2),
    last_updated TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(season_id, position, stat_category, week_number)
);

CREATE INDEX idx_position_dist_lookup ON position_stat_distribution_agg(season_id, position, stat_category, week_number);
CREATE INDEX idx_position_dist_week ON position_stat_distribution_agg(week_number, position);

-- ============================================
-- MATERIALIZED VIEW FOR CURRENT GAME STATS
-- ============================================

-- Materialized view that provides wide-format stats per game
-- This makes it easy to fetch all stats for a player's game at once
CREATE MATERIALIZED VIEW player_game_stats_wide AS
SELECT
    pgs.game_id,
    pgs.player_id,
    pgs.team_id,
    pgs.position,
    p.player_name,
    p.player_external_id,
    g.game_date,
    g.game_week,
    g.season_id,
    -- Aggregate all stats into a JSONB object for easy access
    jsonb_object_agg(pgs.stat_category, pgs.stat_value) AS stats
FROM player_game_stats pgs
JOIN players p ON pgs.player_id = p.player_id
JOIN games g ON pgs.game_id = g.game_id
GROUP BY pgs.game_id, pgs.player_id, pgs.team_id, pgs.position,
         p.player_name, p.player_external_id, g.game_date, g.game_week, g.season_id;

CREATE UNIQUE INDEX idx_game_stats_wide_pk ON player_game_stats_wide(game_id, player_id);
CREATE INDEX idx_game_stats_wide_player ON player_game_stats_wide(player_id, game_date DESC);
CREATE INDEX idx_game_stats_wide_week ON player_game_stats_wide(season_id, game_week, position);

-- ============================================
-- HELPER FUNCTIONS FOR AGGREGATION
-- ============================================

-- Function to update player stat history aggregation for a specific player and stat
CREATE OR REPLACE FUNCTION update_player_stat_history(
    p_player_id INTEGER,
    p_season_id INTEGER,
    p_stat_category VARCHAR
) RETURNS VOID AS $$
BEGIN
    INSERT INTO player_stat_history_agg (
        player_id, season_id, stat_category, stat_values, game_ids,
        game_count, min_value, max_value, avg_value
    )
    SELECT
        pgs.player_id,
        g.season_id,
        pgs.stat_category,
        array_agg(pgs.stat_value ORDER BY g.game_date) AS stat_values,
        array_agg(pgs.game_id ORDER BY g.game_date) AS game_ids,
        COUNT(*)::INTEGER AS game_count,
        MIN(pgs.stat_value) AS min_value,
        MAX(pgs.stat_value) AS max_value,
        AVG(pgs.stat_value) AS avg_value
    FROM player_game_stats pgs
    JOIN games g ON pgs.game_id = g.game_id
    WHERE pgs.player_id = p_player_id
        AND g.season_id = p_season_id
        AND pgs.stat_category = p_stat_category
    GROUP BY pgs.player_id, g.season_id, pgs.stat_category
    ON CONFLICT (player_id, season_id, stat_category)
    DO UPDATE SET
        stat_values = EXCLUDED.stat_values,
        game_ids = EXCLUDED.game_ids,
        game_count = EXCLUDED.game_count,
        min_value = EXCLUDED.min_value,
        max_value = EXCLUDED.max_value,
        avg_value = EXCLUDED.avg_value,
        last_updated = NOW();
END;
$$ LANGUAGE plpgsql;

-- Function to update position stat distribution for a position and stat
CREATE OR REPLACE FUNCTION update_position_stat_distribution(
    p_season_id INTEGER,
    p_position VARCHAR,
    p_stat_category VARCHAR,
    p_week_number INTEGER DEFAULT NULL
) RETURNS VOID AS $$
BEGIN
    INSERT INTO position_stat_distribution_agg (
        season_id, position, stat_category, week_number,
        stat_values, player_count, game_count,
        min_value, max_value, avg_value, median_value
    )
    SELECT
        g.season_id,
        pgs.position,
        pgs.stat_category,
        p_week_number AS week_number,
        array_agg(pgs.stat_value) AS stat_values,
        COUNT(DISTINCT pgs.player_id)::INTEGER AS player_count,
        COUNT(*)::INTEGER AS game_count,
        MIN(pgs.stat_value) AS min_value,
        MAX(pgs.stat_value) AS max_value,
        AVG(pgs.stat_value) AS avg_value,
        percentile_cont(0.5) WITHIN GROUP (ORDER BY pgs.stat_value) AS median_value
    FROM player_game_stats pgs
    JOIN games g ON pgs.game_id = g.game_id
    WHERE g.season_id = p_season_id
        AND pgs.position = p_position
        AND pgs.stat_category = p_stat_category
        AND (p_week_number IS NULL OR g.game_week <= p_week_number)
    GROUP BY g.season_id, pgs.position, pgs.stat_category
    ON CONFLICT (season_id, position, stat_category, week_number)
    DO UPDATE SET
        stat_values = EXCLUDED.stat_values,
        player_count = EXCLUDED.player_count,
        game_count = EXCLUDED.game_count,
        min_value = EXCLUDED.min_value,
        max_value = EXCLUDED.max_value,
        avg_value = EXCLUDED.avg_value,
        median_value = EXCLUDED.median_value,
        last_updated = NOW();
END;
$$ LANGUAGE plpgsql;

-- Function to refresh all aggregations for a specific game
-- Call this after inserting stats for a game
CREATE OR REPLACE FUNCTION refresh_aggregations_for_game(p_game_id INTEGER)
RETURNS VOID AS $$
DECLARE
    v_season_id INTEGER;
    v_week_number INTEGER;
    v_stat_record RECORD;
BEGIN
    -- Get season and week info
    SELECT season_id, game_week INTO v_season_id, v_week_number
    FROM games WHERE game_id = p_game_id;

    -- Update player history for each player/stat in this game
    FOR v_stat_record IN
        SELECT DISTINCT player_id, stat_category
        FROM player_game_stats
        WHERE game_id = p_game_id
    LOOP
        PERFORM update_player_stat_history(
            v_stat_record.player_id,
            v_season_id,
            v_stat_record.stat_category
        );
    END LOOP;

    -- Update positional distributions for each position/stat in this game
    FOR v_stat_record IN
        SELECT DISTINCT position, stat_category
        FROM player_game_stats
        WHERE game_id = p_game_id
    LOOP
        PERFORM update_position_stat_distribution(
            v_season_id,
            v_stat_record.position,
            v_stat_record.stat_category,
            v_week_number
        );
    END LOOP;

    -- Also refresh season-to-date positional distributions (week_number = NULL)
    FOR v_stat_record IN
        SELECT DISTINCT position, stat_category
        FROM player_game_stats
        WHERE game_id = p_game_id
    LOOP
        PERFORM update_position_stat_distribution(
            v_season_id,
            v_stat_record.position,
            v_stat_record.stat_category,
            NULL
        );
    END LOOP;

    -- Refresh materialized view
    REFRESH MATERIALIZED VIEW CONCURRENTLY player_game_stats_wide;
END;
$$ LANGUAGE plpgsql;

-- ============================================
-- RPC WRAPPER FOR SUPABASE
-- ============================================

-- Wrapper function for calling from Supabase RPC (allows calling from Python client)
CREATE OR REPLACE FUNCTION rpc_refresh_aggregations_for_game(game_id_param INTEGER)
RETURNS JSON AS $$
BEGIN
    PERFORM refresh_aggregations_for_game(game_id_param);
    RETURN json_build_object('success', true, 'game_id', game_id_param);
END;
$$ LANGUAGE plpgsql;

-- ============================================
-- COMMENTS FOR DOCUMENTATION
-- ============================================

COMMENT ON TABLE player_stat_history_agg IS
'Pre-aggregated player historical stats stored as arrays for O(1) Recharts histogram queries';

COMMENT ON TABLE position_stat_distribution_agg IS
'Pre-aggregated positional peer stats for O(1) Recharts peer comparison histogram queries';

COMMENT ON MATERIALIZED VIEW player_game_stats_wide IS
'Wide-format view of player game stats with all stats as JSONB for easy single-query access';

COMMENT ON FUNCTION refresh_aggregations_for_game IS
'Call this function after importing game stats to update all related aggregations and materialized views';

COMMENT ON FUNCTION rpc_refresh_aggregations_for_game IS
'RPC wrapper for refresh_aggregations_for_game - callable from Supabase Python client';
