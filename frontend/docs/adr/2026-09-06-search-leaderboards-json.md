# Search leaderboards JSON

## Context

Search needs position → stat → best/worst ranking, but `index/players.json` only carries bios. Fetching every player page for a group is not viable in the Next app.

## Decision

Ballnet publishes one precomputed board per publishable group at `leaderboards/{season}/w{week}/{group}.json`, built from Stage E `ytd_*_pct.parquet`. Rows include `denomYtd` so Knowball can filter on volume. Knowball loads that artifact (Storage → local fallback) and sorts client-side; percentiles are already oriented so Best = high percentile. Min-volume slider defaults to ramp–hold `minNBase × min(asOfWeek, 4)`.

## Consequences

- Weekly `publish-all` must emit leaderboards alongside pages/league; upload includes `leaderboards/`.
- Do not enrich the player index with all percentiles.
- Do not invent a search HTTP/SQL API for this ranking path.
- Returner stays unpublished (same as Stage G).
- Recompute slider floor in Knowball from catalog + week — do not trust a separate published `minN` field.