from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from projection_ops.config import POSITIONS, SETTINGS
from projection_ops.live_data import (
    LiveTables,
    PreparedPosition,
    load_cached_table,
    prepare_position_data,
)
from projection_ops.live_pipeline import DEFAULT_DRAWS, generate_live_forecasts


def _tables():
    schedules = pd.DataFrame(
        [
            {
                "season": 2025,
                "week": 1,
                "game_type": "REG",
                "game_id": "g1",
                "gameday": "2025-09-01",
                "gametime": "13:00",
                "home_team": "AAA",
                "away_team": "BBB",
                "home_score": 10,
                "away_score": 7,
                "spread_line": 0,
                "total_line": 40,
            },
            {
                "season": 2025,
                "week": 2,
                "game_type": "REG",
                "game_id": "g2",
                "gameday": "2025-09-08",
                "gametime": "13:00",
                "home_team": "AAA",
                "away_team": "BBB",
                "home_score": None,
                "away_score": None,
                "spread_line": 1,
                "total_line": 41,
            },
        ]
    )
    rows = []
    for pos, pid in (("QB", "q"), ("RB", "r"), ("WR", "w"), ("TE", "t"), ("K", "k")):
        row = {
            "season": 2025,
            "week": 1,
            "season_type": "REG",
            "game_id": "g1",
            "team": "AAA",
            "position": pos,
            "player_id": pid,
            "player_name": pid.upper(),
            "receptions": 0,
            "receiving_yards": 0,
            "receiving_tds": 0,
            "rushing_yards": 0,
            "rushing_tds": 0,
            "passing_yards": 0,
            "passing_tds": 0,
            "passing_interceptions": 0,
            "fg_made_0_19": 0,
            "fg_made_20_29": 0,
            "fg_made_30_39": 0,
            "fg_made_40_49": 0,
            "fg_made_50_59": 0,
            "fg_made_60_": 0,
            "pat_made": 0,
            "def_sacks": 1,
            "def_interceptions": 0,
            "def_fumbles": 0,
            "def_tds": 0,
            "def_safeties": 0,
            "def_fg_blocks": 0,
            "def_pat_blocks": 0,
            "def_punt_blocks": 0,
            "special_teams_tds": 0,
        }
        if pos in {"QB", "RB", "WR", "TE"}:
            row["rushing_yards"] = -20
        rows.append(row)
    weekly = pd.DataFrame(rows)
    rosters = pd.DataFrame(
        [
            {
                "season": 2025,
                "week": 2,
                "game_type": "REG",
                "team": "AAA",
                "position": p,
                "gsis_id": i,
                "full_name": i.upper(),
                "status_description_abbr": "RES",
            }
            for p, i in (("QB", "q"), ("RB", "r"), ("WR", "w"), ("TE", "t"), ("K", "k"))
        ]
    )
    snaps = pd.DataFrame(
        [
            {
                "season": 2025,
                "week": 1,
                "pfr_player_id": i + "p",
                "offense_snaps": 12,
                "offense_pct": 0.5,
            }
            for i in ("q", "r", "w", "t")
        ]
    )
    ids = pd.DataFrame([{"pfr_id": i + "p", "gsis_id": i} for i in ("q", "r", "w", "t")])
    return LiveTables(schedules, weekly, rosters, snaps, ids, {"sourceFingerprint": "abc"})


def test_negative_skill_outcomes_and_official_availability_are_preserved():
    tables = _tables()
    for position in ("QB", "RB", "WR", "TE"):
        prepared = prepare_position_data(
            2025, 2, position, n_train_seasons=1, refresh=False, tables=tables
        )
        assert prepared.train_rows[0]["fantasy_points"] < 0
        assert prepared.forecast_rows[0]["availability"] == "RES"
        assert prepared.train_rows[0]["offense_snaps"] == 12
        assert prepared.universe == {"scheduled": 1, "included": 1, "excluded": 0}
    dst = prepare_position_data(2025, 2, "DST", n_train_seasons=1, refresh=False, tables=tables)
    assert {r["team"] for r in dst.forecast_rows} == {"AAA", "BBB"}


def test_cache_write_and_offline_read_use_local_partition(tmp_path, monkeypatch):
    import projection_ops.live_data as module

    local = replace(
        SETTINGS,
        root=tmp_path,
        cache=tmp_path / "cache",
        artifacts=tmp_path / "artifacts",
        state=tmp_path / "state",
    )
    monkeypatch.setattr(module, "SETTINGS", local)
    calls = []

    def loader(table, season):
        calls.append((table, season))
        return pd.DataFrame([{"season": season, "value": 3}])

    first, meta = load_cached_table("weekly", [2024], loader=loader)
    assert first.value.tolist() == [3] and meta["partitions"][0]["refreshed"]
    assert (tmp_path / "cache/nflverse/weekly/season=2024/part.parquet").exists()
    second, meta2 = load_cached_table(
        "weekly", [2024], loader=lambda *_: (_ for _ in ()).throw(AssertionError("network"))
    )
    assert second.value.tolist() == [3] and not meta2["partitions"][0]["refreshed"]


def _prepared(position):
    train = []
    for i in range(8):
        y = float(i - 4) if position in {"QB", "RB", "WR", "TE"} else float(i)
        train.append(
            {
                "player_id": f"old{i}",
                "season": 2024,
                "week": i + 1,
                "x": float(i),
                "fantasy_points": y,
            }
        )
    forecasts = [
        {
            "player_id": f"{position.lower()}1",
            "player_name": position + " One",
            "team": "AAA",
            "opponent": "BBB",
            "availability": "ACT",
            "x": 2.0,
        }
    ]
    return PreparedPosition(
        position,
        train,
        forecasts,
        ("x",),
        {"positionSourceFingerprint": "source-" + position},
        {"scheduled": 1, "included": 1, "excluded": 0},
    )


def test_six_position_forests_draws_and_compatibility_metadata(tmp_path, monkeypatch):
    import projection_ops.live_pipeline as module

    local = replace(
        SETTINGS,
        root=tmp_path,
        cache=tmp_path / "cache",
        artifacts=tmp_path / "artifacts",
        state=tmp_path / "state",
    )
    monkeypatch.setattr(module, "SETTINGS", local)
    prepared = {p: _prepared(p) for p in POSITIONS}
    entities, manifest = generate_live_forecasts(
        2025,
        2,
        mode="retrain",
        refresh=False,
        n_draws=31,
        trees=3,
        min_samples_leaf=1,
        prepared=prepared,
    )
    assert len(entities) == 6 and all(len(e["draws"]) == 31 for e in entities)
    assert min(next(e for e in entities if e["position"] == "K")["draws"]) >= 0
    assert min(next(e for e in entities if e["position"] == "DST")["draws"]) >= -4
    assert any(
        x < 0 for e in entities if e["position"] in {"QB", "RB", "WR", "TE"} for x in e["draws"]
    )
    required = {
        "fitSchemaVersion",
        "sourceFingerprint",
        "modelVersion",
        "sklearnVersion",
        "configFingerprint",
        "trainingFingerprint",
        "featureFingerprint",
    }
    assert all(required <= set(manifest["positions"][p]) for p in POSITIONS)
    assert all(
        (tmp_path / "artifacts/models/2025/w2" / p.lower() / "fit.joblib").exists()
        for p in POSITIONS
    )
    assert DEFAULT_DRAWS == 10_000
