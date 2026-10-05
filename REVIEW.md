# Midwest Ball — Full Engineering Review

Scope: `frontend/` (Next.js 16 static export), `backend/` (Python `ballnet` ETL), and
`backend/local_ops/projections/` (the Python `projection_ops` ML package).
All commands were run and their real output is quoted. No source file was modified.

---

## 0. Command results (verified)

| Command | Result |
|---|---|
| `cd frontend && npm run test` | **PASS** — 7 files, 55 tests, exit 0 |
| `cd frontend && npx tsc --noEmit` | **PASS** — exit 0, no output |
| `cd frontend && npm run build` | **PASS** — exit 0, 1440 static pages prerendered |
| `cd frontend && npm run lint` | **FAIL** — exit 1, **8 errors**, 5 warnings |
| `cd backend/local_ops/projections && pytest -q` | **PASS** — 42 tests, exit 0 |
| `cd backend && uv run pytest` | **FAIL** — 11 collection errors, 0 tests collected |
| `find backend/src -name 'test*'` | **empty — zero tests for `ballnet`** |

Lint errors are all `react-hooks/set-state-in-effect` (cascading renders):
`ComparePageClient.tsx:113`, `HighlightsBrowser.tsx:58,258`,
`PlayerPageClient.tsx:65`, `PlayerSearch.tsx:373,399,429,442`.
Plus 5 unused-var warnings in `src/lib/highlights.ts`.

---

## 1. The single biggest issue: the ML system is invisible

The actual machine-learning work lives in **`backend/local_ops/projections/`**, which is
listed in the root `.gitignore` (line: `backend/local_ops/`). It is the strongest code in
the repository and it is **not on GitHub**.

What is in there that never appears to a reviewer:

- **`model.py`** — a CRPS-optimal random forest. It trains `RandomForestRegressor` on a
  multi-output binary target `(y <= threshold_j)` over a threshold grid, then samples
  predictive draws by pooling empirical leaf outcomes. This is a legitimate
  distributional-forecasting construction, not a point regressor with a wrapper.
- **`quality.py`** — rolling-origin historical validation (36 week-ahead folds, 2024 and
  2025 holdouts) comparing the CRPS forest against a LightGBM conditional-residual baseline,
  with **player-clustered and season-week-clustered bootstrap confidence intervals**, plus
  coverage and tail-Brier hard stops.
- **A release gate** (`release_decision()`) that blocks the build when a promoted position
  fails, and forces a written disclosure when a position ships without selection evidence.
- **`storage.py`** — immutable-first, pointer-last publishing with full remote SHA-256
  verification, a compare-and-swap pointer guard, and rollback paths.
- **Real artifacts on disk**: `artifacts/models/2026/w4/{qb,rb,wr,te,k,dst}/fit.joblib`,
  `artifacts/reports/quality/historical-quality.json` with a `.sha256` sidecar.

The repository README describes `backend/` as "Ballnet Python ETL (publishes JSON)". The
word *model* does not appear in the top-level README. An interviewer who clones this repo
sees a data pipeline and a pretty website — not a model.

---

## 2. Verified model results (your strongest asset)

From `artifacts/reports/quality/historical-quality.json`
(protocol `week_ahead_negative_support_v1_no_vegas`, `historicalReplication: true`,
`pristineConfirmation: false`):

| Pos | Gate | Delta CRPS | Player-cluster 95% CI | Rows |
|---|---|---|---|---|
| QB | **pass** | **+0.1006** | [0.0445, 0.1595] | 1328 |
| RB | **pass** | **+0.0581** | [0.0323, 0.0821] | 3253 |
| WR | **pass** | **+0.0516** | [0.0357, 0.0691] | 4952 |
| TE | **pass** | **+0.0425** | [0.0225, 0.0613] | 2510 |
| DST | fail (disclosed) | +0.0130 | [-0.0136, 0.0379] | 1088 |
| K | fail (disclosed) | +0.0116 | [-0.0138, 0.0385] | 1086 |

Four of six positions beat the baseline with intervals excluding zero. K and DST have
positive point estimates whose intervals include zero, and the code **refuses to hide
that** — it ships them only under an explicit `initial_deployment` caveat recorded in the
manifest.

This is genuinely good practice. Keep the artifact; surface it.

---

## 3. Correctness bugs

