from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
DB_PATH = DATA_DIR / "knowball.db"
PARQUET_DIR = DATA_DIR / "parquet"
PLAYER_GAME_LOGS_PATH = PARQUET_DIR / "player_game_logs.parquet"

# Metrics used for league distribution baselines (per-game values).
DISTRIBUTION_METRICS = ("passing_epa", "rushing_epa", "receiving_epa")

TIMEFRAME_CURRENT_SEASON = "Current Season"
TIMEFRAME_LAST_10_WEEKS = "Last 10 Weeks"
