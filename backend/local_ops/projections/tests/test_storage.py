from datetime import datetime, timezone
from projection_ops.pipeline import build_snapshot, fixture_entities
from projection_ops.storage import publish_snapshot, _read_matches


class Fake:
    def __init__(self, fail=None):
        self.data = {}
        self.order = []
        self.fail = fail

    def upload(self, path, data, **kwargs):
        self.order.append(path)
        if path == self.fail:
            raise RuntimeError("boom")
        self.data[path] = data

    def download(self, path):
        return self.data[path]


def test_pointer_is_last(tmp_path, monkeypatch):
    import projection_ops.pipeline as p

    monkeypatch.setattr(
        p,
        "SETTINGS",
        __import__("types").SimpleNamespace(
            artifacts=tmp_path / "a", assert_local_write=lambda x: x
        ),
    )
    snap = build_snapshot(
        season=2026,
        week=2,
        trained_through_week=1,
        entities=fixture_entities(n_draws=100),
        generated_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
        minimum_draws=100,
    )
    f = Fake()
    publish_snapshot(snap, f)
    assert f.order[-1] == "projections/current.json"


def test_failure_never_moves_pointer(tmp_path, monkeypatch):
    import projection_ops.pipeline as p

    monkeypatch.setattr(
        p,
        "SETTINGS",
        __import__("types").SimpleNamespace(
            artifacts=tmp_path / "a", assert_local_write=lambda x: x
        ),
    )
    snap = build_snapshot(
        season=2026,
        week=2,
        trained_through_week=1,
        entities=fixture_entities(n_draws=100),
        generated_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
        minimum_draws=100,
    )
    f = Fake()
    import json

    rel = json.loads((snap / "manifest.json").read_text())["files"][0]["path"]
    f.fail = "projections/2026/w2/" + snap.name + "/" + rel
    try:
        publish_snapshot(snap, f)
    except RuntimeError:
        pass
    assert "projections/current.json" not in f.data


def test_read_matches_tolerates_a_brief_stale_edge_read():
    """A Storage edge can serve the previous pointer bytes once; the commit must still verify."""
    stale = {"projections/current.json": b"old"}
    calls = {"n": 0}

    class Flaky:
        def download(self, path):
            calls["n"] += 1
            if calls["n"] < 3:
                return stale[path]
            return b"new"

    assert _read_matches(Flaky(), "projections/current.json", b"new", timeout=1, interval=0) is True
    assert calls["n"] == 3


def test_read_matches_gives_up_and_reports_false():
    class AlwaysStale:
        def download(self, path):
            return b"old"

    assert (
        _read_matches(AlwaysStale(), "projections/current.json", b"new", timeout=0.05, interval=0)
        is False
    )


def test_publish_fails_closed_when_the_pointer_never_verifies(tmp_path, monkeypatch):
    """A pointer that cannot be read back is a failed commit, not a silent success."""
    import projection_ops.pipeline as p

    monkeypatch.setattr(
        p,
        "SETTINGS",
        __import__("types").SimpleNamespace(
            artifacts=tmp_path / "a", assert_local_write=lambda x: x
        ),
    )
    snap = build_snapshot(
        season=2026,
        week=2,
        trained_through_week=1,
        entities=fixture_entities(n_draws=100),
        generated_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
        minimum_draws=100,
    )

    class StalePointer(Fake):
        def download(self, path):
            if path == "projections/current.json":
                return b'{"stale":true}'
            return self.data[path]  # missing objects raise, like a real backend

    monkeypatch.setattr("projection_ops.storage.POINTER_VERIFY_TIMEOUT_SECONDS", 0.2)
    f = StalePointer()
    try:
        publish_snapshot(snap, f)
    except RuntimeError as exc:
        assert "pointer verification failed" in str(exc)
    else:
        raise AssertionError("an unverifiable pointer must fail the publish")
