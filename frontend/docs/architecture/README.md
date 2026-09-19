# Architecture Orientation & Context Routing

## System Architecture Context

This monorepo (`midwestball/midwestball.github.io`) hosts the Midwest Ball site and data pipeline:

| Path | Role | Visibility |
|---|---|---|
| **`frontend/`** | Public Next.js static site (stats viz, `/ballnet` writeups, Compare) | Public (GitHub Pages) |
| **`backend/`** | Ballnet Python pipeline / DS engine; publishes viz JSON to Supabase Storage | Public |
| **ffoptim** (separate) | Modeling + snake-draft optimization (e.g. Sleeper-linked drafts) | Private |

The frontend must not contain Python ingest, database clients, or model/optimizer code. The backend computes percentiles, KDEs, and player values; the frontend only **renders JSON** matching `frontend/src/lib/distribution.ts` / `frontend/src/lib/payload.ts`.

Upstream histories also exist at `ehfurgeson/knowball` and `ehfurgeson/ballnet` (untouched). Prefer this monorepo for Midwest Ball work.

Before modifying or creating new features, locate the relevant domain in the table below and read its specific documentation.

## Orientation Table

| Domain | Description | Target Document |
|---|---|---|
| **UI & Components** | Locked UX rules for `ExpandableStatRow`, percentiles, tooltips, Recharts, and square/flat chrome. | `docs/architecture/ui-components.md` |
| **Visual chrome** | Square corners, no shadows, tight spacing. | `docs/adr/2026-08-19-flat-square-chrome.md` |
| **Data Contracts** | JSON schemas, catalog hydration, and the Ballnet visualization store. | `docs/architecture/data-contracts.md` |
| **Routing & Pages** | Home, Search, Player, Projections, Compare. | `docs/architecture/routing.md` |
| **Visualization store** | Why the frontend reads JSON only and how the backend should table curves vs player values. | `docs/adr/2026-08-19-visualization-json-store.md` |
| **Split league JSON** | Player pages are scalars; league curves are one file per group/season/week. | `docs/adr/2026-08-20-split-league-distributions.md` |
| **KDE-only league shape** | Every catalog id publishes reflected KDE `curve[]`; histograms and rug `samples` retired. | `docs/adr/2026-08-24-kde-only-league-shape.md` |
| **Stat row / charts** | Expandable row invariants; KDE area chart in `TremorDistribution.tsx`. | `src/components/stat-row/BOUNDARIES.md` |
| **Product split** | Frontend + backend in this monorepo; private ffoptim ownership. | `docs/adr/2026-08-20-three-product-split.md` |
| **Stat catalog** | Position-group invariants and id stability. | `src/lib/catalog/BOUNDARIES.md` |
| **Ballnet JSON loader** | Storage-only fetch; league merge before hydrate. | `src/lib/BOUNDARIES-ballnet-store.md` |
| **Pages + Storage deploy** | Static export on GitHub Pages; loads index/pages/league from public Supabase Storage. | `docs/adr/2026-08-24-vercel-supabase-storage.md` (superseded host) + repo `docs/adr/2026-09-19-monorepo-static-pages.md` |
| **Storage-only loader** | Local and prod both `fetch` `knowball-public`. No sibling `backend/data` reads in the UI. | `docs/adr/2026-09-18-storage-only-loader.md` |
| **Weekly highlights** | Stage H z-score boards → `highlights/{season}/w{week}.json`; home renders only. | `docs/adr/2026-08-25-weekly-highlights-json.md` |
| **Highlight game KDEs** | Season-of-games σ ranking + expandable home charts from `dists/league_weekly/`. | `docs/adr/2026-08-25-highlight-game-kde.md` |
| **Highlight list** | Expandable home rows; σ color; no percentile slider. | `src/components/highlights/BOUNDARIES.md` |
| **Search leaderboards** | Filter → group → stat → Best/Worst from `leaderboards/{season}/w{week}/{group}.json`. | `docs/adr/2026-09-06-search-leaderboards-json.md` |
| **Search Filter UI** | Cascading Filter chrome; bio vs ranked list modes. | `src/components/search/BOUNDARIES.md` |
| **Compare UI** | Side-by-side sliders; one overlay KDE per row; team-primary markers; max 4 same-group. | `src/components/compare/BOUNDARIES.md` |
| **Compare colors** | Franchise primary + same-team brightness from mean ready %. | `docs/adr/2026-09-17-compare-side-by-side.md` |
| **Fantasy position rank** | Backend publishes `fantasyPosRank` + kind; frontend subscripts position labels. Never invent ranks. | `docs/adr/2026-09-17-fantasy-pos-rank.md` |
| **Plot domain** | League `xMax` = qualified season max (Ballnet `_expand_domain`). | `docs/adr/2026-09-17-season-max-plot-domain.md` |
| **Completed-week ramp–hold** | YTD `asOfWeek` may be a partial slate; `completedWeek` is the last fully scored week and drives min-n. | `docs/adr/2026-09-18-completed-week-ramp-hold.md` |
| **Future features** | Ordered backlog: overall %, trajectories, compare follow-ups. | `docs/architecture/future-features.md` |
| **ETL contract** | Backend publish path for frontend viz (Leg 1); reserved later stages. | `.plans/ballnet-etl-knowball-visualizations.md` |
| **Weekly refresh** | Post-game Ballnet recipe. | `../../backend/docs/WEEKLY_OPS.md` |
| **Monorepo + Pages** | Combined histories; static GitHub Pages host. | `../../docs/adr/2026-09-19-monorepo-static-pages.md` |

