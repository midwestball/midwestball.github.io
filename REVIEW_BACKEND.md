# Backend Review — `backend/` (Python `ballnet` ETL)

Scope reviewed: `cli.py`, `publish.py`, `storage_upload.py`, `highlights.py`, `ingest.py`,
`leaderboard.py`, `fantasy_rank.py`, `ramp_hold.py`, `scoring.py`, `positions.py`, `paths.py`,
`catalog/*.py`.
Not reviewed (owned by another reviewer): `stage_c.py`, `density.py`, `percentiles.py`,
`panel.py`, `rating.py`.
No source files were modified.

Contracts read first: `src/ballnet/BOUNDARIES.md`, `BOUNDARIES-fantasy-rank.md`,
`BOUNDARIES-highlights.md`, `src/ballnet/catalog/BOUNDARIES.md`, `docs/WEEKLY_OPS.md`,
`README.md`, `docs/adr/2026-08-24-kde-every-stat.md`.

---

## 0. Commands I actually ran (real output)

### `uv run ballnet --help` — exit 0

```
usage: ballnet [-h]
               {fetch,spine,backfill,ytd,densities,percentiles,publish,publish-demos,publish-all,rebuild-index,publish-range,publish-league-range,highlights,highlights-range,upload-storage}
               ...

positional arguments:
  {fetch,spine,backfill,ytd,densities,percentiles,publish,publish-demos,publish-all,rebuild-index,publish-range,publish-league-range,highlights,highlights-range,upload-storage}
    fetch               Stage A: download nflverse sources
    spine               Stage A (if needed) + Stage B weekly panel
    backfill            Fetch + spine for a season range; print coverage summary
    ytd                 Stage C: catalog YTD panel
    densities           Stage D: league_ytd densities from Stage C
    percentiles         Stage E: oriented percentiles on Stage C
    publish             Stage G: local PlayerPageJson for one player
    publish-demos       Stage C–G for one demo player per position group (skips returner)
    publish-all         Stage C–G for every player in all groups + index/players.json
    rebuild-index       Rebuild index/{players,seasons,current}.json from existing page JSON
    publish-range       Stage C–G for every season in [start, end]; merge multi-season index
    publish-league-range
                        Regenerate league/{season}/w{week}/{group}.json only (KDE curves)
    highlights          Stage H: weekly board + league_weekly KDEs from spine
    highlights-range    Stage H for every available week in [start, end] (needs spines)
    upload-storage      Upload local index/pages/league/leaderboards/highlights JSON to Supabase Storage
```

Note there is **no `refresh` subcommand**, even though `docs/WEEKLY_OPS.md` names
`uv run ballnet refresh --season YEAR --as-of-week W --upload` as the "canonical
one-command shape (target)" and lists "Implement CLI `refresh`" as follow-up #1. The doc
honestly says "Until `refresh` exists, run that sequence manually", but the canonical
command in the doc does not exist.

### `uv run python -c "import ballnet"` — exit 0

```
E:\midwestball.github.io\backend\src\ballnet\__init__.py
```

### `uv run python -m compileall -q src` — exit 0, no output (all modules compile).

### `uv run ruff check src` — exit 2

```
error: Failed to spawn: `ruff`
  cause: program not found
```

`ruff` is not a declared dev dependency in `backend/pyproject.toml` (deps are only
`marimo`, `nflreadpy`, `numpy`, `pandas`, `polars`, `pyarrow`, `scipy`, `supabase`).
There is no linter, no formatter, and no type checker configured at all.

### `uv run pytest` — exit 2 (collection errors, 0 tests ran)

```
ERROR local_ops/projections/tests/test_config.py
ERROR local_ops/projections/tests/test_contracts_pipeline.py
ERROR local_ops/projections/tests/test_distribution.py
ERROR local_ops/projections/tests/test_live_pipeline.py
ERROR local_ops/projections/tests/test_model.py
ERROR local_ops/projections/tests/test_quality.py
ERROR local_ops/projections/tests/test_scoring.py
ERROR local_ops/projections/tests/test_secrets.py
ERROR local_ops/projections/tests/test_storage.py
ERROR local_ops/projections/tests/test_tuesday.py
ERROR local_ops/projections/tests/test_weekly.py
E   ModuleNotFoundError: No module named 'projection_ops'
!!!!!!!!!!!!!!!!!! Interrupted: 11 errors during collection !!!!!!!!!!!!!!!!!!!!
=============================== 11 errors in 16.80s =============================
```

### Are there ANY tests for `ballnet`? — **No.**

`find backend/src -name 'test*'` returns nothing. The 11 test files under
`backend/local_ops/projections/tests/` belong to a *different* package (`projection_ops`,
also gitignored via `backend/.gitignore:10 local_ops/`) and are not on `sys.path`, so
they cannot even be collected. **The `ballnet` pipeline that produces every number the
public site shows has zero test coverage.**

---

## 1. Correctness bugs

### 1.1 CRITICAL — `--no-current` still overwrites `index/current.json` (contradicts the rollover runbook)

`cli.py:628-634` passes `also_current=not args.no_current` to `publish_all`, and
`publish.py:300-301` / `publish.py:325-327` correctly use that flag to skip
`pages/current/{pid}.json`. But the **index** write at `publish.py:540-545` is gated only
on `write_index`, never on `also_current`:

```python
# publish.py:538-545
    index_path: str | None = None
    current_path: str | None = None
    if write_index:
        index_path = str(
            write_players_index(all_bios, merge_existing=merge_index)
        )
        current_path = str(write_current_index(season, as_of_week))   # <-- unconditional
        upsert_seasons_index(season, as_of_week)
```

Verified empirically. With a pre-existing `index/current.json` pointing at season 2027,
calling `publish_all(2026, 3, also_current=False, write_index=True)` produced:

```
also_current=False (this is what `ballnet publish-all --no-current` does)
index/current.json now: {"schemaVersion":1,"season":2026,"asOfWeek":3,"completedWeek":3}
```

