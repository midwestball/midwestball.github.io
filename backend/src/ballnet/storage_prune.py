"""Delete orphaned / stale Supabase Storage objects to reclaim free-tier quota."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Iterable

from ballnet.storage_upload import DEFAULT_BUCKET, active_dataset_prefix, supabase_client

LEGACY_ROOT_TOP_LEVEL = ("pages", "league", "leaderboards", "highlights", "dists")
WEEK_DIR_RE = re.compile(r"^w(\d+)$")
WEEK_FILE_RE = re.compile(r"^w(\d+)(?:\.epa)?\.json$")


@dataclass
class PruneResult:
    deleted: int = 0
    failed: int = 0
    bytes: int = 0
    errors: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)

    def merge(self, other: "PruneResult") -> "PruneResult":
        return PruneResult(
            deleted=self.deleted + other.deleted,
            failed=self.failed + other.failed,
            bytes=self.bytes + other.bytes,
            errors=(self.errors + other.errors)[:40],
            skipped=(self.skipped + other.skipped)[:40],
        )


def _list_page(client, bucket: str, prefix: str, *, offset: int = 0, limit: int = 1000):
    return client.storage.from_(bucket).list(prefix, {"limit": limit, "offset": offset})


def list_all(client, bucket: str, prefix: str) -> list[dict]:
    out: list[dict] = []
    offset = 0
    while True:
        chunk = _list_page(client, bucket, prefix, offset=offset) or []
        if not chunk:
            break
        out.extend(chunk)
        if len(chunk) < 1000:
            break
        offset += 1000
    return out


def iter_object_paths(
    client,
    bucket: str,
    prefix: str,
    *,
    max_depth: int = 16,
) -> Iterable[tuple[str, int]]:
    """Yield (object_path, size_bytes) under prefix. Folders have no id/size."""
    stack = [(prefix.rstrip("/"), 0)]
    seen: set[str] = set()
    while stack:
        current, depth = stack.pop()
        if current in seen:
            continue
        seen.add(current)
        for item in list_all(client, bucket, current):
            name = item.get("name") or ""
            meta = item.get("metadata") or {}
            child = f"{current}/{name}" if current else name
            if item.get("id") and meta.get("size") is not None:
                yield child, int(meta["size"])
            elif depth < max_depth:
                stack.append((child, depth + 1))


def delete_paths(
    client,
    paths: list[str],
    *,
    bucket: str = DEFAULT_BUCKET,
    dry_run: bool = True,
    chunk_size: int = 100,
) -> PruneResult:
    result = PruneResult()
    if not paths:
        return result
    # Size hints already summed by callers when available; still delete in chunks.
    if dry_run:
        result.deleted = len(paths)
        return result
    api = client.storage.from_(bucket)
    for i in range(0, len(paths), chunk_size):
        chunk = paths[i : i + chunk_size]
        try:
            api.remove(chunk)
            result.deleted += len(chunk)
        except Exception as exc:  # noqa: BLE001
            result.failed += len(chunk)
            result.errors.append(f"remove {chunk[0]}…: {type(exc).__name__}: {exc}")
    return result


def collect_prefix(
    client,
    prefix: str,
    *,
    bucket: str = DEFAULT_BUCKET,
) -> tuple[list[str], int]:
    paths: list[str] = []
    total = 0
    for path, size in iter_object_paths(client, bucket, prefix):
        paths.append(path)
        total += size
    return paths, total


def prune_legacy_root(
    *,
    bucket: str = DEFAULT_BUCKET,
    dry_run: bool = True,
    client=None,
) -> PruneResult:
    """Delete pre-migration trees at the bucket root (site reads migrations/)."""
    client = client or supabase_client()
    prefix = active_dataset_prefix(client, bucket)
    if not prefix:
        return PruneResult(skipped=["active dataset is legacy root; refusing legacy prune"])
    paths: list[str] = []
    total = 0
    for top in LEGACY_ROOT_TOP_LEVEL:
        for path, size in iter_object_paths(client, bucket, top):
            if path.startswith("migrations/"):
                continue
            paths.append(path)
            total += size
    result = delete_paths(client, paths, bucket=bucket, dry_run=dry_run)
    result.bytes = total
    return result


def prune_projections_staging(
    *,
    bucket: str = DEFAULT_BUCKET,
    dry_run: bool = True,
    client=None,
) -> PruneResult:
    client = client or supabase_client()
    paths, total = collect_prefix(client, "projections-staging", bucket=bucket)
    result = delete_paths(client, paths, bucket=bucket, dry_run=dry_run)
    result.bytes = total
    return result


def _read_json_object(client, bucket: str, path: str) -> dict | None:
    try:
        raw = client.storage.from_(bucket).download(path)
    except Exception:  # noqa: BLE001
        return None
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def prune_old_projections(
    *,
    bucket: str = DEFAULT_BUCKET,
    keep_weeks: int = 2,
    dry_run: bool = True,
    client=None,
) -> PruneResult:
    """Keep the newest ``keep_weeks`` production projection weeks; delete older."""
    client = client or supabase_client()
    pointer = _read_json_object(client, bucket, "projections/current.json")
    current_week: int | None = None
    if pointer and isinstance(pointer.get("week"), int):
        current_week = int(pointer["week"])
    weeks = []
    for item in list_all(client, bucket, "projections/2026"):
        name = item.get("name") or ""
        m = WEEK_DIR_RE.match(name)
        if m:
            weeks.append(int(m.group(1)))
    weeks = sorted(set(weeks), reverse=True)
    keep: set[int] = set(weeks[: max(1, keep_weeks)])
    if current_week is not None:
        keep.add(current_week)
    paths: list[str] = []
    total = 0
    for week in weeks:
        if week in keep:
            continue
        found, nbytes = collect_prefix(client, f"projections/2026/w{week}", bucket=bucket)
        paths.extend(found)
        total += nbytes
    result = delete_paths(client, paths, bucket=bucket, dry_run=dry_run)
    result.bytes = total
    result.skipped.append(f"kept projection weeks: {sorted(keep)}")
    return result


def _kept_week_for_season(seasons_doc: dict | None, current_doc: dict | None, season: int) -> int | None:
    if current_doc and current_doc.get("season") == season and isinstance(current_doc.get("asOfWeek"), int):
        return int(current_doc["asOfWeek"])
    if seasons_doc and isinstance(seasons_doc.get("seasons"), list):
        for row in seasons_doc["seasons"]:
            if isinstance(row, dict) and row.get("season") == season and isinstance(row.get("asOfWeek"), int):
                return int(row["asOfWeek"])
    return None


def prune_stale_season_weeks(
    *,
    season: int,
    bucket: str = DEFAULT_BUCKET,
    dry_run: bool = True,
    client=None,
    keep_week: int | None = None,
) -> PruneResult:
    """Delete non-kept ``pages/league/leaderboards`` weeks for one season under the active dataset.

    Highlight / play / league_weekly history is retained (week browser).
    """
    client = client or supabase_client()
    prefix = active_dataset_prefix(client, bucket)
    base = f"{prefix}/" if prefix else ""
    if keep_week is None:
        seasons_doc = _read_json_object(client, bucket, f"{base}index/seasons.json")
        current_doc = _read_json_object(client, bucket, f"{base}index/current.json")
        keep_week = _kept_week_for_season(seasons_doc, current_doc, season)
    if keep_week is None:
        return PruneResult(skipped=[f"could not resolve keep week for season {season}"])

    paths: list[str] = []
    total = 0
    for kind in ("pages", "league", "leaderboards"):
        season_prefix = f"{base}{kind}/{season}"
        for item in list_all(client, bucket, season_prefix):
            name = item.get("name") or ""
            m = WEEK_DIR_RE.match(name)
            if not m:
                continue
            week = int(m.group(1))
            if week == keep_week:
                continue
            found, nbytes = collect_prefix(client, f"{season_prefix}/w{week}", bucket=bucket)
            paths.extend(found)
            total += nbytes
    result = delete_paths(client, paths, bucket=bucket, dry_run=dry_run)
    result.bytes = total
    result.skipped.append(f"kept {base}{{pages,league,leaderboards}}/{season}/w{keep_week}")
    return result
