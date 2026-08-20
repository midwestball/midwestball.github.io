### Context
Knowball must render position-aware percentile rows without owning ingest, and the Next.js app is forbidden from talking to Postgres. Visualization data is a join of a stable per-position catalog and precomputed league curves plus player overlays.

### Decision
Ballnet stores a normalized visualization store (league distributions once per season/week/position/stat, player values separately) and publishes denormalized `PlayerPageJson` files. Knowball hydrates the position catalog against that JSON — no `@supabase/supabase-js`, no mock KDE generation.

### Consequences
- New stats are catalog ids first; Ballnet cannot invent slider rows the UI does not list.
- League curves must not be duplicated per player in the private DB; page JSON may embed them for a single fetch.
- `.plans/checklist.md` Supabase-client and Observable Plot steps are superseded by this decision and `docs/architecture/README.md`.
