"""SQLite table definitions for Phase 1 local storage."""

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

STATS_DDL = """
CREATE TABLE IF NOT EXISTS stats (
    player_id TEXT NOT NULL,
    game_id TEXT NOT NULL,
    season INTEGER NOT NULL,
    week INTEGER NOT NULL,
    season_type TEXT,
    team TEXT,
    opponent_team TEXT,
    position TEXT,
    position_group TEXT,
    passing_epa REAL,
    rushing_epa REAL,
    receiving_epa REAL,
    completions INTEGER,
    attempts INTEGER,
    passing_yards REAL,
    passing_tds INTEGER,
    rushing_yards REAL,
    rushing_tds INTEGER,
    receptions INTEGER,
    targets INTEGER,
    receiving_yards REAL,
    receiving_tds INTEGER,
    PRIMARY KEY (player_id, game_id),
    FOREIGN KEY (player_id) REFERENCES players(gsis_id),
    FOREIGN KEY (game_id) REFERENCES games(game_id)
);
"""

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

ALL_DDL = (PLAYERS_DDL, GAMES_DDL, STATS_DDL, LEAGUE_DISTRIBUTIONS_DDL)