### 3.1 CRITICAL — `--no-current` still overwrites `index/current.json`

`publish.py:541-545` gates the index write on `write_index` only, never on `also_current`:

```python
    if write_index:
        index_path = str(write_players_index(all_bios, merge_existing=merge_index))
        current_path = str(write_current_index(season, as_of_week))   # unconditional
        upsert_seasons_index(season, as_of_week)
```

`cli.py:628-634` passes `also_current=not args.no_current`. The reviewer proved that with a
pre-existing `index/current.json` pointing at season 2027, calling
`publish_all(2026, 3, also_current=False, write_index=True)` rewrote it to `{"season":2026,
"asOfWeek":3}`. `publish_range` has the same defect at `publish.py:601-604`.

This contradicts the season-rollover procedure in `docs/WEEKLY_OPS.md`.

### 3.2 CRITICAL — `completedWeek` is fabricated as `asOfWeek`

`publish.py:410-416`:

```python
def _slice_row(s: dict[str, int]) -> dict[str, int]:
    as_of = int(s["asOfWeek"])
    return {
        "season": int(s["season"]),
        "asOfWeek": as_of,
        "completedWeek": int(s["completedWeek"]) if s.get("completedWeek") is not None else as_of,
    }
```

`publish.py:599` builds slices with no `completedWeek`, so the fallback fires. `BOUNDARIES.md`
defines `completed_week` as "the last consecutive REG week where every scheduled game has
scores". Substituting `asOfWeek` corrupts ramp-hold thresholds
(`min_n = n_base * min(ramp_week, 5)`) for any partially-scored week, and because
`write_seasons_index` is a **full replace**, it overwrites real values already in the file.
Note `upsert_seasons_index` (`publish.py:428-448`) does this correctly — the two writers
disagree, which is how the bug survived.

### 3.3 HIGH — `fantasy_rank` modal position uses an order-unstable `unique`

`fantasy_rank.py:221-229` sorts by count and then calls
`.unique(subset=["player_id"], keep="first")` **without `maintain_order=True`**. Polars
documents `keep="first"` as returning *a* row per key, not *the first in sort order*. This
decides which position bucket a player is ranked in, so a wrong pick publishes a wrong
`fantasyPosRank`. One-keyword fix.

### 3.4 HIGH — a closed season republished without `--no-current` gets `kind="consensus"`

`fantasy_rank.py:36-47` returns `"consensus"` whenever `updating_current=True`, and
`publish.py:238,303` pass `updating_current=also_current`. Verified:
`resolve_rank_kind(2025, updating_current=True)` -> `"consensus"` for a season that is
already closed. Today's ECR gets stamped onto a historical page.

### 3.5 HIGH — rank builders ignore `as_of_week` although the cache key includes it

`fantasy_rank.py:59-69` keys the cache on `(season, as_of_week, kind)`, but neither
`_consensus_ranks` (`:143-192`) nor `_finish_ranks` (`:195-245`) takes `as_of_week`.
`_consensus_ranks` calls `nfl.load_ff_rankings("week")` unfiltered; `_finish_ranks` sums the
**entire** season's PPR regardless of week. The cache key promises slice-scoped ranks the
builders do not deliver.

### 3.6 HIGH — `ballnet highlights --season 2026` silently publishes an empty board

`cli.py:818` defaults the week to `default_as_of_week(season)`, which returns `18`
(`publish.py:34-36`). With a live spine at week 3, the reviewer measured the w18 board as
`top: 0`, every `byGroup` empty, **exit 0**. `highlights.weeks_to_publish` already caps at
the spine maximum and should supply the default.

### 3.7 MEDIUM — `leaderboard._row_sort_key` ignores `qualified` despite its docstring

`leaderboard.py:40-45` promises "Qualified + high oriented percentile first" but never reads
`row["qualified"]`. It works only because `percentiles.py:53-59` happens to set
`percentile=None` for unqualified rows — an implicit cross-stage coupling.

### 3.8 MEDIUM — a failed optional fetch is cached as a permanent empty frame

`ingest.py:146-157` writes an empty stub to `data/raw/{name}.parquet` when an optional
source fails, and `ingest.py:139` short-circuits on `out.exists() and not force`. A
transient network blip on `pfr_def` therefore persists until someone remembers `--force`,
and the cached path reports `"(cache)"` without surfacing the `UNAVAILABLE` note. This is
the most likely route to a silently-wrong published season.

