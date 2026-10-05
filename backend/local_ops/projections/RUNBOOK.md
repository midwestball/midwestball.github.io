# Weekly projections runbook

> Production is gated until staging acceptance, the private restore drill, and Tuesday integration are completed. Offline fixtures are smoke artifacts only.

## Environment and tests

```bash
cd backend/local_ops/projections
uv sync --frozen --group test
uv run --frozen --group test pytest -q
uv run --frozen --group test ruff format --check src/ tests/
uv run --frozen python -m projection_ops.cli contract-check
```

## Offline six-position acceptance

```bash
uv run --frozen python -m projection_ops.cli build --season 2026 --week 4 --trained-through-week 3 --mode retrain --offline-fixture
uv run --frozen python -m projection_ops.cli validate --season 2026 --week 4 --snapshot SNAPSHOT_ID
uv run --frozen python -m projection_ops.cli publish --season 2026 --week 4 --snapshot SNAPSHOT_ID --dry-run --prefix projections-staging
```

A live build reads the finalized slate and training data from nflverse:

```bash
uv run --frozen python -m projection_ops.cli build --season 2026 --week 4 --trained-through-week 3 --mode retrain --draws 10000
```

Add `--no-refresh` to reuse the cached source data. `build` refuses a week that is not yet finalized. When K and DST cannot clear the strict selection gate, the build still succeeds if the release decision approves it under the initial-deployment caveat; the caveat and the position evidence are recorded in the manifest under `releaseDecision`. A promoted position failure, a coverage or tail-calibration hard stop, or a missing position fails the build.

The build stages in a temporary directory, validates it, and renames it atomically. A build that fails validation leaves a `.tmp-` directory behind; inspect it, then delete it before rebuilding. Publish uploads entities, index, and manifest, verifies every remote byte/hash/schema, then writes `current.json` last. Any failure leaves the pointer unchanged.

## Credentials

Set `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, and optionally `PROJECTION_OPS_BUCKET`. Lowercase aliases (`supabase_url`, `supabase_service_role_key`) are also read from `backend/.env`. Never echo their values. Use `--dry-run` when credentials or staging approval are absent.

## Backup

Set `PROJECTION_OPS_BACKUP_DIR` to a private encrypted location outside this repository and machine disk, then run:

```bash
uv run --frozen python -m projection_ops.cli backup create
uv run --frozen python -m projection_ops.cli backup verify ARCHIVE.tar.gz
uv run --frozen python -m projection_ops.cli backup restore ARCHIVE.tar.gz --destination EMPTY_DIR
```

Exports exclude `.env`, credentials, `.venv`, caches, bytecode, and large model/draw artifacts.

## Tuesday operation

Projections are the **final** stage of the Tuesday finalized-stats run. One command runs the whole operation:

```bash
uv run --frozen python -m projection_ops.cli tuesday --season 2026 --finalized-week 3
```

The order is fixed and asserted before any work starts:

1. `ballnet fetch --season S --force`
2. `ballnet spine --season S --force-fetch`
3. `ballnet publish-all --season S --as-of-week W`
4. `ballnet highlights --season S --week W`
5. `ballnet upload-storage --index --season S --as-of-week W --highlights`
6. `projections weekly --season S --finalized-week W` (retrain, publish, anonymous GET)

Guarantees:

- A failed historical stage stops the run. Projections never start unless the historical publish succeeded.
- A failed projections stage leaves the historical publication intact, does **not** move `current.json`, records status `stats_complete_projections_failed`, and prints the exact `--resume` recovery command.
- Retention is a sub-step after acceptance, never a routine stage, and stays dry-run.
- Each run writes a report to `state/logs/tuesday-<season>-w<week>-<stamp>.json`.

Useful flags: `--skip-historical` to run only the projections stage, `--dry-run` to rehearse without uploading, `--resume` to republish a validated snapshot without retraining, `--no-retention` to skip the prune sub-step.

```bash
uv run --frozen python -m projection_ops.cli tuesday-report --limit 5
```

To schedule it, point a local cron or Windows Task Scheduler entry at the one `tuesday` command. Do not schedule the individual stages. Confirm week `W` is final before the run; nflverse weeklies often lag end-of-slate.

## Pointer verification is slow by design

The Supabase Storage edge can serve the previous `current.json` for roughly 45 seconds after the pointer bytes change. Pointer confirmation therefore polls for up to 180 seconds. A short window would report a failed commit for a commit that actually succeeded, which is how an unnecessary retrain gets triggered. Expect the last few seconds of `publish` and `weekly` to be quiet.

## Retention

```bash
uv run --frozen python -m projection_ops.cli prune --scope all --dry-run
uv run --frozen python -m projection_ops.cli prune --scope all --execute --report-hash HASH
```

Dry-run is the default. Execution rechecks locks and the current/previous protected set. It refuses to remove compact public snapshots without backup evidence.

## Rollback

Validate the prior immutable revision, then republish only its pointer. Never delete the failed revision during the investigation.
