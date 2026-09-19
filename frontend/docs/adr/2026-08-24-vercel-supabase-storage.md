### Context
The site must serve 2016–present player pages from Ballnet without bundling multi-megabyte JSON or relying on a sibling `backend/data` checkout on the host.

### Decision
**(Historical)** Deploy the Next.js app from `web/` on Vercel and load viz artifacts at runtime from the public Supabase Storage bucket `knowball-public` using plain `fetch` — still no `@supabase/supabase-js`. Index metadata is fetched with React `cache()` instead of static imports. Configure production with `NEXT_PUBLIC_SUPABASE_URL`.

**(Current — superseding host)** The Midwest Ball org site lives in this monorepo under `frontend/`, builds with `output: 'export'`, and deploys `frontend/out` to **GitHub Pages**. Storage remains the data plane. See repo-root `docs/adr/2026-09-19-monorepo-static-pages.md`.

### Consequences
- **Required:** Set `NEXT_PUBLIC_SUPABASE_URL` as a GitHub Actions repository variable (and in local `.env.local`) before Pages builds succeed. Optional `VIZ_STORAGE_BASE_URL` overrides the derived Storage prefix.
- **Gotcha:** Without Storage env, search and pages are empty. Sibling `backend/data` is not a frontend read path (`docs/adr/2026-09-18-storage-only-loader.md`).
- **Deprecated:** Vercel as the Midwest Ball host; `ballnet publish-all --sync-midwestball` / `frontend/public/viz/` as a local preview — prefer `upload-storage`.
