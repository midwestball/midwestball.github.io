# Catalog boundaries

Position catalogs are product configuration, not player data. Rows on a player page come from the catalog for that position group, then overlay a Ballnet JSON snapshot when one exists.

## Always

- Emit **every** catalog stat for the player's position, including permanently gray OL rows.
- Keep `stat.id` stable; Ballnet snapshots join on this id.
- Treat rate stats as **0–1** in the contract (`percent` format). Display as `%` in the UI.
- Compute ramp–hold and percentiles in Ballnet. Knowball only reads `qualified` / `unavailableReason`.

## Ask First

- Adding or removing a published `stat.id` (breaks existing snapshots).
- Changing `kind` (continuous vs discrete formatting) or chart domain for a live id. `kind` does not select a density shape.
- Mapping a new NFL position code to a different group.

## Never

- Synthesize league sample ticks or fake KDE curves from leftover histogram bins.
- Impute 0 for missing NGS/PFR rows.
- Put `formatValue` functions on JSON payloads (Server → Client serialization).

## Silent Failures & Gotchas

- Mixed plan rows (`Rush Att/Yds/TDs`) are **split** into separate slider ids; Ballnet must publish those ids, not a combined blob.
- `alwaysUnavailable` wins even if a snapshot is present — nflverse has no player-level OL sacks/pressures/win rate.
- Percentile orientation is Ballnet's job: Knowball assumes high = good and does not invert again on the slider.
