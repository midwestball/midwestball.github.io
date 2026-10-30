# Frontend decisions

## Conservative matching

All meaningful tokens must match a name or explicit metadata field. One edit is allowed at four characters and two at seven; transpositions cost two edits. Relevance only orders suggestions and bio discovery, never numerical leaderboards.

## Leaderboard domain boundary

Pure discovery helpers retain published ranks, null ordering and joined volume semantics; filtering never changes comparison selections or recomputes published statistics.
