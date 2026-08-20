# Knowball frontend handoff

This document is for the next agent. The product is the Next.js prototype in `web/`. Grow that into the public Knowball site. Do not invent a full product spec — follow the locked prototype decisions below and keep later features light until a human tightens them.

---

## Two repositories

| Repo | Role | Visibility |
|---|---|---|
| **knowball** (this repo) | Public Next.js frontend: stats viz, player pages, marketing/home | Public portfolio |
| **ballnet** (separate) | Private Python ML / ingest / distribution engine | Private |

Knowball must not contain Python ingest, database clients, or model code. Ballnet computes percentiles, KDEs, histograms, and player values; Knowball only **renders JSON** that matches the contract in `web/src/lib/distribution.ts`.

In the Knowball **site**, Ballnet is a **separate page** (a destination in the nav), not mixed into the stats rows. Do not build Ballnet inside this handoff. A stub route or “coming soon” page is enough if you need a nav slot.

---

## Current state (what exists today)

The accepted UI lives in **`web/`**. Ingest, density, and binning belong in **ballnet**, not a rewrite inside knowball. Run the app with:

```bash
cd web
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

| Piece | Path |
|---|---|
| Home | `web/src/app/page.tsx` |
| Search | `web/src/app/search/page.tsx` |
| Player page | `web/src/app/players/[id]/page.tsx` |
| Ballnet stub | `web/src/app/ballnet/page.tsx` |
| Position catalog | `web/src/lib/catalog/` |
| JSON contract | `web/src/lib/payload.ts` |
| Expandable row | `web/src/components/stat-row/ExpandableStatRow.tsx` |
| Percentile slider | `web/src/components/stat-row/PercentileSlider.tsx` |
| Distribution charts | `web/src/components/stat-row/TremorDistribution.tsx` |
| Theme wrapper | `web/src/components/stat-row/variants.tsx` (`TremorVariant`) |
| CDF / copy / colors | `web/src/lib/distribution.ts` |
| Routing fixtures | `web/src/data/players.ts` (bios only — no curves) |

**Stack locked in:** Next.js 16 (App Router), React 19, Tailwind v4, shadcn/ui, Framer Motion, **Recharts** (Tremor/zinc palette). Chart.js and Observable Plot were prototyped and **discarded** — do not reintroduce them.

**Visual chrome:** square corners only (`--radius: 0`), no rounded boxes or pills, no drop shadows. See `docs/architecture/ui-components.md` and `docs/adr/2026-08-19-flat-square-chrome.md`.

---

## ExpandableStatRow — locked UX

Collapsed row: chevron, stat name, raw value, ordinal badge, Savant-style bar.

Slider:

- Track is **0–100 percentile**, so **99 is always right of 79** across rows.
- Thumb fill/color = `percentileColor(percentile)` (blue = low, red = high).
- **Not** aligned to the chart x-axis. A warped x-axis was tried and rejected (squeezed tails).

Expanded:

- Framer Motion height animation.
- Caption: **`{pct}%` square label (same slider color) + ` of the league has a {STAT} of {VALUE} or lower.`**  
  If `higherIsBetter` is false, use **`or higher`**.
- Chart x-axis = **raw stat**, fixed global `[xMin, xMax]`.
- Chart y-axis = **relative frequency** (proportion, shown as %). Never raw counts.
- Shade + dashed `ReferenceLine` at the **player’s raw value**.
- Continuous stats: smooth area (KDE). Discrete: bars (uniform bins).

### Tooltips (locked copy)

1. Title: **`{VALUE} {STAT NAME}`** e.g. `13 Rushing Touchdowns`, `5.38 Yards per Carry`
2. Rank: **`This {STAT NAME} is in the {Nth} percentile.`** (CDF at the hovered x; inverted when `higherIsBetter` is false)
3. Frequency:
   - Histogram: **`{p}% of the league has {VALUE}.`** (bin start / count, **not** a range)
   - KDE: **`Relative frequency: {p}% — how common this value is (higher means more typical).`**  
     That `%` is density on the same scale as the y-axis, **not** “percent of the league at this exact point.”

Percentile math: inclusive CDF \(P(X \le x)\). The caption is **not** “better than 95% of players” (too strong for discrete ties).

---

## Data contract (what Ballnet should eventually POST/GET)

Types: `StatPayload` in `web/src/lib/distribution.ts`. JSON snapshots: `JsonStatSnapshot` in `web/src/lib/payload.ts`. The position catalog supplies labels, domains, and format enums; Ballnet supplies values, percentiles, and curve/bin coordinates.

Shared snapshot fields: `id`, `playerValue`, `percentile` (0–100, already oriented so high = good), `qualified`, `xMin`, `xMax`, `yMax`.

- **Continuous:** `curve: { x, y }[]` from Gaussian KDE with **reflection** at bounds. `y` integrates to ~1 over the grid.
- **Discrete:** `bins: { x0, x1, mid, y, count }[]` with **fixed uniform width**, empty bins included. `y = count / n`.

Player pages are **position-aware**: every catalog stat for that position is rendered. Empty snapshots stay gray. Do not generate mock KDEs in Knowball.

---

## Next steps (vague on purpose)

Promote `web/` to be the Knowball app (or merge it to repo root).

### Site shape (not designed yet)

1. **Home** — weekly highlights: players and teams that had strong performances that week. Keep this **vague**: a few cards or lists, current week, no ranking formula or layout locked here.
2. **Search** — every player is searchable. Default context is **current season**.
3. **Player page** — profile + a stack of `ExpandableStatRow` for that player’s stats vs the league, current season by default. **At the bottom**, a dropdown of seasons they played (or seasons we have). Changing it reloads the same page for that year. Do not add “last 10 weeks / all-time” windows unless a human asks.
4. **Ballnet page** — separate nav item. Private product; this repo only needs a public-facing page/entry, not the ML app.

Wire data later: JSON from Ballnet (or a thin BFF). Until then, mocked `StatPayload[]` is fine.

---

## Explicit non-goals for the next agent

- Do not rebuild Chart.js / Observable Plot variants.
- Do not re-bend the chart x-axis to match the slider.
- Do not implement Ballnet, weekly highlight logic, or a full design system beyond the locked square/flat chrome.
- Do not add rounded boxes, pills, or shadows.
- Do not connect a database from the Next.js app.

---

## Suggested first PR sequence

1. Make `web/` the Knowball app (or move Next.js to repo root).
2. Turn the lab page into a **player page shell** using the existing `TremorVariant` / `ExpandableStatRow`.
3. Add routing stubs: `/`, `/players/[id]`, `/ballnet` (placeholder).
4. Add player search and a season `<select>` at the bottom of the player page (options can be mocked).
5. Leave home highlights as a simple placeholder section.