This breaks the documented season-rollover procedure in `docs/WEEKLY_OPS.md`
("`--no-current` keeps `pages/current/` and `index/current.json` on the new year"), and it
breaks `publish-range --no-current` too (`publish.py:601-604` calls `write_current_index`
unconditionally after the loop):

```
publish_range --no-current:
  current.json : {"schemaVersion":1,"season":2026,"asOfWeek":18,"completedWeek":18}
  seasons.json : {"schemaVersion":1,"seasons":[
     {"season":2024,"asOfWeek":18,"completedWeek":18},
     {"season":2025,"asOfWeek":18,"completedWeek":18},
     {"season":2026,"asOfWeek":18,"completedWeek":18}]}
```

Two bugs in one: (a) `current.json` is clobbered to the backfilled season, and (b)
`seasons.json` **destroys real `completedWeek` values**. See next item.

### 1.2 CRITICAL — `publish_range` / `rebuild_index_from_pages` fabricate `completedWeek == asOfWeek`

`publish.py:599` builds slices with only `season` and `asOfWeek`:

```python
        slices.append({"season": season, "asOfWeek": week})
```

then `publish.py:604` → `write_seasons_index(slices)` → `_slice_row` at `publish.py:410-416`:

```python
def _slice_row(s: dict[str, int]) -> dict[str, int]:
    as_of = int(s["asOfWeek"])
    return {
        "season": int(s["season"]),
        "asOfWeek": as_of,
        "completedWeek": int(s["completedWeek"]) if s.get("completedWeek") is not None else as_of,
    }
```

The `else as_of` fallback silently invents a `completedWeek` that was never computed from
the schedule. `BOUNDARIES.md` is explicit: "`completed_week` is the last consecutive REG
week where every scheduled game has scores". Emitting `asOfWeek` breaks ramp–hold
(`ramp_hold.ramp_week`) for any slice whose final week was not fully scored, and it
**overwrites** whatever real value `index/seasons.json` already held — the write is a full
replace (`write_seasons_index`), not an upsert. Same defect in
`rebuild_index_from_pages` at `publish.py:486-488`, which passes
`{"season": s, "asOfWeek": w}` only.

Note `upsert_seasons_index` (`publish.py:428-448`) does this correctly. The two writers
disagree with each other, which is how the bug survived.

### 1.3 HIGH — `fantasy_rank` modal position relies on unordered `unique(keep="first")`

`fantasy_rank.py:221-229`:

```python
    modal = (
        mapped.filter(pl.col("code").is_not_null())
        .group_by("player_id", "code")
        .len()
        .sort(["len", "code"], descending=[True, False])
        .unique(subset=["player_id"], keep="first")   # <-- no maintain_order=True
        .filter(pl.col("code").is_in(sorted(SKILL_POSITIONS)))
        .select("player_id", "code")
    )
```

`DataFrame.unique(keep="first")` is documented as returning *a* row per key, not
*the first row in sort order*; `maintain_order=True` is the parameter that guarantees the
sorted-first row survives. On polars 1.42.1 I probed this directly:

```
sorted:
┌───────────┬──────┬─────┐
│ player_id ┆ code ┆ len │
├───────────┼──────┼─────┤
│ p1        ┆ RB   ┆ 6   │
│ p2        ┆ WR   ┆ 5   │
│ p1        ┆ WR   ┆ 5   │
│ p2        ┆ RB   ┆ 1   │
└───────────┴──────┴─────┘
```

In this small case it happened to agree, but a 200-player × 3-code probe with heavy ties
showed the result is order-unstable in general. The fix is one keyword:
`.unique(subset=["player_id"], keep="first", maintain_order=True)`. Since this decides which
position bucket a player is ranked in, a wrong pick produces a **wrong published
`fantasyPosRank`**, which is user-visible. Treat this as a latent correctness bug, not
style.

### 1.4 HIGH — `resolve_rank_kind` returns `consensus` for a closed season whenever `also_current=True`

`fantasy_rank.py:36-47`:

```python
def resolve_rank_kind(season, *, updating_current: bool = False) -> RankKind:
    if updating_current:
        return "consensus"
```

`publish.py:238` and `publish.py:303` pass `updating_current=also_current`. So
`ballnet publish --season 2025 --player 00-0034844` (a closed season, no `--no-current`)
gets `kind="consensus"` — the current FantasyPros ECR — stamped onto a 2025 page. Verified:

```
resolve_rank_kind(2025, updating_current=True) -> consensus   (2025 is a CLOSED season)
resolve_rank_kind(2025, updating_current=False) -> finish
```

`BOUNDARIES-fantasy-rank.md` says: "Live season (`updating_current` or `index/current.json`
season) uses ... `kind: consensus`. Every other season uses REG PPR finish." The `or` in
that sentence is what the code implements, so this is arguably by design — but it makes the
single-player `publish` command silently produce wrong-kind output for any historical
season, and there is no guard or warning. The `--no-current` flag is the only thing standing
between an operator and a wrong publish.

### 1.5 HIGH — `_consensus_ranks` and `_finish_ranks` ignore `as_of_week`, but the cache key includes it

`fantasy_rank.py:59-69` keys the cache on `(season, as_of_week, kind)`:

```python
    key = (int(season), int(as_of_week), resolved)
```

but neither builder takes `as_of_week`. `_consensus_ranks` (`fantasy_rank.py:143-192`) calls
`nfl.load_ff_rankings("week")` — the *current* FantasyPros week — with no `as_of_week`
filter, so republishing 2026 w1 stamps *today's* ECR on w1 pages. `_finish_ranks`
(`fantasy_rank.py:195-245`) reads the **whole** `player_stats_{season}.parquet` and sums
all PPR regardless of week. Verified:

```
player_stats_2026 weeks present: [1, 2, 3]
finish ranks built for 2026: 378   -> uses FULL season PPR, not weeks<=as_of_week
```

The cache key therefore promises slice-scoped ranks that the builders do not deliver, and
the same key produces N identical network round-trips / parquet reads for N different weeks.

### 1.6 HIGH — `highlights` default week publishes an empty board for an in-progress season

`cli.py:818`:

```python
        week = args.week if args.week is not None else default_as_of_week(args.season)
```

