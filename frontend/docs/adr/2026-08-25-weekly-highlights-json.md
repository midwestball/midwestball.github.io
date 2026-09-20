### Context
The home page needs weekly “best games” without fetching dozens of player page JSON files or embedding highlight math in Stage G publish.

### Decision
Ballnet Stage H reads Stage B spines, scores curated catalog stats with oriented z-scores vs **all-time** single-game peers (seasons `2016..S-1` full + season `S` weeks `<= W`), and publishes one board per week at `highlights/{season}/w{week}.json` plus allowlist KDEs under `dists/league_weekly/`. The frontend loads those objects via public Storage `fetch` and renders them on `/`.

Payload: `schemaVersion: 1`, `top[]`, `byGroup`, rows with `playerId`, `statId`, `value`, `zScore`, `peerN`, `oneInN`, `rarityTier`, `rank`, optional `also[]` (same-player secondary performances). Lists are collapsed to one primary row per player (max `zScore`) before caps.

### Consequences
- **Required:** Run `ballnet highlights --season Y --week W` after spines exist for `2016..Y`; upload with `upload-storage --season Y --highlights` (board + `dists/league_weekly/`). Home resolves week from `index/current.json`.
- **Required:** Home shows snapped `rarityTier` (“1 in N” on `10^k`) with bronze→purple chrome; ranking stays on `zScore`.
- **Deprecated:** Using the player index slice as home “highlights.” Same-week-only and season-of-games-only peer z for Stage H (superseded by all-time peers).
- **Deferred:** Separate season / all-time board **tabs** (peer sample is already all-time).
- **Unchanged:** No Stage G coupling; no frontend SQL client.

### Superseding (2026-09-19)
All-time peer sample, `rarityTier` + `also[]`, and rarity UI replace season-of-games σ chrome. See also `2026-08-25-highlight-game-kde.md`.
