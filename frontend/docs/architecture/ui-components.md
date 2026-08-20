# UI components

Locked `ExpandableStatRow` behavior. Tremor/zinc palette, Savant percentile colors, Recharts only. Square, flat, tight chrome — see `docs/adr/2026-08-19-flat-square-chrome.md`.

## Visual chrome

Every surface is a sharp rectangle: panels, inputs, selects, buttons, nav hits, ordinal badges, caption pills, tooltips, chart empty-states, slider tracks, and slider thumbs. `--radius` is `0`. Padding is compact (`px-2` / `py-1`–`py-2` on rows; page shells `px-4 py-4`–`py-5`). Adjacent sections use hairline `border` / `divide`, not `gap-6` stacks.

**Never add rounded boxes.** Do not use `rounded-*`, `rounded-full`, capsule chips, or `shadow-*` / ring-as-elevation. If a library default rounds a corner, override to `rounded-none`.

## Collapsed row

Chevron, stat name (fixed left column), inline 0–100 percentile slider, raw value, ordinal badge. The slider track is **not** aligned to the chart x-axis. Rows are flush on the page — no per-stat card chrome or row rules. Section labels (Volume, Scoring, …) group rows with zero extra vertical gap by default.

Unavailable rows (pending, insufficient sample, missing source, not in nflverse) keep the same chrome with `—` value/badge, empty gray track, and reduced opacity. Do not hide catalog stats.

## Expanded

Framer Motion height. Caption: `{pct}%` square label in the slider color + ` of the league has a {STAT} of {VALUE} or lower.` (`or higher` when `higherIsBetter` is false).

Chart x = raw stat on `[xMin, xMax]`. Chart y = relative frequency as %. Shade + dashed `ReferenceLine` at the player value. Continuous = KDE area; discrete = uniform bars.

## Tooltips

1. `{VALUE} {STAT NAME}`
2. `This {STAT NAME} is in the {Nth} percentile.`
3. Histogram: `{p}% of the league has {VALUE}.` (bin start, not a range). KDE: `Relative frequency: {p}% — how common this value is (higher means more typical).`

Never claim the player is "better than N% of the league".

## Never

- Chart.js, Observable Plot, or warping the chart axis to match the slider.
- Mixing Ballnet marketing into the stat stack — Ballnet is its own route.
- Rounded boxes, pills, or drop shadows on any UI chrome.