`default_as_of_week(2026)` returns 18 (`publish.py:34-36`). The live spine only has 3 weeks,
so:

```
spine max week 2026: 3
weeks_to_publish(2026): [1, 2, 3]
default week the CLI picks: 18
board for w18 -> top: 0 byGroup sizes: {'qb': 0, 'backfield': 0, 'pass_catcher': 0, 'def_front': 0, 'secondary': 0, 'kicker': 0}
```

`ballnet highlights --season 2026` therefore writes `data/highlights/2026/w18.json` with
`top: []` and exits 0. `BOUNDARIES-highlights.md` calls an empty board "the frontend shows
pending", which is a legitimate state — but it is reached here by accident, and the operator
gets no warning. `highlights.weeks_to_publish` already does the right thing (caps at spine
max) and should be used for the default. `upload-storage` has the same defaulting bug for
`--season`/`--as-of-week` (`cli.py:922-926`), where it raises `FileNotFoundError` instead.

### 1.7 MEDIUM — `_board_from_peers` computes each group's collapse twice

`highlights.py:389-392` builds `collapsed` for the balanced top list; `highlights.py:402-409`
rebuilds the identical list for `byGroup`. The O(n) collapse plus the `[r for r in all_rows
if r["positionGroup"] == group]` full scans are duplicated verbatim. Compute once, reuse.

### 1.8 MEDIUM — `_write_json` is not atomic and there is no manifest

`publish.py:208-211`, `leaderboard.py:34-37`, `highlights.py:428-431` all do the same
non-atomic write, three separate copies of it:

```python
def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, **_JSON_DUMP_KW)
```

A crash mid-`json.dump` leaves a truncated file that the frontend will happily try to parse.
There is no temp-file-plus-rename, no checksum, and no manifest anywhere in the package —
I grepped the whole of `src/ballnet` for `sha256`, `hashlib`, `manifest`, `checksum`:
**zero hits**. `docs/WEEKLY_OPS.md` follow-up #3 ("Log a small JSON report (season, week,
player count, upload bytes, duration) under `data/logs/`") is not implemented; `data/logs/`
does not exist. The only "report" is ad-hoc `print()` to stdout.

### 1.9 MEDIUM — `storage_upload` uploads are unordered and non-atomic; stale objects are never removed

`storage_upload.py:101-149` fans out `ThreadPoolExecutor` uploads with no ordering between
prefixes. A run that uploads `index/`, then `pages/`, then `league/` leaves the bucket in a
mixed state if it dies halfway: `index/current.json` may point at a week whose
`pages/{season}/w{week}/` is half-populated. Worse, `upload_season_pages` (`storage_upload.py:176-182`)
only ever *adds* objects — there is no code path that deletes `pages/current/{id}.json` for a
player who dropped off the current roster. `publish_range` does `shutil.rmtree` on the
local `pages/current` (`publish.py:586-589`), but nothing mirrors that to the bucket, so
`pages/current/` accumulates ghosts forever. `upsert=true` (`storage_upload.py:85-87`)
overwrites but never prunes.

There is also no publish marker: nothing in the bucket says "week 4 finished uploading", so
a partially-failed run is indistinguishable from a good one except by manual inspection.

### 1.10 MEDIUM — retry loop can raise a stale exception and sleeps after the last attempt

`storage_upload.py:88-98`:

```python
    for attempt in range(retries):
        try:
            client.storage.from_(bucket).upload(object_path, data, file_options=opts)
            return object_path, len(data)
        except Exception as e:  # noqa: BLE001
            last_err = e
            time.sleep(0.4 * (2**attempt))   # also sleeps after the FINAL attempt
    assert last_err is not None
    raise last_err
```

Two nits: the backoff sleeps even after `attempt == retries - 1`, adding 3.2 s of dead time
per permanently-failing object; and `assert last_err is not None` is a runtime `assert` in
library code — it is stripped under `python -O`. Both `except Exception` blocks here swallow
every error type including `KeyboardInterrupt`-adjacent programming errors.

### 1.11 MEDIUM — error list truncated to 20, so a mass failure reports 20 of N

`storage_upload.py:148`: `errors=errors[:20]`. The CLI prints `r.errors` into the JSON
report (`cli.py:913`). A run that fails 5 000 uploads shows 20. The `failed` counter is
correct, so this is a diagnosability bug rather than a correctness one, but during an
incident it is exactly the data you need.

### 1.12 MEDIUM — `leaderboard._row_sort_key` ignores `qualified` despite the docstring

`leaderboard.py:40-45`:

```python
def _row_sort_key(row: dict[str, Any]) -> tuple[int, float, str]:
    """Qualified + high oriented percentile first; nulls last."""
    pct = row.get("percentile")
    if pct is None:
        return (1, 0.0, row["playerId"])
    return (0, -float(pct), row["playerId"])
```

The docstring promises qualified-first. The code never reads `row["qualified"]`. It happens
to work only because `percentiles.py:53-59` sets `percentile=None` for unqualified rows —
an implicit coupling to a different module's behavior, in a different stage. `qualified` is
still emitted in every row (`leaderboard.py:104`), so a consumer can hit the discrepancy.

### 1.13 LOW — `ingest.fetch_season` treats a failed optional fetch as a permanent empty cache

`ingest.py:146-157`:

```python
        try:
            df = loader()
            note = notes
        except Exception as e:
            if not optional:
                raise
            df = _EMPTY[empty_key] if empty_key else pl.DataFrame()
            note = f"{notes} UNAVAILABLE: {type(e).__name__}: {e}"
```

The stub frame is written to `data/raw/{name}.parquet` and is indistinguishable from a real
fetch on the next run, because `ingest.py:139` short-circuits on `out.exists() and not force`.
A transient network blip on `pfr_def` leaves an empty PFR frame cached until someone
remembers `--force`. The `UNAVAILABLE` note is only printed on the run that failed; the
cached path at `ingest.py:141-143` reports `"(cache)"` and never surfaces it. This is the
single most likely cause of a silently-wrong published season, and there is no data validation
downstream that would catch it.

