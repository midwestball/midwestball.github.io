# Mac Setup Guide

## Step 1: PostgreSQL Database Setup

You've already created the database `knowball`, now let's populate it with the schema.

### Apply the Schema

Run this command from your project root:

```bash
psql -d knowball -f supabase/migrations/001_initial_schema.sql
```

This will:
- Create all tables (sports, seasons, teams, players, games, stats, etc.)
- Set up indexes for performance
- Create helper functions and triggers
- **Seed initial data** (NFL sport + 2024 season)

### Verify the Schema

Check that tables were created:

```bash
psql -d knowball -c "\dt"
```

You should see tables like: `sports`, `seasons`, `teams`, `players`, `games`, `player_game_stats`, etc.

## Step 2: Configure Environment Variables

### Get Your Supabase Credentials

1. Go to [Supabase Dashboard](https://app.supabase.com)
2. Select your project
3. Go to **Settings** → **API**
4. Copy:
   - **Project URL** (looks like `https://xxxxx.supabase.co`)
   - **anon public key** (long JWT token)

### Update .env File

Edit `data_collection/.env`:

```bash
# Supabase Configuration
SUPABASE_URL=https://your-project-id.supabase.co
SUPABASE_KEY=your_long_anon_key_here

# Local Database Configuration
LOCAL_DATABASE_URL=postgresql://localhost/knowball
USE_LOCAL_DB=true
```

**Note:** Adjust the `LOCAL_DATABASE_URL` if you need authentication:
```bash
# With username/password
LOCAL_DATABASE_URL=postgresql://username:password@localhost/knowball

# With different port
LOCAL_DATABASE_URL=postgresql://localhost:5433/knowball
```

### Test Database Connection

```bash
cd data_collection
python test_connection.py
```

## Step 3: Seed Teams and Players

Now populate your databases with NFL teams and rosters from ESPN:

```bash
cd data_collection
python main.py --mode seed --use-local-db
```

This will:
- ✅ Fetch all 32 NFL teams from ESPN
- ✅ Fetch complete rosters for each team
- ✅ Write teams and players to **both** Supabase and local database

**Expected output:**
- 32 teams
- ~1,700+ players

## Step 4: Collect Game Data

### Collect a Single Week

```bash
python main.py --mode collect --week 10 --use-local-db --local-stats
```

This will:
- ✅ Fetch all games from Week 10
- ✅ Store teams/players/games in **both** databases
- ✅ Store stats **only in local database** (saves Supabase storage)

### Collect Multiple Weeks

For a full season backfill:

```bash
# Collect weeks 1-10
for week in {1..10}; do
  python main.py --mode collect --week $week --use-local-db --local-stats
  sleep 3  # Be nice to ESPN's API
done
```

## Step 5: Calculate Analytics (Local Only)

After collecting data, run analytics on your local database:

```bash
# Calculate percentiles
python main.py --mode percentiles --use-local-db

# Calculate performance scores
python main.py --mode scores --use-local-db
```

## Step 6: Full Pipeline (Recommended)

For ongoing weekly updates, use the full mode:

```bash
python main.py --mode full --use-local-db --local-stats
```

This runs:
1. Collect latest week's games
2. Calculate percentiles
3. Calculate impressiveness scores

## Quick Reference

### Database Architecture

**Supabase (Cloud):**
- Sports, Seasons, Teams, Players, Games
- Used by your web app

**Local PostgreSQL:**
- Everything in Supabase PLUS:
- player_game_stats (thousands of records)
- weekly_percentiles
- player_performance_scores
- Used for analytics and development

### Common Commands

```bash
# Check local database
psql -d knowball -c "SELECT COUNT(*) FROM teams;"
psql -d knowball -c "SELECT COUNT(*) FROM players;"
psql -d knowball -c "SELECT COUNT(*) FROM games;"
psql -d knowball -c "SELECT COUNT(*) FROM player_game_stats;"

# View recent games
psql -d knowball -c "SELECT game_id, game_date, game_week FROM games ORDER BY game_date DESC LIMIT 5;"

# Test connection
cd data_collection
python test_connection.py
```

## Troubleshooting

### "psql: command not found"

Add PostgreSQL to your PATH (for PostgreSQL.app):

```bash
# Add to ~/.zshrc or ~/.bash_profile
export PATH="/Applications/Postgres.app/Contents/Versions/latest/bin:$PATH"

# Reload
source ~/.zshrc
```

### "peer authentication failed"

Update PostgreSQL authentication. Edit `/usr/local/var/postgres/pg_hba.conf`:

```
# Change this line:
local   all   all   peer

# To this:
local   all   all   trust
```

Then restart PostgreSQL:
```bash
brew services restart postgresql
```

### "database does not exist"

Create the database:
```bash
createdb knowball
```

### Connection Issues

Test your connection string:
```bash
psql postgresql://localhost/knowball
```

If that works, your connection string is correct!

## Next Steps

After setup:
1. ✅ Schema applied to local PostgreSQL
2. ✅ .env configured with Supabase + local database
3. ✅ Teams and players seeded
4. ✅ Game data collected with `--local-stats`

Now you can:
- Collect weekly data with `--local-stats` to minimize Supabase usage
- Run analytics locally
- Use Supabase data in your web app
