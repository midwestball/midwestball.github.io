### Context
Docs previously treated Ballnet as a private ML/optimization sandbox and folded draft matrices into the same engine. Ownership then split across three products with different visibility.

### Decision
**frontend/** (this monorepo) is the public Next.js static site (stats viz, `/ballnet` writeups, `/compare`). **backend/** is the public Python pipeline/DS engine that publishes viz JSON. **ffoptim** remains a separate private modeling and snake-draft optimization engine; the frontend only hosts the user-facing Compare consumer. Fantasy optimization must not live in `backend/`.

Originally these were separate repos (`knowball` / `ballnet` / `ffoptim`). Midwest Ball org hosting combines knowball + ballnet histories into `midwestball.github.io` as `frontend/` + `backend/` (`docs/adr/2026-09-19-monorepo-static-pages.md` at repo root). Upstream `ehfurgeson/knowball` and `ehfurgeson/ballnet` stay independent.

### Consequences
- Agents must not describe Ballnet/`backend/` as private or as the draft optimizer.
- Raw nflverse extracts and service-role Storage writes may still be local/private; the backend *codebase* and published viz JSON are public.
- Superseded two-repo + Clerk/Stripe Leg 2 checklist lives under `.plans/archive/checklist-superseded.md` only.
- Orientation starts at `docs/architecture/README.md` (under `frontend/`) and the repo root README.
