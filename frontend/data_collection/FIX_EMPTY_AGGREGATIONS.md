# Fix Empty Aggregation Tables - Quick Guide

## Your Current Situation

Based on your description:
- ✅ `player_stat_history_agg` has data in **local DB**
- ❌ `player_stat_history_agg` is EMPTY in **Supabase**
- ❌ `position_stat_distribution_agg` is EMPTY in **both**

---

## Why This Happened

You ran:
```bash
python main.py --mode backfill --use-local-db
```

**Old behavior (before my fix):**
- This only backfilled the LOCAL database
- Supabase was not touched at all

**New behavior (after my fix):**
- This will backfill BOTH Supabase and local
- Matches the expected behavior

---

## The Fix - Step by Step

### Step 1: Understand What You Have

First, let's check what data you have in each database.

#### Check Local Database
```bash
cd ~/Documents/GitHub/knowball

# Check if you have stats in local DB
psql -U ehfurgeson -d knowball -c "SELECT COUNT(*) FROM player_game_stats;"

# Check if you have games
psql -U ehfurgeson -d knowball -c "SELECT COUNT(*) FROM games;"

# Check player_stat_history_agg
psql -U ehfurgeson -d knowball -c "SELECT COUNT(*) FROM player_stat_history_agg;"

# Check position_stat_distribution_agg
psql -U ehfurgeson -d knowball -c "SELECT COUNT(*) FROM position_stat_distribution_agg;"
```

#### Check Supabase Database
Go to Supabase Dashboard → SQL Editor and run:
```sql
-- Check if you have stats
SELECT COUNT(*) FROM player_game_stats;

-- Check if you have games
SELECT COUNT(*) FROM games;

-- Check aggregation tables
SELECT COUNT(*) FROM player_stat_history_agg;
SELECT COUNT(*) FROM position_stat_distribution_agg;
```

---

### Step 2: Determine Your Collection Mode

**Question:** When you collected your data originally, did you use `--local-stats`?

#### If you're NOT sure, check:
```bash
# If your Supabase player_game_stats has data, you did NOT use --local-stats
# If Supabase player_game_stats is empty, you DID use --local-stats
```

Go to Supabase → SQL Editor:
```sql
SELECT COUNT(*) FROM player_game_stats;
```

**If COUNT > 0:** You did NOT use `--local-stats` (stats are in Supabase)
**If COUNT = 0:** You DID use `--local-stats` (stats are only in local DB)

---

### Step 3: Run the Correct Backfill Command

#### Scenario A: You Have Stats in Supabase (Did NOT use --local-stats)

This means you collected with either:
- `python main.py --mode collect` (Supabase only), OR
- `python main.py --mode collect --use-local-db` (both databases)

**Run this to backfill BOTH databases:**
```bash
cd ~/Documents/GitHub/knowball/data_collection

# This will backfill Supabase AND local
python main.py --mode backfill --use-local-db
```

**Expected logs:**
```
INFO - Starting aggregation backfill...
INFO - Backfilling SUPABASE database and LOCAL database
INFO - Found X games in Supabase
INFO - Processed 10/X games (SUPABASE)
INFO - Processed 20/X games (SUPABASE)
...
INFO - Also backfilling local database...
INFO - Found X games in local database
INFO - Processed 10/X games (LOCAL)
...
INFO - Aggregation backfill complete!
```

#### Scenario B: You Have Stats ONLY in Local DB (Used --local-stats)

This means you collected with:
- `python main.py --mode collect --use-local-db --local-stats`

**Your options:**

**Option 1: Keep stats local only (recommended for cost savings)**
```bash
cd ~/Documents/GitHub/knowball/data_collection

# Backfill local DB only
python main.py --mode backfill --use-local-db --local-stats
```

**Option 2: Sync stats to Supabase and backfill both**

If you want stats in Supabase too, you'd need to:
1. Re-collect the data without `--local-stats` flag, OR
2. Manually copy stats from local to Supabase (complex, not recommended)

For now, I recommend **Option 1** - keep stats local only.

---

### Step 4: Verify the Fix

#### Check Local Database
```bash
# Should show many rows now
psql -U ehfurgeson -d knowball -c "SELECT COUNT(*) FROM position_stat_distribution_agg;"

# Sample the data
psql -U ehfurgeson -d knowball -c "
SELECT position, stat_category, game_count, array_length(stat_values, 1) as value_count
FROM position_stat_distribution_agg
LIMIT 5;
"
```

#### Check Supabase Database
Go to Supabase Dashboard → SQL Editor:
```sql
-- Should show many rows now (if you didn't use --local-stats)
SELECT COUNT(*) FROM position_stat_distribution_agg;

-- Sample the data
SELECT position, stat_category, game_count, array_length(stat_values, 1) as value_count
FROM position_stat_distribution_agg
LIMIT 5;
```

---

## Quick Commands Reference

### I Want Everything in Supabase AND Local (Full Sync)
```bash
# Backfill both databases
python main.py --mode backfill --use-local-db
```

### I Want Stats Local Only, Metadata in Supabase (Cost-Efficient)
```bash
# Backfill local only
python main.py --mode backfill --use-local-db --local-stats
```

### I Want Everything in Supabase Only (Cloud-First)
```bash
# Backfill Supabase only
python main.py --mode backfill
```

---

## Understanding the Log Output

When you run backfill, you should see:

### Good Signs ✅
```
INFO - Starting aggregation backfill...
INFO - Backfilling SUPABASE database and LOCAL database
INFO - Found 50 games in Supabase
INFO - Processed 10/50 games (SUPABASE)
INFO - Processed 20/50 games (SUPABASE)
INFO - Processed 30/50 games (SUPABASE)
INFO - Processed 40/50 games (SUPABASE)
INFO - Processed 50/50 games (SUPABASE)
INFO - Also backfilling local database...
INFO - Found 50 games in local database
INFO - Processed 10/50 games (LOCAL)
...
INFO - Aggregation backfill complete!
```

### Bad Signs ❌
```
ERROR - No active season found in Supabase
ERROR - Failed to refresh Supabase aggregations for game 123: [error message]
ERROR - Local-only backfill requires local database
```

If you see errors:
1. Copy the full error message
2. Check which database failed (Supabase or local)
3. Verify that database has the necessary data (games, stats)

---

## Most Likely Solution For You

Based on what you told me, run this:

```bash
cd ~/Documents/GitHub/knowball/data_collection

# Backfill both Supabase and local
python main.py --mode backfill --use-local-db
```

Then verify:
```bash
# Check local
psql -U ehfurgeson -d knowball -c "SELECT COUNT(*) FROM position_stat_distribution_agg;"
```

And check Supabase via Dashboard → SQL Editor:
```sql
SELECT COUNT(*) FROM position_stat_distribution_agg;
```

Both should now have data! ✅

---

## Still Having Issues?

If aggregations are still empty after backfill:

1. **Check for errors in the log output**
   - Look for lines with "ERROR" or "Failed"
   - These will tell you what went wrong

2. **Verify stats exist**
   ```bash
   # Local
   psql -U ehfurgeson -d knowball -c "SELECT COUNT(*) FROM player_game_stats;"
   ```

   Supabase:
   ```sql
   SELECT COUNT(*) FROM player_game_stats;
   ```

   If stats are empty, aggregations will be empty too!

3. **Check the SQL function works**
   ```bash
   # Test the function manually on game_id 1
   psql -U ehfurgeson -d knowball -c "SELECT refresh_aggregations_for_game(1);"
   ```

   If this errors, the migration didn't apply correctly.

---

## Need Help?

Save the full output from the backfill command and any error messages you see!
