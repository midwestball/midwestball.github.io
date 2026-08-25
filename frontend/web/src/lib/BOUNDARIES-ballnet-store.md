# Boundaries: `web/src/lib/ballnet-store`

## Always

- Prefer Storage public URLs when configured (`NEXT_PUBLIC_SUPABASE_URL` or `VIZ_STORAGE_BASE_URL`); fall back to sibling `ballnet/data` or synced `src/data/ballnet/` copies.
- Load `index/{players,current,seasons}.json` at runtime — do not statically import the player index into the Next bundle.
- Merge `league/{season}/w{week}/{group}.json` into player snapshots before hydration so `ready` rows have `curve[]`.
- Keep Knowball free of Supabase clients / service keys — public object fetches only.

## Ask First

- Changing Storage path layout (`pages/`, `league/`, `index/`).
- Turning remote fetches back on while local prefer is active (`VIZ_PREFER_LOCAL` / `BALLNET_DATA_DIR`).

## Never

- Import full page or league JSON into the Next bundle.
- Invent league curves in the UI when the league file is missing.

## Silent Failures & Gotchas

- With `VIZ_PREFER_LOCAL=1` or `BALLNET_DATA_DIR` set, remote Storage is skipped even when `NEXT_PUBLIC_SUPABASE_URL` is present (local smoke testing).
- Legacy league files without `curve[]` keep rows pending until `league/` is re-uploaded.
- Production (Vercel) requires `NEXT_PUBLIC_SUPABASE_URL`; there is no sibling `ballnet/data` on serverless.
- Index + page fetches use `revalidate: 3600` — expect up to one hour before a Ballnet republish shows live.
