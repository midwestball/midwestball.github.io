# Knowball frontend

Next.js app for the public Knowball site (stats viz, Ballnet writeups page, ffoptim draft UI). Data ingest and densities live in the public **ballnet** pipeline; draft modeling lives in private **ffoptim**. This app renders published JSON only — no mock KDE generation.

```bash
npm install
cp .env.example .env.local   # NEXT_PUBLIC_SUPABASE_URL required for Storage-backed pages
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

**Vercel:** set Root Directory to `web`, add `NEXT_PUBLIC_SUPABASE_URL`. See repo root [`README.md`](../README.md).

Architecture: `docs/architecture/README.md`. Locked stat-row UX: `docs/architecture/ui-components.md`.
