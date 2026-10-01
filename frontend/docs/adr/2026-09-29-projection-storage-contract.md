# ADR: Projection Storage Contract

**Status:** Accepted

## Decision

Serve weekly projections as schema-versioned public JSON under `projections/` in `knowball-public`. Use one no-cache mutable `current.json` commit pointer and immutable snapshot revisions. Load with plain browser `fetch`. Resolve server-published entity and manifest paths relative to the index after traversal checks.

Publish expected model-draw means and compact, shared-grid KDE PDF/CDF arrays. Do not publish raw draws or model artifacts. Runtime validation rejects unsupported schema versions, unsafe paths, linkage mismatches, and malformed curves.

## Consequences

The static site sees a new weekly pointer without rebuilding. A partially uploaded revision remains invisible until pointer promotion. Immutable entity responses can be cached by full URL. Probability math must use the PDF's piecewise-linear geometry rather than interpolating CDF knots.
