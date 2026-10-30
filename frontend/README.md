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

## Published leaderboard filters

Discovery uses season boards, oriented percentiles, published fantasy ranks, and completed-week ramp?hold qualification. WR and TE share one pass-catcher board. Run `npm run test -- src/lib/search/leaderboards.test.ts`.

## Share URL schemas

Search uses `p,season,pos,stat,sort,min,q`; projections use route-specific `p,focus,points`. Trades use readable `v=1&r=ID,~IR_ID&g=GIVE&a=RECEIVE&d=DROP` with optional fixed-order slot settings. Invalid trade imports report errors without partial repair. Run `npm run test -- src/lib/share-state`.

## Accessible player suggestions

Search, weekly projections, ROS and roster pickers share focus, arrow keys, Enter, Escape and collapse behavior. Eligibility and default numerical ordering remain caller-owned. Run `npm run test -- src/components/search/player-combobox.test.tsx`.
