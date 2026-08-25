### Context
Knowball must serve 2016–2025 player pages from Ballnet without bundling multi-megabyte JSON or relying on a sibling `ballnet/data` checkout on Vercel.

### Decision
Deploy the Next.js app from `web/` (via root `vercel.json`) and load all viz artifacts at runtime from the public Supabase Storage bucket `knowball-public` using plain `fetch` — still no `@supabase/supabase-js`. Index metadata (`index/players.json`, `index/current.json`, `index/seasons.json`) is fetched on the server with React `cache()` instead of static imports. Configure production with `NEXT_PUBLIC_SUPABASE_URL`.

### Consequences
- **Required:** Set `NEXT_PUBLIC_SUPABASE_URL` on Vercel before deploy. Optional `VIZ_STORAGE_BASE_URL` overrides the derived Storage prefix.
- **Deprecated:** Treating synced `web/src/data/ballnet/*.json` as the production source of truth — keep them only as local offline fallback after `ballnet publish-all --sync-knowball`.
- **Unchanged:** No PostgREST, no service role key, no mock KDE generation in the Next app.
