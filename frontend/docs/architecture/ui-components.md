# UI components

Locked `ExpandableStatRow` behavior. Tremor/zinc palette, Savant percentile colors, Recharts only. Square, flat, tight chrome — see `docs/adr/2026-08-19-flat-square-chrome.md`.

## Visual chrome

Every surface is a sharp rectangle: panels, inputs, selects, buttons, nav hits, caption pills, tooltips, chart empty-states, slider tracks, and slider thumbs. `--radius` is `0`. Padding is compact (`px-2` / `py-1`–`py-2` on rows; page shells `px-4 py-4`–`py-5`). Adjacent sections use hairline `border` / `divide`, not `gap-6` stacks.

**Never add rounded boxes.** Do not use `rounded-*`, `rounded-full`, capsule chips, or `shadow-*` / ring-as-elevation. If a library default rounds a corner, override to `rounded-none`.

## Collapsed row

Chevron, stat name (fixed left column), **raw value** (fixed width, left-aligned so starts line up), then inline 0–100 percentile slider (tracks share a common left edge). The percentile lives **only on the slider thumb** — no separate ordinal badge to the right. The slider track is **not** aligned to the chart x-axis. Rows are flush on the page — no per-stat card chrome or row rules. Section labels (Efficiency, Production, Volume, …) group rows with zero extra vertical gap by default.

Unavailable rows (pending, insufficient sample, missing source, not in nflverse) keep the same chrome with `—` value, empty gray track, and reduced opacity. Do not hide catalog stats.

Thumb / caption label text uses `percentileContrastText` so mid-scale pale yellows stay readable (dark ink on light fills, white on deep blue/red).

## Expanded

Framer Motion height. Caption: `{pct}%` square label in the slider color + ` of the league has a {STAT} of {VALUE} or lower.` (`or higher` when `higherIsBetter` is false).

Chart x = raw stat on `[xMin, xMax]`. Dashed `ReferenceLine` at the player value. Shading matches standing copy: when `higherIsBetter`, shade **left** of the player value; when false, shade **right**.

**KDE (canonical):** all stats render KDE area charts from `StatPayload.curve[]`. Catalog `kind` (continuous vs discrete) is formatting metadata only. Do not branch on histogram bars.

## Tooltips

1. `{VALUE} {STAT NAME}`
2. `This {STAT NAME} is in the {Nth} percentile.`
3. KDE: `Density: {y} — how concentrated values are here (higher means more typical).` Chart y is density (∫y dx ≈ 1), not a percent of the league.

Never claim the player is "better than N% of the league".

## Never

- Chart.js, Observable Plot, or warping the chart axis to match the slider.
- Histogram bars in the chart layer — KDE only.
- Mixing Ballnet writeups or ffoptim draft UI into the stat stack — those are their own routes (`/ballnet`, `/ffoptim`).
- Rounded boxes, pills, or drop shadows on any UI chrome.
- Labeling KDE density as a percent of the league.
