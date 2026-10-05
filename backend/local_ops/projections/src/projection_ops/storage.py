"""Immutable-first Supabase Storage publication with pointer-last commit."""

from __future__ import annotations
from pathlib import Path
from typing import Callable, Protocol
from urllib.request import Request, urlopen
import json, os, time
from .contracts import canonical_bytes, sha256_bytes, validate_document, validate_snapshot
from .pipeline import pointer_for


class StorageBackend(Protocol):
    def upload(self, path: str, data: bytes, *, cache_control: str, upsert: bool) -> None: ...
    def download(self, path: str) -> bytes: ...


def _safe_prefix(prefix: str) -> str:
    value = prefix.strip("/")
    if not value or "/" in value or "\\" in value or value in {".", ".."}:
        raise ValueError("storage prefix must be one safe namespace segment")
    return value


# Measured against the real bucket: re-uploading identical bytes is visible at once,
# but when the pointer bytes actually change the Storage edge can serve the previous
# object for ~45s. A shorter window reports a failed commit for a commit that
# succeeded, which is how a duplicate retrain gets triggered.
POINTER_VERIFY_TIMEOUT_SECONDS = 180


def _read_matches(
    backend: "StorageBackend",
    path: str,
    expected: bytes,
    *,
    timeout: float | None = None,
    interval: float = 3.0,
) -> bool:
    """Confirm a just-written pointer, tolerating the edge's read-after-write lag.

    Poll until the pointer reads back or the timeout expires. Callers must treat a
    timeout as a failed commit, because a pointer that never verifies is unusable
    as a commit record even if the upload itself returned success.
    """
    limit = POINTER_VERIFY_TIMEOUT_SECONDS if timeout is None else timeout
    deadline = time.monotonic() + limit
    while True:
        try:
            if backend.download(path) == expected:
                return True
        except Exception:
            pass
        if time.monotonic() >= deadline:
            return False
        time.sleep(interval)


class SupabaseBackend:
    def __init__(self, bucket: str):
        from supabase import create_client
        from .secrets import load_backend_credentials

        load_backend_credentials()
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
        if not url or not key:
            raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required")
        self.bucket = create_client(url, key).storage.from_(bucket)

    def upload(self, path, data, *, cache_control, upsert):
        self.bucket.upload(
            path,
            data,
            {
                "content-type": "application/json",
                "cache-control": cache_control,
                "upsert": "true" if upsert else "false",
            },
        )

    def download(self, path):
        return bytes(self.bucket.download(path))


def publish_snapshot(
    directory: Path, backend: StorageBackend, *, dry_run: bool = False, prefix: str = "projections"
) -> dict:
    prefix = _safe_prefix(prefix)
    summary = validate_snapshot(directory)
    index = json.loads((directory / "index.json").read_text())
    manifest = json.loads((directory / "manifest.json").read_text())
    base = f"{prefix}/{index['season']}/w{index['week']}/{index['snapshotId']}"
    ordered = [x["path"] for x in manifest["files"] if x["path"].startswith("entities/")] + [
        "index.json",
        "manifest.json",
    ]
    uploads = []
    pointer_path = f"{prefix}/current.json"
    old_pointer: bytes | None = None
    if not dry_run:
        try:
            old_pointer = backend.download(pointer_path)
        except Exception:
            old_pointer = None
    for rel in ordered:
        remote = f"{base}/{rel}"
        data = (directory / rel).read_bytes()
        state = "planned"
        if not dry_run:
            try:
                existing = backend.download(remote)
            except Exception:
                existing = None
            if existing is not None:
                if existing != data:
                    raise RuntimeError(f"immutable remote collision: {remote}")
                state = "verified_existing"
            else:
                backend.upload(remote, data, cache_control="31536000", upsert=False)
                state = "uploaded"
        uploads.append(
            {"path": remote, "bytes": len(data), "sha256": sha256_bytes(data), "state": state}
        )
    if not dry_run:
        # Full remote byte verification is the publication gate.
        for item in uploads:
            got = backend.download(item["path"])
            if len(got) != item["bytes"] or sha256_bytes(got) != item["sha256"]:
                raise RuntimeError(f"remote verification failed: {item['path']}")
            validate_document(json.loads(got))
    pointer = pointer_for(directory)
    if prefix != "projections":
        pointer["indexPath"] = pointer["indexPath"].replace("projections/", prefix + "/", 1)
        pointer["manifestPath"] = pointer["manifestPath"].replace("projections/", prefix + "/", 1)
    pointer_data = canonical_bytes(pointer)
    if not dry_run:
        try:
            current_pointer = backend.download(pointer_path)
        except Exception:
            current_pointer = None
        if current_pointer != old_pointer:
            raise RuntimeError(f"remote pointer changed during publication: {pointer_path}")
        backend.upload(pointer_path, pointer_data, cache_control="0", upsert=True)
        # The pointer is the commit record, so a read-after-write miss is retried
        # briefly: a Storage edge can briefly serve the previous bytes.
        if not _read_matches(backend, pointer_path, pointer_data):
            raise RuntimeError(f"remote pointer verification failed: {pointer_path}")
    return summary | {
        "dryRun": dry_run,
        "uploads": uploads,
        "pointerPath": pointer_path,
        "pointerSha256": sha256_bytes(pointer_data),
    }


