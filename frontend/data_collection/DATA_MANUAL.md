# Data Collection Manual

## Overview
The data collection system fetches NFL data from ESPN and stores it in Supabase and/or a local PostgreSQL database.

## Prerequisites
1. Python 3.8+
2. Supabase account with configured database
3. (Optional) Local PostgreSQL database
4. Environment variables configured in `.env`:
   - `SUPABASE_URL`
   - `SUPABASE_KEY`
   - `LOCAL_DATABASE_URL` (if using local database)
   - `USE_LOCAL_DB=true` (optional, for always using local DB)

## Usage

### Basic Command Structure
```bash
cd data_collection
python main.py --mode <MODE> [OPTIONS]
```

## Modes

### 1. Seed Initial Data
Populate teams and players from ESPN.
```bash
python main.py --mode seed
```

### 2. Collect Weekly Games
Fetch game data and stats for a specific week.

**Auto-detect current week:**
```bash
python main.py --mode collect
```

**Specify season and week:**
```bash
python main.py --mode collect --season 2024 --week 10
```

### 3. Calculate Percentiles
Calculate statistical percentiles from local database (requires local DB).
```bash
python main.py --mode percentiles --use-local-db
```

### 4. Calculate Impressiveness Scores
Calculate player performance scores (requires local DB).
```bash
python main.py --mode scores --use-local-db
```

### 5. Full Pipeline
Run collection + percentiles + scores in one command.
```bash
python main.py --mode full --use-local-db
```

## Database Options

### Use Local Database
Write data to both Supabase and local PostgreSQL:
```bash
python main.py --mode collect --use-local-db
```

### Local Stats Only (Recommended)
Store **stats ONLY** in local database, everything else in Supabase:
```bash
python main.py --mode collect --use-local-db --local-stats
```

**Benefits:**
- Reduces Supabase storage costs
- Keeps metadata (teams, players, games) in Supabase for your app
- Stores heavy statistical data locally for analytics

## Common Workflows

### Production Collection (Minimal Supabase Usage)
```bash
# Collect with stats only in local DB
python main.py --mode collect --use-local-db --local-stats

# Calculate analytics locally
python main.py --mode percentiles --use-local-db
python main.py --mode scores --use-local-db
```

### Full Local Development
Set `USE_LOCAL_DB=true` in `.env`, then:
```bash
python main.py --mode full --local-stats
```

### Initial Setup
```bash
# 1. Seed teams and players
python main.py --mode seed --use-local-db

# 2. Collect all season data (one week at a time)
for week in {1..18}; do
  python main.py --mode collect --week $week --use-local-db --local-stats
  sleep 2
done

# 3. Calculate analytics
python main.py --mode percentiles --use-local-db
python main.py --mode scores --use-local-db
```

## Logs
Log files are automatically created in the `data_collection` directory:
- `data_collection_YYYYMMDD.log`

## Troubleshooting

**Error: "No active season found"**
- Run seed mode first: `python main.py --mode seed`

**Error: "--local-stats requires --use-local-db"**
- Add `--use-local-db` flag or set `USE_LOCAL_DB=true` in `.env`

**Error: "Percentile calculation requires local database"**
- Percentiles and scores modes require a local database with stats data
