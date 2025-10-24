# Desktop Database Migration Instructions

## Overview
This document provides instructions for updating your **desktop local PostgreSQL database** to match the schema changes made on your MacBook.

**DO NOT RUN THESE ON YOUR CURRENT MACHINE** - These instructions are for when you're on your desktop computer.

## Background
We've made the following schema changes:
1. ✅ **Added** new aggregation tables for efficient Recharts rendering
2. ❌ **Removed** deprecated tables: `weekly_percentiles` and `player_performance_scores`

These tables are no longer needed because the new `player_stat_history_agg` and `position_stat_distribution_agg` tables store raw value arrays, which are more efficient and flexible.

## Migration Steps (Run on Desktop)

### Step 1: Backup Your Database (IMPORTANT!)
```bash
# Create a backup before making any changes
pg_dump -h localhost -U your_username -d knowball > knowball_backup_$(date +%Y%m%d).sql
```

### Step 2: Connect to Your Local Database
```bash
# Connect to PostgreSQL
psql -h localhost -U your_username -d knowball
```

### Step 3: Apply Migration 002 (Add New Tables)

Copy and paste the entire contents of `supabase/migrations/002_player_stats_aggregations.sql` into your psql session, OR run:

```bash
psql -h localhost -U your_username -d knowball -f supabase/migrations/002_player_stats_aggregations.sql
```

This will create:
- `player_stat_history_agg` - Player historical stats as arrays
- `position_stat_distribution_agg` - Positional peer data as arrays
- `player_game_stats_wide` - Materialized view for wide-format stats
- Helper functions for updating aggregations

### Step 4: Apply Migration 003 (Drop Old Tables)

```bash
psql -h localhost -U your_username -d knowball -f supabase/migrations/003_drop_deprecated_tables.sql
```

This will drop:
- `player_performance_scores`
- `weekly_percentiles`

**OR** run these commands manually in psql:

```sql
-- Drop deprecated tables
DROP TABLE IF EXISTS player_performance_scores CASCADE;
DROP TABLE IF EXISTS weekly_percentiles CASCADE;
```

### Step 5: Populate Aggregation Tables (If You Have Existing Data)

If you already have game stats in your database, you need to backfill the new aggregation tables:

```sql
-- Get your active season ID
SELECT season_id FROM seasons WHERE is_active = TRUE;
-- Note the season_id returned (example: 1)

-- Populate aggregations for all existing games
-- Replace 1 with your actual season_id
DO $$
DECLARE
    game_record RECORD;
BEGIN
    FOR game_record IN
        SELECT game_id FROM games WHERE season_id = 1 ORDER BY game_date
    LOOP
        PERFORM refresh_aggregations_for_game(game_record.game_id);
        RAISE NOTICE 'Processed game_id: %', game_record.game_id;
    END LOOP;
END $$;
```

**⚠️ WARNING**: This may take a while if you have many games!

### Step 6: Verify Migration Success

```sql
-- Check that new tables exist
\dt player_stat_history_agg
\dt position_stat_distribution_agg

-- Check that old tables are gone
\dt weekly_percentiles
\dt player_performance_scores

-- Verify data in new tables
SELECT COUNT(*) FROM player_stat_history_agg;
SELECT COUNT(*) FROM position_stat_distribution_agg;

-- View sample data
SELECT player_id, stat_category, game_count, array_length(stat_values, 1) as num_values
FROM player_stat_history_agg
LIMIT 5;
```

## What Changed

### Removed Tables

| Table | Purpose | Why Removed |
|-------|---------|-------------|
| `weekly_percentiles` | Stored pre-computed percentile buckets (p10, p25, p50, etc.) | New tables store raw arrays, allowing dynamic percentile calculation |
| `player_performance_scores` | Stored "impressiveness scores" | Not used in frontend; can calculate on-the-fly if needed |

### Added Tables

| Table | Purpose | Benefit |
|-------|---------|---------|
| `player_stat_history_agg` | Stores player's historical stat values as arrays | O(1) lookup for Recharts personal histograms |
| `position_stat_distribution_agg` | Stores positional peer stat values as arrays | O(1) lookup for Recharts peer comparison histograms |
| `player_game_stats_wide` | Materialized view with all stats in JSONB | Easy single-query access to all stats for a game |

## Troubleshooting

### Error: "relation already exists"
- The tables might already exist. Check with `\dt` in psql
- If needed, drop them first: `DROP TABLE table_name CASCADE;`

### Error: "relation does not exist" when dropping
- The tables might already be dropped or never existed
- This is fine, continue with the migration

### Migration takes too long on Step 5
- You can run the backfill in batches or skip it and let it populate naturally as new games are collected
- The aggregation trigger will auto-populate for new data

## Rollback Instructions (If Something Goes Wrong)

If you need to rollback:

```bash
# Restore from backup
psql -h localhost -U your_username -d knowball < knowball_backup_YYYYMMDD.sql
```

## Notes
- These migrations have already been applied to your MacBook's local database
- Supabase will be updated when you run the migrations there
- After migration, the old `percentiles` and `scores` modes in `main.py` will no longer work (they'll be removed)
