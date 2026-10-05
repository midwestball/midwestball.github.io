"""Operator command family for projection snapshots."""

from __future__ import annotations
import argparse, json, sys
from datetime import datetime, timezone
from pathlib import Path
from .config import SETTINGS
from .contracts import canonical_bytes, sha256_file, validate_snapshot, verify_schema_copy
from .pipeline import build_snapshot, fixture_entities
from .storage import (
    SupabaseBackend,
    publish_staging_snapshot,
    publish_snapshot,
    verify_anonymous_snapshot,
    verify_remote_snapshot,
)
from .retention import plan_retention, execute_retention
from .backup import create_export, verify_export, restore_export
from .live_pipeline import MODEL_VERSION, generate_live_forecasts
from .live_data import load_live_tables, resolve_finalized_and_target
from .weekly import WeeklyLedger, WeeklyPlan, require_final_tuesday_stage
from . import tuesday as tuesday_ops
from .quality import release_decision, disclosure_caveats


class _DryBackend:
    pass


def _snapshot(args) -> Path:
    return SETTINGS.artifacts / "public" / str(args.season) / f"w{args.week}" / args.snapshot


def parser():
    p = argparse.ArgumentParser(prog="projection-ops")
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("contract-check")
    b = sub.add_parser("build")
    b.add_argument("--season", type=int, required=True)
    b.add_argument("--week", type=int, required=True)
    b.add_argument("--trained-through-week", type=int)
    b.add_argument("--mode", choices=["auto", "retrain", "reuse"], default="auto")
    b.add_argument("--offline-fixture", action="store_true")
    b.add_argument("--no-refresh", action="store_true")
    b.add_argument("--seed", type=int, default=20260929)
    b.add_argument("--draws", type=int, default=10000)
    for name in ("validate", "publish"):
        x = sub.add_parser(name)
        x.add_argument("--season", type=int, required=True)
        x.add_argument("--week", type=int, required=True)
        x.add_argument("--snapshot", required=True)
        if name == "publish":
            x.add_argument("--dry-run", action="store_true")
            x.add_argument("--bucket", default="knowball-public")
            x.add_argument("--prefix", default="projections-staging")
    ac = sub.add_parser("accept-staging")
    ac.add_argument("--bucket", default="knowball-public")
    ac.add_argument("--prefix", default="projections-staging")
    w = sub.add_parser("weekly")
    w.add_argument("--season", type=int, required=True)
    w.add_argument("--finalized-week", type=int, required=True)
    w.add_argument("--bucket", default="knowball-public")
    w.add_argument("--prefix", default="projections-staging")
    w.add_argument("--dry-run", action="store_true")
    w.add_argument("--resume", action="store_true")
    w.add_argument("--force-rerun", action="store_true")
    w.add_argument("--reason")
    w.add_argument("--seed", type=int, default=0)
    pr_ = sub.add_parser("promote")
    pr_.add_argument("--season", type=int, required=True)
    pr_.add_argument("--week", type=int, required=True)
    pr_.add_argument("--snapshot", required=True)
    pr_.add_argument("--bucket", default="knowball-public")
    pr_.add_argument("--from-prefix", default="projections-staging")
    pr_.add_argument("--confirm-production", action="store_true")
    tu = sub.add_parser("tuesday")
    tu.add_argument("--season", type=int, required=True)
    tu.add_argument("--finalized-week", type=int, required=True)
    tu.add_argument("--bucket", default="knowball-public")
    tu.add_argument("--prefix", default="projections-staging")
    tu.add_argument("--dry-run", action="store_true")
    tu.add_argument("--resume", action="store_true")
    tu.add_argument("--skip-historical", action="store_true")
    tu.add_argument("--no-retention", action="store_true")
    dt = sub.add_parser("tuesday-report")
    dt.add_argument("--season", type=int)
    dt.add_argument("--limit", type=int, default=5)
    pr = sub.add_parser("prune")
    pr.add_argument("--scope", choices=["all", "local", "remote"], default="all")
    pr.add_argument("--dry-run", action="store_true")
    pr.add_argument("--execute", action="store_true")
    pr.add_argument("--report-hash")
    ba = sub.add_parser("backup")
    ba.add_argument("action", choices=["create", "verify", "restore"])
    ba.add_argument("archive", nargs="?")
    ba.add_argument("--destination")
    return p


