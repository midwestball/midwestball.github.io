# Boundaries: `web/src/components/search`

## Always

- Position filter options are publishable **groups** (`GROUP_LABEL`), not raw NFL codes; stats come from `STATS_BY_GROUP` (skip `alwaysUnavailable`).
- Ranked Best/Worst lists load `leaderboards/{season}/w{week}/{group}.json` via the search server action — never N player-page fetches.
- Sort on oriented percentile (100 = good); Best = descending, Worst = ascending; null percentiles last.
- Filter row sits under the search input; Stat and Best/Worst stay visible but disabled (gray) until prerequisites are set.
- Min-volume slider sits on the same row, right-aligned (`ml-auto`). Floor and default = ramp–hold `minNBase × min(asOfWeek, 4)`; filter with `denomYtd >= min`.
- Keep square chrome (`rounded-none`, no pills/shadows) on Filter controls.

## Ask First

- Changing the leaderboard JSON shape or Storage path.
- Syncing filter state into URL query params (not shipped).
- Allowing the volume slider below ramp–hold (currently floored there).

## Never

- Invent ranks when the leaderboard artifact is missing.
- Bundle leaderboard JSON into the Next client bundle.
- Mix highlight z-score boards with YTD search sort.

## Silent Failures & Gotchas

- Position only (no stat) still uses the bio index scoped to that group — no values shown until a stat is chosen.
- Missing leaderboard → “Rankings not published…” while bio search still works when only position is set or filters are cleared.
- Demo players in the index have no leaderboard rows.
- Leaderboards without `denomYtd` (pre-republish) drop all ranked rows once a min volume is applied — republish Stage G leaderboards after adding the field.
- Slider max is the max `denomYtd` in the loaded board (at least the ramp–hold floor).
