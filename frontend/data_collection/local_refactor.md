# Local Database Refactor Plan

## Overview
This document provides a comprehensive plan to add a local PostgreSQL database alongside Supabase for storing complete historical sports data and running complex analytics queries.

## Architecture Goals

### Current State
- Data collection writes to Supabase only
- Limited by Supabase free tier storage
- Complex queries (percentiles) require RPC functions

### Target State
- **Supabase**: Current season + last 2-3 seasons (for production app queries)
- **Local PostgreSQL**: Complete historical data (all seasons, unlimited storage)
- **Analytics**: Run percentile calculations and complex queries on local DB
- **Flexibility**: Flag-based control to write to both or just Supabase

### Data Flow
```
ESPN API → Collection Script → {
    ├─→ Supabase (always, for app)
    └─→ Local PostgreSQL (optional flag, for analytics/history)
}

Analytics Queries (percentiles, etc.) → Local PostgreSQL only
```

## Implementation Plan

### Step 1: Create `local_database.py`

**Location**: `data_collection/local_database.py`

**Purpose**: PostgreSQL client using asyncpg (similar to old database.py)

**Requirements**:
- Copy the original `database.py` implementation (before Supabase refactor)
- Use `asyncpg` for connection pooling
- Implement all the same methods as current `database.py`:
  - `connect()`
  - `close()`
  - `acquire()` context manager
  - `get_or_create_team()`
  - `get_or_create_player()`
  - `insert_game()`
  - `insert_player_stats_batch()`
  - `get_active_season()`
  - `get_sport_id()`
  - `get_current_week()`
- Add raw SQL query support for percentile calculations:
  - `execute_raw_query(query, *args)`
  - `fetch_one(query, *args)`
  - `fetch_many(query, *args)`

**Key Implementation Details**:
```python
import asyncpg
from typing import Optional, List, Dict, Any
from contextlib import asynccontextmanager
import logging
import json

logger = logging.getLogger(__name__)

class LocalDatabase:
    def __init__(self, connection_string: str):
        self.connection_string = connection_string
        self.pool = None

    async def connect(self):
        self.pool = await asyncpg.create_pool(
            self.connection_string,
            min_size=2,
            max_size=10,
            command_timeout=60
        )
        logger.info("Local database connection pool created")

    async def close(self):
        if self.pool:
            await self.pool.close()
            logger.info("Local database connection pool closed")

    @asynccontextmanager
    async def acquire(self):
        async with self.pool.acquire() as conn:
            yield conn

    # ... implement all other methods from original database.py
```

### Step 2: Update `config.py`

**Changes needed**:
1. Add local database configuration
2. Add flag for enabling local database usage

**New configuration variables**:
```python
class Config:
    # Supabase (existing)
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_KEY = os.getenv("SUPABASE_KEY")

    # Local PostgreSQL (new)
    LOCAL_DATABASE_URL = os.getenv("LOCAL_DATABASE_URL")
    USE_LOCAL_DB = os.getenv("USE_LOCAL_DB", "false").lower() == "true"

    # ESPN and other configs (existing)
    ESPN_BASE_URL = "https://site.api.espn.com/apis/site/v2/sports"
    # ... rest of existing config

    @classmethod
    def validate_config(cls):
        if not cls.SUPABASE_URL:
            raise ValueError("SUPABASE_URL environment variable not set")
        if not cls.SUPABASE_KEY:
            raise ValueError("SUPABASE_KEY environment variable not set")

        # Only validate local DB if it's enabled
        if cls.USE_LOCAL_DB and not cls.LOCAL_DATABASE_URL:
            raise ValueError("USE_LOCAL_DB is true but LOCAL_DATABASE_URL is not set")

        return True
```

### Step 3: Update `.env`

**Add local database configuration**:
```bash
# Supabase Configuration (existing)
SUPABASE_URL=your_supabase_url_here
SUPABASE_KEY=your_supabase_anon_key_here

# Local PostgreSQL Configuration (new)
# Set to 'true' to also write data to local database
USE_LOCAL_DB=false

# Local PostgreSQL connection string
# Format: postgresql://username:password@localhost:5432/database_name
# Example: postgresql://postgres:password@localhost:5432/knowball_analytics
LOCAL_DATABASE_URL=postgresql://postgres:password@localhost:5432/knowball_analytics
```

