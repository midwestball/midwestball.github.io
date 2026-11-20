# Boundaries: play panel + play highlights

## Always

- Keep play grain **off Stage B**. Persist plays under `data/plays/plays_{season}.parquet`; never widen the player-week spine join key.
- Classify actor-centric plays from cached REG PBP: `reception`, `rush`, `pass`, `interception`, `sack`, `kick_return`, `punt_return`, `field_goal` (made), `punt`, `tackle_for_loss`, `fumble_recovery` (change-of-possession), `forced_fumble` (−EPA). Attach weekly roster `position_code` / `position_group` (season fallback when the week row is missing).
- Score rarity with the same empirical-inclusive favorable-tail method as Stage H (`empirical-inclusive-v2`), peering within `(play_class, position_code)` and falling back to position_group then class-wide when `peerN < MIN_PEER_N`.
- Before publishing boards, pair same `(game_id, play_id)` pass + reception into one `completion` card (`passer → receiver`, rarer peer perspective primary, other as `secondaryPeerKey`). Board sections follow `BOARD_CLASSES` (completion + rush/defense/special teams).
- Persist offense-centric `epa` on the play panel. Publish **raw** and **EPA** boards: `w{week}.json` / `w{week}.epa.json` (Storage under `highlights/plays/`). EPA mode ranks actor-oriented EPA (`−epa` for defense / punt returns). Include game clock plus situation (`down`, `distance`, `yardline` / `yardline100`) and pass detail (`airYards`, `yardsAfterCatch`) when present.
- Publish peer histograms for board `peerKey`s to `dists/league_plays/{season}/w{week}.json` and `w{week}.epa.json`. Upload raw + EPA board/dist together; do not embed `curve`/`bins` on board rows.
- Play league shapes publish **bins + domain + nSample only**. Omit `valueCounts` (and empty curves) — the play expand UI charts bins, and exact counts explode EPA Storage size.
- Tolerate missing historical play panels for years in `PLAY_HIGHLIGHTS_START_YEAR..S-1`; record them as `missingPeerSeasons`. Require the current season panel.

## Ask First

- Exploding PBP into Stage B / Stage C catalog ids (`red_zone_*`, `route_pct`).
- Changing play class definitions or peer-key fallback order.
- Surfacing `/lab/plays` in site navigation.

## Never

- Fold play rarity into Stage G `publish.py` or Stage H game boards.
- Invent frontend catalog `stat.id` values for play metrics — play boards use play-local `statId` / `statLabel`.
- Upload play boards under a new top-level Storage prefix without updating the frontend loader contract.

## Silent Failures & Gotchas

- PBP fetch is optional in Stage A; `play-panel` fails clearly if `pbp_{season}.parquet` is missing.
- With only the current season cached, rarity peers are same-season-to-date (still useful); backfill older `play-panel` seasons to widen the window.
- Pass completions appear once as `pass` (passer) and once as `reception` (receiver) — intentional.
- Half-sack credits without `sack_player_id` use `half_sack_1_player_id` only (no double-count of half_sack_2 in v1).
