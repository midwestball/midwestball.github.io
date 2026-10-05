# Projections boundaries

## Always

- Treat `backend/local_ops/projections/` as the only canonical runtime, state, artifact, and backup unit.
- Use the frozen local uv lock and commands from this directory.
- Validate against the versioned public projection schema before upload.
- Publish immutable objects first and `projections/current.json` last.
- Run once per finalized week, as the final Tuesday data stage.
- Apply the protected-set retention policy documented in `RUNBOOK.md`.
- Keep `ruff format --check src/ tests/` clean.

## Never

- Upload fitted models, training data, or raw draws to Supabase.
- Delete the current pointer target, previous known-good snapshot/model set, or any artifact used by active work or investigation.
- Print, archive, or commit credentials.
- Commit `projections_plan.md`. It is an internal migration worklog, not project documentation.
- Write outside the package root. `Settings.assert_local_write` enforces this for every runtime path.

## Version control

Source, tests, and `contract/` are tracked. Runtime state is not:

| Tracked | Ignored |
|---|---|
| `src/`, `tests/`, `contract/` | `cache/` nflverse downloads |
| `pyproject.toml`, `uv.lock`, `.python-version` | `artifacts/` models, draws, public snapshots |
| `README.md`, `RUNBOOK.md`, `BOUNDARIES.md`, this file | `state/` ledger, locks, logs |
| `.env.example` | `.env`, `.venv/`, `__pycache__/` |

The package finds its own root by walking up for `pyproject.toml`, so it works standalone or
in the monorepo. `PROJECTION_OPS_ROOT` overrides the root when a copy must write to itself.
