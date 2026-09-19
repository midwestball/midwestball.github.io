# Boundaries: `web/src/components/search`

## Always

- Position filter options are publishable groups (`GROUP_LABEL`) except **WR / TE**, which split the `pass_catcher` leaderboard client-side. Stats still come from `STATS_BY_GROUP.pass_catcher` (skip `alwaysUnavailable`). Percentiles stay pass-catcher-wide.
- Year select sits to the right of the search input; options come from Ballnet `index/seasons.json` (plus current). Bio list is scoped to players whose `seasons` include the selected year. Changing year also reloads `leaderboards/{season}/w{asOfWeek}/…` using that season’s published data week and recomputes the ramp–hold floor from `completedWeek` (last fully scored week), not `asOfWeek`.
- Ranked Best/Worst lists load `leaderboards/{season}/w{week}/{group}.json` via the search server action — never N player-page fetches.
- Player result links include `?season=` for the selected search year.
- Sort on oriented percentile (100 = good); Best = descending, Worst = ascending; null percentiles last.
- Stat dropdown may include search-only **Fantasy Rank** (`fantasy_pos_rank`) for QB / backfield / WR / TE. Not a catalog `stat.id`. Best = rank 1 first; Worst = largest published rank first. Drop players Ballnet omitted. No min-volume slider.
- Filter row sits under the search input; Stat and Best/Worst stay visible but disabled (gray) until prerequisites are set.
- Filter controls and min-volume may wrap independently on narrow widths (`flex-wrap` on both the outer row and the filter group).
- Min-volume control: label **Min Volume** (specific catalog volume name in the tooltip). On a shared row it `grow`s to fill from the filters to the right edge; `basis-[12rem]` lets it wrap on small screens, then grows to full width. The range track is `flex-1`; the number input stays fixed for precision. Default = ramp–hold `minNBase × min(completedWeek, 5)` (`board.completedWeek`, else seasons.json, else `asOfWeek`); range is **0…max(volume)**.
- Resolve volume as `board.stats[volumeStatId].value` joined by `playerId` when the catalog sets `volumeStatId`; else fall back to the rate row’s `denomYtd`. If neither yields any values, filter with `qualified` and keep the slider disabled.
- Label the control from the volume sibling’s catalog `label` (e.g. “Min Field Goal Attempts”), not the rate row’s display `denom`.
- Keep square chrome (`rounded-none`, no pills/shadows) on Filter controls.

## Ask First

- Changing the leaderboard JSON shape or Storage path.
- Syncing filter state into URL query params (not shipped).

## Never

- Split Ballnet `pass_catcher` publish/leaderboard/league JSON for the search WR/TE filter — client-side `position` filter only.
- Add Fantasy Rank to position catalogs or player-page sliders — search Stat list only.
- Invent ranks when the leaderboard artifact is missing, or invent `fantasyPosRank` when Ballnet omitted it.
- Compute Expert Consensus Rank or PPR finish in the Next app — render published `fantasyPosRank` / `fantasyPosRankKind` only.
- Change tooltip copy away from kind-specific sentences (`Rank according to fantasy consensus` / `PPR finish among {QBs|WRs|RBs|TEs} that season`).
- Bundle leaderboard JSON into the Next client bundle.
- Mix highlight z-score boards with YTD search sort.
- Treat a rejected `fetchLeaderboard` as an empty result list — surface the error state.
- Invent volume for `red_zone_*` / `route_pct` (or other missing-spine ids) via a fake sibling.

## Silent Failures & Gotchas

- Position only (no stat) still uses the bio index scoped to that group — no values shown until a stat is chosen. Season team/position on bio rows is overlaid from that season’s leaderboard artifact(s) when available, including `fantasyPosRank` / `fantasyPosRankKind`; `index/players.json` team is latest-only and used only as fallback (players missing from boards, demos). Do not read ranks from the index.
- Fantasy Rank is omitted for OL / defense / K / P (Ballnet never publishes those ranks). Backfield FBs without a rank drop out of the ranked list.
- WR vs TE search filters still load `leaderboards/…/pass_catcher.json`. Overlay season `position` from that board before filtering so a WR/TE switch that year lands in the right list.
- Demo players in the index have no leaderboard rows.
- NGS-week / games / snaps / dropbacks / air-yards / tackle_chances denoms leave `volumeStatId` unset — slider uses `denomYtd` when published, otherwise stays gray (“Volume not available for this stat”) rather than a false “Min Carries”.
- Stats with no spine source yet (`red_zone_*`, `route_pct`, …) publish null volume and `qualified: false` → empty ranked list + disabled slider (“No volume data for this stat yet”).
- Slider is interactive when any resolved volume exists (`max > 0`); going below ramp–hold is allowed for exploration, but changing the selected stat resets to the baseline.
- Number input clamps to `0…volumeMax` on blur / Enter; empty draft restores the last committed value.
- Leaderboard fetch clears the previous board and sets `loading` so a failed request cannot leave a silent empty list.
