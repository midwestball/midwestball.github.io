"""Test Supabase connectivity and optionally migrate direct URL to session pooler."""

from __future__ import annotations

import argparse
import sys

from sqlalchemy import create_engine, text
from sqlalchemy.engine.url import make_url

from knowball.config import get_supabase_db_url


def _project_ref(host: str | None) -> str:
    if not host:
        return ""
    return host.removeprefix("db.").split(".", maxsplit=1)[0]


def to_session_pooler_url(url: str, *, region: str = "us-east-1") -> str:
    """Convert a Supabase direct URL to session-mode pooler (IPv4-friendly)."""
    parsed = make_url(url)
    ref = _project_ref(parsed.host)
    pooler = parsed.set(
        username=f"postgres.{ref}",
        host=f"aws-0-{region}.pooler.supabase.com",
        port=5432,
    )
    return pooler.render_as_string(hide_password=False)


def test_url(url: str) -> None:
    engine = create_engine(url)
    try:
        with engine.connect() as conn:
            one = conn.execute(text("SELECT 1")).scalar()
            print(f"Connection OK (SELECT 1 = {one})")
            tables = conn.execute(
                text(
                    "SELECT tablename FROM pg_tables "
                    "WHERE schemaname = 'public' ORDER BY tablename"
                )
            ).fetchall()
            names = [row[0] for row in tables]
            print(f"Public tables: {names if names else '(none — run ingest)'}")
    finally:
        engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Test Supabase DB connection")
    parser.add_argument(
        "--pooler",
        action="store_true",
        help="Use session pooler URL (recommended on IPv4-only networks)",
    )
    parser.add_argument(
        "--region",
        default="us-east-1",
        help="Supabase pooler region when using --pooler (must match dashboard)",
    )
    args = parser.parse_args()

    base_url = get_supabase_db_url()
    if not base_url:
        print("No Supabase URL found in .streamlit/secrets.toml or env.", file=sys.stderr)
        sys.exit(1)

    if args.pooler:
        url = to_session_pooler_url(base_url, region=args.region)
        label = f"session pooler ({args.region})"
    else:
        url = base_url
        label = "direct"
        if "db." in url and ".supabase.co" in url:
            print(
                "Note: Direct Supabase hosts are often IPv6-only. "
                "If this fails, copy the Session pooler URI from Supabase Connect "
                "into secrets.toml, or re-run with --pooler and the correct --region.\n"
            )

    print(f"Testing {label} connection...")
    try:
        test_url(url)
    except Exception as exc:
        message = str(exc.__cause__ or exc).split("\n")[0]
        print(f"FAILED: {message}", file=sys.stderr)
        if "could not translate host name" in message or "Network is unreachable" in message:
            print(
                "\nLikely fix: use the Session pooler URI (IPv4) from Supabase Connect, "
                "not the Direct URI.",
                file=sys.stderr,
            )
        elif "tenant/user" in message or "tenant identifi" in message:
            print(
                "\nLikely fix: confirm the project is fully provisioned, the password is "
                "current, and pooler_region matches Project Settings General Region.",
                file=sys.stderr,
            )
        sys.exit(1)


if __name__ == "__main__":
    main()
