### Context
Embedded league KDE shapes on every `PlayerPageJson` exhausted free-tier Storage (~355 MB/season). Curves are league-scoped, not player-specific.

### Decision
Ballnet publishes scalar-only player pages under `pages/{season}/w{week}/{gsis}.json` and shared camelCase league files under `league/{season}/w{week}/{positionGroup}.json`. Knowball loads both (parallel/cached) and merges shapes before `hydratePlayerStats`.

### Consequences
- Do not re-embed `curve` on player pages for Storage size.
- `ready` rows require `curve[]` after league merge (or legacy embedded curves).
- Uploads must include `league/` alongside `pages/` and `index/`.
- Prefer `VIZ_PREFER_LOCAL=1` + `BALLNET_DATA_DIR` for local smoke tests without Storage.
