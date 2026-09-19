### Context
Embedded league KDE shapes on every `PlayerPageJson` exhausted free-tier Storage (~355 MB/season). Curves are league-scoped, not player-specific.

### Decision
Ballnet publishes scalar-only player pages under `pages/{season}/w{week}/{gsis}.json` and shared camelCase league files under `league/{season}/w{week}/{positionGroup}.json`. the frontend loads both (parallel/cached) and merges shapes before `hydratePlayerStats`.

### Consequences
- Do not re-embed `curve` on player pages for Storage size.
- `ready` rows require `curve[]` after league merge (or legacy embedded curves).
- Uploads must include `league/` alongside `pages/` and `index/`.
- Local smoke tests use Storage after `upload-storage` (`docs/adr/2026-09-18-storage-only-loader.md`). Do not point the frontend at `backend/data`.
