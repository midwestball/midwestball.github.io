# Supabase Migration Guide - Detailed Step-by-Step

This guide will walk you through applying database migrations to Supabase using the Dashboard SQL Editor.

---

## Before You Start

✅ **Prerequisites:**
1. You should have already applied migrations to your local database (see [APPLY_MIGRATIONS_MACBOOK.md](APPLY_MIGRATIONS_MACBOOK.md))
2. You have access to your Supabase account
3. You know your Supabase project URL: `https://jajjpgppagogippajhhy.supabase.co`

---

## Step 1: Login to Supabase Dashboard

### 1.1 Open Your Browser
Open your web browser (Chrome, Safari, Firefox, etc.)

### 1.2 Navigate to Supabase
Go to: **https://supabase.com/dashboard**

### 1.3 Login
- Enter your email and password
- Click **"Sign In"**

### 1.4 Select Your Project
- You should see your project in the dashboard
- Click on your **"knowball"** project (or whatever you named it)
- The URL should change to: `https://supabase.com/dashboard/project/jajjpgppagogippajhhy`

---

## Step 2: Open the SQL Editor

### 2.1 Find SQL Editor in Sidebar
Look at the **left sidebar** of the Supabase Dashboard. You'll see a list of options:

```
📊 Home
🏢 Table Editor
👤 Authentication
📦 Storage
📝 SQL Editor        ← Click this one!
🔌 Database
⚙️  Settings
```

### 2.2 Click "SQL Editor"
- Click on **"SQL Editor"** (it has a 📝 icon)
- You should now see the SQL Editor interface

### 2.3 Understand the SQL Editor Interface

The SQL Editor has several parts:

```
┌─────────────────────────────────────────────────────────┐
│  + New query     Snippets ▼    Queries ▼               │  ← Top toolbar
├─────────────────────────────────────────────────────────┤
│                                                          │
│  [Large text area for SQL code]                         │  ← SQL input area
│                                                          │
│                                                          │
├─────────────────────────────────────────────────────────┤
│  RUN (or Cmd+Enter on Mac)                 Save Query   │  ← Run button
├─────────────────────────────────────────────────────────┤
│  Results appear here after running                       │  ← Results area
└─────────────────────────────────────────────────────────┘
```

---

## Step 3: Create a Backup Query (IMPORTANT!)

Before making any changes, let's create a backup query to verify tables.

### 3.1 Click "New Query"
- Click the **"+ New query"** button at the top left

### 3.2 Name Your Query (Optional)
- You can name it "Check Tables Before Migration" or leave it as "Untitled query"

### 3.3 Run Pre-Migration Check
Copy and paste this SQL into the editor:

```sql
-- Check what tables currently exist
SELECT tablename
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY tablename;
```

### 3.4 Run the Query
- Click **"RUN"** button (or press `Cmd+Enter` on Mac, `Ctrl+Enter` on Windows)

### 3.5 Review Results
✅ **You should see a list of tables including:**
- `games`
- `player_game_stats`
- `player_performance_scores` (this will be deleted)
- `players`
- `seasons`
- `teams`
- `weekly_percentiles` (this will be deleted)
- ... and others

📸 **Screenshot this list** or save the query - you can compare it later!

---

## Step 4: Apply Migration 002 (Add New Tables)

### 4.1 Open Migration File on Your Mac
1. Open **Finder**
2. Navigate to: `Documents > GitHub > knowball > supabase > migrations`
3. Find the file: **`002_player_stats_aggregations.sql`**
4. Open it with **TextEdit** or **VS Code**

### 4.2 Create a New Query in Supabase
- In Supabase SQL Editor, click **"+ New query"** again
- Optional: Name it "Migration 002 - Add Aggregation Tables"

### 4.3 Copy the Migration SQL
1. **Select ALL** the text in `002_player_stats_aggregations.sql`
   - Mac: Press `Cmd+A` to select all
2. **Copy** the text
   - Mac: Press `Cmd+C`

The file is ~260 lines long and starts with:
```sql
-- Migration 002: Player Stats Aggregation Tables
-- Created to optimize Recharts histogram queries
...
```

### 4.4 Paste into Supabase SQL Editor
1. Click in the SQL Editor text area in Supabase
2. **Paste** the SQL
   - Mac: Press `Cmd+V`

### 4.5 Review Before Running
⚠️ **IMPORTANT:** Before clicking RUN, scroll through and make sure:
- The entire file was copied (should end with `COMMENT ON FUNCTION...`)
- No weird characters or formatting issues
- Everything looks like valid SQL

### 4.6 Run Migration 002
1. Click the **"RUN"** button (or press `Cmd+Enter`)
2. **Wait** - this may take 5-10 seconds

