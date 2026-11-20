"""Unit tests for Storage prune helpers (no network)."""

from __future__ import annotations

from types import SimpleNamespace

from ballnet import storage_prune as prune
from ballnet.play_highlights import compact_play_league_shapes_payload


def test_compact_play_league_shapes_drops_value_counts():
    payload = {
        "schemaVersion": 1,
        "stats": {
            "rush|pos:RB": {
                "kind": "continuous",
                "xMin": 0,
                "xMax": 10,
                "yMax": 1,
                "curve": [],
                "representation": "histogram",
                "bins": [{"lower": 0, "upper": 5, "count": 3}],
                "valueCounts": [{"value": 1.0, "count": 2}],
                "nSample": 3,
            }
        },
    }
    out = compact_play_league_shapes_payload(payload)
    shape = out["stats"]["rush|pos:RB"]
    assert shape["bins"]
    assert shape["nSample"] == 3
    assert "valueCounts" not in shape
    assert "curve" not in shape


class _Bucket:
    def __init__(self, tree: dict[str, list[dict]]):
        self.tree = tree
        self.removed: list[str] = []

    def list(self, prefix, options=None):
        return list(self.tree.get(prefix, []))

    def remove(self, paths):
        self.removed.extend(paths)

    def download(self, path):
        raise AssertionError(f"unexpected download {path}")


def _client(bucket: _Bucket):
    return SimpleNamespace(storage=SimpleNamespace(from_=lambda name: bucket))


def test_delete_paths_dry_run_does_not_remove():
    bucket = _Bucket({})
    result = prune.delete_paths(_client(bucket), ["a.json", "b.json"], dry_run=True)
    assert result.deleted == 2
    assert bucket.removed == []


def test_delete_paths_execute_chunks():
    bucket = _Bucket({})
    result = prune.delete_paths(
        _client(bucket), ["a.json", "b.json", "c.json"], dry_run=False, chunk_size=2
    )
    assert result.deleted == 3
    assert bucket.removed == ["a.json", "b.json", "c.json"]


def test_kept_week_prefers_current_pointer():
    week = prune._kept_week_for_season(
        {"seasons": [{"season": 2026, "asOfWeek": 7}]},
        {"season": 2026, "asOfWeek": 8},
        2026,
    )
    assert week == 8
