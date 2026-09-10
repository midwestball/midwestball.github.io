### Context
Knowball must serve 2016–2025 player pages from Ballnet without bundling multi-megabyte JSON or relying on a sibling `ballnet/data` checkout on Vercel.

### Decision
Deploy the Next.js app from `web/` (via root `vercel.json`) and load all viz artifacts at runtime from the public Supabase Storage bucket `knowball-public` using plain `fetch` — still no `@supabase/supabase-js`. Index metadata (`index/players.json`, `index/current.json`, `index/seasons.json`) is fetched on the server with React `cache()` instead of static imports. Configure production with `NEXT_PUBLIC_SUPABASE_URL`.

### Consequences
- **Required:** Set `NEXT_PUBLIC_SUPABASE_URL` on Vercel before deploy (Production + Preview as needed), then redeploy. Optional `VIZ_STORAGE_BASE_URL` overrides the derived Storage prefix.
- **Gotcha:** Without Storage env and without a sibling `ballnet/data` checkout, search and pages are empty — configure Storage for normal local/prod use.
- **Local only:** Optional `ballnet publish-all --sync-knowball ../knowball/web` writes a gitignored mirror under `web/public/viz/`; do not commit Ballnet artifacts into Knowball.
- **Unchanged:** No PostgREST, no service role key, no mock KDE generation in the Next app.
