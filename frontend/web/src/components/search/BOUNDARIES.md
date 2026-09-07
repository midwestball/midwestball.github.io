# Boundaries: `web/src/components/search`

## Always

- Position filter options are publishable **groups** (`GROUP_LABEL`), not raw NFL codes; stats come from `STATS_BY_GROUP` (skip `alwaysUnavailable`).
- Ranked Best/Worst lists load `leaderboards/{season}/w{week}/{group}.json` via the search server action — never N player-page fetches.
- Sort on oriented percentile (100 = good); Best = descending, Worst = ascending; null percentiles last.
- Filter row sits under the search input; Stat and Best/Worst stay visible but disabled (gray) until prerequisites are set.
- Min-volume control sits on the same row, right-aligned (`ml-auto`), fixed compact width (does not `flex-1`). Default = ramp–hold `minNBase × min(asOfWeek, 5)`; range is **0…max(volume)** so users may go below baseline. Pair the range with a direct number input for large spans.
- Resolve volume as `board.stats[volumeStatId].value` joined by `playerId` when the catalog sets `volumeStatId`; else fall back to the rate row’s `denomYtd`. If neither yields any values, filter with `qualified` and keep the slider disabled.
- Label the control from the volume sibling’s catalog `label` (e.g. “Min Field Goal Attempts”), not the rate row’s display `denom`.
- Keep square chrome (`rounded-none`, no pills/shadows) on Filter controls.

## Ask First

- Changing the leaderboard JSON shape or Storage path.
- Syncing filter state into URL query params (not shipped).

## Never

- Invent ranks when the leaderboard artifact is missing.
- Bundle leaderboard JSON into the Next client bundle.
- Mix highlight z-score boards with YTD search sort.
- Treat a rejected `fetchLeaderboard` as an empty result list — surface the error state.
- Invent volume for `red_zone_*` / `route_pct` (or other missing-spine ids) via a fake sibling.

## Silent Failures & Gotchas

- Position only (no stat) still uses the bio index scoped to that group — no values shown until a stat is chosen.
- Demo players in the index have no leaderboard rows.
- NGS-week / games / snaps / dropbacks / air-yards / tackle_chances denoms leave `volumeStatId` unset — slider uses `denomYtd` when published, otherwise stays gray (“Volume not available for this stat”) rather than a false “Min Carries”.
- Stats with no spine source yet (`red_zone_*`, `route_pct`, …) publish null volume and `qualified: false` → empty ranked list + disabled slider (“No volume data for this stat yet”).
- Slider is interactive when any resolved volume exists (`max > 0`); going below ramp–hold is allowed for exploration, but changing the selected stat resets to the baseline.
- Number input clamps to `0…volumeMax` on blur / Enter; empty draft restores the last committed value.
- Leaderboard fetch clears the previous board and sets `loading` so a failed request cannot leave a silent empty list.
