# knowball

Public football stats visualization site. Renders JSON published by [ballnet](https://github.com/ehfurgeson/ballnet). Draft optimization UI will live here; modeling stays in private **ffoptim**.

App: [`web/`](web/). Architecture: [`docs/architecture/README.md`](docs/architecture/README.md).

## Deploy on Vercel

1. Connect this GitHub repo in Vercel.
2. Set **Root Directory** to **`web`** in the Vercel project settings.
3. Add environment variable **`NEXT_PUBLIC_SUPABASE_URL`** = your Supabase project URL (e.g. `https://xxxx.supabase.co`). Knowball fetches public JSON from bucket `knowball-public` — no service key needed.
4. Deploy.

Data paths on Storage: `index/`, `pages/{season}/w{week}/`, `league/{season}/w{week}/`. Uploaded via `ballnet upload-storage` (see sibling `ballnet/docs/WEEKLY_OPS.md`).

## Local dev

```bash
cd web
cp .env.example .env.local   # set NEXT_PUBLIC_SUPABASE_URL
npm install
npm run dev
```

Without Supabase, use synced copies under `web/src/data/ballnet/` (`ballnet publish-all --sync-knowball ../knowball/web`) or point `BALLNET_DATA_DIR` at a local ballnet `data/` tree with `VIZ_PREFER_LOCAL=1`.
