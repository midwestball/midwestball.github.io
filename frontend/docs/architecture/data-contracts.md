# Data contracts

Knowball renders JSON. Ballnet computes it. Do not put a database client in this app.

## Page payload

`PlayerPageJson` in `web/src/lib/payload.ts`: player bio, `season`, `asOfWeek`, and `stats[]` snapshots keyed by catalog `id`.

Hydration (`hydratePlayerStats`) always walks the **full position catalog**. Missing snapshots stay `pending`. `alwaysUnavailable` catalog flags become `not_in_nflverse` even if Ballnet sends a row.

Rate stats are stored **0–1**. Percentile is inclusive CDF \(P(X \le x)\), already oriented so the slider's 100 is "good".

## Recommended Ballnet store (visualization only)

Curves are a **league** object. Player pages only need a scalar overlay. That is why this is two tables plus a bio index — not a copy of nflverse.

```text
players
  player_id (GSIS) pk
  display_name, position, team, pfr_player_id

player_seasons
  (player_id, season) pk
  team, position

league_distributions
  (season, as_of_week, position_group, stat_id) pk
  kind, x_min, x_max, y_max
  curve jsonb | bins jsonb
  n_sample, computed_at

player_stat_values
  (player_id, season, as_of_week, stat_id) pk
  player_value, percentile, denom_ytd, min_n
  qualified boolean
  unavailable_reason null | insufficient_sample | missing_source | not_in_nflverse
```

`as_of_week` is the NFL week being viewed. Ramp–hold uses `min_n = n_base × min(w, 4)` in Ballnet, then sets `qualified`.

Publish path: join those tables into one `PlayerPageJson` per player-season (Storage object or static file). Knowball fetches that file. Search can later use a tiny `players` index JSON — still not a runtime SQL client.

## Do not

- Store raw weekly box scores in Knowball.
- Duplicate the KDE onto every player row in Postgres.
- Impute 0 when NGS/PFR is missing (`missing_source`).
