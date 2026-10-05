"""Durable once-per-plan weekly execution ledger and Tuesday-stage safety gates."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import hashlib
import json
import os
import tempfile

from .config import SETTINGS
from .contracts import canonical_bytes


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _snapshot_digest(path: Path) -> str:
    files = sorted(p for p in path.rglob("*") if p.is_file())
    digest = hashlib.sha256()
    for item in files:
        digest.update(item.relative_to(path).as_posix().encode())
        digest.update(b"\0")
        digest.update(hashlib.sha256(item.read_bytes()).digest())
    return digest.hexdigest()


@dataclass(frozen=True)
class WeeklyPlan:
    season: int
    finalized_week: int
    target_week: int
    source_fingerprint: str
    model_version: str
    schema_version: int = 1

    def __post_init__(self) -> None:
        if self.season < 2000:
            raise ValueError("invalid season")
        if not 0 <= self.finalized_week <= 22:
            raise ValueError("invalid finalized week")
        if not 1 <= self.target_week <= 22:
            raise ValueError("invalid target week")
        for value, name in (
            (self.source_fingerprint, "source fingerprint"),
            (self.model_version, "model version"),
        ):
            if not value or not value.strip():
                raise ValueError(f"{name} is required")

    @property
    def key(self) -> str:
        return hashlib.sha256(canonical_bytes(asdict(self))).hexdigest()


class DuplicateWeeklyRun(RuntimeError):
    """The expensive routine plan already has a ledger entry."""


class WeeklyLedger:
    """Small atomic JSON ledger. It stores identifiers, never credentials or input data."""

    def __init__(self, path: Path | None = None):
        self.path = path or SETTINGS.state / "weekly_runs.json"
        SETTINGS.assert_local_write(self.path)

    def _read(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"version": 1, "runs": {}}
        value = json.loads(self.path.read_text(encoding="utf-8"))
        if value.get("version") != 1 or not isinstance(value.get("runs"), dict):
            raise RuntimeError("invalid weekly ledger")
        return value

    def _write(self, value: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        SETTINGS.assert_local_write(self.path)
        fd, raw = tempfile.mkstemp(prefix=".weekly-runs-", suffix=".tmp", dir=self.path.parent)
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(canonical_bytes(value))
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(raw, self.path)
        finally:
            if os.path.exists(raw):
                os.unlink(raw)

    def get(self, plan: WeeklyPlan) -> dict[str, Any] | None:
        item = self._read()["runs"].get(plan.key)
        return dict(item) if item else None

    def begin(
        self,
        plan: WeeklyPlan,
        *,
        snapshot_id: str | None = None,
        force_rerun: bool = False,
        reason: str | None = None,
    ) -> dict[str, Any]:
        data = self._read()
        prior = data["runs"].get(plan.key)
        if prior and not force_rerun:
            raise DuplicateWeeklyRun(
                f"weekly plan already exists ({prior['status']}); resume snapshot "
                f"{prior.get('snapshotId') or '<not-yet-validated>'} instead of retraining"
            )
        if force_rerun:
            if not reason or not reason.strip():
                raise ValueError("force rerun requires a non-empty reason")
            if not prior:
                raise ValueError("force rerun requires an existing plan entry")
            if not snapshot_id or snapshot_id == prior.get("snapshotId"):
                raise ValueError("force rerun requires a new snapshot ID")
            history = list(prior.get("reruns", []))
            history.append(
                {
                    "previousSnapshotId": prior.get("snapshotId"),
                    "reason": reason.strip(),
                    "at": _now(),
                }
            )
        else:
            history = []
        entry = {
            "plan": asdict(plan),
            "planKey": plan.key,
            "status": "building",
            "snapshotId": snapshot_id,
            "startedAt": _now(),
            "updatedAt": _now(),
            "reruns": history,
        }
        data["runs"][plan.key] = entry
        self._write(data)
        return dict(entry)

    def record_validated(
        self, plan: WeeklyPlan, snapshot_id: str, snapshot_path: Path
    ) -> dict[str, Any]:
        if not snapshot_id:
            raise ValueError("snapshot ID is required")
        path = SETTINGS.assert_local_write(snapshot_path)
        if not path.is_dir():
            raise ValueError("validated snapshot directory does not exist")
        return self._update(
            plan,
            status="validated",
            snapshotId=snapshot_id,
            snapshotPath=str(path),
            snapshotDigest=_snapshot_digest(path),
        )

    def record_upload_failure(
        self, plan: WeeklyPlan, error: BaseException | str, recovery_command: str
    ) -> dict[str, Any]:
        current = self._require(plan)
        if not current.get("snapshotId") or current.get("status") not in {
            "validated",
            "upload_failed",
        }:
            raise RuntimeError("upload failure may only be recorded for a validated snapshot")
        if not recovery_command.strip():
            raise ValueError("exact recovery command is required")
        return self._update(
            plan,
            status="upload_failed",
            failure=str(error),
            tuesdayStatus="stats complete, projections failed",
            recoveryCommand=recovery_command.strip(),
        )

    def resume(self, plan: WeeklyPlan) -> dict[str, Any]:
        entry = self._require(plan)
        if entry.get("status") not in {"validated", "upload_failed"} or not entry.get("snapshotId"):
            raise RuntimeError("no validated snapshot is available to resume")
        path = Path(entry.get("snapshotPath", ""))
        SETTINGS.assert_local_write(path)
        if not path.is_dir():
            raise RuntimeError("recorded validated snapshot is missing")
        if _snapshot_digest(path) != entry.get("snapshotDigest"):
            raise RuntimeError("validated snapshot changed; resume refused")
        return entry

    def record_success(
        self, plan: WeeklyPlan, *, pointer_path: str, anonymous_verified: bool
    ) -> dict[str, Any]:
        entry = self._require(plan)
        if entry.get("status") not in {"validated", "upload_failed"}:
            raise RuntimeError("only a validated snapshot can succeed")
        if not anonymous_verified:
            raise RuntimeError("anonymous GET verification is required")
        return self._update(
            plan,
            status="complete",
            pointerPath=pointer_path,
            anonymousVerified=True,
            completedAt=_now(),
        )

    def record_stage_failure(
        self, plan: WeeklyPlan, error: BaseException | str, recovery_command: str
    ) -> dict[str, Any]:
        if not recovery_command.strip():
            raise ValueError("exact recovery command is required")
        return self._update(
            plan,
            status="failed",
            failure=str(error),
            tuesdayStatus="stats complete, projections failed",
            recoveryCommand=recovery_command.strip(),
        )

    def _require(self, plan: WeeklyPlan) -> dict[str, Any]:
        item = self._read()["runs"].get(plan.key)
        if not item:
            raise KeyError("weekly plan is not in the ledger")
        return item

    def _update(self, plan: WeeklyPlan, **changes: Any) -> dict[str, Any]:
        data = self._read()
        if plan.key not in data["runs"]:
            raise KeyError("weekly plan is not in the ledger")
        data["runs"][plan.key].update(changes)
        data["runs"][plan.key]["updatedAt"] = _now()
        self._write(data)
        return dict(data["runs"][plan.key])


def require_final_tuesday_stage(
    *,
    historical_publish_succeeded: bool,
    finalized_schedule_confirmed: bool,
    trained_through_week: int,
    plan: WeeklyPlan,
    remaining_stages: list[str] | tuple[str, ...] = (),
) -> None:
    """Fail closed before expensive work; retention/ledger closeout are substeps, not stages."""
    if not historical_publish_succeeded:
        raise RuntimeError("historical stats publication has not succeeded")
    if not finalized_schedule_confirmed:
        raise RuntimeError("completed week is not confirmed final")
    if trained_through_week != plan.finalized_week:
        raise RuntimeError("trainedThrough must equal the finalized week")
    if remaining_stages:
        raise RuntimeError(
            f"projections must be the final Tuesday stage; remaining: {', '.join(remaining_stages)}"
        )
