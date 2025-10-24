-- Migration 003: Drop Deprecated Tables
-- This migration removes tables that are replaced by the new aggregation system
-- Tables being dropped:
-- 1. weekly_percentiles - Replaced by position_stat_distribution_agg (stores raw arrays instead of pre-computed percentiles)
-- 2. player_performance_scores - Replaced by on-the-fly percentile calculation from aggregated arrays

-- ============================================
-- DROP DEPRECATED TABLES
-- ============================================

-- Drop player_performance_scores table
DROP TABLE IF EXISTS player_performance_scores CASCADE;

-- Drop weekly_percentiles table
DROP TABLE IF EXISTS weekly_percentiles CASCADE;

-- ============================================
-- COMMENTS
-- ============================================

COMMENT ON DATABASE current_database() IS
'Removed weekly_percentiles and player_performance_scores tables in favor of array-based aggregation tables that are more efficient for Recharts visualizations';
