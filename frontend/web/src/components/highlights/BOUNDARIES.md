# Boundaries: `web/src/components/highlights`

## Always

- Render Stage H board rows only — no client-side z-score math.
- Keep square chrome (`rounded-none`, hairline borders) matching search rows.
- Link to `/players/{id}?season=` from the board’s season.

## Ask First

- Showing `oneInN` rarity copy on the home page (coordinate with Mason).
- Adding season / all-time board tabs.

## Never

- Fetch individual player page JSON for the home board.
- Invent ranks when `loadHighlightsBoard` returns null.

## Silent Failures & Gotchas

- Missing board → empty top list + pending copy on home; do not fall back to player-index slice.
- Stat formatting looks up Knowball catalog by `positionGroup` + `statId`; unknown ids fall back to raw number.
