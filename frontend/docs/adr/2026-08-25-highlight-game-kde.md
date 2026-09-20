### Context
Home highlight rows need an expandable single-game KDE (not season YTD) colored by rarity tier, while ranking must stay consistent with that same peer pool.

### Decision
Ballnet Stage H scores boards against **all-time** single-game peers and publishes allowlist curves at `dists/league_weekly/{season}/w{week}/{group}.json` (`scope: "league_game_all_time"`). The frontend loads those separately from `league/` YTD files, expands highlight rows with Framer Motion (no percentile slider), and colors fill/caption via `rarityTierColor` (bronze→purple ladder; shimmer on tiers ≥ 100). Shared `DistributionChart` accepts an explicit color + standing copy so player pages keep percentile behavior.

### Consequences
- **Required:** Run `ballnet highlights` then `upload-storage --highlights` so both the board and `dists/league_weekly/` land in Storage. Home must not invent curves when a weekly dist is missing.
- **Required:** Ranking uses all-time oriented z; collapsed chip, chart color, and caption use snapped `rarityTier` (“1 in N” vs all-time peers).
- **Deprecated:** Reusing `league/{season}/w{week}/{group}.json` for home expand charts. Savant `sigmaColor` on home highlight chrome. Season-of-games-only peer sample / `scope: "league_weekly"`.
- **Unchanged:** No Stage G coupling; no curves embedded on `HighlightRow`.

### Superseding (2026-09-19)
All-time KDE sample + rarity-tier chrome replace season-of-games σ coloring.
