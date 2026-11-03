# Weekly / post-game ops plan

Goal: after each NFL week (or after a slate finishes), refresh Midwest Ball viz for the **current season** through the latest completed REG week, then upload Storage.

Run commands from **`backend/`** in this monorepo.

## Canonical one-command shape (target)

```bash
uv run ballnet refresh --season YEAR --as-of-week W --upload
```

Intended stages inside `refresh` (not a new math path — wrap what already exists):

1. **A** `fetch --season YEAR` (incremental nflverse cache)
2. **B** `spine --season YEAR`
3. **C–E** for every publishable group at `as-of-week W` (ytd → densities → percentiles)
4. **G** `publish-all --season YEAR --as-of-week W` (scalar pages + league KDE + search leaderboards + **merged** index/current/seasons)
5. **H** `highlights --season YEAR --week W` (weekly board vs **all-time** single-game peers + `league_weekly` KDEs → `data/highlights/` + `data/dists/league_weekly/`; needs spines for `2016..YEAR`)
   - Historical backfill: `highlights-range --start 2016 --end YEAR [--upload]`
6. Optional: `--upload` → `upload-storage --index --season YEAR --highlights` (pages + league + leaderboards + highlights + league_weekly)
   - All weeks for one year: `upload-storage --season YEAR --highlights-only --all-highlight-weeks`

Until `refresh` exists, run that sequence manually (see below).

## Manual recipe (works today)

```bash
cd backend
uv sync

YEAR=2026
W=1   # latest completed REG week

uv run ballnet fetch --season $YEAR --force
uv run ballnet spine --season $YEAR --force-fetch
uv run ballnet publish-all --season $YEAR --as-of-week $W
uv run ballnet highlights --season $YEAR --week $W
uv run ballnet upload-storage --index --season $YEAR --as-of-week $W --highlights
```

`publish-all` without `--skip-pipeline` already runs C–E then G for all groups. It **merges** into the multi-season players/seasons index by default (use `--replace-index` only when intentionally wiping history).

The frontend reads index/pages from **Supabase Storage** only (local `npm run dev` included). `publish-all` is not enough — `upload-storage` is what the UI sees. Do not commit Ballnet JSON into `frontend/`.

### Active dataset and weekly publication

`upload-storage` resolves `index/ballnet-dataset.json` once per command and uploads
to its `prefix`, the same location the frontend reads. A missing pointer or an
explicit empty prefix selects the legacy bucket root. An invalid pointer or a
failed pointer read stops the upload; it must not silently publish elsewhere.
The selected destination is printed in the upload log. Projections keep their
separate `projections/` production prefix.

When `--index` is included, pages, league shapes, leaderboards, and requested
highlights upload first. Any reported failure prevents the index upload.
`index/current.json` uploads after the players and seasons indexes succeed.
Mutable uploads use zero cache lifetime so new page loads can discover updates.

The historical generator must publish the observed-v2 histograms and empirical
rarity used by the current frontend. Keep the generator changes in version
control together with the frontend contract; a saved historical rebuild alone
does not update the scheduled weekly generator.

On November 3, 2026, the watcher and Tuesday tasks were running, but publishing
Week 8 into the legacy root while the website read
`migrations/ballnet-v2-20261029` at Week 7. The historical observed-v2 generator
changes had also been left in GitHub Desktop stash commit
`7c79f3719d2276496f10536f7529dd7edb1e9b25`. The historical generator and its tests
were recovered without applying or deleting the stash's unrelated projection
changes. The uploader now follows the active dataset pointer, and Week 8 was
rebuilt with that generator.

Recovery verification: the forced historical run completed at 10:45 Eastern
with zero upload failures (1,713 pages, eight league files, eight leaderboards,
seven highlight/weekly-distribution files, and three index files). All 14 Week 8
games were final. The active public index reported `asOfWeek: 8` and
`completedWeek: 8`; 28 public objects matched local bytes. The isolated backend
suite passed 31 tests, including active-dataset uploads and early Tuesday
launches. The scheduled Tuesday run separately published Week 9
projections trained through Week 8. Browser UI verification was unavailable;
public HTTP reads verified the frontend's data source.

The original Tuesday wrapper subsequently reported a log-file sharing failure
after its projection CLI had succeeded. The local PowerShell runner now retries
brief log locks, and the promotion wrapper prints a verification summary instead
of duplicating its entire JSON inventory. A simulated lock check confirmed that
two failed writes are retried successfully. Recovery verifies the production
projection manifest's public objects by hash and schema before marking the
Tuesday slot complete; a logging failure alone must not trigger another retrain.

