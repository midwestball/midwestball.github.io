import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import projection_ops.weekly as weekly
from projection_ops.weekly import (
    DuplicateWeeklyRun,
    WeeklyLedger,
    WeeklyPlan,
    require_final_tuesday_stage,
)


def settings(tmp_path):
    root = tmp_path.resolve()
    return SimpleNamespace(
        state=root / "state",
        artifacts=root / "artifacts",
        assert_local_write=lambda p: p.resolve()
        if p.resolve().is_relative_to(root)
        else (_ for _ in ()).throw(ValueError("escape")),
    )


def plan():
    return WeeklyPlan(2026, 3, 4, "source-abc", "model-v1")


def test_duplicate_refused_and_failed_upload_resumes_same_snapshot(tmp_path, monkeypatch):
    monkeypatch.setattr(weekly, "SETTINGS", settings(tmp_path))
    ledger = WeeklyLedger()
    p = plan()
    snapshot = tmp_path / "artifacts/public/2026/w4/snap-a"
    snapshot.mkdir(parents=True)
    ledger.begin(p)
    ledger.record_validated(p, "snap-a", snapshot)
    ledger.record_upload_failure(p, "network down", "ops publish --snapshot snap-a")
    assert ledger.resume(p)["snapshotId"] == "snap-a"
    with pytest.raises(DuplicateWeeklyRun):
        ledger.begin(p, snapshot_id="snap-b")


def test_force_rerun_requires_reason_and_new_snapshot(tmp_path, monkeypatch):
    monkeypatch.setattr(weekly, "SETTINGS", settings(tmp_path))
    ledger = WeeklyLedger()
    p = plan()
    ledger.begin(p, snapshot_id="snap-a")
    with pytest.raises(ValueError):
        ledger.begin(p, force_rerun=True, snapshot_id="snap-b")
    with pytest.raises(ValueError):
        ledger.begin(p, force_rerun=True, snapshot_id="snap-a", reason="correction")
    entry = ledger.begin(p, force_rerun=True, snapshot_id="snap-b", reason="corrected source")
    assert entry["reruns"][-1]["reason"] == "corrected source"


def test_tuesday_stage_must_be_final_and_failure_has_recovery(tmp_path, monkeypatch):
    monkeypatch.setattr(weekly, "SETTINGS", settings(tmp_path))
    p = plan()
    with pytest.raises(RuntimeError):
        require_final_tuesday_stage(
            historical_publish_succeeded=True,
            finalized_schedule_confirmed=True,
            trained_through_week=3,
            plan=p,
            remaining_stages=["other"],
        )
    require_final_tuesday_stage(
        historical_publish_succeeded=True,
        finalized_schedule_confirmed=True,
        trained_through_week=3,
        plan=p,
    )
    ledger = WeeklyLedger()
    ledger.begin(p)
    result = ledger.record_stage_failure(p, "boom", "weekly resume --plan abc")
    assert result["tuesdayStatus"] == "stats complete, projections failed"
    assert result["recoveryCommand"] == "weekly resume --plan abc"
