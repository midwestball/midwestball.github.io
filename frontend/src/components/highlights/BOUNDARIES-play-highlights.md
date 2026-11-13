# Boundaries: play highlights lab (`/lab/plays`)

## Always

- Render published `highlights/plays/{season}/w{week}.json` rows only — no client-side rarity math.
- Show game clock (`gameClock` / `clock` + `quarter`) on each row when present.
- Keep the route out of `SiteHeader` nav until product asks to ship it.

## Ask First

- Adding play highlights to site navigation or the home page.
- Adding expand charts / KDEs for play boards.

## Never

- Reuse Stage H `HighlightList` expand charts (those expect `league_weekly` game shapes).
- Invent ranks or rarity when Storage returns null.