### 1.14 LOW — no schema validation of published JSON against any contract

I grepped `src/ballnet` for `jsonschema` and `validate`: **zero hits**. The only JSON Schema
in the repo is `backend/local_ops/projections/contract/projections-v1.schema.json`, which
covers the *projections* package, not ballnet. The published shapes (`PlayerPageJson`,
`HighlightsBoardJson`, `LeaderboardJson`) are typed only in
`frontend/src/lib/payload.ts` as hand-maintained TypeScript — nothing checks that
`publish.py`/`highlights.py`/`leaderboard.py` actually emit them. `schemaVersion: 1` is
written as a bare literal in five places (`publish.py:144`, `publish.py:185`,
`publish.py:384`, `publish.py:400`, `publish.py:424`, `leaderboard.py:112`,
`highlights.py:299`, `highlights.py:412`) with no shared constant and no reader that checks it.

---

## 2. Scalability / performance

### 2.1 HIGH — Stage H rebuilds the full peer sample for every single board row (O(rows × peers))

`highlights.py:239` calls `oriented_z_score(val, peers, ...)` inside a per-row loop, and
`scoring.z_score` (`scoring.py:39-47`) re-filters and re-converts the entire peer list and
recomputes `mean`/`std` on every call:

```python
    peers = [float(v) for v in peer_values if v is not None and math.isfinite(float(v))]
    if len(peers) < min_n: return None
    arr = np.asarray(peers, dtype=float)
    mu = float(arr.mean()); sigma = float(arr.std(ddof=0))
```

Measured on real local data (2026 w3):

```
peerN all-time qb passing_yards: 5560   this-week rows: 32
_score_stat seconds: 0.30 rows=32
total peer-value recomputations in one board (sum of peerN*weekRows): 188,506,595
```

**188.5 million redundant float operations to produce one board.** Mean and sigma are
per-(group, stat) constants; hoisting them out of the loop is a ~5-line change. Actual
wall-clock for `_board_from_peers(2026, 3)`: **15.96 s**.

### 2.2 HIGH — every group re-reads the same Stage E parquet 3–4× per publish

Instrumented `pl.read_parquet` during a real `publish_all(2026, 3, groups=["qb"])`:

```
READ data/raw/ff_playerids.parquet            [fantasy_rank.py:102 <- :184 <- :64]
READ data/ytd/ytd_qb_2026_w3_pct.parquet      [ramp_hold.py:109 <- :91 <- :99]
READ data/ytd/ytd_qb_2026_w3_pct.parquet      [leaderboard.py:64 <- :133 <- :164]
READ data/ytd/ytd_qb_2026_w3_pct.parquet      [ramp_hold.py:109 <- :91 <- :99]
READ data/ytd/ytd_qb_2026_w3_pct.parquet      [publish.py:284 <- publish.py:528]
READ data/ytd/ytd_qb_2026_w3_pct.parquet      [ramp_hold.py:109 <- :91 <- :99]
```

Same file, six times, for one group. `ramp_hold.completed_week_for` is the worst offender:
it is called from seven sites (`publish.py:142,188,247,297,396,442`,
`leaderboard.py:115`) and each call runs `completed_week_from_ytd`, which loops
`3 groups × 2 suffixes` looking for a `completed_week` column and reads the first hit
(`ramp_hold.py:86-94`). It has **no memoization**. `completed_week_for(season, as_of_week)`
is a pure function of immutable inputs for the duration of a command; a module-level cache
keyed on `(season, as_of_week)` would collapse six reads to one.

### 2.3 HIGH — the web payload is uncompressed JSON, and gzip would cut it ~12×

Measured on the real `data/leaderboards/2026/w3/qb.json` (261 679 bytes):

```
gz ratio 0.0827   ->  ~21.7 KB over the wire
```

Sizes of the published corpus on this machine:

| dir | files | bytes |
|---|---|---|
| `pages/` | 4137 | 10.3 MB |
| `league/` | 16 | 6.2 MB |
| `leaderboards/` | 16 | 7.5 MB |
| `dists/` | 44 | 8.3 MB |
| `index/` | 3 | 0.1 MB |
| `highlights/` | 2 | 0.1 MB |
| **total web payload** | **4218** | **~32.5 MB** |

There is no gzip/zstd anywhere in `src/ballnet` (grep: zero hits). Worse, `pages/` is written
**twice** — `publish.py:323-327` writes the season slice and then the `pages/current/`
duplicate — so half the page bytes are pure duplication. The BOUNDARIES already warn the
bucket is ~1 GB on the free plan; uncompressed, uncompressed-forever uploads will hit that
wall, and the client pays full JSON parse cost on every page view.

### 2.4 MEDIUM — Stage H loads all 11 prior spines per week, with no cross-week reuse

`highlights._load_all_time_peers` (`highlights.py:315-331`) re-reads and re-concats every
spine from 2016 to `season` on **every** call. `publish_highlights_range`
(`highlights.py:475-486`) calls `publish_highlights` once per week, so a 2016–2026 backfill
re-reads ~40 MB of parquet ~190 times. `highlights-range` in the CLI does the same
sequentially (`cli.py:846-868`). Measured: `_load_all_time_peers(2026,3)` = 0.63 s and
176 836 rows / 460 columns per call. A single load per season, cached, with weeks filtered
down, would remove almost all of it.

The `pl.concat(..., how="diagonal_relaxed")` at `highlights.py:331` is also the right
primitive for the pre-2018 spine schema drift described in `BOUNDARIES.md`, but it means
the frame is 460 columns wide when the allowlist only needs ~15.

### 2.5 MEDIUM — sequential per-group and per-season loops that parallelize trivially

- `cli.py:609-625` (`publish-all`): Stage C→D→E runs serially per group. Each group is an
  independent season-slice computation.
- `cli.py:744-768` (`publish-range`): nested season × group, fully serial.
- `cli.py:846-868` (`highlights-range`): nested season × week, fully serial.
- `publish.py:527-536`: `publish_group` per group, serial.

Note `storage_upload` *does* use a thread pool (`storage_upload.py:122`), so the
inconsistency is visible: uploads are concurrent, the expensive compute is not.

