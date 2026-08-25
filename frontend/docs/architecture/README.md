# Architecture Orientation & Context Routing

## System Architecture Context

**Knowball** is a public portfolio Next.js frontend (React 19, App Router, Tailwind v4) that exclusively renders pre-computed JSON. Ingest, densities, and percentiles live in **ballnet**. Fantasy draft modeling and optimization live in **ffoptim**.

| Repo | Role | Visibility |
|---|---|---|
| **knowball** (this repo) | Public site: stats viz, Ballnet writeups page, ffoptim draft UI | Public |
| **ballnet** (separate) | Python data pipeline + DS engine; publishes viz JSON for Knowball | Public |
| **ffoptim** (separate) | Modeling + snake-draft optimization (e.g. Sleeper-linked drafts) | Private |

Knowball must not contain Python ingest, database clients, or model/optimizer code. Ballnet computes percentiles, KDEs, and player values; Knowball only **renders JSON** matching `web/src/lib/distribution.ts` / `web/src/lib/payload.ts`.

Before modifying or creating new features, locate the relevant domain in the table below and read its specific documentation.

## Orientation Table

| Domain | Description | Target Document |
|---|---|---|
| **UI & Components** | Locked UX rules for `ExpandableStatRow`, percentiles, tooltips, Recharts, and square/flat chrome. | `docs/architecture/ui-components.md` |
| **Visual chrome** | Square corners, no shadows, tight spacing. | `docs/adr/2026-08-19-flat-square-chrome.md` |
| **Data Contracts** | JSON schemas, catalog hydration, and the Ballnet visualization store. | `docs/architecture/data-contracts.md` |
| **Routing & Pages** | Home, Search, Player, Ballnet writeups, ffoptim stub. | `docs/architecture/routing.md` |
| **Visualization store** | Why Knowball reads JSON only and how Ballnet should table curves vs player values. | `docs/adr/2026-08-19-visualization-json-store.md` |
| **Split league JSON** | Player pages are scalars; league curves are one file per group/season/week. | `docs/adr/2026-08-20-split-league-distributions.md` |
| **KDE-only league shape** | Every catalog id publishes reflected KDE `curve[]`; histograms and rug `samples` retired. | `docs/adr/2026-08-24-kde-only-league-shape.md` |
| **Stat row / charts** | Expandable row invariants; KDE area chart in `TremorDistribution.tsx`. | `web/src/components/stat-row/BOUNDARIES.md` |
| **Product split** | Public knowball + public ballnet + private ffoptim ownership. | `docs/adr/2026-08-20-three-product-split.md` |
| **Stat catalog** | Position-group invariants and id stability. | `web/src/lib/catalog/BOUNDARIES.md` |
| **Ballnet JSON loader** | Storage fetch + local fallback; league merge before hydrate. | `web/src/lib/BOUNDARIES-ballnet-store.md` |
| **Vercel + Storage deploy** | Production loads index/pages/league from public Supabase Storage; no bundled player index. | `docs/adr/2026-08-24-vercel-supabase-storage.md` |
| **ETL contract** | Ballnet publish path for Knowball viz (Leg 1). | `.plans/ballnet-etl-knowball-visualizations.md` |
| **Weekly refresh** | Post-game ballnet recipe (lives in ballnet). | Sibling `ballnet/docs/WEEKLY_OPS.md` |

## App map (where things live)

The accepted UI lives under **`web/`**. Run with `cd web && npm install && npm run dev` → [http://localhost:3000](http://localhost:3000).

| Piece | Path |
|---|---|
| Home | `web/src/app/page.tsx` |
| Search | `web/src/app/search/page.tsx` |
| Player page | `web/src/app/players/[id]/page.tsx` |
| Ballnet page | `web/src/app/ballnet/page.tsx` |
| ffoptim stub | `web/src/app/ffoptim/page.tsx` |
| Position catalog | `web/src/lib/catalog/` |
| JSON contract | `web/src/lib/payload.ts` |
| Expandable row | `web/src/components/stat-row/ExpandableStatRow.tsx` |
| Percentile slider | `web/src/components/stat-row/PercentileSlider.tsx` |
| Distribution charts | `web/src/components/stat-row/TremorDistribution.tsx` |
| Theme wrapper | `web/src/components/stat-row/variants.tsx` (`TremorVariant`) |
| CDF / copy / colors | `web/src/lib/distribution.ts` |
| Routing fixtures | `web/src/data/players.ts` (Ballnet index + lab demos — no curves) |

**Stack locked in:** Next.js 16 (App Router), React 19, Tailwind v4, shadcn/ui, Framer Motion, **Recharts** (Tremor/zinc palette). Chart.js and Observable Plot were prototyped and **discarded** — do not reintroduce them.

## Global System Invariants

To prevent architectural drift, the following rules apply globally to this repository and supersede all other instructions:

* **No Backend Logic:** Never introduce Python, database clients, or data ingestion scripts into this repository. Knowball only consumes and renders JSON (via public Storage `fetch`, not SQL).
* **Strict Charting Stack:** All data visualization must use Recharts matching the established Tremor aesthetic. Chart.js, Observable Plot, and custom axis-bending are strictly forbidden.
* **Precise Math Copy:** Percentile calculations represent the inclusive CDF ($P(X \le x)$). UI copy must strictly reflect relative frequency and never claim a player is "better than N% of players" due to discrete ties. KDE y-axis is density (∫y dx ≈ 1), not a percent of the league.
* **Square chrome:** No rounded boxes, pills, or drop shadows. Radius is always `0`; elevation is 1px borders only.
* **No mock KDEs:** Empty snapshots stay gray/`pending`. Do not invent league curves in the Next app.

## Explicit non-goals

* Do not rebuild Chart.js / Observable Plot variants.
* Do not re-bend the chart x-axis to match the slider.
* Do not implement ballnet pipelines or ffoptim models inside this repo.
* Do not connect PostgREST or `@supabase/supabase-js` — public Storage URLs only.
* Do not add rounded boxes, pills, or shadows.
