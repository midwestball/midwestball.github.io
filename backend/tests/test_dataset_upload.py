import json
from types import SimpleNamespace

import pytest
from storage3.exceptions import StorageApiError

from ballnet import cli, storage_upload as storage


class Bucket:
    def __init__(self, pointer):
        self.pointer = pointer
        self.uploads = []

    def download(self, path):
        assert path == "index/ballnet-dataset.json"
        if isinstance(self.pointer, Exception):
            raise self.pointer
        return json.dumps(self.pointer).encode()

    def upload(self, path, data, *, file_options):
        self.uploads.append((path, data, file_options))


def client_for(bucket):
    return SimpleNamespace(storage=SimpleNamespace(from_=lambda name: bucket))


@pytest.mark.parametrize("prefix", ["", "migrations/ballnet-v2-20261029"])
def test_uploads_follow_website_dataset(tmp_path, prefix):
    bucket = Bucket({"schemaVersion": 1, "prefix": prefix})
    path = tmp_path / "w8.json"
    path.write_text('{"week":8}')
    result = storage.upload_files([("highlights/2026/w8.json", path)], client=client_for(bucket))
    assert result.failed == 0 and result.uploaded == 1
    assert bucket.uploads[0][0] == (prefix + "/" if prefix else "") + "highlights/2026/w8.json"
    assert bucket.uploads[0][2]["cache-control"] == "0"


def test_only_missing_pointer_allows_legacy_fallback():
    missing = Bucket(StorageApiError("missing", "NoSuchKey", 400))
    assert storage.active_dataset_prefix(client_for(missing)) == ""
    denied = Bucket(StorageApiError("denied", "AccessDenied", 403))
    with pytest.raises(StorageApiError):
        storage.active_dataset_prefix(client_for(denied))


@pytest.mark.parametrize("pointer", [None, {}, {"schemaVersion": 2, "prefix": ""},
    {"schemaVersion": 1, "prefix": "../bad"}, {"schemaVersion": 1, "prefix": None}])
def test_invalid_pointer_stops_before_any_upload(tmp_path, pointer):
    bucket = Bucket(pointer)
    path = tmp_path / "data.json"
    path.write_text("{}")
    with pytest.raises(ValueError):
        storage.upload_files([("index/current.json", path)], client=client_for(bucket))
    assert bucket.uploads == []


@pytest.mark.parametrize("failed", [0, 1])
def test_cli_pins_destination_and_commits_index_after_success(monkeypatch, failed):
    calls = []
    fake_client = object()
    monkeypatch.setattr(cli, "supabase_client", lambda: fake_client)
    monkeypatch.setattr(cli, "active_dataset_prefix", lambda client, bucket: "migrations/live")

    def upload(label):
        def run(*args, **kwargs):
            assert kwargs["prefix"] == "migrations/live"
            assert kwargs["client"] is fake_client
            calls.append(label)
            return storage.UploadResult("knowball-public", 1, failed if label == "pages" else 0, 1, 0.0, [])
        return run

    for name, label in [("upload_season_pages", "pages"), ("upload_season_league", "league"),
                        ("upload_season_leaderboards", "boards"), ("upload_season_highlights", "highlights"),
                        ("upload_index", "index")]:
        monkeypatch.setattr(cli, name, upload(label))
    args = ["upload-storage", "--season", "2026", "--as-of-week", "8", "--highlights", "--index"]
    if failed:
        with pytest.raises(SystemExit):
            cli.main(args)
        assert "index" not in calls
    else:
        cli.main(args)
        assert calls == ["pages", "league", "boards", "highlights", "index"]
