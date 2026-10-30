# Routing

| Route | Role |
|---|---|
| `/` | Weekly highlights from `highlights/{season}/w{week}.json` (Stage H, all-time peers), offense-first then defense. Expand loads `dists/league_weekly/...` single-game KDEs. Resolves week via `index/current.json`. |
| `/search` | Canonical comparison (up to four same-group players via `p`) and client discovery over the player index, plus Filter cascade (position group → catalog stat → Best/Worst) backed by `leaderboards/{season}/w{week}/{group}.json`. Default context is current season. |
| `/players/[id]/?season=` | Compatibility redirect to `/search/?p=ID&season=...`; no standalone player view. |
| `/ballnet` | Upcoming-week projections use `p=entityKey,...&focus=entityKey&points=12.5`; `horizon=ros&p=playerId,...` selects ROS. |
| `/trades/` | Readable `v=1` roster/trade links open as temporary previews; explicit Save replaces the saved personal roster. |
| `/players/?id=ID&season=YYYY` | Compatibility redirect to the same preselected Search comparison, including IDs published after the last site build. |
| `/compare/`, `/ffoptim/` | Static-exported client redirects to `/search/`, preserving the complete query and hash; JavaScript required. |

Search comparison calls `loadHydratedPlayerSnapshots` for selected IDs: scalar `pages/{season}/w{week}/{id}.json` plus shared `league/{season}/w{week}/{group}.json`, merged before `hydratePlayerStats`. Legacy static player paths are generated only as redirect shells; they never fetch profile data in the browser.

The frontend `fetch`es public Supabase Storage (`NEXT_PUBLIC_SUPABASE_URL` / `VIZ_STORAGE_BASE_URL`) in local and prod. No sibling `backend/data` reads. Ballnet JSON is not committed under `frontend/` (`docs/adr/2026-09-18-storage-only-loader.md`).

`src/data/players.ts` loads Ballnet `index/players.json` from Storage at build (and via client helpers as needed) (+ lab `demo-*` placeholders).

Weekly / post-game refresh: [`backend/docs/WEEKLY_OPS.md`](../../../backend/docs/WEEKLY_OPS.md). After league-only schema changes, `uv run ballnet upload-storage --season YEAR --league-only` is enough; weekly refreshes should upload pages + league + index together. Redeploy/rebuild Pages after Storage updates if you need the build-time index refreshed; client-fetched boards update without a rebuild.

## Browser state

Home season/week, Search selection/discovery, projection selections/focus/threshold and trade scenarios restore through browser history. Owned-field patches preserve unrelated parameters. Rapid edits replace the current entry; discrete selections push entries. Projection horizon changes clear incompatible `p,focus,points`. Appearance is personal browser state and never part of these URLs.

## Player navigation

Filter results are full-row comparison selection buttons with no separate Add action or profile links. Home, weekly/ROS and trade name links navigate to Search with the clicked player selected and the source season where available. Projection cards keep name navigation separate from focus controls. Standalone player profile components are removed.
