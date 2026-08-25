# Boundaries: `web/src/components/highlights`

## Always

- Render Stage H board rows only — no client-side z-score math.
- Keep square chrome (`rounded-none`, hairline borders) matching search rows.
- Expand with Framer Motion like a stat row; chart from `dists/league_weekly` via props — never invent a curve.
- Color collapsed z chip and expanded chart with `sigmaColor` (oriented σ), not percentile.
- Link player name to `/players/{id}?season=` from the board’s season (`stopPropagation` so the link does not toggle expand).

## Ask First

- Showing `oneInN` rarity copy on the home page (coordinate with Mason).
- Adding season / all-time board tabs.

## Never

- Fetch individual player page JSON or YTD `league/` curves for the home board expand.
- Reuse `ExpandableStatRow` / percentile slider on home.
- Invent ranks when `loadHighlightsBoard` returns null.

## Silent Failures & Gotchas

- Missing board → empty top list + pending copy on home; do not fall back to player-index slice.
- Missing `league_weekly` shape for a row → expand shows pending dashed box; row still ranks.
- Stat formatting / `higherIsBetter` look up Knowball catalog by `positionGroup` + `statId`; unknown ids fall back to raw number and assume higher-is-better.
- `peerN` / `zScore` on the board are season-of-games peers (`week <= W`), not same-week-only.
