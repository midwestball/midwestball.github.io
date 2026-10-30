# CSS-first system appearance

Root CSS defaults to soft charcoal (`#202329` canvas, `#292e35` content). A positive `prefers-color-scheme: light` match enables light unless a valid explicit override is present. System changes update CSS live without fetching data, resetting selections or remounting charts.

The reserved `midwestball-theme-preference-v1` contract accepts `system|light|dark`. There is no settings route or visible theme control. A pre-paint bootstrap reads valid explicit overrides into `data-theme`; absence, invalid values and storage failures leave CSS in control. It never writes preferences. Storage events synchronize overrides across tabs. Appearance does not travel in scenario URLs or the roster key.

All routes use semantic surfaces, text, borders, focus and severity colors. Chart support colors use CSS variables; team, percentile and rarity identities retain their existing meanings. Square corners, hairline borders and no shadows remain architectural constraints. Shared controls do not maintain a competing `.dark` class.

Token checks enforce representative text contrast of 4.5:1 and focus/control boundaries of 3:1. They do not verify every composite visual state. Browser first-paint, mobile/zoom, live media switching and chart visual review remain separate checks.

Short reveal transitions and chart animation respect reduced motion. No decorative canvas ships: the optional lattice requires an independent browser performance/accessibility gate.
