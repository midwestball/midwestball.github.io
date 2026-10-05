import json
import types
import pytest
from projection_ops import tuesday as T
from projection_ops.tuesday import Stage, TuesdayStageError, ProjectionsLastViolation


@pytest.fixture(autouse=True)
def isolated_state(tmp_path, monkeypatch):
    """Reports must land in tmp, never in the real state directory."""
    from projection_ops.config import Settings

    fake = Settings.discover().__class__(
        root=tmp_path,
        repo_root=tmp_path,
        cache=tmp_path / "cache",
        artifacts=tmp_path / "artifacts",
        state=tmp_path / "state",
        tracked_schema=tmp_path / "s.json",
        local_schema=tmp_path / "l.json",
    )
    monkeypatch.setattr(T, "SETTINGS", fake)
    monkeypatch.setattr(T, "BACKEND_DIR", tmp_path / "backend")
    return tmp_path


def _hist_and_proj():
    return [
        Stage("fetch", ("fetch",)),
        Stage("upload-storage", ("upload-storage",)),
        Stage("projections", ("python", "-m", "projection_ops.cli", "weekly"), is_projections=True),
    ]


def test_projections_must_be_the_final_stage():
    T.assert_projections_last(_hist_and_proj())
    bad = [Stage("projections", ("p",), is_projections=True), Stage("prune", ("prune",))]
    with pytest.raises(ProjectionsLastViolation):
        T.assert_projections_last(bad)


def test_projections_stage_is_required():
    with pytest.raises(TuesdayStageError):
        T.assert_projections_last([Stage("fetch", ("fetch",))])
    with pytest.raises(TuesdayStageError):
        T.assert_projections_last(
            [
                Stage("projections", ("p",), is_projections=True),
                Stage("projections", ("p",), is_projections=True),
            ]
        )


def test_historical_failure_stops_before_projections():
    calls = []

    def run(stage):
        calls.append(stage.name)
        if stage.name == "publish-all":
            raise TuesdayStageError("empty nflverse week")
        return 0

    with pytest.raises(TuesdayStageError):
        T.run_tuesday(
            season=2026,
            finalized_week=3,
            prefix="projections-staging",
            bucket="knowball-public",
            run=run,
            skip_historical=False,
            retention=False,
        )
    assert "projections" not in calls, "projections must never run after a historical failure"


def test_projection_failure_keeps_historical_and_leaves_pointer():
    def run(stage):
        if stage.is_projections:
            raise TuesdayStageError("quality gate refused")
        return 0

    report = T.run_tuesday(
        season=2026,
        finalized_week=3,
        prefix="projections-staging",
        bucket="knowball-public",
        run=run,
        retention=False,
    )
    assert report.status == "stats_complete_projections_failed"
    assert report.pointerUnchanged is True
    assert "--resume" in report.recoveryCommand
    hist = [s for s in report.stages if not s.is_projections]
    assert hist and hist[-1].status == "completed", "historical publish must have succeeded"
    # The projection stage failed, and nothing ran after it.
    assert report.stages[-1].status == "failed"
    assert not any(s.status == "completed" for s in report.stages[len(hist) :])


def test_successful_run_records_snapshot_and_pointer():
    def run(stage):
        return 0

    report = T.run_tuesday(
        season=2026,
        finalized_week=3,
        prefix="projections-staging",
        bucket="knowball-public",
        run=run,
        retention=False,
    )
    assert report.status == "complete"
    assert report.stages[-1].status == "completed"
    assert report.pointerUnchanged is False


def test_recovery_command_is_exact_and_frozen():
    cmd = T.recovery_command(2026, 3, "projections-staging", "knowball-public")
    assert "uv run --frozen" in cmd
    assert "--season 2026" in cmd and "--finalized-week 3" in cmd
    assert "--prefix projections-staging" in cmd and "--resume" in cmd


