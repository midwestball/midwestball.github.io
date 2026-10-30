# Frontend decisions

## Conservative matching

All meaningful tokens must match a name or explicit metadata field. One edit is allowed at four characters and two at seven; transpositions cost two edits. Relevance only orders suggestions and bio discovery, never numerical leaderboards.

## Leaderboard domain boundary

Pure discovery helpers retain published ranks, null ordering and joined volume semantics; filtering never changes comparison selections or recomputes published statistics.

## Versioned scenario links

Trade URL versioning is independent of saved roster schema v1. Pure parsers reject invalid ownership, overlap, duplicate entries, unsupported versions and oversized lists. Unknown snapshot IDs stay visible as warnings; links select current published data rather than freezing forecasts. Appearance never travels in links.

## Picker interaction

A shared combobox clamps keyboard navigation, closes on outside blur or selection, and keeps focus on its input during pointer selection. Catalog groups and fantasy comparison groups remain separate.

## Discovery request ownership

Board requests depend on season, published week and catalog group. Query and volume changes reuse loaded artifacts; obsolete requests cannot publish under a new request key.

## Independent Search scopes

The Search shell owns one live directory and validated URL state. Discovery filters never erase comparison IDs; only selected IDs drive snapshot hydration. Unknown or unavailable selections remain removable with visible feedback.

## Projection navigation

Snapshot fetch lifetimes are independent of URL edits. Selection history uses discrete entries; threshold commits replace the current entry. Missing IDs report stale selections and thresholds clamp to the published grid. Horizon changes deliberately discard incompatible identity types.

## Personal roster precedence

| State | Source | Storage writes |
| --- | --- | --- |
| Initializing | Browser URL and saved roster | None |
| Local | Personal saved roster, then edits | Autosave |
| Shared | Valid versioned URL | Explicit Save only |
| Invalid | Visible error and recovery | None |

Back to a URL without share fields restores the saved roster. Compound ownership edits are atomic. Invalid draft settings remain editable but cannot be shared. Clipboard failure exposes selectable link text.

## Static legacy links

Legacy routes use replacement navigation to avoid redirect loops in browser history. They remain exported files because GitHub Pages cannot run server redirects. All new comparison links target Search directly.

## CSS-first theme precedence

Charcoal is the root fallback; positive light media detection enables light. Valid explicit `data-theme` overrides beat media detection. Bootstrap reads only the reserved preference key, catches storage failures, and never writes a preference. All app chrome uses semantic tokens; data colors remain independent.

## Theme surface migration

Surface and text tokens carry presentation meaning rather than fixed zinc values. Selected controls use paired primary colors; warnings and deltas preserve severity with explicit text. Theme switching changes CSS only and never remounts data views.

## Projection and trade contrast

Forecast controls and roster warnings share semantic surfaces; signed deltas use success/error ink with text signs. No forecast or lineup arithmetic depends on theme.

## Chart support colors

SVG axes, neutral curves, grids, threshold ink, labels and tooltip surfaces use CSS variables. Team and percentile fills retain their identity; labels use theme ink with team-colored outlines so dark franchise colors do not become unreadable text.