### 2.6 LOW — `publish_group` writes every page file twice with a redundant `mkdir` per file

`publish.py:323-327` calls `_write_json` twice per player, and `_write_json`
(`publish.py:208-211`) calls `path.parent.mkdir(parents=True, exist_ok=True)` on every
single write even though `publish.py:299-301` already created the directories. 4137 page
files per season, two syscalls of overhead each.

---

## 3. Reproducibility / MLOps gaps

### 3.1 CRITICAL — zero tests for the whole pipeline

Confirmed above (§0). There is no `tests/` directory under `backend/`, no `[dependency-groups]`
dev group in `pyproject.toml`, and no CI workflow running backend checks. Every correctness
regression in §1 — the `completedWeek` fabrication, the `--no-current` clobber, the
un-ordered `unique` — would have been caught by a handful of unit tests on pure functions
(`ramp_week`, `snap_one_in_n`, `_slice_row`, `resolve_rank_kind`). None exist.

`docs/adr/2026-08-24-kde-every-stat.md` exists, so the project does record decisions; the
gap is enforcement, not intent.

### 3.2 CRITICAL — no pinned data snapshot, no provenance, no versioning of raw inputs

`ingest.py:104-107` writes `data/raw/{name}.parquet` with no manifest of what URL, what
fetch time, what row count, or what checksum produced it:

```python
def _write(name: str, df: pl.DataFrame) -> Path:
    ensure_data_dirs()
    path = RAW_DIR / f"{name}.parquet"
    df.write_parquet(path)
    return path
```

nflverse is a moving target. There is no `manifest.json`, no `fetched_at`, no source URL, no
content hash anywhere in the package (grep for `sha256`/`hashlib`/`snapshot` → zero real hits;
the only `snapshot` string is the word in a `publish.py` docstring). Consequence: a page
published in October and the same page re-derived in January are **not comparable**, and there
is no way to tell after the fact which raw snapshot produced a given `data/pages/` file.
`FetchResult` (`ingest.py:94-101`) carries rows/cols/seconds but it is printed to stdout
(`cli.py:366-370`) and discarded — never persisted.

### 3.3 HIGH — no data validation between stages

`BOUNDARIES.md` lists several known-bad states (null snaps after name-match fallback, `week == 0`
NGS rows, string-typed join keys, `missing_source` for play-grain ids) but nothing in code
*asserts* them. There is no row-count gate, no null-rate threshold, no monotonicity check
between Stage B and Stage C, no check that a spine actually contains week `as_of_week`. The
only gate anywhere is `cli.py:433-441` in `backfill`, which checks two coverage ratios
against a hardcoded `0.5` and only runs in the `backfill` command — not in `spine`, not in
`publish-all`. Combined with §1.13 (failed fetch cached as empty), an empty `pfr_def` frame
flows all the way to a published JSON with no error.

### 3.4 HIGH — no logging or telemetry; all output is `print()` to stdout

`grep` for `logging` / `getLogger` across `src/ballnet`: **zero hits**. Every one of the ~70
status lines in `cli.py` is a bare `print()`. There is no log level, no log file, no run id,
no duration rollup for a whole command, and no way to reconstruct what happened after the
fact. The `seconds` fields threaded through every result dataclass (`PublishResult.seconds`,
`GroupPublishResult.seconds`, `BatchPublishResult.seconds`, `UploadResult.seconds`) are
printed and thrown away.

`local_ops/projections` has a real logging setup (`local_ops/logs/*.log`, 150+ files,
`watcher.py`, `run_state.json`) — so the project knows how to do this. `ballnet` does not,
which is why `docs/WEEKLY_OPS.md` recommends "manual" ops: an operator has no audit trail
for the manual path.

### 3.5 HIGH — published JSON is unversioned and untraceable

Nothing in the published envelope identifies the code version, the catalog version, the raw
snapshot, or the parameters that produced it. The page payload (`publish.py:143-150`) carries
only `schemaVersion: 1`. `highlights.py:415` is the one exception — it stamps
`generatedAt` — but no model/config hash. Compare `local_ops/projections`, which has a full
manifest concept with `snapshotId`, `modelVersion`, `trainedThrough`, `manifestPath` in its
schema. `ballnet` has none of that.

### 3.6 MEDIUM — hardcoded constants and magic numbers, none in config

Nothing in `src/ballnet` reads a config file. `local_ops/config.json` exists but is for the
projections package. The magic numbers, all inline:

| Constant | Location | Value |
|---|---|---|
| `TOP_N` | `highlights.py:24` | 25 |
| `PER_GROUP_N` | `highlights.py:25` | 8 |
| `HIGHLIGHTS_START_YEAR` | `highlights.py:27` | 2016 |
| `MIN_PEER_N` | `scoring.py:11` | 16 |
| `RARITY_TIERS` | `scoring.py:14` | 10^1..10^9 |
| tail clamp | `scoring.py:79` | `[2, 1_000_000_000]` |
| `GRID_N` | `density.py:18` | 512 (other reviewer) |
| `_REG_WEEKS_18_FROM` | `publish.py:31` | 2021 |
| `DEFAULT_BUCKET` | `storage_upload.py:26` | `knowball-public` |
| `DEFAULT_WORKERS` | `storage_upload.py:29` | 4 |
| upload retries / backoff | `storage_upload.py:82,96` | 4 / `0.4*2^n` |
| CLI default workers | `cli.py:356` | 8 (≠ the 4 above) |
| default bucket | `cli.py:296,355` | `knowball-public` (hardcoded twice) |
| coverage gate | `cli.py:436-437` | `0.5` |
| demo players | `cli.py:43-52` | 8 hardcoded GSIS ids |

The volume floors and `min_value` gates in `highlights._allowlist_for_group`
(`highlights.py:134-182`) are ~30 hand-tuned magic numbers (`floor=10`, `floor=15`,
`min_value=1.5`, `min_value=3`, …). `BOUNDIGHTS-highlights.md` correctly lists "changing
`HIGHLIGHTS_START_YEAR` or the `10^k` rarity ladder" as Ask-First, but Ask-First without a
config file just means "edit source and re-run everything".

