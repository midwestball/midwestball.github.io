# Routing

| Route | Role |
|---|---|
| `/` | Weekly highlights from `highlights/{season}/w{week}.json` (Stage H), offense-first then defense. Expand loads `dists/league_weekly/...` single-game KDEs. Resolves week via `index/current.json`. |
| `/search` | Client filter over the player index, plus Filter cascade (position group → catalog stat → Best/Worst) backed by `leaderboards/{season}/w{week}/{group}.json`. Default context is current season. |
| `/players/[id]?season=` | Position catalog stack + season `<select>` at the bottom. Changing season reloads the same page. Do not add last-10 / all-time windows unless a human asks. |
| `/ballnet` | **Projections** — analyze player performance projections for the upcoming week. |
| `/compare` | **Compare** — up to four same-group players side by side (`?p=id1,id2&season=`). Expand opens one shared league KDE with team-colored markers (`docs/adr/2026-09-17-compare-side-by-side.md`). |
| `/ffoptim` | Redirects to `/compare` (query preserved). |

Player pages call `loadHydratedPlayerSnapshots`: scalar `pages/{season}/w{week}/{id}.json` plus shared `league/{season}/w{week}/{group}.json` (merged before `hydratePlayerStats`).

Knowball `fetch`es public Supabase Storage (`NEXT_PUBLIC_SUPABASE_URL` / `VIZ_STORAGE_BASE_URL`) in local and prod. No sibling `ballnet/data`. Ballnet JSON is not committed under Knowball (`docs/adr/2026-09-18-storage-only-loader.md`).

`web/src/data/players.ts` loads Ballnet `index/players.json` at request time from Storage (+ lab `demo-*` placeholders).

Weekly / post-game ballnet refresh: sibling repo `ballnet/docs/WEEKLY_OPS.md`. After league-only schema changes, `ballnet upload-storage --season YEAR --league-only` is enough; weekly refreshes should upload pages + league + index together.
