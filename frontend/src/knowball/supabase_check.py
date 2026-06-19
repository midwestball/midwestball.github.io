"""Check Supabase connectivity for tests and setup."""

from __future__ import annotations

from sqlalchemy import create_engine, text

from knowball.config import get_supabase_db_url


def supabase_is_reachable(*, timeout: int = 8) -> bool:
    url = get_supabase_db_url()
    if not url:
        return False
    engine = create_engine(url, connect_args={"connect_timeout": timeout})
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
    finally:
        engine.dispose()
