# Boundaries: `web/src/lib/ballnet-store`

## Always

- Prefer Storage public URLs when configured (`NEXT_PUBLIC_SUPABASE_URL` or `VIZ_STORAGE_BASE_URL`); fall back to sibling `ballnet/data` or synced `src/data/ballnet/` copies.
- Load `index/{players,current,seasons}.json`, `highlights/{season}/w{week}.json`, and `dists/league_weekly/{season}/w{week}/{group}.json` at runtime — do not statically import large boards into the Next bundle.
- Merge `league/{season}/w{week}/{group}.json` into player snapshots before hydration so `ready` rows have `curve[]`.
- Keep Knowball free of Supabase clients / service keys — public object fetches only.

## Ask First

- Changing Storage path layout (`pages/`, `league/`, `index/`, `highlights/`, `dists/league_weekly/`).
- Turning remote fetches back on while local prefer is active (`VIZ_PREFER_LOCAL` / `BALLNET_DATA_DIR`).

## Never

- Import full page or league JSON into the Next bundle.
- Invent league curves in the UI when the league or league_weekly file is missing.
- Use YTD `league/` shapes for home highlight expand charts.

## Silent Failures & Gotchas

- With `VIZ_PREFER_LOCAL=1` or `BALLNET_DATA_DIR` set, remote Storage is skipped even when `NEXT_PUBLIC_SUPABASE_URL` is present (local smoke testing).
- Legacy league files without `curve[]` keep rows pending until `league/` is re-uploaded.
- Production (Vercel) requires `NEXT_PUBLIC_SUPABASE_URL`; there is no sibling `ballnet/data` on serverless.
- Missing Storage env: search can still populate from bundled `src/data/ballnet/players.json` while `pages/` / `league/` fail → “Current season · no snapshot yet” / pending rows.
- Index + page fetches use `revalidate: 3600` — expect up to one hour before a Ballnet republish shows live.
- Highlight expand needs a separate `loadLeagueWeeklyGroupJson` fetch; a published board without weekly dists still ranks but charts stay pending.