def test_report_is_written_with_no_secret_material():
    def run(stage):
        return 0

    T.run_tuesday(
        season=2026,
        finalized_week=3,
        prefix="projections-staging",
        bucket="knowball-public",
        run=run,
        retention=False,
    )
    paths = T.report_paths()
    assert len(paths) == 1
    doc = json.loads(paths[0].read_text(encoding="utf-8"))
    assert doc["kind"] == "tuesday-run"
    assert doc["season"] == 2026 and doc["finalizedWeek"] == 3
    text = paths[0].read_text(encoding="utf-8").lower()
    for secret_marker in ("service_role", "supabase_service_role_key", "eyj"):
        assert secret_marker not in text


def test_retention_runs_as_a_substep_not_a_stage():
    calls = []

    def run(stage):
        calls.append(stage.name)
        return 0

    def prune():
        return {
            "protected": [{"id": "snap-a", "reason": "current pointer"}],
            "candidates": [{"id": "old"}],
            "expectedFreedBytes": 10,
            "reportSha256": "abc",
        }

    report = T.run_tuesday(
        season=2026,
        finalized_week=3,
        prefix="projections-staging",
        bucket="knowball-public",
        run=run,
        prune=prune,
    )
    assert "prune" not in calls
    assert report.retention["dryRun"] is True
    assert report.retention["expectedFreedBytes"] == 10


def test_weekly_stage_argv_never_carries_credentials():
    stage = T.projections_stage(2026, 3, prefix="projections-staging", bucket="knowball-public")
    joined = " ".join(stage.argv)
    assert "--prefix projections-staging" in joined
    assert "SUPABASE" not in joined and "eyj" not in joined


def test_projection_stage_reenters_through_the_frozen_lock(monkeypatch):
    monkeypatch.setattr(T, "UV", True)
    argv = T.projections_stage(2026, 3, prefix="projections-staging", bucket="knowball-public").argv
    assert argv[:4] == ("uv", "run", "--frozen", "python")
    assert "weekly" in argv


def test_projection_stage_refuses_production_prefix():
    with pytest.raises(Exception):
        T.assert_projections_last(
            [
                Stage("fetch", ("fetch",)),
                Stage(
                    "projections",
                    T.projections_stage(2026, 3, prefix="projections", bucket="b").argv,
                    is_projections=True,
                ),
            ]
        )


def test_pointer_path_is_surfaced_from_the_nested_publish_result(monkeypatch):
    """The weekly command nests `result`; the Tuesday report must still show the pointer."""
    payload = {
        "weekly": "complete",
        "snapshotId": "snap-1",
        "result": {"pointerPath": "projections-staging/current.json"},
    }

    def fake_run(stage, **kw):
        detail = payload if stage.is_projections else {}
        return T.StageResult(
            stage.name,
            stage.argv,
            "completed",
            0,
            "t0",
            "t1",
            1.0,
            detail=detail,
            is_projections=stage.is_projections,
        )

    monkeypatch.setattr(T, "_run_stage", fake_run)
    report = T.run_tuesday(
        season=2026,
        finalized_week=3,
        prefix="projections-staging",
        bucket="knowball-public",
        retention=False,
    )
    assert report.pointerPath == "projections-staging/current.json"
    assert report.projectionsSnapshotId == "snap-1"


def test_promote_command_requires_explicit_confirmation(capsys):
    """Production must never be reached without the deliberate flag."""
    from projection_ops.cli import main

    with pytest.raises(Exception) as exc:
        main(["promote", "--season", "2026", "--week", "4", "--snapshot", "snap-1"])
    assert "confirm-production" in str(exc.value)


def test_promote_refuses_staging_as_the_source_prefix():
    from projection_ops.cli import main

    with pytest.raises(Exception) as exc:
        main(
            [
                "promote",
                "--season",
                "2026",
                "--week",
                "4",
                "--snapshot",
                "s",
                "--confirm-production",
                "--from-prefix",
                "projections",
            ]
        )
    assert "from-prefix" in str(exc.value)
