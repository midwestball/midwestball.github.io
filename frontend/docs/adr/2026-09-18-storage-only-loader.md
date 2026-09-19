### Context
The UI could read sibling `backend/data` (or `VIZ_PREFER_LOCAL`) even when Storage is configured, so local UI could show unpublished JSON that production never has.

### Decision
The frontend loads every viz artifact from the public Supabase Storage bucket `knowball-public` via `fetch` — local `npm run dev` and GitHub Pages use the same path. Disk fallback, `VIZ_PREFER_LOCAL`, and `BALLNET_DATA_DIR` are removed. The backend still writes gitignored `backend/data/` then `upload-storage`; that local tree is pipeline output, not a frontend read source.

### Consequences
- **Required:** `NEXT_PUBLIC_SUPABASE_URL` (or `VIZ_STORAGE_BASE_URL`) for both local and Pages builds.
- **Gotcha:** Unpublished local JSON is invisible to the UI until `upload-storage`.
- **Deprecated:** Sibling `backend/data` reads, `VIZ_PREFER_LOCAL`, `BALLNET_DATA_DIR`, and `--sync-midwestball` as a way to preview unpublished JSON in the frontend.