### 3.9 MEDIUM — `_write_json` is non-atomic, in three copies

`publish.py:208-211`, `leaderboard.py:34-37`, `highlights.py:428-431` each do
`json.dump` straight onto the target path. A crash mid-write leaves truncated JSON that the
frontend will try to parse. There is no temp-file-plus-rename, no checksum, and no manifest
anywhere in `src/ballnet` (`grep sha256|hashlib|manifest` -> **zero hits**).

---

## 4. Performance

### 4.1 HIGH — `_add_lags` is quadratic and dominates the weekly run

`live_data.py:302-322` loops over every row of a player and, for each, re-scans all of the
player's rows to build `eligible`, then does `out.at[i, ...]` scalar writes.

Measured scaling (20 players, 2 sources):

| games/player | rows | seconds |
|---|---|---|
| 10 | 200 | 0.45 |
| 20 | 400 | 1.14 |
| 40 | 800 | 3.08 |
| 80 | 1600 | 8.89 |

Roughly **2.9x per doubling** — worse than quadratic because of the inner scan plus
`.at` overhead. A real 5-season WR panel did not finish in **20 minutes** (I killed it).

The weekly `tuesday` run confirms the cost end to end:
`state/logs/tuesday-2026-w3-*.json` records the projections stage at
**2047.94 seconds (34 minutes)**.

The whole function can be rewritten vectorized per player with `numpy` cumulative sums,
which would be orders of magnitude faster. This is the highest-value performance fix in the
repository.

### 4.2 HIGH — Stage H recomputes the peer mean and std for every row

`highlights.py:239` calls `oriented_z_score` inside a per-row loop and `scoring.py:39-47`
re-filters and re-converts the entire peer list and recomputes `mean`/`std` each time. Mean
and sigma are per-(group, stat) constants.

Measured: **188,506,595 redundant float operations** for one board; `_board_from_peers(2026,3)`
takes **15.96 s**. Hoisting the two constants out of the loop is a ~5-line change.

### 4.3 HIGH — the same parquet is re-read 6x per publish

Instrumented during a real `publish_all(2026, 3, groups=["qb"])`:

```
READ data/ytd/ytd_qb_2026_w3_pct.parquet   [ramp_hold.py:109 <- :91 <- :99]
READ data/ytd/ytd_qb_2026_w3_pct.parquet   [leaderboard.py:64 <- :133 <- :164]
READ data/ytd/ytd_qb_2026_w3_pct.parquet   [ramp_hold.py:109 <- :91 <- :99]
READ data/ytd/ytd_qb_2026_w3_pct.parquet   [publish.py:284 <- publish.py:528]
READ data/ytd/ytd_qb_2026_w3_pct.parquet   [ramp_hold.py:109 <- :91 <- :99]
```

`ramp_hold.completed_week_for` is called from seven sites and has **no memoization**, even
though it is a pure function of immutable inputs within one command.

### 4.4 HIGH — 32.5 MB of uncompressed JSON on the wire

| dir | files | bytes |
|---|---|---|
| `pages/` | 4137 | 10.3 MB |
| `league/` | 16 | 6.2 MB |
| `leaderboards/` | 16 | 7.5 MB |
| `dists/` | 44 | 8.3 MB |
| `index/` | 3 | 0.1 MB |
| `highlights/` | 2 | 0.1 MB |
| **total** | **4218** | **~32.5 MB** |

No gzip/zstd anywhere in `src/ballnet`. Measured gzip ratio on
`leaderboards/2026/w3/qb.json`: **0.0827** (261 KB -> 21.7 KB). Half of `pages/` is also
written twice (`publish.py:323-327` writes the season slice and the `current/` duplicate).

### 4.5 MEDIUM — frontend refetches identical objects

`ballnet-store.ts:68,81,229` wraps loaders in React `cache()`. That works in the build-time
RSC pass (`players.ts` uses it correctly, and 1440 pages prerender fine), but
`PlayerPageClient.tsx:66` and `ComparePageClient.tsx:129` are `"use client"` components where
`cache()` is a no-op passthrough. Selecting 4 players on Compare issues **4 identical fetches
of the same `league/{season}/w{week}/{group}.json`**.

