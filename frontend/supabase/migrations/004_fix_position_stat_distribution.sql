-- Migration 003: Fix position_stat_distribution_agg GROUP BY bug
-- This migration fixes the SQL bug in update_position_stat_distribution()
-- that was preventing data from being inserted into position_stat_distribution_agg

-- ============================================
-- FIX THE AGGREGATION FUNCTION
-- ============================================

-- Drop and recreate the function with the correct GROUP BY clause
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
    GROUP BY g.season_id, pgs.position, pgs.stat_category, p_week_number  -- FIXED: Added p_week_number
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

-- ============================================
-- COMMENTS
-- ============================================

COMMENT ON FUNCTION update_position_stat_distribution IS
'Fixed version: Now properly groups by week_number to prevent SQL aggregation errors';
