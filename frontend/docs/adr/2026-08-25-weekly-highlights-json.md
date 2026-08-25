### Context
The home page needs weekly “best games” without fetching dozens of player page JSON files or embedding highlight math in Stage G publish.

### Decision
Ballnet Stage H reads the Stage B spine, scores curated catalog stats with oriented z-scores (`ballnet.scoring`), and publishes one board per week at `highlights/{season}/w{week}.json`. Knowball loads that object via public Storage `fetch` and renders it on `/`. Payload: `schemaVersion: 1`, `top[]`, `byGroup`, rows with `playerId`, `statId`, `value`, `zScore`, `peerN`, `oneInN`, `rank`.

### Consequences
- **Required:** Run `ballnet highlights --season Y --week W` after spine exists; upload with `upload-storage --season Y --highlights`. Home resolves week from `index/current.json`.
- **Deprecated:** Using the player index slice as home “highlights.”
- **Deferred:** Season/all-time boards and Mason rarity copy (field `oneInN` is published but not shown yet).
- **Unchanged:** No Stage G coupling; no Knowball SQL client.
