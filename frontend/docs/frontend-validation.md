# Frontend review and validation

Run from `frontend/`:

```text
npm run test
npm run lint
npm run build
python -m http.server 3000 --bind 127.0.0.1 --directory out
```

The static export must contain `search/index.html`, `compare/index.html`, `ffoptim/index.html`, `ballnet/index.html`, and `trades/index.html`. Review the exported site, including direct query URLs, rather than relying only on development behavior.

Automated regression coverage includes published rank ordering, WR/TE splitting, completed-week ramp-hold, volume sibling fallback, fuzzy normalization and conservative typos, typed URL round trips, malformed trade imports, IR/custom slots, maximum roster length, keyboard picker behavior, clipboard fallbacks, Search history and request isolation, weekly threshold navigation, saved-roster protection through shared edits/history, theme preference safety and representative token contrast.

Local verification on 2026-10-29 passed all 147 tests in 28 files and ESLint, and successfully produced 4,576 static pages. A synthetic Node benchmark over 5,000 players and 40 queries measured 32.3 ms median and 46.8 ms p95 filtering time; this is not browser INP or a low-end-device measurement. This environment exposes no browser surfaces: browser inventory was empty and creating an in-app browser failed. Therefore real-browser first-paint, media switching, mobile/200% zoom, pointer/touch, screenshot, screen-reader and cross-browser checks are **unverified**. Automated DOM/contrast checks are not a substitute for those visual checks.

Review tasks:

1. Search for a mildly misspelled athlete, select up to four compatible players, change every discovery filter, and confirm selected columns remain.
2. Open a Search link in a fresh tab; refresh and use Back/Forward. Verify legacy links preserve all query fields.
3. Share weekly focus/threshold and ROS selections, refresh and switch horizons.
4. Save a personal roster, open a different shared trade, edit it, and verify personal storage changes only after explicit Save. Check recovery from a malformed link.
5. Inspect Home, Search/Compare, legacy player redirects, weekly/ROS and Trades in effective light/dark mode. Check first paint, native controls, chart labels, unavailable states and reduced motion. Confirm no visible theme setting exists.

The optional Canvas lattice is deliberately omitted. No code has been pushed or merged as part of local review.

## Comparison-only navigation checks

Filter result rows select directly without Add buttons or profile links. Home, weekly summaries/tables, ROS and roster/package/lineup names link to season-scoped Search comparisons. Both old player URL forms redirect without loading a standalone profile. The follow-up automated run passed 160 tests in 29 files.
