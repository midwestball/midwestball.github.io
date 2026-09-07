# Search leaderboards JSON

## Context

Search needs position → stat → best/worst ranking, but `index/players.json` only carries bios. Fetching every player page for a group is not viable in the Next app.

## Decision

Ballnet publishes one precomputed board per publishable group at `leaderboards/{season}/w{week}/{group}.json`, built from Stage E `ytd_*_pct.parquet`. Knowball loads that artifact (Storage → local fallback) and sorts client-side; percentiles are already oriented so Best = high percentile.

## Consequences

- Weekly `publish-all` must emit leaderboards alongside pages/league; upload includes `leaderboards/`.
- Do not enrich the player index with all percentiles.
- Do not invent a search HTTP/SQL API for this ranking path.
- Returner stays unpublished (same as Stage G).
