# Supabase Database Setup Guide

## Step 1: Create Supabase Project

1. Go to [supabase.com](https://supabase.com) and create a new project
2. Choose your organization and project name
3. Select a database password (save this securely)
4. Choose your region (closest to your users)

## Step 2: Get Connection Details

From your Supabase dashboard, go to Settings > Database and note:
- **Host**: `db.xxx.supabase.co` (where xxx is your project reference)
- **Database name**: `postgres`
- **Username**: `postgres`
- **Password**: Your chosen password
- **Port**: `5432`

## Step 3: Set Up Environment Variables

Create a `.env` file in your project root:

```env
# Supabase Configuration
SUPABASE_URL=https://your-project-ref.supabase.co
SUPABASE_ANON_KEY=your-anon-key-from-settings-api
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key-from-settings-api

# Database Connection
DB_HOST=db.your-project-ref.supabase.co
DB_NAME=postgres
DB_USER=postgres
DB_PASSWORD=your-database-password
DB_PORT=5432

# Application
FLASK_ENV=production
PORT=8080
```

## Step 4: Create Database Schema

1. Go to your Supabase dashboard
2. Navigate to the SQL Editor
3. Execute the following SQL schema:

```sql
-- NBA Stats Database Schema for Supabase
-- Players table
CREATE TABLE players (
    id SERIAL PRIMARY KEY,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    full_name TEXT NOT NULL,
    player_slug TEXT NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_updated TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for fast search
CREATE INDEX idx_players_full_name ON players (full_name);
CREATE INDEX idx_players_slug ON players (player_slug);

-- Games table
CREATE TABLE games (
    id SERIAL PRIMARY KEY,
    game_id TEXT UNIQUE NOT NULL,
    game_date DATE NOT NULL,
    season TEXT NOT NULL,
    home_team TEXT NOT NULL,
    away_team TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for performance
CREATE INDEX idx_games_date ON games (game_date);
CREATE INDEX idx_games_season ON games (season);

-- Player game stats table
CREATE TABLE player_game_stats (
    id SERIAL PRIMARY KEY,
    player_id INTEGER REFERENCES players(id),
    game_id INTEGER REFERENCES games(id),
    points INTEGER,
    rebounds INTEGER,
    assists INTEGER,
    steals INTEGER,
    blocks INTEGER,
    minutes INTEGER,
    field_goals_made INTEGER,
    field_goals_attempted INTEGER,
    field_goal_percentage NUMERIC(5,2),
    three_pointers_made INTEGER,
    three_pointers_attempted INTEGER, 
    three_point_percentage NUMERIC(5,2),
    free_throws_made INTEGER,
    free_throws_attempted INTEGER,
    free_throw_percentage NUMERIC(5,2),
    turnovers INTEGER,
    plus_minus INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(player_id, game_id)
);

-- League averages table
CREATE TABLE league_averages (
    id SERIAL PRIMARY KEY,
    season TEXT NOT NULL,
    stat_type TEXT NOT NULL,
    average_value NUMERIC(8,3) NOT NULL,
    standard_deviation NUMERIC(8,3) NOT NULL,
    min_value NUMERIC(8,3) NOT NULL,
    max_value NUMERIC(8,3) NOT NULL,
    sample_size INTEGER NOT NULL,
    last_updated TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(season, stat_type)
);

-- Impressive performances table
CREATE TABLE impressive_performances (
    id SERIAL PRIMARY KEY,
    player_id INTEGER REFERENCES players(id),
    game_id INTEGER REFERENCES games(id),
    stat_type TEXT NOT NULL,
    value NUMERIC(8,2) NOT NULL,
    z_score NUMERIC(6,3) NOT NULL,
    league_rank INTEGER,
    player_rank INTEGER,
    combined_score NUMERIC(6,3),
    display_until DATE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for performance
CREATE INDEX idx_impressive_performances_scores ON impressive_performances (combined_score DESC);
CREATE INDEX idx_impressive_performances_date ON impressive_performances (display_until);

-- Player statistical distributions
CREATE TABLE player_stat_distributions (
    id SERIAL PRIMARY KEY,
    player_id INTEGER REFERENCES players(id),
    season TEXT NOT NULL,
    stat_type TEXT NOT NULL,
    mean NUMERIC(8,3) NOT NULL,
    median NUMERIC(8,3) NOT NULL,
    std_dev NUMERIC(8,3) NOT NULL,
    min_value NUMERIC(8,3) NOT NULL,
    max_value NUMERIC(8,3) NOT NULL,
    percentile_25 NUMERIC(8,3) NOT NULL,
    percentile_75 NUMERIC(8,3) NOT NULL,
    sample_size INTEGER NOT NULL,
    last_updated TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(player_id, season, stat_type)
);

-- Enable Row Level Security
ALTER TABLE players ENABLE ROW LEVEL SECURITY;
ALTER TABLE games ENABLE ROW LEVEL SECURITY;
ALTER TABLE player_game_stats ENABLE ROW LEVEL SECURITY;
ALTER TABLE league_averages ENABLE ROW LEVEL SECURITY;
ALTER TABLE impressive_performances ENABLE ROW LEVEL SECURITY;
ALTER TABLE player_stat_distributions ENABLE ROW LEVEL SECURITY;

-- Create policies for public read access
CREATE POLICY "Public read access" ON players FOR SELECT USING (true);
CREATE POLICY "Public read access" ON games FOR SELECT USING (true);
CREATE POLICY "Public read access" ON player_game_stats FOR SELECT USING (true);
CREATE POLICY "Public read access" ON league_averages FOR SELECT USING (true);
CREATE POLICY "Public read access" ON impressive_performances FOR SELECT USING (true);
CREATE POLICY "Public read access" ON player_stat_distributions FOR SELECT USING (true);
```

## Step 5: Set Up Service Role Policies

For your data collection scripts, you'll need INSERT/UPDATE permissions. In the Supabase dashboard:

1. Go to Authentication > Policies
2. For each table, create a policy for your service role:

```sql
-- Example policy for service role (replace with your actual service role)
CREATE POLICY "Service role full access" ON players FOR ALL 
USING (auth.role() = 'service_role');
```

## Step 6: Test Connection

Run your Python application to test the database connection:

```bash
python app.py
```

## Step 7: Populate Data

Use your data collection scripts to populate the database with NBA data.

## Security Notes

- Never commit your `.env` file to version control
- Use the service role key only for server-side operations
- The anon key is safe for client-side use but has limited permissions
- RLS policies control data access at the row level

## Monitoring

- Monitor your database usage in the Supabase dashboard
- Set up alerts for usage limits
- Regular backups are automatically handled by Supabase