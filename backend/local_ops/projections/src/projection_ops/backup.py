"""Secret-safe source export and verification."""

from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
import hashlib, json, platform, tarfile, tempfile
from .config import SETTINGS
from .contracts import canonical_bytes, sha256_file

EXCLUDED = {".env", ".venv", "cache", "__pycache__", ".pytest_cache"}
INCLUDED = (
    "src",
    "tests",
    "contract",
    "README.md",
    "RUNBOOK.md",
    "BOUNDARIES.md",
    "projections_plan.md",
    "pyproject.toml",
    "uv.lock",
    ".python-version",
    ".env.example",
)


def _files():
    for name in INCLUDED:
        p = SETTINGS.root / name
        if not p.exists():
            continue
        candidates = [p] if p.is_file() else p.rglob("*")
        for f in candidates:
            if f.is_file() and not any(
                part in EXCLUDED or part.endswith((".pyc", ".pyo")) for part in f.parts
            ):
                yield f


def source_tree_hash() -> str:
    h = hashlib.sha256()
    for f in sorted(_files()):
        rel = f.relative_to(SETTINGS.root).as_posix()
        h.update(rel.encode() + b"\0" + f.read_bytes() + b"\0")
    return h.hexdigest()


def create_export() -> Path:
    out = SETTINGS.backup_dir()
    out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    archive = out / f"projection-ops-{stamp}.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        for f in _files():
            tar.add(
                f,
                arcname=(Path("projections") / f.relative_to(SETTINGS.root)).as_posix(),
                recursive=False,
            )
    manifest = {
        "createdAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "archive": archive.name,
        "archiveSha256": sha256_file(archive),
        "sourceTreeSha256": source_tree_hash(),
        "lockSha256": sha256_file(SETTINGS.root / "uv.lock")
        if (SETTINGS.root / "uv.lock").exists()
        else None,
        "schemaSha256": sha256_file(SETTINGS.local_schema),
        "python": platform.python_version(),
        "exclusions": [
            ".env",
            "credentials",
            ".venv",
            "cache/raw nflverse",
            "__pycache__",
            "large models and draws",
        ],
    }
    archive.with_suffix(archive.suffix + ".manifest.json").write_bytes(canonical_bytes(manifest))
    return archive


def verify_export(archive: Path) -> dict:
    side = archive.with_suffix(archive.suffix + ".manifest.json")
    doc = json.loads(side.read_text())
    if sha256_file(archive) != doc["archiveSha256"]:
        raise ValueError("backup archive hash mismatch")
    with tarfile.open(archive, "r:gz") as tar:
        names = tar.getnames()
        if any(".env" in Path(n).parts or ".." in Path(n).parts for n in names):
            raise ValueError("unsafe backup content")
    return doc


def restore_export(archive: Path, destination: Path) -> None:
    verify_export(archive)
    if destination.exists() and any(destination.iterdir()):
        raise ValueError("restore destination must be empty")
    destination.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive, "r:gz") as tar:
        tar.extractall(destination, filter="data")
