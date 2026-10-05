"""Protected-set retention planning. Dry-run is always the default."""

from __future__ import annotations
from pathlib import Path
from datetime import datetime, timezone
import json, shutil
from .config import SETTINGS
from .contracts import canonical_bytes, sha256_bytes


def _size(path: Path) -> tuple[int, int]:
    files = [p for p in path.rglob("*") if p.is_file()]
    return len(files), sum(p.stat().st_size for p in files)


def plan_retention(*, keep_public: int = 6, keep_draws: int = 6) -> dict:
    if any((SETTINGS.state / "locks").glob("*")):
        raise RuntimeError("active run lock; pruning refused")
    pointer_path = SETTINGS.state / "current.json"
    previous_path = SETTINGS.state / "previous_known_good.json"
    protected = {}
    for p, reason in ((pointer_path, "current pointer"), (previous_path, "previous known-good")):
        if p.exists():
            protected[json.loads(p.read_text())["snapshotId"]] = reason
    snapshots = []
    public = SETTINGS.artifacts / "public"
    for manifest in public.glob("*/w*/*/manifest.json"):
        sid = manifest.parent.name
        count, size = _size(manifest.parent)
        snapshots.append({"id": sid, "path": str(manifest.parent), "files": count, "bytes": size})
    snapshots.sort(key=lambda x: x["id"], reverse=True)
    for x in snapshots[:keep_public]:
        protected.setdefault(x["id"], "newest public retention window")
    candidates = [x for x in snapshots if x["id"] not in protected]
    report = {
        "createdAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "scope": "all",
        "dryRun": True,
        "policy": {"keepPublic": keep_public, "keepDraws": keep_draws},
        "pointerSha256": sha256_bytes(pointer_path.read_bytes()) if pointer_path.exists() else None,
        "protected": [{"id": k, "reason": v} for k, v in sorted(protected.items())],
        "candidates": candidates,
        "expectedFreedBytes": sum(x["bytes"] for x in candidates),
    }
    data = canonical_bytes(report)
    report["reportSha256"] = sha256_bytes(data)
    out = SETTINGS.state / "retention"
    out.mkdir(parents=True, exist_ok=True)
    (out / f"dry-run-{report['reportSha256'][:12]}.json").write_bytes(canonical_bytes(report))
    return report


def _report_hash(report: dict) -> str:
    unsigned = {k: v for k, v in report.items() if k != "reportSha256"}
    return sha256_bytes(canonical_bytes(unsigned))


def execute_retention(report_hash: str) -> dict:
    matches = list((SETTINGS.state / "retention").glob(f"dry-run-{report_hash[:12]}.json"))
    if len(matches) != 1:
        raise ValueError("saved dry-run report not found")
    saved = json.loads(matches[0].read_text())
    if saved.get("reportSha256") != _report_hash(saved) or not saved["reportSha256"].startswith(
        report_hash
    ):
        raise RuntimeError("dry-run report integrity check failed")
    policy = saved.get("policy", {})
    fresh = plan_retention(
        keep_public=int(policy.get("keepPublic", 6)), keep_draws=int(policy.get("keepDraws", 6))
    )
    for field in ("pointerSha256", "protected", "candidates"):
        if fresh[field] != saved[field]:
            raise RuntimeError(f"retention {field} changed; execute refused")
    if any((SETTINGS.state / "locks").glob("*")):
        raise RuntimeError("active run lock; execute refused")
    rehearsal = verify_retention_rehearsal(saved)
    deleted = []
    for item in saved["candidates"]:
        path = Path(item["path"])
        SETTINGS.assert_local_write(path)
        if not path.is_dir() or path.name != item["id"] or not (path / "manifest.json").is_file():
            raise RuntimeError(f"candidate changed or missing: {item['id']}")
        evidence = SETTINGS.state / "retention" / f"backup-{item['id']}.json"
        if not evidence.exists():
            raise RuntimeError(f"missing backup evidence for {item['id']}")
        proof = json.loads(evidence.read_text())
        if (
            proof.get("snapshotId") != item["id"]
            or proof.get("verified") is not True
            or not proof.get("backupIdentifier")
        ):
            raise RuntimeError(f"invalid backup evidence for {item['id']}")
        shutil.rmtree(path)
        deleted.append(item)
    audit = {
        "executedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "dryRunReportHash": saved["reportSha256"],
        "deleted": deleted,
        "protected": saved["protected"],
        "freedBytes": sum(x["bytes"] for x in deleted),
        "rehearsal": rehearsal,
    }
    (SETTINGS.state / "retention" / f"execute-{saved['reportSha256'][:12]}.json").write_bytes(
        canonical_bytes(audit)
    )
    return audit


def verify_retention_rehearsal(report: dict, *, minimum_public_window: int = 4) -> dict:
    """Fail closed unless a proposed prune preserves rollback and the public window."""
    if minimum_public_window < 4:
        raise ValueError("public retention minimum is four")
    protected = {x["id"]: x["reason"] for x in report.get("protected", [])}
    candidate_ids = {x["id"] for x in report.get("candidates", [])}
    if protected.keys() & candidate_ids:
        raise RuntimeError("protected snapshot appears in candidates")
    required_reasons = {"current pointer", "previous known-good"}
    present_reasons = set(protected.values())
    pointer_files = [SETTINGS.state / "current.json", SETTINGS.state / "previous_known_good.json"]
    for path, reason in zip(pointer_files, ("current pointer", "previous known-good")):
        if path.exists():
            sid = json.loads(path.read_text())["snapshotId"]
            if protected.get(sid) != reason:
                raise RuntimeError(f"{reason} is not protected")
            matches = list((SETTINGS.artifacts / "public").glob(f"*/w*/{sid}"))
            if len(matches) != 1:
                raise RuntimeError(f"protected snapshot is missing: {sid}")
    keep = int(report.get("policy", {}).get("keepPublic", 0))
    if keep < minimum_public_window:
        raise RuntimeError("public retention window is below safety minimum")
    return {
        "passed": True,
        "protectedIds": sorted(protected),
        "candidateIds": sorted(candidate_ids),
        "keepPublic": keep,
        "rollbackReasonsPresent": sorted(required_reasons & present_reasons),
    }