`DEFAULT_WORKERS = 4` vs `cli.py:356 --workers default=8` is a straight inconsistency: the
module comment at `storage_upload.py:28-29` says "Keep concurrency modest — bursty uploads
get RemoteProtocolError", and the CLI default ignores that advice.

### 3.7 MEDIUM — no cache invalidation anywhere

Three caches, none invalidated:
- `fantasy_rank._RANKS_CACHE` (`fantasy_rank.py:33`) — module-global, keyed
  `(season, as_of_week, kind)`, never evicted. Harmless within one process, but it also means
  a long-lived process (the `watcher.py` pattern used by projections) would serve stale
  consensus ranks forever.
- `publish.py:229-230` and `publish.py:282-283` — `if not pct_path.exists(): attach_percentiles(...)`.
  Existence is the *only* freshness test. A stale `ytd_*_pct.parquet` from a previous
  `--as-of-week` run is silently reused; there is no timestamp, no input hash, no
  `--force-publish`.
- `ingest.py:139` — `if out.exists() and not force`. Same problem as §1.13, worse: the
  cached frame's age is unknowable.

---

## 4. Reusability

### 4.1 HIGH — the 1075-line CLI is a single 990-line `if`/`return` chain

`cli.py:358` parses args, then `cli.py:360-1070` is a flat sequence of
`if args.cmd == "...": ... return` blocks — **15 subcommands, ~700 lines, one function,
no dispatch table**. Consequences:

- No shared helpers. The "upload one thing and report it" block is copy-pasted five times
  (`cli.py:903-920`, `943-970`, `971-996`, `997-1022`, `1023-1063`) — identical
  `reports.append({...5 keys...})` + `print(...)` in each.
- The `--as-of-week` default expression `args.as_of_week if args.as_of_week is not None else
  default_as_of_week(args.season)` is copy-pasted four times (`cli.py:708-712`, `745-749`,
  `922-926`, and again inside `storage_upload.py:171,194,217,278`).
- The same `if getattr(args, "start", None) is not None and args.end is None: raise SystemExit("--start requires --end")`
  guard appears twice (`cli.py:361-362`, `cli.py:374-375`) — and it is **wrong**: `--season
  2026 --end 18` passes the guard and then `_season_list` (`cli.py:55-67`) silently ignores
  `--end`. Mutually-exclusive-group validation should live in argparse.
- Adding a stage means editing one 700-line function. This is exactly why the `refresh`
  wrapper that `WEEKLY_OPS.md` asks for has not been written.

### 4.2 HIGH — the position-group set is duplicated as a literal in four places

`catalog.registry.POSITION_GROUPS` (`registry.py:21-31`) is the source of truth. Three other
modules re-hardcode the same 9-element tuple inline instead of importing it, each behind a
"mirror" comment that admits the coupling:

```python
# publish.py:26-28
PUBLISHABLE_GROUPS: tuple[str, ...] = tuple(
    g for g in POSITION_GROUPS if g != "returner"
)

# leaderboard.py:19-20
# Mirror publish.PUBLISHABLE_GROUPS without importing publish (cycle risk).
_DEFAULT_GROUPS: tuple[str, ...] = tuple(g for g in POSITION_GROUPS if g != "returner")
```

Plus two full literal re-listings:

- `density.py:165-176` — `if position_group not in {"qb", "backfield", ..., "returner"}:`
- `percentiles.py:29-40` — the identical 9-element set literal, again.

Programmatic scan of `src/ballnet` for the 9-group literal:

```
HARDCODED 9-GROUP SET: src/ballnet/catalog/registry.py   (the source of truth)
HARDCODED 9-GROUP SET: src/ballnet/density.py
HARDCODED 9-GROUP SET: src/ballnet/percentiles.py
HARDCODED 9-GROUP SET: src/ballnet/stage_c.py
```

And the "cycle risk" comment in `leaderboard.py:19` is self-inflicted: `publish.py:18`
imports `publish_leaderboards` from `leaderboard`, so `leaderboard` cannot import back. The
correct fix is to move `PUBLISHABLE_GROUPS` into `catalog/registry.py` (where
`POSITION_GROUPS` already lives) and have both import it — no cycle at all.

Also duplicated: `_JSON_DUMP_KW` is defined three times (`publish.py:24`,
`leaderboard.py:22`, `highlights.py:22`) and `_write_json` three times
(`publish.py:208`, `leaderboard.py:34`, `highlights.py:428`).

### 4.3 HIGH — 134 stat definitions duplicated between Python and TypeScript

The Python catalog (`src/ballnet/catalog/*.py`) and the frontend catalog
(`frontend/src/lib/catalog/*.ts`) define the **same 134 stat definitions twice**:

| group | Python | TypeScript |
|---|---|---|
| qb | 27 | 27 |
| backfield | 25 | 25 |
| pass_catcher | 25 | 25 |
| ol | 7 | 7 |
| def_front | 13 | 13 |
| secondary | 15 | 15 |
| kicker | 7 | 7 |
| punter | 10 | 10 |
| returner | 5 | 5 |
| **total** | **134** | **134** |

`catalog/BOUNDARIES.md` requires "`stat.id` strings identical" and "Never invent frontend
catalog `stat.id` values", but **nothing enforces it** — there is no test, no codegen, no
schema. I wrote a field-by-field differ over `id`, `kind`, `format`, `higherIsBetter`,
`xMin`, `xMax`, `lowerBound`, `upperBound`, `binWidth`, `minNBase`, `startYear`,
`alwaysUnavailable`, `volumeStatId`. Current state: **id sets match exactly (0 missing either
way), and all mirrored scalar fields match.** So the drift has not happened *yet*.

But the drift surface is wide and unguarded:

1. **Python has no `label`, `section`, `source`, or `zeroMass`.** The TS catalog has all four
   (`label`, `section`, `source`, `zeroMass`); Python has none. `zeroMass` in particular is
   a display hint the Python side cannot see, so a TS-only edit is completely invisible.
