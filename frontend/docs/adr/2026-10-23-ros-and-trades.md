# ADR: Compact ROS projections and median trade analysis

**Status:** Accepted

## Decision

The Projections route (`/ballnet`) offers upcoming-week and rest-of-season views.
ROS is loaded on demand from the current weekly revision's optional `rosPath`.
The v1 contract adds an optional `ros.json` object containing 5/25/50/75/95%
quantiles, mean and remaining team games for each QB/RB/WR/TE. It uses the weekly
pointer, immutable caching and snapshot/cutoff/scoring linkage checks. Older
snapshots continue to serve weekly projections and explain ROS unavailability.

`/trades` supports package-only comparisons or roster-aware evaluation. Values
sum individual player medians; they are neither package medians nor probabilities.
Roster-aware evaluation uses exact maximum-weight player/slot matching, including
FLEX and SUPERFLEX, independently before and after the trade. It compares fixed
starting lineups, not weekly lineup policies. Unchanged starters cancel naturally.
IR players cannot start, extra acquisitions may require drops, and dropped players
count toward the roster-value difference. K/DST slots are reserved but unmodeled.

Roster and lineup settings are versioned and saved only in browser localStorage.
Malformed saved data is ignored; players missing from a new snapshot are identified
and must be removed before roster evaluation. No roster is sent to a server.

## Consequences

No database tables, server compute, pairwise matrices, raw draw downloads or new
frontend dependencies are required. The frontend retains square, flat zinc chrome.
The mean remains available for a future expected-points comparison mode.
