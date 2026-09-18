### Context
Knowball can read sibling `ballnet/data` (or `VIZ_PREFER_LOCAL`) even when Storage is configured, so local UI can show unpublished JSON that production never has.

### Decision
Knowball loads every viz artifact from the public Supabase Storage bucket `knowball-public` via `fetch` — local `npm run dev` and Vercel use the same path. Disk fallback, `VIZ_PREFER_LOCAL`, and `BALLNET_DATA_DIR` are removed. Ballnet still writes gitignored `data/` then `upload-storage`; that local tree is pipeline output, not a Knowball read source.

### Consequences
- **Required:** Set `NEXT_PUBLIC_SUPABASE_URL` (or `VIZ_STORAGE_BASE_URL`) for local and prod. Missing env → empty search / pending pages.
- **Required:** `upload-storage` after publish before the UI can show a change. Index + page fetches `revalidate: 3600` — expect up to an hour, or redeploy, after an upload.
- **Deprecated:** Sibling `ballnet/data` reads, `VIZ_PREFER_LOCAL`, `BALLNET_DATA_DIR`, and `--sync-knowball` as a way to preview unpublished JSON in Knowball.
