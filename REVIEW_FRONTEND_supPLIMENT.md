# Frontend Review — Supplement (`midwestball.github.io/frontend`)

Companion to `REVIEW_FRONTEND_deepdive.md` (a deeper, live-measurement review).
This file records findings I verified independently, plus the career-facing framing.
No source file was modified.

---

## 1. Command results (independently re-verified)

| Command | Exit | Result |
|---|---|---|
| `npm run test` | 0 | 7 files, **55 tests passed** |
| `npx tsc --noEmit` | 0 | **zero output** — types clean |
| `npm run build` | 0 | Next 16.3.1 Turbopack; 1440 static pages in 14.4 s |
| `npm run lint` | 1 | **8 errors**, 5 warnings |
| `projection_ops` pytest | 0 | **42 tests passed** |
| `ballnet` pytest | 2 | 11 collection errors, **0 tests** |
| `find backend/src -name 'test*'` | — | **empty** |

All 8 lint errors are `react-hooks/set-state-in-effect`:
`ComparePageClient.tsx:113`, `HighlightsBrowser.tsx:58,258`, `PlayerPageClient.tsx:65`,
`PlayerSearch.tsx:373,399,429,442`.
5 unused-var warnings in `src/lib/highlights.ts`.

**Important nuance the deeper report establishes:** `eslint-config-next` is pinned to
`16.3.1`, and this rule ships in `core-web-vitals`. So a clean checkout *cannot* pass
`npm run lint` — these errors arrived with the dependency bump, not with careless commits.
That is a more accurate framing than "you committed 8 lint errors": the fix is to either
resolve the pattern or acknowledge the rule is newer than the code.

---

## 2. Findings I verified that add to the deeper report

### 2.1 The `React.cache()` no-op — independently confirmed, with the runtime proof

I reached the same conclusion by a different route. `players.ts:13,22,38` uses `cache()`
**correctly**, because those run in the build-time RSC pass — which is why
`generateStaticParams` prerenders 1,431 player paths in 14.4 s. But:

- `PlayerPageClient.tsx:66` — `"use client"`
- `ComparePageClient.tsx:129` — `"use client"`

The deep-dive report quotes the actual React 19.2.8 source (`exports.cache = function (fn)
{ return function () { return fn.apply(null, arguments); }; }`) and proves it at runtime
(`cache() invocations for 2 identical awaits = 2`). That is conclusive.

**The fix already exists in this repo.** `projections.ts:29-100` implements the correct
pattern: an `immutableCache` of shared promises keyed by URL plus `raceAbort`, so a caller
can walk away from a shared request without disturbing other callers. Its comment
explains precisely why the shared request must **not** be bound to one caller's
`AbortSignal`: React tears down the effect that started a fetch and immediately starts
another; the second caller reuses the first caller's doomed promise from the cache, and the
abort belonging to a dead effect surfaces as a live error. `ballnet-store.ts` should adopt
that pattern instead of relying on `cache()`.

### 2.2 No error path and no abort in the load effects

`PlayerPageClient.tsx:63-77`:

```tsx
  useEffect(() => {
    let cancelled = false;
    setStatus("loading");
    void loadHydratedPlayerSnapshots(livePlayer.id, positionGroup, { season }).then(
      ({ page, snapshots }) => { if (cancelled) return; /* setState... */ },
    );
    return () => { cancelled = true; };
  }, [livePlayer.id, livePlayer.position, positionGroup, season]);
```

There is no `.catch(...)`. Today `tryFetchRemoteJson` (`ballnet-store.ts:52-60`) swallows
every error and returns `null`, so the missing handler is masked **by accident rather than
by design**. Tighten that helper and this becomes an unhandled rejection with the UI stuck
on `"loading"` forever. `ComparePageClient.tsx:126-155` has the same shape.

The `cancelled` flag is correct React 19 practice, but a real `AbortController` threaded
through `loadStorageJson` would additionally stop the in-flight request instead of
discarding the response.

### 2.3 Caching headers are inconsistent on the freshness-critical path

`projections.ts` fetches the pointer with `{ cache: "no-store" }`. `ballnet-store.ts:52-60`
passes **no cache option**, so every `fetch` uses the browser default. Given commit
`a49d493 "fix: prevent stale highlights and player data after weekly uploads"`, stale
caching has already caused a real incident here.

### 2.4 No validation guards on the primary data path

This is the sharpest inconsistency in the codebase, and I want to flag it for interview
purposes. `projections.ts:20-27` defines rigorous hand-written guards
(`isProjectionPointer`, `isProjectionIndex`, `isProjectionEntity`) checking monotonic
CDFs, non-negative PDFs, grid-length agreement, snapshot-ID linkage, and path-traversal
via `safeRelativePath`.

`ballnet-store.ts` has **none** — `tryFetchRemoteJson<T>` is a bare cast
(`return (await res.json()) as T`). Because `ballnet` writes JSON **non-atomically**
(`publish.py:208-211`, `leaderboard.py:34-37`, `highlights.py:428-431` all call
`json.dump` straight onto the target), an interrupted publish leaves truncated JSON that
the frontend will accept and render as garbage rather than degrading to a clean "pending"
state. `schemaVersion` is written by the backend and never checked by this reader.

Two modules in the same directory, same project, opposite levels of rigor. An interviewer
who reads both will ask "which one do you trust?" — have an answer ready.

### 2.5 Cross-language catalog parity — verified, no drift

I compared all **134** stat definitions across `backend/src/ballnet/catalog/*.py` and
`frontend/src/lib/catalog/*.ts` on every mirrored field (`kind`, `higherIsBetter`,
`format`, `xMin`, `xMax`, `minNBase`, `lowerBound`, `upperBound`, `alwaysUnavailable`,
`startYear`): **zero semantic divergence**, id sets match exactly.

