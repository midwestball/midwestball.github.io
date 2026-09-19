# Boundaries: `web/src/components/stat-row`

## Always

- Keep collapsed row layout: chevron, label, raw value, inline percentile slider (see `docs/architecture/ui-components.md`).
- Render charts only when `isStatReady` — gray unavailable states for pending / insufficient / missing / not_in_nflverse.
- Use Recharts + square chrome (`rounded-none`, no shadows).
- Player percentile badge comes from Ballnet JSON; do not re-orient in the chart layer.
- `TremorDistribution.tsx` charts KDE `curve[]` for every ready stat (catalog `kind` does not change the chart). Shared `DistributionChart` accepts an explicit color + hover standing so highlights can use σ coloring without percentile fields.

## Ask First

- Changing tooltip standing copy or slider shading semantics (`higherIsBetter` left/right mass).

## Never

- Chart.js, Observable Plot, or axis warping to match the slider track.
- Histogram bars, rug plots, or synthesizing ticks from leftover `bins`/`samples`.
- Mixing ffoptim or Ballnet writeup UI into this stack.

## Silent Failures & Gotchas

- League `curve[]` arrives via `mergeLeagueIntoSnapshots` — not on scalar player pages alone.
- `ready` requires `curve.length > 0` for every catalog kind.
- Lab demos under `/lab/qb` use empty snapshots — charts stay gray until wired to real JSON.
- KDE y-axis is density, not “% of the league”.
