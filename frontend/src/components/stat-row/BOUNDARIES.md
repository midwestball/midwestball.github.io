# Boundaries: `frontend/src/components/stat-row`

## Always

- Keep collapsed row layout: chevron, label, raw value, inline percentile slider (see `docs/architecture/ui-components.md`).
- Render charts only when `isStatReady` — gray unavailable states for pending / insufficient / missing / not_in_nflverse.
- Use Recharts + square chrome (`rounded-none`, no shadows).
- Player percentile badge comes from Ballnet JSON; do not re-orient in the chart layer.
- Version 2 stat rows use observed histogram bins and empirical midranks. Legacy version 1 snapshots may continue to display their KDE until migrated.

## Ask First

- Changing tooltip standing copy or slider shading semantics (`higherIsBetter` left/right mass).

## Never

- Chart.js, Observable Plot, or axis warping to match the slider track.
- Synthesizing histograms from legacy KDE curves or presenting estimates as observed counts.
- Mixing ffoptim or Ballnet writeup UI into this stack.

## Silent Failures & Gotchas

- League `curve[]` arrives via `mergeLeagueIntoSnapshots` — not on scalar player pages alone.
- `ready` requires a valid histogram or a legacy curve and a percentile.
- Lab demos under `/lab/qb` use empty snapshots — charts stay gray until wired to real JSON.
- KDE y-axis is density, not “% of the league”.
