# Boundaries: `ballnet/highlights` (Stage H)

## Always

- Read weekly values from Stage B spine only — never Stage C YTD or Stage G page JSON.
- Score only the curated allowlist in `_allowlist_for_group` (volumes + clear single-game rates).
- Orient z-scores with catalog `higherIsBetter` via `ballnet.scoring` against **all-time** single-game peers: full seasons `HIGHLIGHTS_START_YEAR..S-1` plus season `S` weeks `<= W`.
- Require `peerN >= MIN_PEER_N` (16) before emitting a row; apply volume floors for KDE + z; apply `min_value` only when selecting board rows (rare-event spam), not when building the KDE sample.
- Publish raw `oneInN` (Gaussian tail) and snapped `rarityTier` (`snap_one_in_n` onto `10^k`). Keep ranking / caps on `zScore`.
- Collapse each list to **one primary per player** (max `zScore`); nest other same-player rows as `also[]` before applying `PER_GROUP_N` / `TOP_N`.
- Attach optional `fantasyPosRank` / `fantasyPosRankKind` from `fantasy_rank` onto board rows. Do not reuse highlight `rank` for fantasy position order.
- Write `data/highlights/{season}/w{week}.json` and allowlist curves under `data/dists/league_weekly/{season}/w{week}/{group}.json` (`scope: "league_game_all_time"`). Do not embed `curve[]` on board rows.

## Ask First

- Expanding the allowlist to noisy weekly rates (snap %, cushion, separation).
- Changing global-top balancing across position groups.
- Adding season / all-time board **tabs** (separate publish paths). Peer sample is already all-time.
- Changing `HIGHLIGHTS_START_YEAR` or the `10^k` rarity ladder.

## Never

- Fold highlight math into Stage G `publish.py` or reuse `league/` YTD curves for home expand charts.
- Invent frontend catalog ids here.
- Emit boards for `returner` / empty OL / punter without spine-backed columns.

## Silent Failures & Gotchas

- Missing spine for any year in `HIGHLIGHTS_START_YEAR..season` raises; empty week after filters yields `top: []` (the frontend shows pending).
- `peerN` is the count of qualified all-time player-weeks through S/W, not same-week peers.
- `oneInN` is Gaussian-tail of oriented z; `rarityTier` is the log-space nearest `10^k` for UI.
- Discrete rare events still need `min_value` floors on the board; zeros/low counts stay in the KDE sample so the shape is honest.
- `--highlights` upload must include both the board and `dists/league_weekly/` or home expand charts stay pending.
