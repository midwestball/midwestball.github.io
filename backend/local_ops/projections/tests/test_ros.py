from datetime import datetime, timezone
from types import SimpleNamespace
import json

import numpy as np
import polars as pl
import pytest

from projection_ops.contracts import ContractError, validate_snapshot
from projection_ops.pipeline import build_snapshot, fixture_entities
from projection_ops.ros.data import roster_at_cutoff, snapshots
from projection_ops.ros.pipeline import project_frames
from projection_ops.storage import publish_snapshot
from test_storage import Fake


def ros_doc(cutoff=3):
    return {
        "schemaVersion": 1,
        "kind": "ros",
        "season": 2026,
        "cutoffWeek": cutoff,
        "modelVersion": "ros-test",
        "scoringProfile": "ppr-v1",
        "quantileLevels": [0.05, 0.25, 0.5, 0.75, 0.95],
        "methodology": "Test fixture",
        "entities": [
            {
                "playerId": pos,
                "name": pos,
                "team": "CHI",
                "position": pos,
                "remainingTeamGames": 14,
                "mean": 70,
                "quantiles": [0, 20, 60, 100, 140],
            }
            for pos in ("QB", "RB", "WR", "TE")
        ],
    }


def build(tmp_path, monkeypatch, ros=None):
    import projection_ops.pipeline as pipeline

    monkeypatch.setattr(
        pipeline, "SETTINGS", SimpleNamespace(artifacts=tmp_path, assert_local_write=lambda p: p)
    )
    return build_snapshot(
        season=2026,
        week=4,
        trained_through_week=3,
        entities=fixture_entities(n_draws=100),
        minimum_draws=100,
        generated_at=datetime(2026, 10, 23, tzinfo=timezone.utc),
        ros=ros or ros_doc(),
    )


def test_ros_is_hashed_uploaded_and_verified_before_pointer(tmp_path, monkeypatch):
    path = build(tmp_path, monkeypatch)
    index = json.loads((path / "index.json").read_text())
    assert index["rosPath"] == "ros.json"
    assert "draws" not in (path / "ros.json").read_text()
    backend = Fake()
    publish_snapshot(path, backend)
    assert backend.order[-1] == "projections/current.json"
    ros_path = next(p for p in backend.order if p.endswith("/ros.json"))
    assert backend.order.index(ros_path) < len(backend.order) - 1
    assert validate_snapshot(path)["files"] == 8


def test_ros_upload_failure_preserves_previous_pointer(tmp_path, monkeypatch):
    path = build(tmp_path, monkeypatch)
    backend = Fake(fail=f"projections/2026/w4/{path.name}/ros.json")
    backend.data["projections/current.json"] = b"previous"
    with pytest.raises(RuntimeError):
        publish_snapshot(path, backend)
    assert backend.data["projections/current.json"] == b"previous"


@pytest.mark.parametrize("change", ["cutoff", "quantiles", "duplicate"])
def test_ros_rejects_mixed_cutoffs_crossed_quantiles_and_duplicates(tmp_path, monkeypatch, change):
    doc = ros_doc()
    if change == "cutoff":
        doc["cutoffWeek"] = 2
    if change == "quantiles":
        doc["entities"][0]["quantiles"] = [0, 70, 60, 100, 140]
    if change == "duplicate":
        doc["entities"][1]["playerId"] = "QB"
    with pytest.raises(ContractError):
        build(tmp_path, monkeypatch, doc)


def test_bye_roster_is_preserved_and_latest_traded_team_wins():
    rosters = pl.DataFrame(
        [
            {"gsis_id": "a", "team": "CHI", "week": 2},
            {"gsis_id": "b", "team": "GB", "week": 3},
            {"gsis_id": "a", "team": "GB", "week": 3},
            {"gsis_id": "c", "team": "CHI", "week": 2},
        ]
    ).with_columns(
        pl.lit(2026).alias("season"),
        pl.lit("REG").alias("game_type"),
        pl.lit("WR").alias("position"),
        pl.lit("Player").alias("full_name"),
    )
    result = roster_at_cutoff(rosters, 2026, 3)
    assert set(result["player_id"]) == {"a", "b", "c"}
    assert result.filter(pl.col("player_id") == "a")["team"].item() == "GB"
    assert result.filter(pl.col("player_id") == "c")["team"].item() == "CHI"


