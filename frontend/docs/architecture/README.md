# Architecture Orientation & Context Routing

## System Architecture Context
**Knowball** is a public portfolio Next.js frontend application (React 19, App Router, Tailwind v4). It exclusively renders pre-computed JSON data. All data ingestion, density logic, and machine learning are handled externally by a private Python engine called **Ballnet**. 

Before modifying or creating new features, locate the relevant domain in the table below and read its specific documentation.

## Orientation Table

| Domain | Description | Target Document |
|---|---|---|
| **UI & Components** | Locked UX rules for `ExpandableStatRow`, percentiles, tooltips, Recharts, and square/flat chrome. | `docs/architecture/ui-components.md` |
| **Visual chrome** | Square corners, no shadows, tight spacing. | `docs/adr/2026-08-19-flat-square-chrome.md` |
| **Data Contracts** | JSON schemas, catalog hydration, and the Ballnet visualization store. | `docs/architecture/data-contracts.md` |
| **Routing & Pages** | Page structures for Home, Search, Player profiles, and the Ballnet stub. | `docs/architecture/routing.md` |
| **Visualization store** | Why Knowball reads JSON only and how Ballnet should table curves vs player values. | `docs/adr/2026-08-19-visualization-json-store.md` |
| **Stat catalog** | Position-group invariants and id stability. | `web/src/lib/catalog/BOUNDARIES.md` |

---

## Global System Invariants

To prevent architectural drift, the following rules apply globally to this repository and supersede all other instructions:

* **No Backend Logic:** Never introduce Python, database clients, or data ingestion scripts into this repository. Knowball only consumes and renders JSON.
* **Strict Charting Stack:** All data visualization must use Recharts matching the established Tremor aesthetic. Chart.js, Observable Plot, and custom axis-bending are strictly forbidden.
* **Precise Math Copy:** Percentile calculations represent the inclusive CDF ($P(X \le x)$). UI copy must strictly reflect relative frequency and never claim a player is "better than N% of players" due to discrete ties.
* **Square chrome:** No rounded boxes, pills, or drop shadows. Radius is always `0`; elevation is 1px borders only.