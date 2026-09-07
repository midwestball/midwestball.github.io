# Search leaderboards JSON

## Context

Search needs position → stat → best/worst ranking, but `index/players.json` only carries bios. Fetching every player page for a group is not viable in the Next app.

## Decision

Ballnet publishes one precomputed board per publishable group at `leaderboards/{season}/w{week}/{group}.json`, built from Stage E `ytd_*_pct.parquet`. Rows still include `denomYtd` for ramp–hold parity and fallback. Knowball loads that artifact (Storage → local fallback) and sorts client-side; percentiles are already oriented so Best = high percentile. Min-volume slider defaults to ramp–hold `minNBase × min(asOfWeek, 4)` and filters on catalog `volumeStatId` joined from the sibling counting-stat rows on the same board (`denomYtd` only when `volumeStatId` is unset or the sibling join misses).

## Consequences

- Weekly `publish-all` must emit leaderboards alongside pages/league; upload includes `leaderboards/`.
- Do not enrich the player index with all percentiles.
- Do not invent a search HTTP/SQL API for this ranking path.
- Returner stays unpublished (same as Stage G).
- Recompute slider floor in Knowball from catalog + week — do not trust a separate published `minN` field.
- Catalog `volumeStatId` / `volume_stat_id` must point at a counting-stat id that exists on the same group board; Stage C qualification still uses machine `denom`, not this UX field.