### Step 4: Refactor `main.py`

**Major changes needed**:

#### 4.1: Update database initialization
```python
async def main():
    parser = argparse.ArgumentParser(description="Sports Data Collection")
    parser.add_argument("--mode", choices=["seed", "collect", "percentiles", "scores", "full"], required=True)
    parser.add_argument("--season", type=int, help="NFL season year")
    parser.add_argument("--week", type=int, help="NFL week number")
    parser.add_argument("--use-local-db", action="store_true", help="Also write to local database")

    args = parser.parse_args()

    Config.validate_config()

    # Always initialize Supabase
    supabase_db = Database(Config.SUPABASE_URL, Config.SUPABASE_KEY)

    # Conditionally initialize local DB
    local_db = None
    use_local = args.use_local_db or Config.USE_LOCAL_DB

    if use_local:
        from local_database import LocalDatabase
        local_db = LocalDatabase(Config.LOCAL_DATABASE_URL)

    try:
        await supabase_db.connect()
        if local_db:
            await local_db.connect()
            logger.info("Local database enabled - writing to both databases")

        # Pass both databases to functions
        if args.mode == "seed":
            await seed_initial_data(supabase_db, local_db)

        elif args.mode == "collect":
            await collect_weekly_nfl(supabase_db, local_db, args.season, args.week)

        elif args.mode == "percentiles":
            # Always use local DB for percentiles (if available)
            if local_db:
                await calculate_percentiles(local_db)
            else:
                logger.warning("Percentile calculation requires local database. Use --use-local-db flag")

        elif args.mode == "scores":
            # Use local DB if available, otherwise Supabase
            db_for_scores = local_db if local_db else supabase_db
            await calculate_impressiveness_scores(db_for_scores)

        elif args.mode == "full":
            await collect_weekly_nfl(supabase_db, local_db, args.season, args.week)
            if local_db:
                await calculate_percentiles(local_db)
                await calculate_impressiveness_scores(local_db)
            else:
                logger.warning("Skipping percentiles and scores - requires local database")

        logger.info("All operations completed successfully")

    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)

    finally:
        await supabase_db.close()
        if local_db:
            await local_db.close()
```

#### 4.2: Update `seed_initial_data()`
```python
async def seed_initial_data(supabase_db: Database, local_db: Optional[LocalDatabase]):
    logger.info("Starting initial data seeding...")

    # Seed to Supabase
    nfl_collector = NFLCollector(supabase_db, local_db)
    await nfl_collector.seed_teams_and_players()

    logger.info("Initial seeding complete")
```

#### 4.3: Update `collect_weekly_nfl()`
```python
async def collect_weekly_nfl(
    supabase_db: Database,
    local_db: Optional[LocalDatabase],
    season: int = None,
    week: int = None
):
    logger.info("Starting weekly NFL collection...")

    if not season:
        season = Config.SPORT_CONFIG["nfl"]["current_season"]

    nfl_collector = NFLCollector(supabase_db, local_db)

    if not week:
        season_id = await supabase_db.get_active_season("nfl")
        week = await supabase_db.get_current_week(season_id)

        if week == 0:
            week = 1

        logger.info(f"Auto-detected current week: {week}")

    games_collected = await nfl_collector.collect_weekly_data(season, week)

    logger.info(f"Weekly collection complete: {games_collected} games processed")
    return games_collected
```

