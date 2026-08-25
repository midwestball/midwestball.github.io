# Future product backlog (ordered)

Pre-compute in **ballnet** → publish JSON under reserved Storage prefixes → **knowball** only renders. Do not invent formulas or mock curves in the Next app. Detailed stage / path contracts: `.plans/ballnet-etl-knowball-visualizations.md` (§§10, 12, 15). Shared math (percentile CDF, z-score, `one_in_n`) stays a Ballnet library.

## 1. Home — best performances

**Shipped (weekly):** Stage H → `highlights/{season}/w{week}.json`; Knowball `/` renders `top` + `byGroup`. See `docs/adr/2026-08-25-weekly-highlights-json.md`.

| Follow-up | Intent |
|---|---|
| Breakouts | Individual performances vs the player’s own recent baseline |
| Boards | Best of season / all-time (overall + by position group) |
| Rarity copy | Optional “1 in a thousand / million / billion” framing using published `oneInN` (coordinate with Mason on voice) |

## 2. Overall player percentile → team strength

| Idea | Intent |
|---|---|
| Player overall | Simple mean of that player’s ready-row percentiles (lock weighting later if needed) |
| Team starters | Mean of starter overalls → rough roster strength signal |

Publish on player page scalars and/or a thin `teams/` index — still not a SQL client in Knowball. Copy must stay relative-frequency honest (no “better than N% of the league” from a mean of means without care).

## 3. Player trajectory similarity

Find players whose **year-to-year** (or week-to-year) percentile / value paths look alike. Ballnet builds embeddings or distance features from the Stage B weekly panel + published YTD; Knowball renders a “similar trajectories” list from a small JSON neighbor file.

## 4. Compare player distributions

Overlay or side-by-side KDEs for two players on the same catalog ids. Requires `player_weekly` (or compare) density artifacts under `dists/players/…` — **not** stuffing weekly curves into every `PlayerPageJson`.

## Ownership reminder

| Layer | Owns |
|---|---|
| ballnet | Weekly panel, z-scores, rarity, overall %, team rolls, similarity, player densities, Storage upload |
| knowball | Routes, boards UI, compare chrome, copy |
| ffoptim | Draft optimization only — do not hang these products there |

Ship in the numbered order unless a human reprioritizes. Write an ADR when the first highlight or compare payload shape is locked.