## App map (where things live)

The accepted UI lives under **`frontend/`**. Run with `cd frontend && npm ci && npm run dev` → [http://localhost:3000](http://localhost:3000).

| Piece | Path |
|---|---|
| Home | `src/app/page.tsx` |
| Highlight list | `src/components/highlights/HighlightList.tsx` |
| Search | `src/app/search/page.tsx` |
| Player page | `src/app/players/[id]/page.tsx` + `PlayerPageClient` |
| Projections (`/ballnet`) | `src/app/ballnet/page.tsx` |
| Compare (`/compare`) | `src/app/compare/page.tsx`, `src/components/compare/` |
| Position catalog | `src/lib/catalog/` |
| JSON contract | `src/lib/payload.ts` |
| Position rank label | `src/components/PositionRankLabel.tsx` |
| Expandable row | `src/components/stat-row/ExpandableStatRow.tsx` |
| Percentile slider | `src/components/stat-row/PercentileSlider.tsx` |
| Distribution charts | `src/components/stat-row/TremorDistribution.tsx` |
| Theme wrapper | `src/components/stat-row/variants.tsx` (`TremorVariant`) |
| CDF / copy / colors | `src/lib/distribution.ts` |
| Routing fixtures | `src/data/players.ts` (Ballnet index + lab demos — no curves) |

**Stack locked in:** Next.js 16 (App Router), React 19, Tailwind v4, shadcn/ui, Framer Motion, **Recharts** (Tremor/zinc palette), **`output: 'export'`** for GitHub Pages. Chart.js and Observable Plot were prototyped and **discarded** — do not reintroduce them.

## Global System Invariants

To prevent architectural drift, the following rules apply to **`frontend/`** and supersede other frontend instructions:

* **No Backend Logic in frontend:** Never introduce Python, database clients, or data ingestion scripts into `frontend/`. It only consumes and renders JSON (via public Storage `fetch`, not SQL or `backend/data`).
* **Strict Charting Stack:** All data visualization must use Recharts matching the established Tremor aesthetic. Chart.js, Observable Plot, and custom axis-bending are strictly forbidden.
* **Precise Math Copy:** Percentile calculations represent the inclusive CDF ($P(X \le x)$). UI copy must strictly reflect relative frequency and never claim a player is "better than N% of players" due to discrete ties. KDE y-axis is density (∫y dx ≈ 1), not a percent of the league.
* **Square chrome:** No rounded boxes, pills, or drop shadows. Radius is always `0`; elevation is 1px borders only.
* **No mock KDEs:** Empty snapshots stay gray/`pending`. Do not invent league curves in the Next app.

## Explicit non-goals

* Do not rebuild Chart.js / Observable Plot variants.
* Do not re-bend the chart x-axis to match the slider.
* Do not implement Ballnet pipelines or ffoptim models inside `frontend/`.
* Do not connect PostgREST or `@supabase/supabase-js` — public Storage URLs only.
* Do not add rounded boxes, pills, or shadows.
* Do not reintroduce a Node server deploy (Vercel/`next start`) for this org site — Pages serves `frontend/out`.
