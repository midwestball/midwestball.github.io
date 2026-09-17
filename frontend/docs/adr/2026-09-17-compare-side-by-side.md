### Context
Compare needs a shareable `/compare` route and one shared league KDE per expanded row — not N duplicate plots — with franchise-colored markers and focusable short names.

### Decision
Route lives at `/compare` (`?p=` + `season=`); `/ffoptim` redirects and preserves query params. Expanded rows render `CompareOverlayChart`: one league curve, vertical `ReferenceLine`s per ready player, labels `F. Last` stacked by descending percentile. Hover or click a name (chart label or legend) focuses shade + value/percentile caption; slider thumbs stay Savant-colored. Team fills still come from `compareFillColor`.

### Consequences
- **Required:** Same position group only; unique shade gradient ids per overlay instance; do not invent league curves.
- **Required:** Label stack order = oriented percentile high→low (ties break on `playerId`).
- **Deprecated:** Per-column expanded `DistributionChart` copies on Compare; treating `/ffoptim` as the canonical Compare URL.
- **Unchanged:** Player-page `TremorDistribution` percentile coloring; private ffoptim modeling stays out of Knowball.