def verify_remote_snapshot(
    backend: StorageBackend, pointer: dict, *, prefix: str = "projections"
) -> dict:
    """Download and validate the complete revision referenced by a pointer."""
    prefix = _safe_prefix(prefix)
    expected_prefix = f"{prefix}/"
    for key in ("indexPath", "manifestPath"):
        path = pointer.get(key)
        if (
            not isinstance(path, str)
            or not path.startswith(expected_prefix)
            or ".." in Path(path).parts
        ):
            raise ValueError(f"unsafe {key}")
    index_bytes = backend.download(pointer["indexPath"])
    manifest_bytes = backend.download(pointer["manifestPath"])
    index = json.loads(index_bytes)
    manifest = json.loads(manifest_bytes)
    validate_document(index)
    validate_document(manifest)
    if index.get("snapshotId") != pointer.get("snapshotId") or manifest.get(
        "snapshotId"
    ) != pointer.get("snapshotId"):
        raise RuntimeError("remote snapshot ID mismatch")
    base = pointer["indexPath"].rsplit("/", 1)[0]
    checked = []
    inventory = {item["path"]: item for item in manifest.get("files", [])}
    if "index.json" not in inventory:
        raise RuntimeError("remote manifest does not inventory index.json")
    for rel, item in inventory.items():
        if rel.startswith("/") or ".." in Path(rel).parts:
            raise RuntimeError(f"unsafe manifest path: {rel}")
        path = f"{base}/{rel}"
        content = backend.download(path)
        if len(content) != item["bytes"] or sha256_bytes(content) != item["sha256"]:
            raise RuntimeError(f"remote verification failed: {path}")
        validate_document(json.loads(content))
        checked.append(path)
    # manifest cannot self-inventory, but its downloaded bytes and document are checked above.
    checked.append(pointer["manifestPath"])
    return {"snapshotId": pointer["snapshotId"], "objects": checked, "objectCount": len(checked)}


def publish_staging_snapshot(
    directory: Path,
    backend: StorageBackend,
    *,
    prefix: str = "projections-staging",
    dry_run: bool = False,
) -> dict:
    """Publish to a non-production namespace. Production needs publish_snapshot explicitly."""
    prefix = _safe_prefix(prefix)
    if prefix == "projections":
        raise ValueError("staging publish cannot use the production prefix")
    result = publish_snapshot(directory, backend, dry_run=dry_run, prefix=prefix)
    if not dry_run:
        pointer = json.loads(backend.download(result["pointerPath"]))
        result["remoteVerification"] = verify_remote_snapshot(backend, pointer, prefix=prefix)
    return result


