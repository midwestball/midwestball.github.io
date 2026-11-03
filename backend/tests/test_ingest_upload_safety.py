import polars as pl
import pytest

from ballnet import ingest, storage_upload


def test_optional_fetch_failure_is_retried_and_replaces_stub(tmp_path, monkeypatch):
    monkeypatch.setattr(ingest, "RAW_DIR", tmp_path)
    monkeypatch.setattr(ingest, "ensure_data_dirs", lambda: None)
    frame = pl.DataFrame({"season": [2026], "week": [1], "player_gsis_id": ["p"]})
    for name in ("load_player_stats", "load_snap_counts", "load_pfr_advstats", "load_ff_opportunity", "load_ff_playerids", "load_rosters", "load_schedules", "load_ftn_charting", "load_participation", "load_pbp"):
        monkeypatch.setattr(ingest.nfl, name, lambda *args, **kwargs: frame)
    calls = []

    def nextgen(*args, **kwargs):
        calls.append(kwargs["stat_type"])
        if kwargs["stat_type"] == "passing" and calls.count("passing") == 1:
            raise RuntimeError("temporary")
        return frame

    monkeypatch.setattr(ingest.nfl, "load_nextgen_stats", nextgen)
    first = ingest.fetch_season(2026)
    assert any("UNAVAILABLE" in row.notes for row in first if row.name == "ngs_passing_2026")
    assert (tmp_path / "ngs_passing_2026.unavailable").exists()
    ingest.fetch_season(2026)
    assert calls.count("passing") == 2
    assert not (tmp_path / "ngs_passing_2026.unavailable").exists()
    assert pl.read_parquet(tmp_path / "ngs_passing_2026.parquet").height == 1


def test_missing_requested_group_fails_before_upload(tmp_path, monkeypatch):
    monkeypatch.setattr(storage_upload, "LEAGUE_DIR", tmp_path)
    folder = tmp_path / "2026" / "w1"
    folder.mkdir(parents=True)
    (folder / "qb.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(storage_upload, "upload_files", lambda *args, **kwargs: pytest.fail("must preflight"))
    with pytest.raises(FileNotFoundError, match="missing league files"):
        storage_upload.upload_season_league(2026, 1, groups=["qb", "backfield"])


def test_index_current_upload_waits_for_other_index_files(tmp_path, monkeypatch):
    monkeypatch.setattr(storage_upload, "INDEX_DIR", tmp_path)
    for name in ("players.json", "seasons.json", "current.json"):
        (tmp_path / name).write_text("{}", encoding="utf-8")
    batches = []

    def upload(pairs, *, bucket, **kwargs):
        batches.append([path for path, _ in pairs])
        return storage_upload.UploadResult(bucket, len(pairs), 0, 0, 0.0, [])

    monkeypatch.setattr(storage_upload, "upload_files", upload)
    storage_upload.upload_index()
    assert batches == [["index/players.json", "index/seasons.json"], ["index/current.json"]]