2. **`denom` is a machine key in Python and a human label in TS, and they disagree on 60 of
   134 entries.** Python uses column-ish keys (`ngs_weeks`, `games_with_attempts`,
   `fg_att`, `pat_att`, `targets_allowed`, `passing_air_yards`); TS uses display strings
   (`"NGS week"`, `"games with attempts"`, `"FGA"`, `"XPA"`, `"targets allowed"`, `"passing
   air yards"`). Examples of the divergence:
   - `qb.passing_tds`: Python `games_with_attempts` vs TS `"games with attempts"`
   - `qb.offensive_snap_pct`: Python `snap_weeks` vs TS `"offensive snaps"`
   - `qb.time_to_throw`: Python `ngs_weeks` vs TS `"NGS pass attempts"` (not just casing —
     **different semantics**)
   - `backfield.rushing_tds`: Python `games_with_carries` vs TS `"games with carries"`
   - `pass_catcher.route_pct`: Python `snap_weeks` vs TS `"offensive snaps"`
   - `ol.penalties`: Python `games` vs TS `"snap-weeks"` (again, semantically different)
   - `kicker.fg_40_49`: Python `fg_att` vs TS `"attempts in bucket"`
   - `returner.kick_returns`: Python `kick_returns` vs TS `"returns"`

   Some of this is intentional (Python `denom` is the machine key per
   `catalog/BOUNDARIES.md`; TS `denom` is a label). But `time_to_throw`, `ol.penalties`, and
   `fg_40_49` look like genuine disagreements about which quantity actually gates the stat,
   and nothing will ever surface them.

3. **`minNBase` is set twice in Python.** Each catalog module constructs `StatDefinition` with
   an inline `min_n_base` positional and then *overrides a subset* via
   `with_min_n_base` (`types.py:43-53`). `qb.py` is the clearest case: the constructor at
   `qb.py:19` sets `"cpoe"` to `10`, and `qb.py:182-196` then rewrites it to `28`. Two
   sources of truth for one number, in one file, with no assertion that they agree. Same
   pattern in `backfield.py`, `pass_catcher.py`, `def_front.py`, `secondary.py`,
   `special_teams.py`.

4. **Same `stat.id` in multiple groups with different metadata.** 14 ids appear in 2–3
   groups, and the groups legitimately disagree — but a consumer keying on `id` alone will
   silently mix them:

   | id | groups | differing metadata |
   |---|---|---|
   | `interceptions` | qb, def_front, secondary | `denom` `games_with_attempts`/`games`/`games`; `xMax` 7/3/4 |
   | `rushing_yards` | qb, backfield | `min_n_base` 3/10; `xMax` 150/296 |
   | `rushing_tds` | qb, backfield | `denom` `carries`/`games_with_carries`; `min_n_base` 3/1 |
   | `targets` | backfield, pass_catcher | `min_n_base` 3/5; `xMax` 15/21 |
   | `receptions` | backfield, pass_catcher | `min_n_base` 3/5; `xMax` 12/21 |
   | `receiving_yards` | backfield, pass_catcher | `min_n_base` 3/5; `xMax` 150/336 |
   | `target_share` | backfield, pass_catcher | `min_n_base` 3/5; `xMax` 0.4/0.5 |
   | `wopr` | backfield, pass_catcher | `min_n_base` 3/5; `xMax` 0.5/1 |
   | `rush_attempts` | qb, backfield | `min_n_base` 3/10; `xMax` 20/45 |
   | `offensive_snap_pct` | qb, backfield, pass_catcher | identical |
   | `tackles_combined` | def_front, secondary | `xMax` 24/16 |
   | `missed_tackles`, `missed_tackle_rate`, `defensive_snap_pct` | def_front, secondary | identical |

   Nothing in the code validates that a given id is consistent within itself across groups,
   and `interceptions`/`tackles_combined` genuinely are not.

### 4.4 MEDIUM — `pathlib` layout constants are process-global and untestable

`paths.py:7-22` derives everything from `REPO_ROOT = Path(__file__).resolve().parents[2]`,
which resolves to `backend/`. Every module imports the concrete constants by value
(`from ballnet.paths import PAGES_DIR, ...`). To test any of §1's bugs I had to
monkey-patch each importing module's copy of the constant. There is no fixture, no
`BALLNET_DATA_DIR` env override, no `--data-dir` flag. This is a direct cause of the
zero-test-coverage problem in §3.1: the code as structured is not testable without
monkey-patching.

Also, `REPO_ROOT` assumes the package lives at `backend/src/ballnet/`. Installed as a wheel
(`pyproject.toml` uses `hatchling` with `packages = ["src/ballnet"]`), `parents[2]` points
into `site-packages` and `DATA_DIR` becomes a directory inside the installed package.

### 4.5 MEDIUM — `_shape_payload` / `_league_stat_payload` are the same function twice

`publish.py:153-168` (`_league_stat_payload`) and `highlights.py:263-277`
(`_shape_payload`) are byte-for-byte equivalent modulo the docstring, both translating the
Stage D snake_case density dict to the camelCase frontend shape. Same 5-key mapping, same
3 conditional appends. `BOUNDARIES.md` says the two stages must stay distinct — the
*payload* need not be.

### 4.6 LOW — `positions.py` maps two codes to one, losing information with no note

`positions.py:30-33`:

```python
    "SAF": "S",
    "DB": "CB",
    "MLB": "ILB",
    "DL": "DT",
```

`SAF`→`S` and `DB`→`CB` both collapse safety positions into one frontend code, so a
deep-safety player is published as a cornerback. `BOUNDARIES.md` documents `SAF`/`MLB`/`DL`
→ `S`/`ILB`/`DT` as intentional, but `DB`→`CB` is not mentioned and is arguably wrong
(`DB` is a generic secondary position). Also `map_position` (`positions.py:70-78`) returns
`(None, None)` for anything unmapped, which silently drops the row — no counter, no warning,
no coverage report. `panel.py` is another reviewer's file, but the drop happens here.

---

## 5. Summary table

