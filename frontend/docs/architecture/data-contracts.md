# Data contracts

Knowball renders JSON. Ballnet computes it. Do not put a SQL/PostgREST client in this app — production reads public Supabase **Storage** objects with `fetch`.

## Page payload

`PlayerPageJson` in `web/src/lib/payload.ts`: player bio, `season`, `asOfWeek`, and `stats[]` **scalar** snapshots keyed by catalog `id` (value, percentile, qualified, reasons). Domain + `curve` come from the league file below (or legacy embeds).

Hydration (`hydratePlayerStats`) always walks the **full position catalog**. Missing snapshots stay `pending`. `alwaysUnavailable` catalog flags become `not_in_nflverse` even if Ballnet sends a row. Load path: `loadHydratedPlayerSnapshots` merges league shapes first.

Rate stats are stored **0–1**. Percentile is inclusive CDF \(P(X \le x)\), already oriented so the slider's 100 is "good".

## League payload

`league/{season}/w{week}/{positionGroup}.json` — one file per group slice:

```text
schemaVersion: 1
season, asOfWeek, positionGroup
stats: { [statId]: {
  kind, xMin, xMax, yMax,    # kind is catalog metadata (formatting)
  curve,                     # reflected KDE for every id
} }
```

`ready` rows require non-empty `curve[]` after league merge. Histograms (`bins`) and rug `samples` are not part of the contract.

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
  curve jsonb
  n_sample, computed_at

player_stat_values
  (player_id, season, as_of_week, stat_id) pk
  player_value, percentile, denom_ytd, min_n
  qualified boolean
  unavailable_reason null | insufficient_sample | missing_source | not_in_nflverse
```

`as_of_week` is the NFL week being viewed. Ramp–hold uses `min_n = n_base × min(w, 5)` in Ballnet, then sets `qualified`.

Publish path: Storage (or local `data/`) serves **scalar** `PlayerPageJson` plus **shared** `league/*.json`. Knowball merges at fetch time — still not a runtime SQL client. Weekly home boards are separate Stage H objects under `highlights/{season}/w{week}.json`. Expand charts load allowlist single-game KDEs from `dists/league_weekly/{season}/w{week}/{group}.json` (`scope: "league_weekly"`) — never the YTD `league/` curves.

## Search leaderboard payload

`leaderboards/{season}/w{week}/{positionGroup}.json` — one file per publishable group (not returner):

```text
schemaVersion: 1
season, asOfWeek, positionGroup
stats: { [statId]: [{
  playerId, name, position, team,
  value, percentile,  # percentile already oriented (100 = good)
  denomYtd,        # season-to-date denom for ramp–hold (slider fallback)
  qualified
}] }
```

Built from Stage E `ytd_*_pct.parquet`. Knowball search Filter sorts Best/Worst on `percentile` without fetching player pages. Min-volume slider defaults to ramp–hold `minNBase × min(asOfWeek, 5)` and prefers catalog `volumeStatId` → `board.stats[volumeStatId].value` joined by `playerId`; `denomYtd` is fallback only. Rows may include unqualified players (`percentile: null`); UI keeps nulls last.

## Do not

- Store raw weekly box scores in Knowball.
- Duplicate the KDE onto every player page JSON (or every player row in Postgres).
- Impute 0 when NGS/PFR is missing (`missing_source`).
- Reuse `league_ytd` curves for home highlight expand charts.
- Stuff every percentile into `index/players.json` for search sort.