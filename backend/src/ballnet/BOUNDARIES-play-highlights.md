# Boundaries: play panel + play highlights

## Always

- Keep play grain **off Stage B**. Persist plays under `data/plays/plays_{season}.parquet`; never widen the player-week spine join key.
- Classify actor-centric plays from cached REG PBP: `reception`, `rush`, `pass`, `interception`, `sack`. Attach weekly roster `position_code` / `position_group` (season fallback when the week row is missing).
- Score rarity with the same empirical-inclusive favorable-tail method as Stage H (`empirical-inclusive-v2`), peering within `(play_class, position_code)` and falling back to position_group then class-wide when `peerN < MIN_PEER_N`.
- Publish boards to `data/highlights/plays/{season}/w{week}.json` (Storage: `highlights/plays/...`). Include game clock (`quarter`, `clock`, `gameClock`) on every row.
- Publish peer histograms for board `peerKey`s to `data/dists/league_plays/{season}/w{week}.json` (`scope: "play_all_time"`). Upload board + dist together; do not embed `curve`/`bins` on board rows.
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