#### 4.4: Restore original `calculate_percentiles()` for local DB
```python
async def calculate_percentiles(db: LocalDatabase):
    """
    Calculate percentiles using local PostgreSQL database with raw SQL.
    This function requires a LocalDatabase instance.
    """
    logger.info("Calculating weekly percentiles on local database...")

    async with db.acquire() as conn:
        season_id = await conn.fetchval("""
            SELECT season_id FROM seasons WHERE is_active = TRUE
        """)

        current_week = await conn.fetchval("""
            SELECT MAX(game_week) FROM games WHERE season_id = $1
        """, season_id)

        positions = ["QB", "RB", "WR", "TE"]

        key_stats = {
            "QB": ["passing_yards", "passing_touchdowns", "passer_rating"],
            "RB": ["rushing_yards", "rushing_touchdowns", "rushing_yards_per_attempt"],
            "WR": ["receptions", "receiving_yards", "receiving_touchdowns"],
            "TE": ["receptions", "receiving_yards", "receiving_touchdowns"]
        }

        for position in positions:
            stats_to_calc = key_stats.get(position, [])

            for stat_category in stats_to_calc:
                percentiles = await conn.fetchrow("""
                    WITH position_stats AS (
                        SELECT
                            pgs.stat_value
                        FROM player_game_stats pgs
                        JOIN games g ON pgs.game_id = g.game_id
                        WHERE g.season_id = $1
                            AND g.game_week <= $2
                            AND pgs.position = $3
                            AND pgs.stat_category = $4
                            AND pgs.stat_value > 0
                    )
                    SELECT
                        percentile_cont(0.10) WITHIN GROUP (ORDER BY stat_value) as p10,
                        percentile_cont(0.25) WITHIN GROUP (ORDER BY stat_value) as p25,
                        percentile_cont(0.50) WITHIN GROUP (ORDER BY stat_value) as p50,
                        percentile_cont(0.75) WITHIN GROUP (ORDER BY stat_value) as p75,
                        percentile_cont(0.90) WITHIN GROUP (ORDER BY stat_value) as p90,
                        percentile_cont(0.95) WITHIN GROUP (ORDER BY stat_value) as p95,
                        percentile_cont(0.99) WITHIN GROUP (ORDER BY stat_value) as p99,
                        AVG(stat_value) as mean,
                        STDDEV(stat_value) as std_dev,
                        MIN(stat_value) as min_val,
                        MAX(stat_value) as max_val,
                        COUNT(*) as sample_size
                    FROM position_stats
                """, season_id, current_week, position, stat_category)

                if percentiles and percentiles["sample_size"] > 0:
                    percentile_data = {
                        "p10": float(percentiles["p10"]) if percentiles["p10"] else 0,
                        "p25": float(percentiles["p25"]) if percentiles["p25"] else 0,
                        "p50": float(percentiles["p50"]) if percentiles["p50"] else 0,
                        "p75": float(percentiles["p75"]) if percentiles["p75"] else 0,
                        "p90": float(percentiles["p90"]) if percentiles["p90"] else 0,
                        "p95": float(percentiles["p95"]) if percentiles["p95"] else 0,
                        "p99": float(percentiles["p99"]) if percentiles["p99"] else 0,
                        "mean": float(percentiles["mean"]) if percentiles["mean"] else 0,
                        "std_dev": float(percentiles["std_dev"]) if percentiles["std_dev"] else 0,
                        "min": float(percentiles["min_val"]) if percentiles["min_val"] else 0,
                        "max": float(percentiles["max_val"]) if percentiles["max_val"] else 0
                    }

                    await conn.execute("""
                        INSERT INTO weekly_percentiles (
                            season_id,
                            week_number,
                            position,
                            stat_category,
                            calculation_date,
                            percentile_data,
                            sample_size
                        ) VALUES ($1, $2, $3, $4, NOW(), $5, $6)
                        ON CONFLICT (season_id, week_number, position, stat_category, calculation_date)
                        DO UPDATE SET
                            percentile_data = EXCLUDED.percentile_data,
                            sample_size = EXCLUDED.sample_size
                    """, season_id, current_week, position, stat_category, percentile_data, percentiles["sample_size"])

                    logger.info(f"Calculated percentiles for {position} {stat_category}: {percentiles['sample_size']} samples")

    logger.info("Percentile calculation complete")
```