Note that the newer `projections.ts` already solves this correctly with an `immutableCache`
of shared promises plus `raceAbort` (and documents at length why the shared request must not
be bound to one caller's AbortSignal). The older store should adopt that pattern.

---

## 5. What is genuinely strong (keep and show these)

1. **The CRPS forest and its validation protocol.** Rolling-origin week-ahead folds, a real
   baseline, clustered bootstrap CIs, coverage and tail hard stops. This is the story.
2. **The release gate.** `release_decision()` refuses to ship a failing promoted position and
   forces a written caveat otherwise. Very few hobby projects do this.
3. **Pointer-last immutable publishing** in `storage.py`, with remote SHA-256 verification,
   a CAS guard against a concurrent pointer move, a measured 180 s edge-lag allowance, and
   separate staging/production rollback paths.
4. **Leakage discipline.** `live_data.py:306` derives an as-of timestamp and a 4-hour buffer
   so no same-week game can enter a row's own features; `_normalize_weekly` upper-cases
   positions and maps FB/HB to RB; `quality.py:validate_position` raises if
   `vegas_implied_team_pts` appears in any feature set, and refuses a fold containing a
   future row.
5. **Fingerprinting everywhere.** `training_fingerprint`, `configFingerprint`,
   `featureFingerprint`, `sourceFingerprint`, `drawSha256`, plus per-partition source
   checksums in `source_metadata`.
6. **The Python/TypeScript stat catalogs are in sync.** I compared all 134 definitions
   across both languages on every mirrored field: **zero semantic divergence**. Id sets
   match exactly. (The remaining differences are `denom` strings — Python holds machine keys
   like `ngs_weeks`, TypeScript holds display labels like `"NGS week"` — plus the
   label/section/source/zeroMass fields TypeScript adds. That is intentional, not drift.)
   Three `denom` pairs are worth a second look because the *labels* disagree on meaning
   (`qb.time_to_throw` `ngs_weeks` vs `"NGS pass attempts"`, `ol.penalties` `games` vs
   `"snap-weeks"`, `kicker.fg_40_49` `fg_att` vs `"attempts in bucket"`), but the Python
   machine keys are the ones that drive qualification.
7. **Cross-language math parity.** Python `_kde_cdf` and TS `kdeCdf` implement the same
   trapezoid rule and match exactly.
8. **ADRs and BOUNDARIES files.** 15 ADRs, plus `BOUNDARIES.md` files with explicit
   Always/Ask-First/Never lists. This is real engineering discipline.

---

## 6. Highest-value changes, in order

1. **Un-ignore `backend/local_ops/projections/src/`, `tests/`, and `contract/`.** Ship the
   model code, its tests, and the quality report. Keep caches, artifacts, `.venv`, and
   secrets ignored. This single change transforms the project from "ETL pipeline" into
   "ML engineering project" and is worth more than everything else combined.
2. **Add CI that runs tests, lint, and typecheck.** `.github/workflows/deploy-pages.yml`
   only builds. Your 8 lint errors and your zero-test backend are invisible today.
3. **Write ~15 unit tests for `ballnet`'s pure functions.** `ramp_week`, `_slice_row`,
   `resolve_rank_kind`, `min_n`, `passer_rating`, `_kde_cdf`, `snap_one_in_n`. Bugs 3.1,
   3.2, 3.4 would all have been caught. This is a few hours of work.
4. **Fix the two CRITICAL bugs** (`--no-current` clobber; `completedWeek` fabrication).
5. **Vectorize `_add_lags`** and memoize `completed_week_for`. Recovers most of the 34 minutes.
6. **Hoist mean/std in Stage H** and **enable gzip** on the published JSON.
7. **Make `local_ops` the canonical source in the README**, with the quality table inline.
8. **Adopt the `immutableCache` pattern** from `projections.ts` in `ballnet-store.ts`.
9. **Add a provenance manifest to `ballnet` output** — git SHA, catalog version, raw input
   fingerprint — mirroring what `projection_ops` already records.
10. **Clean up small items**: unused Vercel SVG assets in `frontend/public/`, 5 unused-var
    warnings in `highlights.ts`, the duplicated position-group set in `density.py:165` /
    `percentiles.py:29` (use `registry.POSITION_GROUPS`), and the 1075-line
    single-function `cli.py` dispatcher.
