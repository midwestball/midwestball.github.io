# Shareable state and personal rosters

Search at `/search/` combines comparison and discovery. `p,season` select up to four catalog-compatible players; `pos,stat,sort,min,q` independently scope discovery. WR and TE share the pass-catcher comparison group. Existing `/compare/` and `/ffoptim/` exports replace-navigate to Search while preserving the complete query and hash.

Weekly projections use entity keys in `p`, optional `focus`, and committed numeric `points`; ROS uses player IDs with `horizon=ros`. Changing horizons clears incompatible selection fields. Links select current published artifacts, not immutable historical forecasts; source cutoff and freshness remain visible.

Trades use readable URL schema `v=1`, roster list `r` (`~` prefixes IR), outgoing `g`, incoming `a`, drops `d`, optional fixed-order settings `s`, and `mode=packages`. Pure parsers reject unsupported versions, duplicate/malformed lists, illegal settings and inconsistent ownership. Unavailable snapshot IDs remain visible and prevent invalid evaluation. URLs above 1,800 characters receive a soft warning and JSON text export; lists are never silently shortened.

The personal `midwestball-trade-roster-v1` key and `{version:1,settings,roster}` schema are unchanged. Valid shares open as temporary previews; invalid shares show recovery and never write storage. Preview edits update the URL, while only **Save this roster** replaces personal storage. **Use my saved roster** removes owned share fields and restores personal state. Normal local editing autosaves. Browser navigation back to a local URL restores saved state.

Browser query subscriptions handle native history and popstate. Discrete selections create history entries; rapid query/volume/threshold and shared-preview edits replace the current entry. Only owned fields change. Snapshot fetch lifetimes do not depend on discovery queries, thresholds or appearance. Clipboard failure exposes selectable URL text.

No backend, publication schema, short-link service or local roster migration is involved.

## Player navigation consolidation

Player analysis is now comparison-only. Filter result rows append a compatible player directly; player-name links from other pages start a comparison with the clicked player and source season selected. Standalone profiles are removed; both legacy `/players/` URL forms are redirect shells only. Published scalar artifacts under Storage `pages/` retain their existing schema and purpose for comparison hydration.
