# Boundaries: `web/src/components/search`

## Always

- Position filter options are publishable **groups** (`GROUP_LABEL`), not raw NFL codes; stats come from `STATS_BY_GROUP` (skip `alwaysUnavailable`).
- Ranked Best/Worst lists load `leaderboards/{season}/w{week}/{group}.json` via the search server action — never N player-page fetches.
- Sort on oriented percentile (100 = good); Best = descending, Worst = ascending; null percentiles last.
- Keep square chrome (`rounded-none`, no pills/shadows) on the Filter cascade.

## Ask First

- Changing the leaderboard JSON shape or Storage path.
- Syncing filter state into URL query params (not shipped).

## Never

- Invent ranks when the leaderboard artifact is missing.
- Bundle leaderboard JSON into the Next client bundle.
- Mix highlight z-score boards with YTD search sort.

## Silent Failures & Gotchas

- Filter open + position only (no stat) still uses the bio index scoped to that group — no values shown until a stat is chosen.
- Missing leaderboard → “Rankings not published…” while bio search still works when Filter is cleared or only position is set.
- Demo players in the index have no leaderboard rows.
