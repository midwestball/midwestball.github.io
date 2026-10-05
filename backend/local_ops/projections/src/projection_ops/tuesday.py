"""Tuesday finalized-stats orchestration with projections as the final stage.

The historical Ballnet refresh is a sequence of `ballnet` CLI stages. Projections
run last, retrain through the just-finalized week, and never start unless the
historical publish already succeeded. A projection failure leaves the historical
publication and `projections/current.json` untouched and marks the overall run
"stats complete, projections failed" with the exact recovery command.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Sequence
import json
import os
import subprocess
import sys
import time

from .config import SETTINGS

BACKEND_DIR = SETTINGS.repo_root / "backend"
# Set to False to invoke the current interpreter directly (used by tests only).
UV = True
PROJECTION_PREFIX = "projections"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class TuesdayStageError(RuntimeError):
    """A stage failed. The message never carries a secret or a raw credential."""


class ProjectionsLastViolation(TuesdayStageError):
    """Something tried to run after the projections stage."""


@dataclass(frozen=True)
class Stage:
    name: str
    argv: tuple[str, ...]
    is_projections: bool = False


@dataclass
class StageResult:
    name: str
    argv: tuple[str, ...]
    status: str  # completed | failed | skipped
    exitCode: int | None = None
    startedAt: str | None = None
    finishedAt: str | None = None
    seconds: float | None = None
    error: str | None = None
    detail: dict = field(default_factory=dict)
    is_projections: bool = False


def historical_stages(
    season: int, week: int, *, fetch: bool = True, highlight: bool = True
) -> list[Stage]:
    """Ballnet finalized-stats stages A through H plus the Storage upload."""
    stages: list[Stage] = []
    if fetch:
        stages.append(Stage("fetch", ("fetch", "--season", str(season), "--force")))
    stages.append(Stage("spine", ("spine", "--season", str(season), "--force-fetch")))
    stages.append(
        Stage("publish-all", ("publish-all", "--season", str(season), "--as-of-week", str(week)))
    )
    if highlight:
        stages.append(
            Stage("highlights", ("highlights", "--season", str(season), "--week", str(week)))
        )
    stages.append(
        Stage(
            "upload-storage",
            (
                "upload-storage",
                "--index",
                "--season",
                str(season),
                "--as-of-week",
                str(week),
                "--highlights",
            ),
        )
    )
    return stages


def projections_stage(
    season: int,
    finalized_week: int,
    *,
    prefix: str,
    bucket: str,
    resume: bool = False,
    force_rerun: bool = False,
    reason: str | None = None,
    dry_run: bool = False,
) -> Stage:
    # Always re-enter through the frozen lock so the Tuesday run can never drift
    # onto a different environment than the one the operator rehearsed.
    # Production needs a separately approved promotion, so the Tuesday path refuses it.
    if prefix.strip("/") == PROJECTION_PREFIX:
        raise TuesdayStageError(
            "the Tuesday run refuses the production prefix without explicit promotion approval"
        )
    runner = (
        ["uv", "run", "--frozen", "python", "-m", "projection_ops.cli"]
        if UV
        else [sys.executable, "-m", "projection_ops.cli"]
    )
    argv = runner + [
        "weekly",
        "--season",
        str(season),
        "--finalized-week",
        str(finalized_week),
        "--bucket",
        bucket,
        "--prefix",
        prefix,
    ]
    if resume:
        argv.append("--resume")
    if dry_run:
        argv.append("--dry-run")
    if force_rerun:
        argv += ["--force-rerun", "--reason", reason or ""]
    return Stage("projections", tuple(argv), is_projections=True)


def assert_projections_last(stages: Sequence[Stage]) -> None:
    """Fail closed if any routine stage follows the expensive projections stage."""
    flags = [stage.is_projections for stage in stages]
    if not any(flags):
        raise TuesdayStageError("the Tuesday run must include the projections stage")
    if flags.count(True) != 1:
        raise TuesdayStageError("the Tuesday run must contain exactly one projections stage")
    if flags[-1] is not True:
        raise ProjectionsLastViolation("projections must be the final Tuesday stage")


def _run_stage(stage: Stage, *, cwd: Path, env: dict | None, run: Callable | None) -> StageResult:
    started = _now()
    clock = time.monotonic()
    try:
        if run is not None:
            code = run(stage)
        else:
            proc = subprocess.run(
                list(stage.argv), cwd=str(cwd), env=env, capture_output=True, text=True
            )
            if proc.returncode != 0:
                tail = [x for x in (proc.stderr or proc.stdout or "").strip().splitlines() if x][
                    -3:
                ]
                # Stage output is diagnostic only; it never carries a credential by construction.
                raise TuesdayStageError("; ".join(tail)[:400] or f"exit {proc.returncode}")
            code = proc.returncode
        return StageResult(
            stage.name,
            stage.argv,
            "completed",
            code,
            started,
            _now(),
            round(time.monotonic() - clock, 2),
            detail=_parse_cli_json(proc.stdout if run is None else ""),
            is_projections=stage.is_projections,
        )
    except Exception as exc:
        return StageResult(
            stage.name,
            stage.argv,
            "failed",
            None,
            started,
            _now(),
            round(time.monotonic() - clock, 2),
            str(exc)[:400],
            is_projections=stage.is_projections,
        )


def _parse_cli_json(stdout: str) -> dict:
    """Projections print a single JSON object; other stages print nothing useful."""
    if not stdout or not stdout.strip().startswith("{"):
        return {}
    try:
        value = json.loads(stdout)
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


@dataclass
class TuesdayRun:
    season: int
    finalized_week: int
    status: str  # complete | stats_complete_projections_failed
    stages: list[StageResult]
    startedAt: str
    finishedAt: str
    projectionsSnapshotId: str | None = None
    pointerPath: str | None = None
    pointerUnchanged: bool | None = None
    retention: dict | None = None
    recoveryCommand: str | None = None

    def to_dict(self) -> dict:
        return {
            "kind": "tuesday-run",
            "season": self.season,
            "finalizedWeek": self.finalized_week,
            "status": self.status,
            "startedAt": self.startedAt,
            "finishedAt": self.finishedAt,
            "projectionsSnapshotId": self.projectionsSnapshotId,
            "pointerPath": self.pointerPath,
            "pointerUnchanged": self.pointerUnchanged,
            "recoveryCommand": self.recoveryCommand,
            "retention": self.retention,
            "stages": [
                {
                    "name": s.name,
                    "status": s.status,
                    "exitCode": s.exitCode,
                    "startedAt": s.startedAt,
                    "finishedAt": s.finishedAt,
                    "seconds": s.seconds,
                    "error": s.error,
                    "detail": s.detail,
                    "isProjections": s.is_projections,
                }
                for s in self.stages
            ],
        }


def run_tuesday(
    *,
    season: int,
    finalized_week: int,
    prefix: str,
    bucket: str,
    dry_run: bool = False,
    resume: bool = False,
    skip_historical: bool = False,
    retention: bool = True,
    run: Callable | None = None,
    prune: Callable | None = None,
) -> TuesdayRun:
    """Execute the Tuesday operation, projections last.

    `run` is an injected stage runner used by tests. In production it is None and
    each stage runs as a real subprocess.
    """
    stages: list[Stage] = []
    if not skip_historical:
        stages += historical_stages(season, finalized_week)
    stages.append(
        projections_stage(
            season, finalized_week, prefix=prefix, bucket=bucket, resume=resume, dry_run=dry_run
        )
    )
    assert_projections_last(stages)

    started = _now()
    env = None if run is not None else os.environ.copy()
    results: list[StageResult] = []
    for stage in stages:
        if stage.is_projections:
            break
        result = _run_stage(
            stage, cwd=BACKEND_DIR if not stage.is_projections else SETTINGS.root, env=env, run=run
        )
        results.append(result)
        if result.status == "failed":
            # Nothing after a failed historical stage may run, including projections.
            skipped = [
                StageResult(s.name, s.argv, "skipped", is_projections=s.is_projections)
                for s in stages[stages.index(stage) + 1 :]
            ]
            report = TuesdayRun(
                season,
                finalized_week,
                "failed",
                results + skipped,
                started,
                _now(),
                recoveryCommand=None,
            )
            _write_report(report)
            raise TuesdayStageError(
                f"historical stage {stage.name} failed; projections did not run: {result.error}"
            )

    proj = _run_stage(stages[-1], cwd=SETTINGS.root, env=env, run=run)
    results.append(proj)
    if proj.status == "failed":
        # Historical publish stays intact and the pointer is not moved.
        report = TuesdayRun(
            season,
            finalized_week,
            "stats_complete_projections_failed",
            results,
            started,
            _now(),
            pointerUnchanged=True,
            recoveryCommand=recovery_command(season, finalized_week, prefix, bucket),
        )
        report.retention = _retention_summary(prune) if retention else None
        _write_report(report)
        return report

    # The weekly command nests the publication result; surface the pointer so the
    # operator can see at a glance which revision the run committed.
    nested = proj.detail.get("result") if isinstance(proj.detail.get("result"), dict) else {}
    report = TuesdayRun(
        season,
        finalized_week,
        "complete",
        results,
        started,
        _now(),
        projectionsSnapshotId=proj.detail.get("snapshotId"),
        pointerPath=nested.get("pointerPath") or proj.detail.get("pointerPath"),
        pointerUnchanged=False,
    )
    report.retention = _retention_summary(prune) if retention else None
    _write_report(report)
    return report


def recovery_command(season: int, finalized_week: int, prefix: str, bucket: str) -> str:
    return (
        f"uv run --frozen python -m projection_ops.cli weekly --season {season} "
        f"--finalized-week {finalized_week} --bucket {bucket} --prefix {prefix} --resume"
    )


def _retention_summary(prune: Callable | None) -> dict | None:
    """Retention runs as a sub-step after acceptance, never as a routine stage."""
    if prune is None:
        return None
    report = prune()
    return {
        "dryRun": True,
        "protected": report.get("protected", []),
        "candidates": [c.get("id") for c in report.get("candidates", [])],
        "expectedFreedBytes": report.get("expectedFreedBytes"),
        "reportSha256": report.get("reportSha256"),
    }


def _write_report(report: TuesdayRun) -> Path:
    out = SETTINGS.state / "logs"
    SETTINGS.assert_local_write(out)
    out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = SETTINGS.assert_local_write(
        out / f"tuesday-{report.season}-w{report.finalized_week}-{stamp}.json"
    )
    path.write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")
    return path


def report_paths() -> list[Path]:
    out = SETTINGS.state / "logs"
    return sorted(out.glob("tuesday-*.json")) if out.exists() else []
