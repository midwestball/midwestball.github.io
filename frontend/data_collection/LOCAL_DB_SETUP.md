# Local Database Setup Guide

This guide explains how to set up and use the local PostgreSQL database alongside Supabase for analytics and machine learning.

## Architecture Overview

### Dual Database System

- **Supabase**: Production database for the app, stores current season + recent data
- **Local PostgreSQL**: Analytics database on your machine, stores complete historical data

### Benefits

1. **Unlimited Storage**: Store all historical data locally without Supabase storage limits
2. **Fast Queries**: Run complex analytics queries (percentiles, ML) locally without RPC functions
3. **Flexibility**: Flag-based control to write to both databases or just Supabase
4. **ML Ready**: Local database optimized for machine learning workflows

## Prerequisites

### 1. Install PostgreSQL

**Windows:**
- Download from [postgresql.org](https://www.postgresql.org/download/windows/)
- Or use Chocolatey: `choco install postgresql`

**macOS:**
```bash
brew install postgresql@14
brew services start postgresql@14
```

**Linux:**
```bash
sudo apt-get install postgresql postgresql-contrib
sudo systemctl start postgresql
```

### 2. Create Database

```bash
# Create the database
createdb knowball_analytics

# Verify connection
psql knowball_analytics
```

### 3. Install Python Dependencies

```bash
pip install asyncpg
```

All other dependencies should already be installed.

## Setup Steps

### Step 1: Configure Environment

Edit your `.env` file in `data_collection/`:

```bash
# Supabase Configuration (existing)
SUPABASE_URL="https://your-project.supabase.co"
SUPABASE_KEY="your-anon-key"

# Local PostgreSQL Configuration (new)
USE_LOCAL_DB=true

# Update with your PostgreSQL credentials
LOCAL_DATABASE_URL=postgresql://postgres:yourpassword@localhost:5432/knowball_analytics
```

**Connection String Format:**
```
postgresql://username:password@host:port/database
```

### Step 2: Setup Database Schema

Run the setup script to create all tables:

```bash
cd data_collection
python setup_local_db.py
```

This will:
1. Connect to your local PostgreSQL database
2. Execute the schema from `supabase/migrations/001_initial_schema.sql`
3. Create all tables (sports, teams, players, games, stats, percentiles, ML tables)
4. Verify the setup

**Optional Arguments:**
```bash
# Use custom connection string
python setup_local_db.py --connection-string "postgresql://user:pass@localhost:5432/mydb"

# Use custom schema file
python setup_local_db.py --schema-file /path/to/schema.sql

# Skip verification
python setup_local_db.py --skip-verification
```

### Step 3: Seed Initial Data

Seed teams and players to both databases:

```bash
python main.py --mode seed --use-local-db
```

This will:
- Fetch all NFL teams from ESPN
- Fetch all players for each team
- Create records in both Supabase and local database

## Usage

### Collect Data (Dual-Write Mode)

Collect weekly data and write to both databases:

```bash
# Collect current week
python main.py --mode collect --use-local-db

# Collect specific week
python main.py --mode collect --season 2024 --week 8 --use-local-db
```

**What happens:**
1. Fetches games from ESPN API
2. Writes games and stats to **Supabase**
3. Also writes to **local database** (when `--use-local-db` is used)

### Calculate Percentiles (Local Only)

Percentile calculations require local database:

```bash
python main.py --mode percentiles --use-local-db
```

**What happens:**
1. Queries local database with raw SQL
2. Calculates percentiles using PostgreSQL functions
3. Stores results in `weekly_percentiles` table

**Why local only?** Complex percentile queries with `percentile_cont()` are much faster locally than through Supabase RPC functions.

### Calculate Performance Scores

```bash
python main.py --mode scores --use-local-db
```

Uses local database if available, otherwise falls back to Supabase.

### Full Workflow

Run complete workflow (collect + percentiles + scores):

```bash
python main.py --mode full --season 2024 --week 8 --use-local-db
```

### Supabase-Only Mode

You can still use Supabase only (without local database):

```bash
# Don't use --use-local-db flag
python main.py --mode collect --season 2024 --week 8

# Or set in .env
USE_LOCAL_DB=false
```

## Syncing Data to Supabase

After calculating percentiles and scores locally, sync them to Supabase:

### Sync Recent Weeks

```bash
# Sync most recent week
python sync_to_supabase.py --mode games --weeks 1

# Sync last 3 weeks
python sync_to_supabase.py --mode games --weeks 3
```

### Sync Percentiles

```bash
python sync_to_supabase.py --mode percentiles --weeks 1
```

### Sync Performance Scores

```bash
python sync_to_supabase.py --mode scores --weeks 1
```

### Sync Everything

```bash
python sync_to_supabase.py --mode all --weeks 1
```

**What gets synced:**
- Recent game data and stats
- Calculated percentiles
- Performance scores
- ML predictions (when implemented)

## Configuration Options

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `SUPABASE_URL` | Supabase project URL | Required |
| `SUPABASE_KEY` | Supabase anon key | Required |
| `LOCAL_DATABASE_URL` | PostgreSQL connection string | None |
| `USE_LOCAL_DB` | Enable local database | `false` |

### Command-Line Flags

| Flag | Description |
|------|-------------|
| `--use-local-db` | Enable local database for this run |
| `--mode` | Operation mode (seed, collect, percentiles, scores, full) |
| `--season` | NFL season year |
| `--week` | NFL week number |

## Machine Learning Workflow

### Recommended ML Setup

1. **Collect Historical Data** (local only)
   ```bash
   # Collect multiple seasons to local database
   for week in {1..18}; do
     python main.py --mode collect --season 2023 --week $week --use-local-db
   done
   ```

2. **Calculate Percentiles** (local)
   ```bash
   python main.py --mode percentiles --use-local-db
   ```

3. **Train Models** (use local database)
   ```python
   from local_database import LocalDatabase
   from config import Config

   async def train_model():
       db = LocalDatabase(Config.LOCAL_DATABASE_URL)
       await db.connect()

       # Query historical data
       data = await db.fetch_many("""
           SELECT * FROM player_game_stats
           WHERE game_id IN (
               SELECT game_id FROM games WHERE season_id = ...
           )
       """)

       # Train your model here
       # ...

       await db.close()
   ```

4. **Sync Results to Supabase** (for app)
   ```bash
   python sync_to_supabase.py --mode all --weeks 2
   ```

## Database Schema

Both databases have identical schemas:

### Core Tables
- `sports` - Sports metadata (NFL, NBA, etc.)
- `seasons` - Season information
- `teams` - Team records
- `players` - Player profiles
- `games` - Game records
- `player_game_stats` - Raw statistics

### Analytics Tables
- `weekly_percentiles` - Calculated percentile distributions
- `player_performance_scores` - Impressiveness scores

### ML Tables
- `ml_models` - Model metadata
- `ml_feature_store` - Feature vectors
- `ml_predictions` - Model predictions

## Troubleshooting

### Connection Issues

**Error: "Database does not exist"**
```bash
createdb knowball_analytics
```

**Error: "Password authentication failed"**
- Check your PostgreSQL password
- Update `LOCAL_DATABASE_URL` in `.env`
- Verify with: `psql -U postgres -d knowball_analytics`

**Error: "Connection refused"**
- Ensure PostgreSQL is running
- Windows: Check Services
- macOS: `brew services list`
- Linux: `sudo systemctl status postgresql`

### Schema Issues

**Error: "Relation does not exist"**
- Run setup script again: `python setup_local_db.py`
- Check schema file path

**Error: "Duplicate object"**
- Tables already exist (this is OK)
- Drop and recreate if needed: `dropdb knowball_analytics && createdb knowball_analytics`

### Performance Issues

**Slow queries?**
- Check indexes: All key indexes are created in schema
- Vacuum database: `VACUUM ANALYZE;`
- Check connection pool size in `local_database.py`

## Best Practices

### Data Management

1. **Supabase**: Keep 2-3 most recent seasons
2. **Local**: Store all historical data
3. **Sync**: Push recent weeks + analytics to Supabase regularly

### Development Workflow

1. Develop and test queries locally (fast)
2. Run analytics on local database (complex queries)
3. Sync results to Supabase (for production app)
4. Keep local database as source of truth for historical data

### Backup Strategy

**Local Database:**
```bash
# Backup
pg_dump knowball_analytics > backup_$(date +%Y%m%d).sql

# Restore
psql knowball_analytics < backup_20240101.sql
```

**Supabase:**
- Automatic backups (check your Supabase plan)
- Can restore from local if needed

## Advanced Usage

### Custom Queries

Use `local_database.py` for custom analytics:

```python
from local_database import LocalDatabase

async def custom_query():
    db = LocalDatabase("postgresql://...")
    await db.connect()

    # Raw SQL query
    results = await db.fetch_many("""
        SELECT p.player_name, AVG(pgs.stat_value) as avg_yards
        FROM player_game_stats pgs
        JOIN players p ON pgs.player_id = p.player_id
        WHERE pgs.stat_category = 'passing_yards'
        GROUP BY p.player_name
        ORDER BY avg_yards DESC
        LIMIT 10
    """)

    for row in results:
        print(f"{row['player_name']}: {row['avg_yards']:.2f}")

    await db.close()
```

### Pruning Old Data

Remove old data from Supabase to save space:

```sql
-- Remove seasons older than 2022
DELETE FROM games WHERE season_id IN (
    SELECT season_id FROM seasons WHERE season_year < 2022
);
```

### Exporting Data

Export for analysis:

```bash
# CSV export
psql knowball_analytics -c "COPY (SELECT * FROM player_game_stats) TO STDOUT WITH CSV HEADER" > stats.csv

# JSON export
psql knowball_analytics -c "SELECT json_agg(t) FROM (SELECT * FROM player_game_stats) t" > stats.json
```

## Next Steps

1. Set up your local PostgreSQL database
2. Configure `.env` with your credentials
3. Run setup script: `python setup_local_db.py`
4. Seed initial data: `python main.py --mode seed --use-local-db`
5. Start collecting: `python main.py --mode collect --use-local-db`
6. Calculate analytics: `python main.py --mode percentiles --use-local-db`
7. Sync to Supabase: `python sync_to_supabase.py --mode all --weeks 1`

## Support

If you encounter issues:
1. Check logs in `data_collection_YYYYMMDD.log`
2. Verify PostgreSQL is running
3. Check `.env` configuration
4. Review error messages in terminal

For questions about the schema, see: `supabase/migrations/001_initial_schema.sql`
