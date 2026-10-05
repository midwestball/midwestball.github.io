# Fantasy projection operations

Weekly fantasy point distributions for QB, RB, WR, TE, K, and DST. The package estimates a
full predictive distribution per player rather than a point estimate, validates it against a
baseline with rolling-origin folds, and refuses to release a position whose evidence is weak.

Source, tests, and the contract schema are version controlled. Runtime state — the nflverse
cache, fitted models, raw draws, weekly ledger, and logs — is not; see `.gitignore`.

## How it works

1. **`live_data.py`** builds leakage-safe per-position frames. Every feature is derived from
   games that finished before that row's own as-of timestamp, so no row can see its own result.
2. **`model.py`** fits a CRPS-optimal random forest. Rather than regressing a point estimate,
   it trains on the indicator vector `P(y <= t_j)` over a threshold grid and samples draws from
   empirical leaf outcomes, which yields a genuine predictive distribution.
3. **`quality.py`** runs rolling-origin week-ahead validation against a LightGBM conditional
   residual baseline, with player-clustered and season-week-clustered bootstrap intervals, plus
   coverage and tail-Brier hard stops.
4. **`distribution.py`** converts draws into a shared-grid KDE with a CDF derived from exactly
   the published PDF, so any probability the UI shows agrees with the shaded chart area.
5. **`storage.py`** publishes immutable objects first and the `current.json` pointer last,
   verifying every remote byte and hash before the pointer moves.

## Current release status

Implemented and tested: schema/KDE contract, six-position offline smoke build, scoring and CRPS forest primitives, local validation, immutable-first/pointer-last Storage publishing, pruning safeguards, and secret-safe source exports. The frontend consumes the same schema.

**Production remains gated.** An authenticated staging publish, the anonymous GET check, the private off-machine backup/restore drill, the Tuesday ledger integration, and the rollback rehearsal are still outstanding. Historical revalidation *has* been run; its report is `artifacts/reports/quality/historical-quality.json`, which is runtime output and therefore not version controlled. Note that the validation protocol needs live nflverse history, so the published numbers cannot be re-derived from the offline fixture alone.

### Measured model quality

Rolling-origin week-ahead validation, 2024 and 2025 holdouts, 36 folds, scored by CRPS against
a LightGBM conditional-residual baseline. Intervals are 95% player-clustered bootstrap.

| Position | Gate | Delta CRPS | Player-cluster 95% CI | Fold rows |
|---|---|---|---|---|
| QB | pass | +0.1006 | [0.0445, 0.1595] | 1328 |
| RB | pass | +0.0581 | [0.0323, 0.0821] | 3253 |
| WR | pass | +0.0516 | [0.0357, 0.0691] | 4952 |
| TE | pass | +0.0425 | [0.0225, 0.0613] | 2510 |
| DST | disclosed | +0.0130 | [-0.0136, 0.0379] | 1088 |
| K | disclosed | +0.0116 | [-0.0138, 0.0385] | 1086 |

QB, RB, WR, and TE clear the frozen gate. K and DST have positive point estimates whose
intervals include zero, so they ship only under an explicit `initial_deployment` caveat that
is recorded in every snapshot manifest. See `Model evidence` below.

## Start here

Requires Python 3.11 or 3.12. No network access is needed for any command below.

```bash
uv sync --frozen --group test
uv run --frozen --group test pytest -q
uv run --frozen --group test ruff format --check src/ tests/
uv run --frozen python -m projection_ops.cli contract-check
uv run --frozen python -m projection_ops.cli build --season 2026 --week 4 --trained-through-week 3 --offline-fixture
```

The package locates its own root by walking up for `pyproject.toml`, so it runs from any
location. Set `PROJECTION_OPS_ROOT` to override the root explicitly; a copy of this tree then
writes to itself instead of back to the original.

Run the whole Tuesday operation, projections last:

```bash
uv run --frozen python -m projection_ops.cli tuesday --season 2026 --finalized-week 3
```

Live build for a published week (requires network access to nflverse):

```bash
uv run --frozen python -m projection_ops.cli build --season 2026 --week 4 --trained-through-week 3 --mode retrain --draws 10000
```

See `RUNBOOK.md` for validation, dry-run publishing, backups, and pruning.

## Model evidence

The audited legacy rolling gates promoted the CRPS forest for QB, RB, WR, and TE. TE was conservative, and a small high-projection QB segment had weaker evidence. K and DST remain initial deployments without the same head-to-head selection evidence.

### Release policy

QB, RB, WR, and TE are **promoted** positions. A gate failure in any of them blocks release.

K and DST are **initial deployment**. They may ship when the only gap is incomplete head-to-head selection evidence, and only with a published caveat. A coverage or tail-calibration hard stop still blocks release, and a missing position result refuses the release outright. The rule lives in `projection_ops.quality.release_decision()` and every snapshot manifest records the resulting `releaseDecision`.

The 2026 week 4 live build ships K (`deltaCrps` about `0.0116`) and DST (`deltaCrps` about `0.0130`) under that caveat. Both gains are positive, but the player-cluster 95% interval crosses zero, so head-to-head selection is unproven. Consumers must treat K and DST as projections to sanity-check, not settled answers. V1 retains negative skill-position scores and applies true hard walls only to K (`0`) and DST (`-4`).

## Safety

- Do not put secrets in source, manifests, logs, or backups.
- Never upload models, raw draws, or training rows.
- The tracked and local schema SHA-256 values must match.
- All writes stay below this root, except `PROJECTION_OPS_BACKUP_DIR`, which must be outside the repository.
