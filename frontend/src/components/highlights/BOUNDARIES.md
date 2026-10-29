# Boundaries: `frontend/src/components/highlights`

## Always

- Render Stage H board rows only — no client-side z-score math for ranking (home may re-sort published rows into offense/defense overall lists by published `zScore`).
- Home layout: offense overall (preview 8 + “See more”) → offense by group (preview 3 + “See more”). Defense sections are hidden until distribution issues are fixed (note in hero). Season + week pickers (2016–current); URL `?season=&week=` for shareable links.
- Keep square chrome (`rounded-none`, hairline borders) matching search rows.
- Expand with Framer Motion like a stat row; chart from `dists/league_weekly` via props — never invent a curve. Curves are all-time single-game peers (`scope: "league_game_all_time"`).
- Show empirical **`rarityTier`** (“1 in N”) chips: bronze from 50, silver from 100, gold from 1,000, diamond from 10,000, and purple from 100,000. Shimmer starts at bronze.
- Highlight histograms shade whole bins through the hovered or focused bin and show the observed bin and cumulative shares. Preserve the published bin-edge semantics.
- One list row per player (primary = highest `zScore`). Nested `also[]` performances render only when expanded (“Also this week”). `HighlightList` always runs `collapseHighlightsByPlayer` so older boards without `also` still dedupe.
- Link player name to the static-safe `/players/?id={id}&season=` route using the board's season (`stopPropagation` so the link does not toggle expand).
- Render published `fantasyPosRank` on the position label via `PositionRankLabel`. Tooltip copy is kind-specific. `stopPropagation` so the subscript does not toggle expand.

## Ask First

- Adding season / all-time board **tabs** (separate boards). Peer sample is already all-time; home has season/week pickers instead.
- Changing the `10^k` rarity ladder or tier colors.
- Re-enabling defensive highlight sections on home (needs distribution fix first).

## Never

- Fetch individual player page JSON or YTD `league/` curves for the home board expand.
- Reuse `ExpandableStatRow` / percentile slider on home.
- Invent ranks when `loadHighlightsBoard` returns null, or invent `fantasyPosRank` when Ballnet omitted it.
- Treat highlight `rank` as a fantasy position rank — that field is z-score board order among unique players.
- Color home chips with Savant σ (`sigmaColor`) — rarity tiers own the chrome.

## Silent Failures & Gotchas

- Missing board → empty top list + pending copy on home; do not fall back to player-index slice.
- Missing `league_weekly` shape for a row → expand shows pending dashed box; row still ranks.
- Stat formatting / `higherIsBetter` look up the frontend catalog by `positionGroup` + `statId`; unknown ids fall back to raw number and assume higher-is-better.
- `peerN` / `zScore` on the board are **all-time** single-game peers (2016+ through season/week), not same-week-only or season-only.
- `prefers-reduced-motion: reduce` disables rarity chip shimmer.