The remaining differences are intentional: `denom` holds a machine key in Python
(`ngs_weeks`) and a display label in TypeScript (`"NGS week"`), and TypeScript adds
`label`/`section`/`source`/`zeroMass`. The Python docstrings say "must match midwestball
`frontend/src/lib/catalog/qb.ts`", so parity is clearly intended — but nothing enforces
it. A single generated source of truth, or a parity test, would lock it in.

### 2.6 Cross-language CDF math — verified identical

Python `density.py:_kde_cdf` and TypeScript `distribution.ts:kdeCdf` implement the same
trapezoid rule with matching branch structure and bounds clamping. I read both
side by side; they agree. `projection-math.ts` likewise matches
`distribution.py:cdf_at` / `quantile` on the mainline.

**This is a genuine strength worth surfacing**: the percentile the entire site displays is
computed identically on both sides, with no floating-point divergence of consequence. But
nothing tests it — `distribution.ts` has **zero tests**, including `kdeCdf`, the single
most important function in the file.

**Highest-value test you could add**: replay a real published `league/` file and assert the
frontend percentile equals the backend `percentile` for a set of player values. That test
guards the one invariant the entire product rests on.

### 2.7 Demo fixtures leak into production

`player-index.ts:8-100` defines 11 `DEMO_PLAYERS` with fabricated names ("Demo
Quarterback", team `"KNB"`). `players.ts:16` merges them into `loadPlayerIndex()`, so they
enter the published player index, appear in search, and get prerendered as real routes
(`/players/demo-qb`). The comment says "Lab-only placeholders" but nothing gates them to
the lab. Confirmed in my build output: `/players/demo-qb`, `/players/demo-rb`,
`/players/demo-fb` appear among the prerendered paths.

### 2.8 Dead scaffold assets

`frontend/public/` retains `file.svg`, `globe.svg`, `next.svg`, `vercel.svg`,
`window.svg` from the Create-Next-App scaffold, with zero references in `src`. `.nojekyll`
must stay. Also `shadcn@^4.18.0` is a CLI sitting in `dependencies` rather than
`devDependencies`, and `binWidth` (`catalog/types.ts:63`) is populated everywhere and read
nowhere.

---

## 3. Testing gaps (frontend)

55 tests pass and the targeting is sensible — the hardest logic (CDF inversion, quantile
inversion, retry/abort resilience) rather than trivial rendering. Gaps:

- **`distribution.ts`: zero tests.** `kdeCdf`, `percentileAt`, `shadedThrough`,
  `insertValuePoint`, `percentileColor`, `snapOneInN`, `rarityTierColor` all untested.
- **`ballnet-store.ts`: zero tests.** `mergeLeagueIntoSnapshots` (`:154-175`) encodes a
  real precedence rule — an embedded curve wins over the shared league shape — unverified.
- Untested: `player-index.ts`, `payload.ts`, `stat-status.ts`, `viz-config.ts`.
  `team-colors.ts` has 7 tests.
- No test exercises the `"use client"` fetch path — exactly where the `cache()` and
  missing-error-handling issues live.
- No accessibility or interaction tests on the slider-heavy components.

---

## 4. Presenting the frontend

**Genuine strengths**
- Rigorous runtime validation of external JSON (`projections.ts`).
- The retry/backoff/abort design in `projections.ts:66-120`, with a comment documenting a
  real diagnosed production bug (shared promise + AbortSignal interaction). That is a
  strong interview story.
- Clean TypeScript: no `any`, no `@ts-ignore`, `tsc --noEmit` clean.
- Current stack: Next 16 + React 19 + Tailwind v4 + static export.
- 1,431 player pages prerendered in 14.4 s.

**How to frame it honestly**
The frontend is competent, well-tested React work — but it is not the differentiator. Every
other candidate can list React. Lead with the model (see `../REVIEW.md` §1-2) and present
the frontend as the delivery layer that made the model's output consumable: a static export
with no server runtime, reading validated versioned snapshots from object storage.

The most impressive frontend story is not a component — it is the `projections.ts` loader:
immutable snapshot pointers, shared-promise deduplication, bounded retry with backoff,
abort that does not poison other callers, and a 15 s shared-request timeout so a hung
response is not cached forever. That is production reasoning about distributed systems, and
it is worth 30 seconds of your interview time.

**Anticipated questions**
- *"Why is `cache()` not deduplicing?"* — it is a server-only API; the client build makes
  it an identity function. Fix is the `immutableCache` pattern already used elsewhere in
  the same codebase.
- *"Why is one module validated and the other not?"* — the newer projections work got the
  rigorous treatment; the older store predates it. Honest answer: the guards should be
  backported, and the non-atomic backend writes are the real root cause.
- *"Why 8 lint errors on main?"* — the pinned `eslint-config-next` 16.3.1 ships this rule
  in `core-web-vitals`; a clean checkout cannot pass. CI does not run lint, so it went
  unnoticed.

---

## 5. Suggested fixes, cheapest first

1. Add lint + typecheck + test to CI. Resolve or explicitly baseline the 8
   `set-state-in-effect` errors.
2. Delete the 5 unused-var warnings in `highlights.ts` and the 5 dead SVGs in `public/`.
3. Port `immutableCache` + `raceAbort` from `projections.ts` into `ballnet-store.ts`; drop
   the misleading `cache()` wrappers. Fixes the N-fold duplicate fetches and the stale-cache
   risk together.
4. Add validation guards to `ballnet-store.ts` (check `schemaVersion`, `stats`, `curve`).
5. Add `distribution.ts` tests, including the cross-language percentile parity test.
6. Gate `DEMO_PLAYERS` behind a dev-only check.
7. Pass a real `AbortSignal` from the load effects; add `.catch` handlers.
