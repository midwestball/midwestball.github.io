# Routing

| Route | Role |
|---|---|
| `/` | Weekly highlights from `highlights/{season}/w{week}.json` (Stage H). Expand loads `dists/league_weekly/...` single-game KDEs. Resolves week via `index/current.json`. |
| `/search` | Client filter over the player index. Default context is current season. |
| `/players/[id]?season=` | Position catalog stack + season `<select>` at the bottom. Changing season reloads the same page. Do not add last-10 / all-time windows unless a human asks. |
| `/ballnet` | Public Ballnet destination: DS writeups / research narrative (not the pipeline repo itself). |
| `/ffoptim` | Public stub for the draft-optimizer UI. Modeling lives in the private **ffoptim** repo; this page will later host Sleeper-linked draft help. |

Player pages call `loadHydratedPlayerSnapshots`: scalar `pages/{season}/w{week}/{id}.json` plus shared `league/{season}/w{week}/{group}.json` (merged before `hydratePlayerStats`).

Fetch order: Supabase Storage public URL when configured (`NEXT_PUBLIC_SUPABASE_URL` / `VIZ_STORAGE_BASE_URL`); else sibling `ballnet/data/` when `BALLNET_DATA_DIR` or default relative path is set; else synced copies under `web/src/data/ballnet/`. `VIZ_PREFER_LOCAL=1` forces local only.

`web/src/data/players.ts` loads Ballnet `index/players.json` at request time (+ lab `demo-*` placeholders). Optional offline copies live under `web/src/data/ballnet/` via `ballnet publish-all --sync-knowball ../knowball/web` (or `publish-range`).

Weekly / post-game ballnet refresh: sibling repo `ballnet/docs/WEEKLY_OPS.md`. After league-only schema changes, `ballnet upload-storage --season YEAR --league-only` is enough; weekly refreshes should upload pages + league + index together.
