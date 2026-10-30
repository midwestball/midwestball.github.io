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

Discovery uses season boards, oriented percentiles, published fantasy ranks, and completed-week ramp-hold qualification. WR and TE share one pass-catcher board. Run `npm run test -- src/lib/search/leaderboards.test.ts`.

## Share URL schemas

Search uses `p,season,pos,stat,sort,min,q`; projections use route-specific `p,focus,points`. Trades use readable `v=1&r=ID,~IR_ID&g=GIVE&a=RECEIVE&d=DROP` with optional fixed-order slot settings. Invalid trade imports report errors without partial repair. Run `npm run test -- src/lib/share-state`.

## Accessible player suggestions

Search, weekly projections, ROS and roster pickers share focus, arrow keys, Enter, Escape and collapse behavior. Eligibility and default numerical ordering remain caller-owned. Run `npm run test -- src/components/search/player-combobox.test.tsx`.

## Discovery composition

A request-keyed discovery hook owns board loading and qualification; controlled filter and result components render that state independently. Run `npm run test -- src/components/search/search-discovery.test.tsx`.

## Canonical Search

`/search/?p=A,B&season=2026&pos=wr&stat=fantasy_pos_rank` combines comparison with the complete discovery filters. Query edits replace history; discrete choices push history. Filter changes preserve selected players. Run `npm run test -- src/components/search`.

## Projection links

Weekly links restore entity keys, focus and optional points thresholds; ROS links restore player IDs. Back/Forward reconciles selections without restarting snapshot loading. Switching horizons clears incompatible keys. Run `npm run test -- src/components/projections src/lib/share-state`.

## Shared trade previews

A shared trade opens as a temporary preview. Editing it updates its URL without autosaving over `midwestball-trade-roster-v1`; Save this roster explicitly writes the unchanged v1 schema, and Use my saved roster restores personal state. Invalid links never write storage. Run `npm run test -- src/components/trades`.

## Legacy routes

`/compare/` and `/ffoptim/` preserve query strings when redirecting to canonical Search in the browser. Both remain static exports; JavaScript is required. Run `npm run build` and inspect `out/search/index.html`, `out/compare/index.html`, `out/ffoptim/index.html`.

## Automatic appearance

CSS follows effective browser light/dark preference, defaults to charcoal when indeterminate, and updates live. No theme control is shown. The reserved `midwestball-theme-preference-v1` key accepts `system|light|dark`; explicit overrides apply before paint and synchronize across tabs. Run `npm run test -- src/lib/theme`.

## Semantic feature surfaces

Panels, forms, selected actions, warnings, unavailable states and keyboard focus use semantic tokens across all routes; percentile and team identities retain their original colors. Run `npm run test` for feature regressions.

## Local feedback and motion

Loading and error messages stay beside the affected data, with controls retained. Chart and row motion honors reduced-motion preference; the site has no decorative canvas dependency. Run `npm run test -- src/components`.

## Home navigation

Home season/week choices preserve unrelated query parameters and create navigable history entries. Back/Forward restores the published slice, with invalid weeks falling back to the available range. Run `npm run test -- src/components/highlights/highlights-navigation.test.tsx`.

## Compatible discovery results

Selecting comparison players hides discovery rows from other catalog groups in both bio and ranked views, without changing numerical ordering or clearing discovery filters. Removing the selection restores the full discovery scope. Run `npm run test -- src/components/search/search-discovery.test.tsx`.

## Stable Search width

Search fills the available page width up to its existing `max-w-6xl` limit before any distribution is opened. Expanding or closing a comparison plot changes height only; the page does not shrink-wrap its contents.

## Search section order

Search and season controls come first, followed by selected players and their comparison. The Filter results section groups publication context, filters and the matching list so filter changes are clearly scoped to those results. Run `npm run test -- src/components/search/search-discovery.test.tsx`.

## Direct comparison selection

Click or keyboard-activate a Filter results row to add its player to the comparison. Rows have no separate Add button or profile navigation. Selected, unavailable and capped rows remain disabled, while published rank tooltips retain their own interaction. Run `npm run test -- src/components/search`.