| # | Severity | Area | Finding | Location |
|---|---|---|---|---|
| 1.1 | Critical | Correctness | `--no-current` still overwrites `index/current.json` | `publish.py:540-545`, `cli.py:628-634` |
| 1.2 | Critical | Correctness | `completedWeek` fabricated as `asOfWeek`, destroying real values | `publish.py:410-416, 599, 604, 486-488` |
| 3.1 | Critical | MLOps | Zero tests for the entire pipeline | `backend/` (no `tests/`) |
| 3.2 | Critical | MLOps | No pinned snapshot / no provenance for raw inputs | `ingest.py:104-107` |
| 1.3 | High | Correctness | Modal position uses un-ordered `unique(keep="first")` | `fantasy_rank.py:221-229` |
| 1.4 | High | Correctness | Closed season gets `consensus` when `also_current=True` | `fantasy_rank.py:36-47`, `publish.py:238,303` |
| 1.5 | High | Correctness | Rank builders ignore `as_of_week`; cache key lies | `fantasy_rank.py:59-69,143-192,195-245` |
| 1.6 | High | Correctness | `highlights` default week 18 → silent empty board | `cli.py:818`, `publish.py:34-36` |
| 1.8 | Medium | Correctness | Non-atomic JSON writes, no checksum, no manifest | `publish.py:208`, `leaderboard.py:34`, `highlights.py:428` |
| 1.9 | Medium | Correctness | Unordered uploads; stale bucket objects never pruned | `storage_upload.py:101-149,176-182` |
| 2.1 | High | Performance | 188M redundant float ops per Stage H board (16 s) | `highlights.py:239`, `scoring.py:39-47` |
| 2.2 | High | Performance | Same parquet read 6× per group; `completed_week_for` uncached | `ramp_hold.py:97-102`, 7 call sites |
| 2.3 | High | Performance | ~32.5 MB web payload uncompressed; gzip = 8.3% | `publish.py:24`, `leaderboard.py:22`, `highlights.py:22` |
| 3.3 | High | MLOps | No validation between stages; gate only in `backfill` | `cli.py:433-441` |
| 3.4 | High | MLOps | No logging at all; ~70 bare `print()` | `src/ballnet/**` |
| 3.5 | High | MLOps | Published JSON unversioned / untraceable | `publish.py:143-150` |
| 4.1 | High | Reusability | 1075-line CLI, 15 subcommands in one `if` chain | `cli.py:358-1070` |
| 4.2 | High | Reusability | Position-group set hardcoded in 4 modules | `density.py:165`, `percentiles.py:29`, `leaderboard.py:20` |
| 4.3 | High | Reusability | 134 stat definitions duplicated py↔ts, 60 `denom` mismatches | `catalog/*.py` ↔ `frontend/src/lib/catalog/*.ts` |
| 1.13 | Medium | Correctness | Failed optional fetch cached as permanent empty frame | `ingest.py:146-157, 139` |
| 1.12 | Medium | Correctness | `_row_sort_key` docstring promises `qualified`, code ignores it | `leaderboard.py:40-45` |
| 1.10 | Medium | Correctness | Retry sleeps after final attempt; `assert` in library code | `storage_upload.py:88-98` |
| 3.6 | Medium | MLOps | ~15 magic constants, no config file; workers 4 vs 8 | `highlights.py:24-27`, `scoring.py:11,14`, `storage_upload.py:29` vs `cli.py:356` |
| 3.7 | Medium | MLOps | Three caches, none invalidated | `fantasy_rank.py:33`, `publish.py:229,282`, `ingest.py:139` |
| 4.4 | Medium | Reusability | Global path constants; untestable without monkey-patching | `paths.py:7-22` |
| 2.4 | Medium | Performance | All 11 spines re-read per week, no cross-week reuse | `highlights.py:315-331` |
| 2.5 | Medium | Performance | Serial season×group×week loops | `cli.py:609,744,846` |
| 4.5 | Medium | Reusability | `_shape_payload` duplicated verbatim | `publish.py:153` / `highlights.py:263` |
| 1.7 | Low | Correctness | Group collapse computed twice per board | `highlights.py:389-392, 402-409` |
| 1.11 | Low | Correctness | Error list truncated to 20 | `storage_upload.py:148` |
| 1.14 | Low | Correctness | No schema validation of published JSON | `src/ballnet/**` |
| 4.6 | Low | Reusability | `DB`→`CB` collapse; unmapped positions dropped silently | `positions.py:30-33, 70-78` |

---

## 6. Suggested order of work

1. **Add tests first.** A `tests/` dir plus a dev dependency group. Pure functions
   (`ramp_week`, `min_n`, `_slice_row`, `snap_one_in_n`, `resolve_rank_kind`,
   `oriented_z_score`) need no fixtures. Add a `BALLNET_DATA_DIR` override in `paths.py` so
   the rest becomes testable (§4.4).
2. **Fix the two Critical correctness bugs** (§1.1, §1.2). Both are one-line-ish guards in
   `publish.py`, and both currently corrupt published state on the documented rollover path.
3. **Add a catalog parity test** (§4.3): parse the TS catalog and assert id-set and field
   parity against `catalog/*.py`. Cheap, and it locks the contract `catalog/BOUNDARIES.md`
   already claims in prose. Then resolve the 3 suspicious `denom` disagreements and collapse
   the double `minNBase` definitions.
4. **Hoist mean/sigma out of the Stage H inner loop** (§2.1) and memoize
   `completed_week_for` (§2.2). Two small changes, most of the runtime back.
5. **Serve gzip** (§2.3) and stop writing `pages/current/` unless `--also-current` (§1.1 fix
   naturally supports this).
6. **Write a run manifest** (§3.2, §3.5): a `data/manifests/{season}_w{week}.json` with
   fetched-at, source URLs, row counts, content hashes, git SHA, and the resolved catalog.
   Upload it *last*, and treat it as the completion marker that §1.9 currently lacks.
7. **Replace `print()` with `logging`** (§3.4) and move the magic constants into a config
   module (§3.6).
8. **Refactor `cli.py` into a dispatch table** (§4.1) — this is what unblocks the
   `refresh` command `WEEKLY_OPS.md` has been asking for since the doc was written.