The registered Tuesday trigger also had a fixed UTC offset: Windows reported
November 10's next run at 09:00 Eastern, before the configured 10:00 slot.
Updating the stored-password task was rejected with a credential error. The
entrypoint therefore keeps an early Tuesday launch alive until the configured
time, then reloads state and schedule so a concurrent manual completion cannot
cause duplicate training. Future `register_tasks.ps1` registrations use a
floating local-time boundary. The existing task account and stored credentials
are preserved; the early-launch handling makes its current trigger usable.

## Automation options (pick later)

| Option | Pros | Cons |
|---|---|---|
| **Manual** after MNF / Tuesday AM | Simple, secrets stay local | Easy to forget |
| **cron / launchd** on a laptop or small VM | Cheap; same `uv run` | Machine must be on; secrets on disk |
| **GitHub Actions** (scheduled or `workflow_dispatch`) | Auditable; no local machine | Needs self-hosted or paid runner for long jobs + Storage secrets; nflverse download size |

Recommendation for v1: **manual or local cron** calling the recipe above. Move to GitHub Actions only after `refresh` is one command and runtime/secrets are measured.

### Secrets for upload

- `backend/.env`: `supabase_url`, `supabase_service_role_key`
- Never put the service role in `frontend/` or the static bundle
- Frontend only needs public `NEXT_PUBLIC_SUPABASE_URL` / `VIZ_STORAGE_BASE_URL` (anon is unused for Storage public URLs)

### Scheduling tip

nflverse weeklies often lag end-of-slate by hours. Prefer **Tuesday ~10:00 America/New_York** (or after you confirm week `W` is complete in raw box scores) over “Monday midnight.”

## Fantasy position ranks

Weekly `publish-all` for the **current** season refreshes FantasyPros weekly ECR (`fantasyPosRankKind: "consensus"`) on pages, search leaderboards, and highlight rows (QB/WR/RB/TE only).

Closed seasons use PPR finish among that position (`kind: "finish"`). After a season ends and `index/current.json` advances to year `Y+1`, **republish year `Y` at its final REG week** so last year’s pages switch from consensus to finish:

```bash
# Current pointer is already Y+1
uv run ballnet publish-all --season $Y --as-of-week 18 --no-current --skip-pipeline
uv run ballnet highlights --season $Y --week 18
uv run ballnet upload-storage --season $Y --as-of-week 18 --highlights
```

(`--no-current` keeps `pages/current/` and `index/current.json` on the new year. Kind resolution then treats `$Y` as finish.)

One-time historical backfill (finish ranks on 2016–last closed season):

```bash
uv run ballnet publish-range --start 2016 --end $Y --skip-pipeline --no-current
# then upload each season slice + index
```

## What *not* to re-run every week

- Full `publish-range --start 2016 --end …` — historical season-end slices are static unless you intentionally rebuild
- `publish-league-range` alone — prefer full `publish-all` so pages + percentiles stay aligned with league curves
- `--also-current` Storage upload — doubles quota; the frontend uses `index/current.json`

## Failure modes to watch

- Empty/partial nflverse week → sparse YTD / wrong as-of-week — verify spine week max before publish
- Mid-week TNF: `--as-of-week` is the latest played week so those boxes land in YTD; ramp–hold uses published `completedWeek` (last fully scored week) until the slate is final
- Storage free-tier burst drops — retry `upload-storage --season YEAR` (upsert)
- Index out of sync with search — re-run `upload-storage --index` (frontend reads Storage, not a git-synced copy)

## Follow-ups before automating

1. Implement CLI `refresh` (wrapper; no new Stage math).
2. Optional: detect latest REG week from spine / nflverse schedule instead of passing `--as-of-week`.
3. Log a small JSON report (season, week, player count, upload bytes, duration) under `data/logs/`.
4. Only then wire cron or Actions.

## Recommendation
Keep the manual/local-cron until a thin Ballnet refresh wrapper exists; only then consider GitHub Actions. Prefer Tuesday AM (America/New_York) so nflverse weeklies have landed.
## Fantasy projections (final Tuesday stage)

Run projections only after finalized historical stats publish successfully. The ignored local runner must use its frozen lock. It uploads immutable objects first and `projections/current.json` last. A projection failure must not undo the historical publish or move the old pointer. Run pruning in dry-run mode after acceptance; current, previous known-good, active-run, and required retention-window artifacts stay protected.

### One command for the whole Tuesday operation

Stages 1-6 above plus projections run in the required order by a single command, from `backend/local_ops/projections`:

```bash
uv run --frozen python -m projection_ops.cli tuesday --season YEAR --finalized-week W
```

This asserts projections are last before any work starts, stops if the historical publish fails, and on a projection failure leaves the historical data and `current.json` untouched while reporting status `stats_complete_projections_failed` with the exact recovery command. Schedule this one command, never the individual stages. Full details and flags are in `backend/local_ops/projections/RUNBOOK.md`.