def set_staging_pointer(
    backend: StorageBackend, pointer: dict, *, prefix: str = "projections-staging"
) -> dict:
    """Move only a staging pointer after full remote validation."""
    prefix = _safe_prefix(prefix)
    if prefix == "projections":
        raise ValueError("staging helper refuses production current")
    verification = verify_remote_snapshot(backend, pointer, prefix=prefix)
    data = canonical_bytes(pointer)
    path = f"{prefix}/current.json"
    backend.upload(path, data, cache_control="0", upsert=True)
    if not _read_matches(backend, path, data):
        raise RuntimeError("staging pointer verification failed")
    return {
        "pointerPath": path,
        "pointerSha256": sha256_bytes(data),
        "remoteVerification": verification,
    }


def rollback_staging_pointer(
    backend: StorageBackend, pointer: dict, *, prefix: str = "projections-staging"
) -> dict:
    return set_staging_pointer(backend, pointer, prefix=prefix)


def rollback_production_pointer(
    backend: StorageBackend, pointer: dict, *, confirm_production: bool = False
) -> dict:
    """Explicit, separate production rollback path with a deliberate confirmation gate."""
    if not confirm_production:
        raise RuntimeError("production rollback requires confirm_production=True")
    verification = verify_remote_snapshot(backend, pointer, prefix="projections")
    data = canonical_bytes(pointer)
    path = "projections/current.json"
    backend.upload(path, data, cache_control="0", upsert=True)
    if not _read_matches(backend, path, data):
        raise RuntimeError("production rollback pointer verification failed")
    return {
        "pointerPath": path,
        "pointerSha256": sha256_bytes(data),
        "remoteVerification": verification,
    }


def anonymous_get_json(
    url: str, *, timeout: float = 15.0, get: Callable[[str, float], bytes] | None = None
) -> dict:
    """Fetch public JSON without auth headers. An injected getter keeps tests offline."""
    if get is None:

        def get(target: str, seconds: float) -> bytes:
            request = Request(target, headers={"Accept": "application/json"}, method="GET")
            with urlopen(request, timeout=seconds) as response:
                if response.status != 200:
                    raise RuntimeError(f"anonymous GET failed: HTTP {response.status}")
                return response.read()

    value = json.loads(get(url, timeout))
    if not isinstance(value, dict):
        raise RuntimeError("anonymous GET did not return a JSON object")
    validate_document(value)
    return value


def verify_anonymous_snapshot(
    public_base_url: str, pointer: dict, *, prefix: str = "projections-staging"
) -> dict:
    """Verify anonymous public GET for pointer, index, manifest, and every entity."""
    prefix = _safe_prefix(prefix)
    base = public_base_url.rstrip("/")
    current = anonymous_get_json(f"{base}/{prefix}/current.json")
    if current != pointer:
        raise RuntimeError("anonymous pointer differs from authenticated pointer")
    index = anonymous_get_json(f"{base}/{pointer['indexPath']}")
    manifest = anonymous_get_json(f"{base}/{pointer['manifestPath']}")
    if index.get("snapshotId") != pointer.get("snapshotId") or manifest.get(
        "snapshotId"
    ) != pointer.get("snapshotId"):
        raise RuntimeError("anonymous snapshot linkage mismatch")
    revision = pointer["indexPath"].rsplit("/", 1)[0]
    checked = [f"{prefix}/current.json", pointer["indexPath"], pointer["manifestPath"]]
    for item in manifest.get("files", []):
        rel = item["path"]
        if rel == "index.json":
            continue
        doc = anonymous_get_json(f"{base}/{revision}/{rel}")
        if doc.get("snapshotId") != pointer.get("snapshotId"):
            raise RuntimeError(f"anonymous object linkage mismatch: {rel}")
        checked.append(f"{revision}/{rel}")
    return {
        "snapshotId": pointer["snapshotId"],
        "classes": ["pointer", "index", "manifest", "entity"],
        "objectCount": len(checked),
        "paths": checked,
    }
