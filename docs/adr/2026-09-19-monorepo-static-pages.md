### Context
Midwest Ball needed one org repo that preserves knowball + ballnet history, deploys the viz site on GitHub Pages, and keeps the Python ETL runnable beside it — without rewriting the original `ehfurgeson/knowball` or `ehfurgeson/ballnet` remotes.

### Decision
Combine histories into `midwestball/midwestball.github.io` as `frontend/` (Next.js static export) and `backend/` (Ballnet CLI). Production viz data remains public Supabase Storage (`knowball-public`); Pages only hosts the static `frontend/out` build. Cursor/agent paths are stripped on import and denied in root `.gitignore`.

### Consequences
- **Required:** Set repo Actions variable `NEXT_PUBLIC_SUPABASE_URL` (public project URL) before Pages builds succeed.
- **Gotcha:** Player/Compare season and selection query strings are resolved client-side; static export cannot re-run RSC for `searchParams`.
- **Unchanged:** Original knowball and ballnet repos stay independent; this monorepo is a history-preserving org fork for Pages hosting.
