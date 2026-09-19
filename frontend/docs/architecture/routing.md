# Routing

| Route | Role |
|---|---|
| `/` | Weekly highlights from `highlights/{season}/w{week}.json` (Stage H), offense-first then defense. Expand loads `dists/league_weekly/...` single-game KDEs. Resolves week via `index/current.json`. |
| `/search` | Client filter over the player index, plus Filter cascade (position group → catalog stat → Best/Worst) backed by `leaderboards/{season}/w{week}/{group}.json`. Default context is current season. |
| `/players/[id]/?season=` | Position catalog stack + season `<select>` at the bottom. Changing season updates the query string; **client** reloads snapshots from Storage (static export cannot re-run RSC for `searchParams`). |
| `/ballnet` | **Projections** — analyze player performance projections for the upcoming week. |
| `/compare/` | **Compare** — up to four same-group players side by side (`?p=id1,id2&season=`). Expand opens one shared league KDE with team-colored markers (`docs/adr/2026-09-17-compare-side-by-side.md`). Selection/season are client-driven. |
| `/ffoptim/` | Client redirect to `/compare/` (query preserved). |

Player pages call `loadHydratedPlayerSnapshots`: scalar `pages/{season}/w{week}/{id}.json` plus shared `league/{season}/w{week}/{group}.json` (merged before `hydratePlayerStats`). Shell HTML for every player id is generated at build via `generateStaticParams`; snapshot JSON loads in the browser.

The frontend `fetch`es public Supabase Storage (`NEXT_PUBLIC_SUPABASE_URL` / `VIZ_STORAGE_BASE_URL`) in local and prod. No sibling `backend/data` reads. Ballnet JSON is not committed under `frontend/` (`docs/adr/2026-09-18-storage-only-loader.md`).

`src/data/players.ts` loads Ballnet `index/players.json` from Storage at build (and via client helpers as needed) (+ lab `demo-*` placeholders).

Weekly / post-game refresh: [`backend/docs/WEEKLY_OPS.md`](../../../backend/docs/WEEKLY_OPS.md). After league-only schema changes, `uv run ballnet upload-storage --season YEAR --league-only` is enough; weekly refreshes should upload pages + league + index together. Redeploy/rebuild Pages after Storage updates if you need the build-time index refreshed; client-fetched boards update without a rebuild.
