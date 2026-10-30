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
