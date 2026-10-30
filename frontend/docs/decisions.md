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

## Player and highlight surfaces

Player catalogs and highlight rows use the shared surface hierarchy. Rarity and percentile colors retain published meaning and their existing contrast-aware labels.

## Shared and fallback chrome

Public lab, loading and not-found routes share the same semantic appearance as primary screens. Shared controls do not depend on a separate dark class or competing appearance state.

## Synchronous Search history

Native history updates are synchronous and subscribed through the browser query store, preventing query clearing after a picker selection from overwriting a pending navigation. Popstate restores selection and filters. Snapshot fetches exclude bios unavailable in the chosen season.

## Calm local feedback

Discovery and comparison retain controls while pending data occupies a reserved local region. Reveal transitions are brief and become immediate under reduced motion; chart animations also respect that preference. Decorative lattice work is omitted because it is optional and lacks a browser performance gate in this environment.

## Home history ownership

Home writes only season/week on deliberate control changes, using synchronous history and explicit popstate reconciliation. There is no stale-state mirroring effect to overwrite a restored URL. Fractional and out-of-range choices are rejected.

## Long trade link fallback

Links above 1,800 characters receive a soft warning and an intact JSON text export. No list is truncated to meet this warning threshold. Empty explicit player lists are malformed; canonical empty lists are omitted. Package previews do not offer a roster-save action.

## Representative contrast gate

Automated checks validate primary, secondary and muted ink on canvas, content, hover and popover surfaces at 4.5:1, with focus and input boundaries at 3:1. These token checks supplement rather than replace browser layout and composite-color review.

## Stable comparison subscriptions

The comparison hook memoizes validated IDs from the raw selection string, independently of discovery query changes. Regression fixtures verify typing does not hydrate snapshots again.

## Navigation regression evidence

Hermetic component fixtures exercise weekly entity-key/threshold restoration without snapshot reload and trade navigation from one shared roster back to personal saved state without clobbering storage.

## Accessible option targets

Active descendants identify the actual option target, with presentation-only list wrappers. Clicking an already-focused picker reopens suggestions after selection, without requiring an artificial blur or reopening automatically.

## Recoverable comparison failures

Failed comparison hydration shows a local error and retry action while discovery controls remain available. Retrying changes only the comparison request revision and never clears selected IDs.

## Recovery regression evidence

ROS navigation retains player-ID semantics and reports stale selections. Theme bootstrap safely returns to CSS control if browser storage throws.

## Search control alignment

The season selector aligns with the query input even while its suggestion list is expanded, rather than vertically centering against the entire dropdown.
