# Knowball

NFL player stats, visualized. Knowball is a public web app that shows how a player’s season-to-date numbers sit in the league distribution—percentiles and density curves, not just raw totals.

Data is computed by [ballnet](https://github.com/ehfurgeson/ballnet) and served as JSON from Supabase Storage. This repo is the Next.js frontend only.

**Stack:** Next.js (App Router) · React · Tailwind · Recharts · Vercel

## Local development

```bash
cd web
npm install
npm run dev
```

Set `NEXT_PUBLIC_SUPABASE_URL` to your Supabase project URL (e.g. in `.env.local`). Knowball reads the public `knowball-public` bucket—no service key required.

## Deploy

1. Connect this repo in Vercel and set **Root Directory** to `web`.
2. Add `NEXT_PUBLIC_SUPABASE_URL`.
3. Deploy.

## Related

- [ballnet](https://github.com/ehfurgeson/ballnet) — ingest, densities, percentiles, and JSON publish
