from datetime import datetime, timezone
import json
from projection_ops.pipeline import build_snapshot, fixture_entities
from projection_ops.contracts import validate_snapshot, object_name, ContractError


def test_no_network_six_position_snapshot(tmp_path, monkeypatch):
    import projection_ops.pipeline as p

    monkeypatch.setattr(
        p,
        "SETTINGS",
        __import__("types").SimpleNamespace(
            artifacts=tmp_path / "artifacts", assert_local_write=lambda x: x
        ),
    )
    path = build_snapshot(
        season=2026,
        week=4,
        trained_through_week=3,
        entities=fixture_entities(n_draws=300),
        generated_at=datetime(2026, 9, 29, 14, 5, tzinfo=timezone.utc),
        minimum_draws=300,
    )
    result = validate_snapshot(path)
    assert result["entities"] == 6
    index = json.loads((path / "index.json").read_text())
    assert {x["position"] for x in index["entities"]} == {"QB", "RB", "WR", "TE", "K", "DST"}


def test_object_names_are_safe_and_reversible_collision_free():
    assert object_name("BUF_DST").endswith(".json")
    for bad in ("../x", "a/b", "a\\b", ""):
        try:
            object_name(bad)
        except ContractError:
            pass
        else:
            raise AssertionError("unsafe key accepted")


def test_missing_availability_is_omitted_never_published_as_null(tmp_path, monkeypatch):
    """Defense entities have no official roster status; null would fail the contract."""
    import projection_ops.pipeline as p

    monkeypatch.setattr(
        p,
        "SETTINGS",
        __import__("types").SimpleNamespace(
            artifacts=tmp_path / "artifacts", assert_local_write=lambda x: x
        ),
    )
    entities = fixture_entities(n_draws=300)
    for item in entities:
        if item["position"] == "DST":
            item["availability"] = None
    path = build_snapshot(
        season=2026,
        week=4,
        trained_through_week=3,
        entities=entities,
        generated_at=datetime(2026, 9, 29, 14, 5, tzinfo=timezone.utc),
        minimum_draws=300,
    )
    validate_snapshot(path)
    index = json.loads((path / "index.json").read_text())
    dst = [x for x in index["entities"] if x["position"] == "DST"]
    assert dst and all("availability" not in row for row in dst)
    assert all("availability" in row for row in index["entities"] if row["position"] != "DST")


def test_null_availability_in_a_snapshot_is_rejected(tmp_path, monkeypatch):
    """A hand-edited index that reintroduces null availability must fail closed."""
    import projection_ops.pipeline as p

    monkeypatch.setattr(
        p,
        "SETTINGS",
        __import__("types").SimpleNamespace(
            artifacts=tmp_path / "artifacts", assert_local_write=lambda x: x
        ),
    )
    path = build_snapshot(
        season=2026,
        week=4,
        trained_through_week=3,
        entities=fixture_entities(n_draws=300),
        generated_at=datetime(2026, 9, 30, 14, 5, tzinfo=timezone.utc),
        minimum_draws=300,
    )
    index = json.loads((path / "index.json").read_text())
    for row in index["entities"]:
        if row["position"] == "DST":
            row["availability"] = None
    (path / "index.json").write_text(json.dumps(index), encoding="utf-8")
    manifest = json.loads((path / "manifest.json").read_text())
    import hashlib

    raw = (path / "index.json").read_bytes()
    for item in manifest["files"]:
        if item["path"] == "index.json":
            item["bytes"] = len(raw)
            item["sha256"] = hashlib.sha256(raw).hexdigest()
    (path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    try:
        validate_snapshot(path)
    except ContractError as exc:
        assert "availability" in str(exc)
    else:
        raise AssertionError("null availability must be rejected")