#### 4.5: Update `calculate_impressiveness_scores()`
```python
async def calculate_impressiveness_scores(db):
    """
    Calculate impressiveness scores.
    Works with either LocalDatabase (asyncpg) or Database (Supabase).
    """
    logger.info("Calculating impressiveness scores...")

    # Check if it's a LocalDatabase (has asyncpg pool) or Supabase Database
    is_local = hasattr(db, 'pool')

    if is_local:
        # Use original SQL-based implementation
        async with db.acquire() as conn:
            season_id = await conn.fetchval("""
                SELECT season_id FROM seasons WHERE is_active = TRUE
            """)

            current_week = await conn.fetchval("""
                SELECT MAX(game_week) FROM games WHERE season_id = $1
            """, season_id)

            recent_games = await conn.fetch("""
                SELECT game_id FROM games
                WHERE season_id = $1 AND game_week = $2
            """, season_id, current_week)

            for game_record in recent_games:
                game_id = game_record["game_id"]

                stats = await conn.fetch("""
                    SELECT
                        pgs.stat_id,
                        pgs.player_id,
                        pgs.position,
                        pgs.stat_category,
                        pgs.stat_value
                    FROM player_game_stats pgs
                    WHERE pgs.game_id = $1
                """, game_id)

                for stat in stats:
                    percentile_record = await conn.fetchrow("""
                        SELECT percentile_data
                        FROM weekly_percentiles
                        WHERE season_id = $1
                            AND week_number = $2
                            AND position = $3
                            AND stat_category = $4
                        ORDER BY calculation_date DESC
                        LIMIT 1
                    """, season_id, current_week, stat["position"], stat["stat_category"])

                    if not percentile_record:
                        continue

                    percentiles = percentile_record["percentile_data"]
                    stat_value = float(stat["stat_value"])

                    if stat_value >= percentiles.get("p99", 0):
                        percentile_rank = 99
                    elif stat_value >= percentiles.get("p95", 0):
                        percentile_rank = 95
                    elif stat_value >= percentiles.get("p90", 0):
                        percentile_rank = 90
                    elif stat_value >= percentiles.get("p75", 0):
                        percentile_rank = 75
                    elif stat_value >= percentiles.get("p50", 0):
                        percentile_rank = 50
                    else:
                        percentile_rank = 25

                    impressiveness = percentile_rank * (stat_value / max(percentiles.get("mean", 1), 1))

                    await conn.execute("""
                        INSERT INTO player_performance_scores (
                            game_id,
                            player_id,
                            stat_category,
                            raw_value,
                            percentile_rank,
                            impressiveness_score,
                            score_version
                        ) VALUES ($1, $2, $3, $4, $5, $6, 'v1')
                        ON CONFLICT (game_id, player_id, stat_category, score_version)
                        DO UPDATE SET
                            raw_value = EXCLUDED.raw_value,
                            percentile_rank = EXCLUDED.percentile_rank,
                            impressiveness_score = EXCLUDED.impressiveness_score,
                            calculated_at = NOW()
                    """, game_id, stat["player_id"], stat["stat_category"], stat["stat_value"], percentile_rank, impressiveness)

    else:
        # Use Supabase implementation (current implementation)
        # ... keep current Supabase-based implementation
        pass

    logger.info("Impressiveness score calculation complete")
```

### Step 5: Update `collectors/nfl_collector.py`

**Changes needed**: Accept both databases and write to both when available

```python
class NFLCollector:
    def __init__(self, supabase_db: Database, local_db: Optional[LocalDatabase] = None):
        self.supabase_db = supabase_db
        self.local_db = local_db
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Sports Analytics Platform)"
        })
        self.espn_base = Config.get_espn_url("nfl", "")

    async def _ensure_team(self, sport_id: int, team_data: Dict) -> Dict[str, int]:
        """
        Ensure team exists in both databases.
        Returns dict with both team_ids: {"supabase": id, "local": id}
        """
        team_external_id = str(team_data["team"]["id"])
        team_info = team_data["team"]

        team_record = {
            "name": team_info.get("name"),
            "abbreviation": team_info.get("abbreviation"),
            "displayName": team_info.get("displayName"),
            "location": team_info.get("location"),
            "color": team_info.get("color"),
            "logo": team_info.get("logo"),
            "metadata": {
                "alternateColor": team_info.get("alternateColor"),
                "links": team_info.get("links", [])
            }
        }

        # Always create in Supabase
        supabase_team_id = await self.supabase_db.get_or_create_team(
            sport_id,
            team_external_id,
            team_record
        )

        result = {"supabase": supabase_team_id}

        # Optionally create in local DB
        if self.local_db:
            local_team_id = await self.local_db.get_or_create_team(
                sport_id,
                team_external_id,
                team_record
            )
            result["local"] = local_team_id

        return result

    # Similar updates for _parse_player_stats, _process_game, etc.
    # Each method should write to both databases when local_db is available
```

