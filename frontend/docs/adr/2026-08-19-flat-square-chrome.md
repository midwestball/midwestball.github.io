### Context
Knowball’s prototype chrome used rounded cards, pills, and drop shadows, which read as a generic dashboard and wasted vertical space on dense percentile stacks.

### Decision
The UI is square, flat, and tight: `border-radius: 0` on every box (panels, inputs, badges, tooltips, slider tracks/thumbs, buttons). Elevation is borders and type only — no `shadow-*`, no ring/box-shadow chrome. Spacing defaults to hairline gaps and compact padding.

### Consequences
- Never add `rounded-*` (including `rounded-full` / pills) or `shadow-*` on containers or controls. If a shadcn primitive ships radius, override to `rounded-none`.
- `--radius` in `web/src/app/globals.css` stays `0`. Do not reintroduce `--radius-lg` as visual policy.
- New pages follow the same flush list language as `TremorVariant`; cards are 1px borders, not floating tiles.
