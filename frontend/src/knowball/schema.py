"""SQLite table definitions for Phase 1 local storage."""

from knowball.stats_schema import stats_ddl

PLAYERS_DDL = """
CREATE TABLE IF NOT EXISTS players (
    gsis_id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    position TEXT,
    position_group TEXT,
    headshot_url TEXT,
    first_name TEXT,
    last_name TEXT,
    college TEXT,
    height TEXT,
    weight INTEGER,
    birth_date TEXT
);
"""

GAMES_DDL = """
CREATE TABLE IF NOT EXISTS games (
    game_id TEXT PRIMARY KEY,
    season INTEGER NOT NULL,
    week INTEGER NOT NULL,
    game_type TEXT,
    gameday TEXT,
    weekday TEXT,
    gametime TEXT,
    home_team TEXT NOT NULL,
    away_team TEXT NOT NULL,
    home_score INTEGER,
    away_score INTEGER,
    location TEXT,
    result INTEGER,
    total REAL,
    overtime INTEGER
);
"""

STATS_DDL = stats_ddl()

LEAGUE_DISTRIBUTIONS_DDL = """
CREATE TABLE IF NOT EXISTS league_distributions (
    metric TEXT NOT NULL,
    timeframe_context TEXT NOT NULL,
    bin_start REAL NOT NULL,
    bin_end REAL NOT NULL,
    count INTEGER NOT NULL,
    PRIMARY KEY (metric, timeframe_context, bin_start, bin_end)
);
"""

LEAGUE_KDE_DDL = """
CREATE TABLE IF NOT EXISTS league_kde (
    metric TEXT NOT NULL,
    timeframe_context TEXT NOT NULL,
    grid_index INTEGER NOT NULL,
    x REAL NOT NULL,
    density REAL NOT NULL,
    axis_min REAL NOT NULL,
    axis_max REAL NOT NULL,
    PRIMARY KEY (metric, timeframe_context, grid_index)
);
"""

ALL_DDL = (PLAYERS_DDL, GAMES_DDL, STATS_DDL, LEAGUE_DISTRIBUTIONS_DDL, LEAGUE_KDE_DDL)
