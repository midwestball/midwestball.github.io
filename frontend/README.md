# Frontend

Static Next.js site for Midwest Ball (GitHub Pages).

```bash
npm ci
cp .env.example .env.local   # NEXT_PUBLIC_SUPABASE_URL
npm run dev
npm run build                # static export → out/
```

Reads Ballnet viz JSON from public Supabase Storage only. Deployed via the repo-root GitHub Actions Pages workflow.

Player and comparison distributions use the original reflected Gaussian KDE; v2 data reconstructs the curve from exact peer-value counts while retaining empirical percentiles. Highlights use observed single-game histograms.

## Player matching

Player discovery normalizes punctuation and diacritics and accepts conservative name typos; short team and position queries remain exact. Ranked results retain published numerical ordering. Run `npm run test -- src/lib/search/fuzzy.test.ts`.
