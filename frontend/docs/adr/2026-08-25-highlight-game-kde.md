### Context
Home highlight rows need an expandable single-game KDE (not season YTD) colored by oriented σ, while ranking must stay consistent with that same peer pool.

### Decision
Ballnet Stage H rescored boards against season-of-games peers (`week <= W` player-weeks) and publishes allowlist curves at `dists/league_weekly/{season}/w{week}/{group}.json` (`scope: "league_weekly"`). Knowball loads those separately from `league/` YTD files, expands highlight rows with Framer Motion (no percentile slider), and colors fill/caption via `sigmaColor` (Savant stops clipped at ±3σ). Shared `DistributionChart` accepts an explicit color + standing copy so player pages keep percentile behavior.

### Consequences
- **Required:** Run `ballnet highlights` then `upload-storage --highlights` so both the board and `dists/league_weekly/` land in Storage. Home must not invent curves when a weekly dist is missing.
- **Required:** Ranking, collapsed z chip, chart color, and caption all use season-of-games oriented z — not same-week-only peers and not percentiles.
- **Deprecated:** Reusing `league/{season}/w{week}/{group}.json` for home expand charts.
- **Unchanged:** No Stage G coupling; no curves embedded on `HighlightRow`; `oneInN` copy still deferred.
