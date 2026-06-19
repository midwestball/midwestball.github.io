import os
import tomllib
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
TIMEFRAME_ALL_TIME = "All-Time"
TIMEFRAME_BEST_SEASON = "best_season"

# League-wide precomputed contexts (ingest). Player UI uses per-player options instead.
TIMEFRAME_OPTIONS = (
    TIMEFRAME_CURRENT_SEASON,
    TIMEFRAME_LAST_10_WEEKS,
    TIMEFRAME_ALL_TIME,
)

METRIC_LABELS: dict[str, str] = {
    "passing_epa": "Passing EPA",
    "rushing_epa": "Rushing EPA",
    "receiving_epa": "Receiving EPA",
}

# Local SQLite is the default for loaders, cache, and ingest.
DB_URL = None  # set below after sqlite_url is defined


def sqlite_url(db_path: Path = DB_PATH) -> str:
    """SQLAlchemy URL for a local SQLite file."""
    return f"sqlite:///{db_path.resolve().as_posix()}"


DB_URL = sqlite_url()


def _normalize_postgres_url(url: str) -> str:
    """Ensure SQLAlchemy uses the psycopg2 driver."""
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg2://", 1)
    return url


def _load_secrets_toml() -> dict:
    secrets_path = PROJECT_ROOT / ".streamlit" / "secrets.toml"
    if not secrets_path.exists():
        return {}
    try:
        with secrets_path.open("rb") as secrets_file:
            return tomllib.load(secrets_file)
    except (tomllib.TOMLDecodeError, OSError):
        return {}


def _project_ref_from_host(host: str | None) -> str:
    if not host:
        return ""
    return host.removeprefix("db.").split(".", maxsplit=1)[0]


def _to_session_pooler_url(url: str, *, region: str) -> str:
    """Convert Supabase direct host to session pooler (IPv4-friendly)."""
    from sqlalchemy.engine.url import make_url

    parsed = make_url(url)
    ref = _project_ref_from_host(parsed.host)
    pooler = parsed.set(
        username=f"postgres.{ref}",
        host=f"aws-0-{region}.pooler.supabase.com",
        port=5432,
    )
    return pooler.render_as_string(hide_password=False)


def _resolve_postgres_url(raw_url: str) -> str:
    """Normalize a Postgres URL and optionally map Direct → Session pooler."""
    url = _normalize_postgres_url(raw_url)
    conn = _load_secrets_toml().get("connections", {}).get("knowball_db", {})
    if conn.get("use_pooler") and "pooler.supabase.com" not in url:
        region = str(conn.get("pooler_region", "us-east-1"))
        return _to_session_pooler_url(url, region=region)
    return url


def get_supabase_db_url() -> str | None:
    """PostgreSQL URL from env or Streamlit secrets; None if not configured."""
    raw = os.environ.get("SUPABASE_DB_URL") or os.environ.get("DATABASE_URL")
    if raw:
        return _resolve_postgres_url(raw)

    conn = _load_secrets_toml().get("connections", {}).get("knowball_db", {})
    url = conn.get("url")
    if not url:
        return None
    return _resolve_postgres_url(str(url))


def supabase_is_configured() -> bool:
    return get_supabase_db_url() is not None
