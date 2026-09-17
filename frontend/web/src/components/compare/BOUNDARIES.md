# Boundaries: `web/src/components/compare`

## Always

- Cap selection at **4** players; URL state is `/compare?p=id1,id2&season=YYYY` (`/ffoptim` only redirects).
- Restrict the picker to one catalog **position group** after the first player is chosen so rows align on `stat.id`.
- Expanded rows use **one** `CompareOverlayChart` (shared league curve + per-player markers). Chart fill/focus color comes from `compareFillColor`. Slider thumbs stay Savant percentile colored.
- Marker labels use `shortPlayerName` (`F. Last`) and stack by descending oriented percentile.
- Keep square chrome (`rounded-none`, no pills/shadows).

## Ask First

- Allowing cross-group compare (partial id overlap only).
- Changing brightness to use a published overall percentile instead of a client mean of ready rows.
- Showing every player’s shade at once (current UX is focus-only shade).

## Never

- Invent league curves or team colors from player-page JSON — colors live in `team-colors.ts`; curves still come from Ballnet league merge.
- Embed draft-optimizer / ffoptim modeling here.
- Render a separate expanded KDE per column for the same `stat.id`.

## Silent Failures & Gotchas

- Index `team` / `position` are latest-only; display prefers season page bio when hydrated.
- Unknown team abbreviations fall back to zinc (`#52525b`).
- Players missing from the index (stale `p=` ids) are dropped silently on load.
- Demo / unpublished players show gray unavailable rows; overlay omits markers without a ready curve.
- SVG name hit-targets can be finicky — the ranked legend under the chart duplicates hover/click focus.
