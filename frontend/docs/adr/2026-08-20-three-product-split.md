### Context
Docs previously treated Ballnet as a private ML/optimization sandbox and folded draft matrices into the same engine. The product is now three repos with different visibility and ownership.

### Decision
**knowball** is the public Next.js site (stats viz, `/ballnet` writeups, `/ffoptim` draft UI). **ballnet** is the public Python pipeline/DS engine that publishes viz JSON. **ffoptim** is the private modeling and snake-draft optimization engine; Knowball only hosts the user-facing page/consumer. Fantasy optimization must not live in ballnet.

### Consequences
- Agents must not describe ballnet as private or as the draft optimizer.
- Raw nflverse extracts and service-role DB writes may still be local/private; the ballnet *codebase* and published viz JSON are public.
- Superseded two-repo + Clerk/Stripe Leg 2 checklist lives under `.plans/archive/checklist-superseded.md` only.
- HANDOFF.md is removed; orientation starts at `docs/architecture/README.md`.
