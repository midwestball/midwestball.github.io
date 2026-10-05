import json
from pathlib import Path

import pytest

from ballnet import publish


def _batch(
    season: int,
    as_of_week: int,
    bios: list[dict] | None = None,
) -> publish.BatchPublishResult:
    return publish.BatchPublishResult(
        season=season,
        as_of_week=as_of_week,
        groups=[],
        index_path=None,
        current_index_path=None,
        players=len(bios or []),
        bios=bios or [],
        seconds=0.0,
    )


def test_slice_row_requires_completed_week() -> None:
    with pytest.raises(ValueError, match="missing completedWeek"):
        publish._slice_row({"season": 2026, "asOfWeek": 3})


def test_slice_row_preserves_completed_week() -> None:
    assert publish._slice_row(
        {"season": 2026, "asOfWeek": 3, "completedWeek": 2}
    ) == {
        "season": 2026,
        "asOfWeek": 3,
        "completedWeek": 2,
    }


def test_publish_all_no_current_does_not_write_current_index(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    current_index_calls: list[tuple[int, int]] = []
    seasons_calls: list[tuple[int, int]] = []

    monkeypatch.setattr(publish, "ensure_data_dirs", lambda: None)
    monkeypatch.setattr(publish, "fantasy_pos_ranks", lambda *args, **kwargs: {})
    monkeypatch.setattr(publish, "publish_league_slice", lambda *args, **kwargs: [])
    monkeypatch.setattr(publish, "publish_leaderboards", lambda *args, **kwargs: [])
    monkeypatch.setattr(
        publish,
        "write_players_index",
        lambda *args, **kwargs: Path("players.json"),
    )
    monkeypatch.setattr(
        publish,
        "write_current_index",
        lambda season, week: current_index_calls.append((season, week))
        or Path("current.json"),
    )
    monkeypatch.setattr(
        publish,
        "upsert_seasons_index",
        lambda season, week: seasons_calls.append((season, week))
        or Path("seasons.json"),
    )

    result = publish.publish_all(
        2026,
        3,
        groups=[],
        also_current=False,
        write_index=True,
    )

    assert current_index_calls == []
    assert seasons_calls == [(2026, 3)]
    assert result.current_index_path is None


def test_publish_range_no_current_leaves_current_index_untouched(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    current_index_calls: list[tuple[int, int]] = []
    season_rows: list[dict[str, int]] = []
    publish_calls: list[bool] = []

    def fake_publish_all(
        season: int,
        week: int,
        **kwargs: object,
    ) -> publish.BatchPublishResult:
        publish_calls.append(bool(kwargs["also_current"]))
        return _batch(season, week)

    monkeypatch.setattr(publish, "ensure_data_dirs", lambda: None)
    monkeypatch.setattr(publish, "publish_all", fake_publish_all)
    monkeypatch.setattr(
        publish,
        "completed_week_for",
        lambda season, week: week - 1,
    )
    monkeypatch.setattr(
        publish,
        "write_players_index",
        lambda *args, **kwargs: Path("players.json"),
    )
    monkeypatch.setattr(
        publish,
        "write_seasons_index",
        lambda rows: season_rows.extend(rows) or Path("seasons.json"),
    )
    monkeypatch.setattr(
        publish,
        "write_current_index",
        lambda season, week: current_index_calls.append((season, week))
        or Path("current.json"),
    )

    result = publish.publish_range(
        2024,
        2025,
        groups=[],
        as_of_week=3,
        also_current_latest=False,
    )

    assert publish_calls == [False, False]
    assert current_index_calls == []
    assert result.current_index_path is None
    assert season_rows == [
        {"season": 2024, "asOfWeek": 3, "completedWeek": 2},
        {"season": 2025, "asOfWeek": 3, "completedWeek": 2},
    ]


def test_publish_range_writes_current_index_only_for_latest_when_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    current_index_calls: list[tuple[int, int]] = []

    monkeypatch.setattr(publish, "ensure_data_dirs", lambda: None)
    monkeypatch.setattr(
        publish,
        "publish_all",
        lambda season, week, **kwargs: _batch(season, week),
    )
    monkeypatch.setattr(publish, "completed_week_for", lambda season, week: week)
    monkeypatch.setattr(
        publish,
        "write_players_index",
        lambda *args, **kwargs: Path("players.json"),
    )
    monkeypatch.setattr(
        publish,
        "write_seasons_index",
        lambda rows: Path("seasons.json"),
    )
    monkeypatch.setattr(
        publish,
        "write_current_index",
        lambda season, week: current_index_calls.append((season, week))
        or Path("current.json"),
    )

    result = publish.publish_range(
        2024,
        2025,
        groups=[],
        as_of_week=3,
        also_current_latest=True,
    )

    assert current_index_calls == [(2025, 3)]
    assert result.current_index_path == "current.json"


def test_rebuild_index_computes_completed_week_for_each_slice(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    pages_dir = tmp_path / "pages"
    index_dir = tmp_path / "index"
    page_dir = pages_dir / "2026" / "w3"
    page_dir.mkdir(parents=True)
    (page_dir / "player.json").write_text(
        '{"player":{"id":"player","name":"Player","position":"QB","team":"T"}}',
        encoding="utf-8",
    )

    monkeypatch.setattr(publish, "PAGES_DIR", pages_dir)
    monkeypatch.setattr(publish, "INDEX_DIR", index_dir)
    monkeypatch.setattr(
        publish,
        "ensure_data_dirs",
        lambda: index_dir.mkdir(exist_ok=True),
    )
    monkeypatch.setattr(publish, "completed_week_for", lambda season, week: 2)

    result = publish.rebuild_index_from_pages([(2026, 3)])

    assert result["current_index_path"] == str(index_dir / "current.json")
    seasons = json.loads(
        (index_dir / "seasons.json").read_text(encoding="utf-8")
    )
    assert seasons["seasons"] == [
        {"season": 2026, "asOfWeek": 3, "completedWeek": 2}
    ]
