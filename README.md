# midwestball.github.io

Monorepo for [Midwest Ball](https://midwestball.github.io/): static viz site + football data pipeline.

| Path | Role |
|---|---|
| [`frontend/`](frontend/) | Next.js App Router site (static export → GitHub Pages) |
| [`backend/`](backend/) | Ballnet Python ETL (publishes JSON to Supabase Storage) |

Originals `ehfurgeson/knowball` and `ehfurgeson/ballnet` are unchanged. This repo imported their histories under `frontend/` and `backend/`.

## Frontend (Pages)

```bash
cd frontend
cp .env.example .env.local   # set NEXT_PUBLIC_SUPABASE_URL
npm ci
npm run dev                  # local
npm run build                # writes out/ for Pages
```

GitHub Actions deploys `frontend/out` on push to `main`. Set repository variable `NEXT_PUBLIC_SUPABASE_URL` to the public Supabase project URL.

## Backend (ETL)

```bash
cd backend
uv sync
uv run ballnet --help
# Weekly recipe: see backend/docs/WEEKLY_OPS.md
# Optional local index mirror: --sync-knowball ../frontend
```

Pipeline artifacts stay in gitignored `backend/data/`; production handoff is `upload-storage` to the public `knowball-public` bucket.

## Docs

- [Monorepo + static Pages ADR](docs/adr/2026-09-19-monorepo-static-pages.md)
- Frontend architecture: [`frontend/docs/architecture/README.md`](frontend/docs/architecture/README.md)
- Backend ops: [`backend/docs/WEEKLY_OPS.md`](backend/docs/WEEKLY_OPS.md)
