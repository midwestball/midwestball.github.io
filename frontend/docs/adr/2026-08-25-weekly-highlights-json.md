### Context
The home page needs weekly “best games” without fetching dozens of player page JSON files or embedding highlight math in Stage G publish.

### Decision
Ballnet Stage H reads the Stage B spine, scores curated catalog stats with oriented z-scores vs **season-of-games** peers (`ballnet.scoring`), and publishes one board per week at `highlights/{season}/w{week}.json` plus allowlist KDEs under `dists/league_weekly/`. Knowball loads those objects via public Storage `fetch` and renders them on `/`. Payload: `schemaVersion: 1`, `top[]`, `byGroup`, rows with `playerId`, `statId`, `value`, `zScore`, `peerN`, `oneInN`, `rank`.

### Consequences
- **Required:** Run `ballnet highlights --season Y --week W` after spine exists; upload with `upload-storage --season Y --highlights` (board + `dists/league_weekly/`). Home resolves week from `index/current.json`.
- **Deprecated:** Using the player index slice as home “highlights.” Same-week-only peer z for Stage H ranking (superseded by season-of-games; see `2026-08-25-highlight-game-kde.md`).
- **Deferred:** Season/all-time boards and Mason rarity copy (field `oneInN` is published but not shown yet).
- **Unchanged:** No Stage G coupling; no Knowball SQL client.
