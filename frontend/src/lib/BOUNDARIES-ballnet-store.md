# Boundaries: `frontend/src/lib/ballnet-store`

## Always

- Load every viz artifact from public Supabase Storage (`NEXT_PUBLIC_SUPABASE_URL` or `VIZ_STORAGE_BASE_URL`). Local `npm run dev` and GitHub Pages share this path. Do not bundle Ballnet JSON in the frontend git tree.
- Load `index/{players,current,seasons}.json`, `highlights/{season}/w{week}.json`, `leaderboards/{season}/w{week}/{group}.json`, and `dists/league_weekly/{season}/w{week}/{group}.json` via `fetch` — do not statically import large boards into the Next bundle.
- Merge `league/{season}/w{week}/{group}.json` into player snapshots before hydration so `ready` rows have `curve[]`.
- Keep the frontend free of Supabase clients / service keys — public object fetches only.

## Ask First

- Changing Storage path layout (`pages/`, `league/`, `index/`, `highlights/`, `leaderboards/`, `dists/league_weekly/`).
- Adding any disk / `backend/data` read path (forbidden by `docs/adr/2026-09-18-storage-only-loader.md`).

## Never

- Import full page, league, or leaderboard JSON into the Next bundle.
- Read `backend/data`, `BALLNET_DATA_DIR`, `VIZ_PREFER_LOCAL`, or `frontend/public/viz/`.
- Invent league curves in the UI when the league or league_weekly file is missing.
- Use YTD `league/` shapes for home highlight expand charts.
- Commit Ballnet publish artifacts under `frontend/src/data/ballnet/` or `frontend/public/viz/`.
- Reintroduce Server Actions for Storage loads (static export / Pages cannot run them).

## Silent Failures & Gotchas

- Missing Storage env → empty search / “no snapshot yet”. Publish is not enough; `upload-storage` is what the UI sees.
- Legacy league files without `curve[]` keep rows pending until `league/` is re-uploaded.
- Static export has no ISR — client fetches see Storage as soon as the network allows; rebuild Pages when build-time `generateStaticParams` / home SSG payloads must change.
- Highlight expand needs a separate `loadLeagueWeeklyGroupJson` fetch; a published board without weekly dists still ranks but charts stay pending.
- Search Filter Best/Worst uses `fetchLeaderboard` / `loadLeaderboard` from the browser; bio-only filter still works when the board is absent.
- Search min-volume uses `completedWeek` from the board / seasons / current index. Missing field → `asOfWeek` (historical slices). Do not recompute schedule completeness in the Next app.
