# Boundaries: `src/ballnet/catalog`

## Always

- Keep `stat.id` strings identical to frontend `src/lib/catalog/*.ts` (and the ETL brief).
- Put machine denoms on `StatDefinition.denom` (e.g. `ngs_rush_weeks`, `targets_allowed`) — Stage C maps those keys on the wide panel.
- Keep `volume_stat_id` in sync with frontend `volumeStatId` (the frontend search UX only).
- Register every group in `registry.STATS_BY_GROUP` / `POSITION_GROUPS`.

## Ask First

- Adding or renaming a `stat.id` (must start as a frontend catalog change).
- Changing domain / `higherIsBetter` without mirroring the frontend. Catalog `kind` / `binWidth` are formatting metadata; they do not select a density shape.

## Never

- Invent slider rows that the frontend does not list.
- Impute 0 for missing NGS/PFR/snap sources via catalog defaults.
- Derived rates are ratio-of-sums on the wide panel; emit `None` when the denominator is 0.
- Drive Stage C ramp–hold off `volume_stat_id` — qualification stays on machine `denom`.

## Silent Failures & Gotchas

- OL pass-protection ids stay `always_unavailable` and are omitted from Stage C output; the frontend still grays them from its catalog.
- Play-grain ids (`red_zone_*`, `route_pct`) exist in catalogs but Stage C always marks `missing_source` until PBP/participation land on the spine.
- Returner group has no spine rows today (nflverse positions are WR/RB primary, not KR/PR).
- `volume_stat_id` is the frontend UX for the search min-volume join; leave it unset for NGS-week / games / snaps / dropbacks / air-yards / tackle_chances denoms.