### 4.7 Check for Success

✅ **SUCCESS looks like:**
```
Success. No rows returned
```
or
```
Success
Query returned no results
```

You might also see output in the "Messages" tab like:
```
CREATE TABLE
CREATE INDEX
CREATE FUNCTION
...
```

❌ **ERROR looks like:**
```
ERROR:  syntax error at or near "..."
```
or
```
ERROR:  relation "player_stat_history_agg" already exists
```

**If you see "already exists" error:** This is OK! It means the table was already created. You can continue.

**If you see other errors:** STOP and save the error message. Don't proceed to the next step.

### 4.8 Save the Query (Optional)
- Click **"Save query"** if you want to keep this for your records
- Name it something like "Migration 002 - Applied [today's date]"

---

## Step 5: Verify New Tables Were Created

### 5.1 Create Another New Query
- Click **"+ New query"** again

### 5.2 Check New Tables
Copy and paste this SQL:

```sql
-- Check that new tables were created
SELECT tablename
FROM pg_tables
WHERE schemaname = 'public'
AND tablename LIKE '%_agg'
ORDER BY tablename;
```

### 5.3 Run the Query
Click **"RUN"**

✅ **Expected Results:**
You should see 2 tables:
1. `player_stat_history_agg`
2. `position_stat_distribution_agg`

### 5.4 Check New Functions
Run this query:

```sql
-- Check that new functions were created
SELECT proname as function_name
FROM pg_proc
WHERE proname IN (
    'refresh_aggregations_for_game',
    'rpc_refresh_aggregations_for_game',
    'update_player_stat_history',
    'update_position_stat_distribution'
)
ORDER BY proname;
```

✅ **Expected Results:**
You should see all 4 function names listed.

---

## Step 6: Apply Migration 003 (Drop Old Tables)

### 6.1 Open Migration File on Your Mac
1. In **Finder**, navigate to: `Documents > GitHub > knowball > supabase > migrations`
2. Find the file: **`003_drop_deprecated_tables.sql`**
3. Open it with **TextEdit** or **VS Code**

### 6.2 Create a New Query in Supabase
- In Supabase SQL Editor, click **"+ New query"**
- Optional: Name it "Migration 003 - Drop Deprecated Tables"

### 6.3 Copy the Migration SQL
1. **Select ALL** the text in `003_drop_deprecated_tables.sql`
   - Mac: Press `Cmd+A`
2. **Copy** the text
   - Mac: Press `Cmd+C`

The file is short (~30 lines) and looks like:
```sql
-- Migration 003: Drop Deprecated Tables
...
DROP TABLE IF EXISTS player_performance_scores CASCADE;
DROP TABLE IF EXISTS weekly_percentiles CASCADE;
```

### 6.4 Paste into Supabase SQL Editor
1. Click in the SQL Editor text area
2. **Paste** the SQL
   - Mac: Press `Cmd+V`

### 6.5 Run Migration 003
1. Click the **"RUN"** button
2. Wait for completion (should be quick, 1-2 seconds)

### 6.6 Check for Success

✅ **SUCCESS looks like:**
```
Success. No rows returned
```

You might see in the Messages tab:
```
DROP TABLE
DROP TABLE
```

❌ **If you see error like "table does not exist":**
This is OK! It just means the tables were already deleted or never existed.

---

## Step 7: Verify Old Tables Were Removed

### 7.1 Create a New Query
- Click **"+ New query"**

### 7.2 Check Old Tables Are Gone
Copy and paste:

```sql
-- Verify old tables are deleted
SELECT tablename
FROM pg_tables
WHERE schemaname = 'public'
AND tablename IN ('weekly_percentiles', 'player_performance_scores');
```

### 7.3 Run the Query

✅ **Expected Result:**
```
No rows returned
```
or an empty results table.

This confirms the old tables are gone! ✅

---

## Step 8: Final Verification - List All Tables

Let's see the complete final state:

### 8.1 Create a New Query
- Click **"+ New query"**

### 8.2 List All Tables
```sql
-- List all current tables
SELECT tablename
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY tablename;
```

### 8.3 Run and Review

✅ **You should now see:**
- `games` ✅
- `ml_feature_store` ✅
- `ml_models` ✅
- `ml_predictions` ✅
- `player_game_stats` ✅
- `player_stat_history_agg` ✅ **NEW!**
- `players` ✅
- `position_stat_distribution_agg` ✅ **NEW!**
- `seasons` ✅
- `sports` ✅
- `teams` ✅

❌ **You should NOT see:**
- `weekly_percentiles` ❌ (deleted)
- `player_performance_scores` ❌ (deleted)

