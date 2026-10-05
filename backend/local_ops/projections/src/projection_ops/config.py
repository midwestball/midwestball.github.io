"""Paths and frozen v1 model/distribution configuration."""

from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import os

POSITIONS = ("QB", "RB", "WR", "TE", "K", "DST")
HARD_WALLS = {"K": 0.0, "DST": -4.0}
SCORING_DESCRIPTIONS = {
    "QB": "0.04/pass yard + 4/pass TD - 2/INT + 0.1/rush yard + 6/rush TD",
    "RB": "full PPR: reception + 0.1/scrimmage yard + 6/rush or receiving TD",
    "WR": "full PPR: reception + 0.1/scrimmage yard + 6/rush or receiving TD",
    "TE": "full PPR: reception + 0.1/scrimmage yard + 6/rush or receiving TD",
    "K": "1/PAT + 3/FG under 40 + 4/FG 40-49 + 5/FG 50-59 + 6/FG 60+",
    "DST": "1/sack + 2/takeaway + 6/def/ST TD + 2/safety + 2/blocked kick + standard points-allowed tiers",
}
MODEL_STATUS = {
    "QB": "promoted",
    "RB": "promoted",
    "WR": "promoted",
    "TE": "promoted_with_calibration_note",
    "K": "initial_deployment",
    "DST": "initial_deployment",
}

# Positions promoted on head-to-head model-selection evidence. These must pass the
# frozen historical gate before any live snapshot is built.
PROMOTED_POSITIONS = ("QB", "RB", "WR", "TE")
# Positions that may ship with an explicit initial-deployment disclosure when their
# selection evidence is incomplete. Disclosure is allowed only when the weaker
# evidence is a small CRPS margin, never when coverage or tail calibration hard-stops.
INITIAL_DEPLOYMENT_POSITIONS = ("K", "DST")


def _tracked_schema(repo: Path, local_schema: Path) -> Path:
    """Return the canonical copy of the contract schema.

    In the monorepo the tracked copy lives beside the frontend. Standalone there is no
    frontend, so the package's own contract copy is authoritative. Either way the two are
    compared by hash in ``contracts.verify_schema_copy``; this only chooses which file is
    the reference.
    """
    candidate = repo / "frontend" / "docs" / "contracts" / "projections-v1.schema.json"
    return candidate if candidate.is_file() else local_schema


@dataclass(frozen=True)
class Settings:
    root: Path
    repo_root: Path
    cache: Path
    artifacts: Path
    state: Path
    tracked_schema: Path
    local_schema: Path

    @classmethod
    def discover(cls) -> "Settings":
        """Locate the package root, the repository root, and the contract schema.

        ``root`` is this package's own directory (the one holding ``pyproject.toml``).
        It is found by walking upward for that marker, so the package works from any
        location instead of only at its original four-levels-deep path.

        ``repo_root`` is the enclosing project (the directory holding ``.git``). It is
        only needed for the backend CLI and the credential file, so when the package is
        used standalone it falls back to ``root``.

        ``PROJECTION_OPS_ROOT`` overrides both, which is what lets a copied tree write to
        itself rather than back into the original checkout.
        """
        override = os.environ.get("PROJECTION_OPS_ROOT")
        if override:
            root = Path(override).expanduser().resolve()
        else:
            here = Path(__file__).resolve()
            root = next(
                (p for p in here.parents if (p / "pyproject.toml").is_file()),
                here.parents[2],
            )
        repo = next((p for p in root.parents if (p / ".git").exists()), root)
        local_schema = root / "contract" / "projections-v1.schema.json"
        return cls(
            root,
            repo,
            root / "cache",
            root / "artifacts",
            root / "state",
            _tracked_schema(repo, local_schema),
            local_schema,
        )

    def assert_local_write(self, path: Path) -> Path:
        candidate = path.resolve()
        if not candidate.is_relative_to(self.root.resolve()):
            raise ValueError(f"write path escapes projection ops root: {candidate}")
        return candidate

    def backup_dir(self) -> Path:
        raw = os.environ.get("PROJECTION_OPS_BACKUP_DIR")
        if not raw:
            raise RuntimeError("PROJECTION_OPS_BACKUP_DIR is required")
        out = Path(raw).expanduser().resolve()
        if out.is_relative_to(self.repo_root.resolve()):
            raise ValueError("backup directory must be outside the repository")
        return out


SETTINGS = Settings.discover()
