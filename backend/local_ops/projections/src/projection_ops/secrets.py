"""Backend-only credential loading. Values are never logged or serialized."""

from __future__ import annotations
from pathlib import Path
import os
from dotenv import dotenv_values
from .config import SETTINGS


def load_backend_credentials() -> None:
    path = SETTINGS.repo_root / "backend" / ".env"
    if not path.exists():
        raise RuntimeError(f"backend credential file is missing: {path}")
    values = dotenv_values(path)
    aliases = {
        "SUPABASE_URL": ("SUPABASE_URL", "supabase_url"),
        "SUPABASE_SERVICE_ROLE_KEY": ("SUPABASE_SERVICE_ROLE_KEY", "supabase_service_role_key"),
    }
    for canonical, names in aliases.items():
        if os.environ.get(canonical):
            continue
        value = next((values.get(name) for name in names if values.get(name)), None)
        if value:
            os.environ[canonical] = str(value)
    missing = [name for name in aliases if not os.environ.get(name)]
    if missing:
        raise RuntimeError("missing backend credential variables: " + ", ".join(missing))
