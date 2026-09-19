# Frontend

Static Next.js site for Midwest Ball (formerly Knowball `web/`).

```bash
npm ci
cp .env.example .env.local   # NEXT_PUBLIC_SUPABASE_URL
npm run dev
npm run build                # static export → out/
```

Reads Ballnet viz JSON from public Supabase Storage only. Deployed via GitHub Pages from the repo root workflow.