**Key pattern for all write operations**:
```python
# Always write to Supabase
await self.supabase_db.insert_game(...)

# Conditionally write to local DB
if self.local_db:
    await self.local_db.insert_game(...)
```

### Step 6: Add Import Statements

Update import statements in `main.py`:
```python
import asyncio
import logging
import sys
import argparse
from datetime import datetime
from typing import Optional

from config import Config
from database import Database  # Supabase
from local_database import LocalDatabase  # PostgreSQL (conditional import)
from collectors.nfl_collector import NFLCollector
```

## Database Schema Considerations

### Important Notes:
1. **Schema Compatibility**: Local PostgreSQL database should have the **exact same schema** as Supabase
2. **Migration**: You can use Supabase's schema export to create local tables
3. **Sync Strategy**:
   - Write to both databases during collection
   - Local DB can have more historical data
   - Supabase can be pruned to keep only recent seasons

### Getting the Schema:
From Supabase dashboard:
1. Go to Database → Schema
2. Export SQL schema
3. Run on local PostgreSQL to create matching tables

## Usage Examples

After refactoring, usage will be:

```bash
# Activate virtual environment
source .venv/bin/activate

# Collect to Supabase only (default)
python main.py --mode collect --season 2024 --week 8

# Collect to both Supabase AND local database
python main.py --mode collect --season 2024 --week 8 --use-local-db

# Calculate percentiles (requires local database)
python main.py --mode percentiles --use-local-db

# Full workflow with local database
python main.py --mode full --season 2024 --week 8 --use-local-db
```

Alternatively, set in `.env`:
```bash
USE_LOCAL_DB=true
```
Then the `--use-local-db` flag is not needed.

## Testing Strategy

### Phase 1: Verify local_database.py
1. Create `local_database.py`
2. Test connection to local PostgreSQL
3. Verify all CRUD operations work

### Phase 2: Test dual-write
1. Update `config.py` and `.env`
2. Run seed operation to both databases
3. Verify data exists in both

### Phase 3: Test analytics
1. Populate local DB with test data
2. Run percentile calculations
3. Verify results are correct

### Phase 4: Integration test
1. Run full workflow with `--mode full --use-local-db`
2. Verify data in both databases
3. Check percentile and score calculations

## Rollback Plan

If something goes wrong:
1. The Supabase-only code path remains unchanged
2. Simply don't use `--use-local-db` flag
3. Remove `local_database.py` if needed
4. Everything continues to work with Supabase only

## Additional Enhancements (Optional)

### Future improvements to consider:

1. **Sync Command**: Add `--mode sync-to-supabase` to push local data to Supabase
2. **Backfill Command**: Add `--mode backfill-local` to pull Supabase data to local
3. **Pruning Command**: Add `--mode prune-supabase` to remove old seasons from Supabase
4. **Data Export**: Add utilities to export local data to CSV/JSON for analysis
5. **Backup Script**: Automated local database backups

## Prerequisites

### Local PostgreSQL Setup:
```bash
# Install PostgreSQL (macOS)
brew install postgresql@14
brew services start postgresql@14

# Create database
createdb knowball_analytics

# Verify connection
psql knowball_analytics
```

### Python Dependencies:
All dependencies should already be installed (asyncpg, supabase-py, etc.)

## Summary

This refactor provides:
- ✅ Unlimited local storage for historical data
- ✅ Fast complex queries without RPC functions
- ✅ Supabase for production app queries
- ✅ Flexible flag-based control
- ✅ No breaking changes to existing Supabase-only workflow
- ✅ Easy to test and develop locally

The implementation is straightforward and follows clean separation of concerns. The local database code is essentially the original asyncpg implementation restored, while Supabase integration remains intact.
