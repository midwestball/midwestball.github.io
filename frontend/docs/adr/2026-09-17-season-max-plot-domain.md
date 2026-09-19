### Context
Plot axes should span the qualified in-sample range so both edges sit on recorded season extremes, not leftover catalog weekly floors/ceilings.

### Decision
Ballnet `_expand_domain` sets published league (and weekly highlight) domains to **`[sample_min, sample_max]`** for that `(season, as_of_week, group, stat)`. Empty sample keeps the catalog domain. Axes stay raw-value ordered (low→high): for `higherIsBetter`, left = worst / 0th and right = best / 100th; for lower-is-better, worst sits at the high/right end without flipping the chart. the frontend continues to trust published `xMin`/`xMax`.

### Consequences
- **Required:** Republish densities → percentiles → league/pages/highlights and Storage upload after this change.
- **Required:** Treat published `xMin`/`xMax` as in-sample min/max, not catalog weekly bounds.
- **Deprecated:** Prefer-catalog `xMin` or `xMax` when a qualified sample exists; one-sided season-max-only domains.
- **Unchanged:** Reflection walls still use catalog `lower_bound` / `upper_bound`; the frontend does not invent domains or flip axes by `higherIsBetter`.