def test_real_ros_forest_retrains_deterministically_and_exports_only_summaries():
    rows = [
        {
            "player_id": f"{pos}-{i}",
            "player_name": f"{pos} {i}",
            "team": "CHI",
            "position": pos,
            "season": 2025,
            "cutoff_week": 4,
            "remaining_team_games": 13,
            "cur_points_total": float(i),
            "ros_points": float(i * 10),
        }
        for pos in ("QB", "RB", "WR", "TE")
        for i in range(6)
    ]
    train = pl.DataFrame(rows)
    from projection_ops.ros.features import FEATURE_COLUMNS

    train = train.with_columns(
        *[pl.lit(None).alias(c) for c in FEATURE_COLUMNS if c not in train.columns]
    )
    target = train.filter(pl.col("cur_points_total") == 3).with_columns(
        pl.lit(2026).alias("season")
    )
    args = dict(seed=7, n_draws=200, params={"n_estimators": 3, "min_samples_leaf": 1, "n_jobs": 1})
    a = project_frames(train, target, **args)
    assert a == project_frames(train, target, **args)
    assert len(a) == 4
    assert all(len(p["quantiles"]) == 5 and p["quantiles"] == sorted(p["quantiles"]) for p in a)
    assert all(
        set(p)
        == {"playerId", "name", "team", "position", "remainingTeamGames", "mean", "quantiles"}
        for p in a
    )
    with pytest.raises(ValueError, match="precede"):
        project_frames(target, target, **args)


def test_live_snapshot_features_do_not_see_post_cutoff_points():
    rosters = pl.DataFrame(
        {
            "gsis_id": ["p"],
            "team": ["CHI"],
            "week": [1],
            "season": [2026],
            "game_type": ["REG"],
            "position": ["WR"],
            "full_name": ["Player"],
        }
    )
    schedule = pl.DataFrame(
        {"season": [2026] * 3, "team": ["CHI"] * 3, "week": [1, 2, 3]}
    ).with_columns(pl.col("season", "week").cast(pl.Int32))
    panel = pl.DataFrame(
        {
            "player_id": ["p"] * 3,
            "team": ["CHI"] * 3,
            "season": [2026] * 3,
            "week": [1, 2, 3],
            "points": [10.0, 20.0, 999.0],
        }
    )
    panel = panel.with_columns(
        pl.lit(True).alias("active"),
        *[
            pl.lit(1.0).alias(c)
            for c in (
                "targets",
                "carries",
                "attempts",
                "offense_snaps",
                "offense_snap_pct",
                "target_share",
                "air_yards_share",
                "wopr",
                "points_ewma_short",
                "points_ewma_med",
            )
        ],
    )
    result = snapshots(panel, schedule, rosters, [2026], [2])
    assert result["cur_points_total"].item() == 30
    assert result["ros_points"].item() == 999
    assert result["remaining_team_games"].item() == 1


def test_weekly_runs_ros_after_weekly_forests_before_snapshot(tmp_path, monkeypatch, capsys):
    import projection_ops.cli as cli
    import projection_ops.pipeline as pipeline
    import projection_ops.weekly as weekly

    settings = SimpleNamespace(
        artifacts=tmp_path / "artifacts", state=tmp_path / "state", assert_local_write=lambda p: p
    )
    for mod in (cli, pipeline, weekly):
        monkeypatch.setattr(mod, "SETTINGS", settings)
    quality = settings.artifacts / "reports/quality/historical-quality.json"
    quality.parent.mkdir(parents=True)
    quality.write_text("{}")
    monkeypatch.setattr(cli, "release_decision", lambda _: {"approved": True})
    monkeypatch.setattr(cli, "disclosure_caveats", lambda _: [])
    monkeypatch.setattr(
        cli,
        "load_live_tables",
        lambda *a, **k: SimpleNamespace(
            schedules=None, source_metadata={"sourceFingerprint": "test"}
        ),
    )
    monkeypatch.setattr(cli, "resolve_finalized_and_target", lambda *a: 4)
    events = []

    def weekly_forecasts(*a, **k):
        assert k["mode"] == "retrain"
        events.append("weekly")
        return fixture_entities(n_draws=100), {}

    def ros_forecasts(season, cutoff, **kwargs):
        assert (season, cutoff) == (2026, 3)
        events.append("ros")
        return ros_doc(), {"mode": "retrain"}

    def snapshot(**kwargs):
        events.append("snapshot")
        kwargs["minimum_draws"] = 100
        return build_snapshot(**kwargs)

    monkeypatch.setattr(cli, "generate_live_forecasts", weekly_forecasts)
    monkeypatch.setattr(cli, "generate_ros_forecasts", ros_forecasts)
    monkeypatch.setattr(cli, "build_snapshot", snapshot)
    assert cli.main(["weekly", "--season", "2026", "--finalized-week", "3", "--dry-run"]) == 0
    assert events == ["weekly", "ros", "snapshot"]
    assert json.loads(capsys.readouterr().out)["weekly"] == "validated_publish_dry_run"
