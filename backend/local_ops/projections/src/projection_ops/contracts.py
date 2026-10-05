"""Canonical JSON bytes, schema checks, filenames, and snapshot validation."""

from __future__ import annotations
from pathlib import Path
import base64, hashlib, json, math, re
from jsonschema import Draft202012Validator, FormatChecker
from .config import SETTINGS, HARD_WALLS, POSITIONS


class ContractError(ValueError):
    pass


def canonical_bytes(value: object) -> bytes:
    return (
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
        )
        + "\n"
    ).encode()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def verify_schema_copy() -> str:
    if not SETTINGS.tracked_schema.exists():
        raise ContractError(f"tracked schema missing: {SETTINGS.tracked_schema}")
    if not SETTINGS.local_schema.exists():
        raise ContractError(f"local schema missing: {SETTINGS.local_schema}")
    a = sha256_file(SETTINGS.tracked_schema)
    b = sha256_file(SETTINGS.local_schema)
    if a != b:
        raise ContractError(f"schema hash mismatch: tracked={a} local={b}")
    return a


def validator() -> Draft202012Validator:
    verify_schema_copy()
    return Draft202012Validator(
        json.loads(SETTINGS.local_schema.read_text(encoding="utf-8")),
        format_checker=FormatChecker(),
    )


def validate_document(doc: dict) -> None:
    errors = sorted(validator().iter_errors(doc), key=lambda e: list(e.absolute_path))
    if errors:
        raise ContractError(
            "; ".join(f"{'.'.join(map(str, e.absolute_path)) or '$'}: {e.message}" for e in errors)
        )


def object_name(entity_key: str) -> str:
    if not entity_key or "/" in entity_key or "\\" in entity_key or entity_key in {".", ".."}:
        raise ContractError("unsafe entityKey")
    encoded = base64.urlsafe_b64encode(entity_key.encode()).decode().rstrip("=")
    return encoded + ".json"


def _trap(grid: list[float], pdf: list[float], wall: float | None) -> list[float]:
    out = [0.0]
    for i in range(len(grid) - 1):
        area = (
            0.0
            if wall is not None and grid[i] < wall
            else (pdf[i] + pdf[i + 1]) * (grid[i + 1] - grid[i]) / 2
        )
        out.append(out[-1] + area)
    return out


def validate_snapshot(directory: Path) -> dict:
    index_path = directory / "index.json"
    manifest_path = directory / "manifest.json"
    if not index_path.exists() or not manifest_path.exists():
        raise ContractError("snapshot requires index.json and manifest.json")
    index = json.loads(index_path.read_text(encoding="utf-8"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    validate_document(index)
    validate_document(manifest)
    grid = index["xGrid"]
    if any(not math.isfinite(x) for x in grid) or any(b <= a for a, b in zip(grid, grid[1:])):
        raise ContractError("xGrid must be finite and strictly increasing")
    seen = set()
    paths = []
    for row in index["entities"]:
        if row["entityKey"] in seen:
            raise ContractError("duplicate entityKey")
        seen.add(row["entityKey"])
        paths.append(row["path"])
        expected = "entities/" + object_name(row["entityKey"])
        if row["path"] != expected:
            raise ContractError(f"noncanonical entity path: {row['path']}")
        p = directory / row["path"]
        if not p.resolve().is_relative_to(directory.resolve()) or not p.exists():
            raise ContractError(f"missing entity: {row['path']}")
        doc = json.loads(p.read_text(encoding="utf-8"))
        validate_document(doc)
        if doc["snapshotId"] != index["snapshotId"] or doc["entityKey"] != row["entityKey"]:
            raise ContractError("entity linkage mismatch")
        if abs(doc["expectedPoints"] - row["expectedPoints"]) > 1e-8:
            raise ContractError("expectedPoints mismatch")
        if len(grid) != len(doc["pdf"]) or len(grid) != len(doc["cdf"]):
            raise ContractError("grid/pdf/cdf length mismatch")
        if doc["lowerBound"] != HARD_WALLS.get(row["position"]):
            raise ContractError("incorrect lowerBound")
        calc = _trap(grid, doc["pdf"], doc["lowerBound"])
        if abs(calc[-1] - 1) > 2e-6 or abs(doc["cdf"][0]) > 1e-10 or abs(doc["cdf"][-1] - 1) > 2e-6:
            raise ContractError("PDF/CDF endpoints invalid")
        if any(b + 1e-10 < a for a, b in zip(doc["cdf"], doc["cdf"][1:])):
            raise ContractError("CDF not monotone")
        if max(abs(a - b) for a, b in zip(calc, doc["cdf"])) > 2e-6:
            raise ContractError("CDF differs from published PDF trapezoids")
        if abs(max(doc["pdf"]) - doc["yMax"]) > 2e-6:
            raise ContractError("yMax mismatch")
    inventory = {x["path"]: x for x in manifest["files"]}
    expected_paths = {"index.json", *paths}
    if set(inventory) != expected_paths:
        raise ContractError("manifest inventory is incomplete or has extras")
    for rel in expected_paths:
        data = (directory / rel).read_bytes()
        item = inventory[rel]
        if item["bytes"] != len(data) or item["sha256"] != sha256_bytes(data):
            raise ContractError(f"manifest hash/size mismatch: {rel}")
    if manifest["snapshotId"] != index["snapshotId"]:
        raise ContractError("manifest snapshot mismatch")
    return {
        "snapshotId": index["snapshotId"],
        "entities": len(index["entities"]),
        "files": len(expected_paths),
        "bytes": sum(x["bytes"] for x in inventory.values()),
    }
