# Boundaries: play highlights lab (`/lab/plays`)

## Always

- Render published `highlights/plays/{season}/w{week}.json` rows only — no client-side rarity math.
- Expand charts from `dists/league_plays/{season}/w{week}.json` keyed by row `peerKey` — never invent bins.
- Show game clock (`gameClock` / `clock` + `quarter`) on each row when present.
- Keep the route out of `SiteHeader` nav until product asks to ship it.

## Ask First

- Adding play highlights to site navigation or the home page.

## Never

- Reuse Stage H `league_weekly` game shapes for play expand charts.
- Invent ranks, rarity, or histogram bins when Storage returns null.