---

## Step 9: Check Materialized Views

### 9.1 Create a New Query

### 9.2 List Materialized Views
```sql
-- Check materialized views
SELECT schemaname, matviewname
FROM pg_matviews
WHERE schemaname = 'public';
```

✅ **Expected Result:**
You should see:
- `player_game_stats_wide` ✅ **NEW!**

---

## Step 10: Test the Functions (Optional)

Let's make sure the new functions work:

### 10.1 Test the RPC Function
```sql
-- Test that the RPC function exists and can be called
-- Note: This will fail if you don't have any games yet, but that's OK
-- We're just testing that the function exists
SELECT rpc_refresh_aggregations_for_game(1);
```

**If you see an error like "game does not exist":** That's fine! The function works, you just don't have game_id 1 yet.

✅ **If you see:** `{"success": true, "game_id": 1}` - Perfect! The function works.

---

## 🎉 Migration Complete!

You've successfully applied both migrations to Supabase!

### What You've Done:
✅ Added `player_stat_history_agg` table
✅ Added `position_stat_distribution_agg` table
✅ Added `player_game_stats_wide` materialized view
✅ Created helper functions for aggregations
✅ Removed deprecated `weekly_percentiles` table
✅ Removed deprecated `player_performance_scores` table

### Next Steps:

1. **Close all temporary queries** (or save the verification ones for future reference)

2. **Test data collection** - When you collect new data, aggregations will auto-populate:
   ```bash
   # On your Mac terminal
   cd ~/Documents/GitHub/knowball/data_collection
   python main.py --mode collect --week 10
   ```

3. **Your Recharts app will now be able to query the efficient aggregation tables!**

---

## 🚨 Troubleshooting

### Problem: "Permission denied" errors
**Cause:** Your Supabase service role doesn't have permissions
**Solution:** You shouldn't see this with the default Supabase setup, but if you do:
1. Go to **Settings** > **Database** in Supabase
2. Make sure you're using the **service_role** key (not the anon key)

### Problem: SQL Editor is empty or won't load
**Cause:** Browser issue or slow connection
**Solution:**
1. Refresh the page (F5 or Cmd+R)
2. Try a different browser
3. Check your internet connection

### Problem: "Syntax error" when running migration
**Cause:** Copy/paste issue - some characters may have been corrupted
**Solution:**
1. Open the migration file in VS Code (not TextEdit)
2. Make sure you selected ALL text (scroll to bottom to verify)
3. Copy again and try pasting in a fresh query

### Problem: Migration seems stuck (loading forever)
**Cause:** Large migration or slow connection
**Solution:**
1. Wait 30 seconds
2. If still stuck, refresh the page
3. Re-run the verification queries to see if it actually completed

---

## 📸 Visual Reference

### What the SQL Editor Should Look Like:

```
┌────────────────────────────────────────────────────────────┐
│  Supabase Dashboard                        Your Project ▼  │
├────────────────────────────────────────────────────────────┤
│  ☰  SQL Editor                                             │
│                                                             │
│  + New query    [Search queries...]    [Filter ▼]         │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐ │
│  │ -- Migration 002: Player Stats Aggregation Tables   │ │
│  │ -- Created to optimize Recharts histogram queries   │ │
│  │                                                       │ │
│  │ CREATE TABLE player_stat_history_agg (               │ │
│  │     agg_id BIGSERIAL PRIMARY KEY,                    │ │
│  │     player_id INTEGER REFERENCES players...          │ │
│  │     ...                                               │ │
│  │ );                                                    │ │
│  └──────────────────────────────────────────────────────┘ │
│                                                             │
│  [ RUN (Cmd+Enter) ]                      [ Save query ]  │
│                                                             │
│  Results:                                                  │
│  ┌──────────────────────────────────────────────────────┐ │
│  │ Success. No rows returned                            │ │
│  └──────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────┘
```

---

## Questions?

If you get stuck:
1. **Check the error message** - read it carefully
2. **Look in the Troubleshooting section** above
3. **Save the error message** and ask for help
4. **Don't panic** - Supabase has automatic backups, nothing is permanently broken!

---

## Quick Command Reference

**Navigate to SQL Editor:**
Supabase Dashboard → SQL Editor (left sidebar)

**Create new query:**
Click "+ New query" button

**Run query:**
Click "RUN" button or press `Cmd+Enter` (Mac) / `Ctrl+Enter` (Windows)

**Copy migration file:**
Finder → Documents/GitHub/knowball/supabase/migrations → Select file → Cmd+A → Cmd+C

**Paste in SQL Editor:**
Click in editor → Cmd+V

That's it! You're all set! 🚀