def main(argv=None):
    args = parser().parse_args(argv)
    if args.command == "contract-check":
        out = {"schemaSha256": verify_schema_copy()}
    elif args.command == "build":
        trained = (
            args.trained_through_week if args.trained_through_week is not None else args.week - 1
        )
        if args.offline_fixture:
            path = build_snapshot(
                season=args.season,
                week=args.week,
                trained_through_week=trained,
                entities=fixture_entities(args.seed, args.draws),
                minimum_draws=args.draws,
            )
            out = {
                "snapshotId": path.name,
                "path": str(path),
                "mode": args.mode,
                "offlineFixture": True,
            }
        else:
            if args.draws != 10_000:
                raise ValueError("live builds require exactly 10,000 draws")
            quality = SETTINGS.artifacts / "reports" / "quality" / "historical-quality.json"
            if not quality.exists():
                raise RuntimeError("historical quality report is required before a live build")
            quality_doc = json.loads(quality.read_text())
            decision = release_decision(quality_doc)
            if not decision["approved"]:
                raise RuntimeError(
                    "historical quality gate did not approve a release; live build refused: "
                    + ", ".join(decision["blocked"])
                )
            entities, live_manifest = generate_live_forecasts(
                args.season,
                args.week,
                mode=args.mode,
                refresh=not args.no_refresh,
                n_draws=args.draws,
                seed=args.seed,
            )
            path = build_snapshot(
                season=args.season,
                week=args.week,
                trained_through_week=trained,
                entities=entities,
                minimum_draws=args.draws,
            )
            manifest_path = path / "manifest.json"
            manifest = json.loads(manifest_path.read_text())
            manifest["liveRun"] = live_manifest
            manifest["qualityReportSha256"] = sha256_file(quality)
            manifest["validation"]["warnings"] = disclosure_caveats(decision)
            manifest["releaseDecision"] = decision
            manifest_path.write_bytes(canonical_bytes(manifest))
            validate_snapshot(path)
            out = {
                "snapshotId": path.name,
                "path": str(path),
                "mode": args.mode,
                "offlineFixture": False,
                "entities": len(entities),
                "qualityReportSha256": manifest["qualityReportSha256"],
            }
    elif args.command == "validate":
        out = validate_snapshot(_snapshot(args))
    elif args.command == "publish":
        if args.prefix == "projections":
            raise RuntimeError("production publication requires separate explicit owner approval")
        backend = _DryBackend() if args.dry_run else SupabaseBackend(args.bucket)
        out = publish_staging_snapshot(
            _snapshot(args), backend, dry_run=args.dry_run, prefix=args.prefix
        )
    elif args.command == "accept-staging":
        if args.prefix == "projections":
            raise RuntimeError("accept-staging refuses the production prefix")
        backend = SupabaseBackend(args.bucket)
        pointer = json.loads(backend.download(f"{args.prefix}/current.json"))
        from .secrets import load_backend_credentials
        import os

        load_backend_credentials()
        public_base = (
            os.environ["SUPABASE_URL"].rstrip("/") + f"/storage/v1/object/public/{args.bucket}"
        )
        out = verify_anonymous_snapshot(public_base, pointer, prefix=args.prefix)
    elif args.command == "weekly":
        if args.prefix == "projections":
            raise RuntimeError(
                "weekly command refuses production without a separately approved promotion"
            )
        quality = SETTINGS.artifacts / "reports" / "quality" / "historical-quality.json"
        if not quality.exists():
            raise RuntimeError("historical quality report is missing")
        decision = release_decision(json.loads(quality.read_text()))
        if not decision["approved"]:
            raise RuntimeError(
                "historical quality gate did not approve a release: "
                + ", ".join(decision["blocked"])
            )
        seasons = list(range(args.season - 3, args.season + 1))
        tables = load_live_tables(seasons, target_season=args.season, refresh=not args.resume)
        target = resolve_finalized_and_target(tables.schedules, args.season, args.finalized_week)
        source = tables.source_metadata["sourceFingerprint"]
        plan = WeeklyPlan(args.season, args.finalized_week, target, source, MODEL_VERSION)
        ledger = WeeklyLedger()
        require_final_tuesday_stage(
            historical_publish_succeeded=True,
            finalized_schedule_confirmed=True,
            trained_through_week=args.finalized_week,
            plan=plan,
        )
        backend = _DryBackend() if args.dry_run else SupabaseBackend(args.bucket)
        try:
            if args.resume:
                entry = ledger.resume(plan)
                path = Path(entry["snapshotPath"])
            else:
                pending = f"pending-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
                ledger.begin(
                    plan,
                    snapshot_id=pending if args.force_rerun else None,
                    force_rerun=args.force_rerun,
                    reason=args.reason,
                )
                entities, live_manifest = generate_live_forecasts(
                    args.season,
                    target,
                    mode="retrain",
                    refresh=False,
                    n_draws=10_000,
                    seed=args.seed,
                    tables=tables,
                )
                path = build_snapshot(
                    season=args.season,
                    week=target,
                    trained_through_week=args.finalized_week,
                    entities=entities,
                    minimum_draws=10_000,
                )
                manifest_path = path / "manifest.json"
                manifest = json.loads(manifest_path.read_text())
                manifest["liveRun"] = live_manifest
                manifest["qualityReportSha256"] = sha256_file(quality)
                manifest["validation"]["warnings"] = disclosure_caveats(decision)
                manifest["releaseDecision"] = decision
                manifest_path.write_bytes(canonical_bytes(manifest))
                validate_snapshot(path)
                ledger.record_validated(plan, path.name, path)
            result = publish_staging_snapshot(
                path, backend, dry_run=args.dry_run, prefix=args.prefix
            )
            if args.dry_run:
                out = {
                    "weekly": "validated_publish_dry_run",
                    "snapshotId": path.name,
                    "targetWeek": target,
                    "result": result,
                }
            else:
                pointer = json.loads(backend.download(f"{args.prefix}/current.json"))
                from .secrets import load_backend_credentials
                import os

                load_backend_credentials()
                base = (
                    os.environ["SUPABASE_URL"].rstrip("/")
                    + f"/storage/v1/object/public/{args.bucket}"
                )
                anonymous = verify_anonymous_snapshot(base, pointer, prefix=args.prefix)
                ledger.record_success(
                    plan, pointer_path=f"{args.prefix}/current.json", anonymous_verified=True
                )
                out = {
                    "weekly": "complete",
                    "snapshotId": path.name,
                    "targetWeek": target,
                    "result": result,
                    "anonymous": anonymous,
                }
        except Exception as exc:
            recovery = (
                "uv run --frozen python -m projection_ops.cli weekly "
                f"--season {args.season} --finalized-week {args.finalized_week} "
                f"--resume --prefix {args.prefix}"
            )
            try:
                current = ledger.get(plan)
                if current and current.get("status") in {"validated", "upload_failed"}:
                    ledger.record_upload_failure(plan, exc, recovery)
                elif current:
                    ledger.record_stage_failure(plan, exc, recovery)
            finally:
                raise
    elif args.command == "promote":
        # Production promotion is a separate, deliberate step. It never infers approval.
        if not args.confirm_production:
            raise RuntimeError(
                "production promotion requires --confirm-production after an explicit owner decision"
            )
        if args.from_prefix == "projections":
            raise ValueError("--from-prefix must be the staging prefix")
        source = _snapshot(args)
        if not source.is_dir():
            raise RuntimeError(f"local snapshot is missing: {source}")
        backend = SupabaseBackend(args.bucket)
        staged = json.loads(backend.download(f"{args.from_prefix}/current.json"))
        if staged["snapshotId"] != args.snapshot:
            raise RuntimeError(
                f"snapshot {args.snapshot} is not what {args.from_prefix} currently serves ({staged['snapshotId']}); "
                "promote the accepted revision or publish and accept the new one first"
            )
        out = publish_snapshot(source, backend, prefix="projections")
        pointer = json.loads(backend.download("projections/current.json"))
        out["remoteVerification"] = verify_remote_snapshot(backend, pointer, prefix="projections")
        from .secrets import load_backend_credentials
        import os

        load_backend_credentials()
        base = os.environ["SUPABASE_URL"].rstrip("/") + f"/storage/v1/object/public/{args.bucket}"
        out["anonymous"] = verify_anonymous_snapshot(base, pointer, prefix="projections")
        out["promotedFrom"] = args.from_prefix
    elif args.command == "tuesday":
        if args.prefix == "projections":
            raise RuntimeError(
                "tuesday command refuses production without a separately approved promotion"
            )
        report = tuesday_ops.run_tuesday(
            season=args.season,
            finalized_week=args.finalized_week,
            prefix=args.prefix,
            bucket=args.bucket,
            dry_run=args.dry_run,
            resume=args.resume,
            skip_historical=args.skip_historical,
            retention=not args.no_retention,
            prune=plan_retention,
        )
        out = report.to_dict()
        if report.status != "complete":
            raise RuntimeError(
                f"tuesday run {report.status}: "
                + ", ".join(s.error or "" for s in report.stages if s.status == "failed")
            )
    elif args.command == "tuesday-report":
        paths = tuesday_ops.report_paths()
        if args.season:
            paths = [p for p in paths if f"-{args.season}-" in p.name]
        out = [json.loads(p.read_text(encoding="utf-8")) for p in paths[-args.limit :]]
    elif args.command == "prune":
        if args.execute:
            if not args.report_hash:
                raise ValueError("--execute requires --report-hash from a saved dry run")
            out = execute_retention(args.report_hash)
        else:
            out = plan_retention()
    elif args.command == "backup":
        if args.action == "create":
            out = {"archive": str(create_export())}
        elif args.action == "verify":
            out = verify_export(Path(args.archive))
        else:
            if not args.destination:
                raise ValueError("restore requires --destination")
            restore_export(Path(args.archive), Path(args.destination))
            out = {"restored": args.destination}
    print(json.dumps(out, indent=2, default=str))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"projection-ops: {exc}", file=sys.stderr)
        raise SystemExit(2)
