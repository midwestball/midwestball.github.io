"""Play panel classification + empirical play rarity."""

from __future__ import annotations

import numpy as np
import polars as pl

from ballnet.play_highlights import (
    _board_from_peers,
    _fallback_keys,
    _peer_keys_on_board,
    _score_play,
    _with_peer_keys,
    build_play_league_shapes,
)
from ballnet.play_panel import _classify_plays
from ballnet.scoring import snap_one_in_n


def _mini_pbp() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "season": [2026, 2026, 2026, 2026, 2026],
            "week": [1, 1, 1, 1, 1],
            "game_id": ["g1"] * 5,
            "play_id": [1, 2, 3, 4, 5],
            "posteam": ["ARI", "ARI", "ARI", "ARI", "ARI"],
            "defteam": ["LAC", "LAC", "LAC", "LAC", "LAC"],
            "qtr": [1, 1, 2, 3, 4],
            "time": ["14:56", "10:00", "5:00", "8:30", "1:00"],
            "game_seconds_remaining": [3596.0, 3300.0, 2100.0, 1410.0, 60.0],
            "touchdown": [0, 0, 1, 0, 0],
            "desc": ["rec", "rush", "pass td", "int", "sack"],
            "play_type": ["pass", "run", "pass", "pass", "pass"],
            "complete_pass": [1, 0, 1, 0, 0],
            "rush_attempt": [0, 1, 0, 0, 0],
            "interception": [0, 0, 0, 1, 0],
            "sack": [0, 0, 0, 0, 1],
            "receiver_player_id": ["wr1", None, "wr1", None, None],
            "receiver_player_name": ["Wide", None, "Wide", None, None],
            "receiving_yards": [27.0, None, 40.0, None, None],
            "passer_player_id": ["qb1", None, "qb1", "qb1", "qb1"],
            "passer_player_name": ["Pass", None, "Pass", "Pass", "Pass"],
            "passing_yards": [27.0, None, 40.0, None, None],
            "rusher_player_id": [None, "rb1", None, None, None],
            "rusher_player_name": [None, "Run", None, None, None],
            "rushing_yards": [None, 12.0, None, None, None],
            "interception_player_id": [None, None, None, "cb1", None],
            "interception_player_name": [None, None, None, "Pick", None],
            "return_yards": [None, None, None, 25.0, None],
            "sack_player_id": [None, None, None, None, "edge1"],
            "sack_player_name": [None, None, None, None, "Sack"],
            "yards_gained": [27.0, 12.0, 40.0, 0.0, -8.0],
        }
    )


def test_classify_plays_splits_types_and_keeps_clock():
    plays = _classify_plays(_mini_pbp())
    classes = sorted(plays["play_class"].unique().to_list())
    assert classes == ["interception", "pass", "reception", "rush", "sack"]
    rec = plays.filter(pl.col("play_class") == "reception").sort("play_id")
    assert rec["clock"].to_list() == ["14:56", "5:00"]
    assert rec["value"].to_list() == [27.0, 40.0]
    sack = plays.filter(pl.col("play_class") == "sack")
    assert sack["value"].to_list() == [8.0]
    assert sack["team"].to_list() == ["LAC"]  # defender team


def test_fallback_keys_prefer_position_then_group():
    assert _fallback_keys("reception", "WR", "pass_catcher") == [
        "reception|pos:WR",
        "reception|group:pass_catcher",
        "reception|all",
    ]


def test_play_rarity_empirical_inclusive_and_game_clock():
    peers = _with_peer_keys(
        pl.DataFrame(
            {
                "season": [2026] * 20,
                "week": [1] * 19 + [2],
                "game_id": ["g"] * 20,
                "play_id": list(range(20)),
                "play_class": ["reception"] * 20,
                "metric_id": ["receiving_yards"] * 20,
                "value": [10.0] * 19 + [80.0],
                "player_id": ["p"] * 20,
                "player_display_name": ["Star"] * 20,
                "team": ["ARI"] * 20,
                "opponent_team": ["LAC"] * 20,
                "position_code": ["WR"] * 20,
                "position_group": ["pass_catcher"] * 20,
                "quarter": [1] * 20,
                "clock": ["12:00"] * 19 + ["0:45"],
                "game_seconds_remaining": [3400.0] * 20,
                "touchdown": [False] * 20,
                "desc": ["catch"] * 20,
            }
        )
    )
    board, peer_map = _board_from_peers(peers, 2026, 2)
    assert board["top"]
    assert "reception|pos:WR" in peer_map
    row = board["top"][0]
    assert row["value"] == 80.0
    assert row["peerN"] == 20
    assert row["favorableCount"] == 1
    assert row["oneInN"] == 20
    assert row["rarityTier"] == snap_one_in_n(20)
    assert row["gameClock"] == "Q1 0:45"
    assert row["clock"] == "0:45"
    assert row["quarter"] == 1


def test_score_play_falls_back_when_position_bucket_is_thin():
    peer_map = {
        "reception|all": np.sort(np.asarray([1.0] * 20 + [50.0], dtype=float)),
    }
    row = _score_play(
        {
            "play_class": "reception",
            "position_code": "WR",
            "position_group": "pass_catcher",
            "value": 50.0,
            "metric_id": "receiving_yards",
            "player_id": "p1",
            "player_display_name": "Wide",
            "team": "ARI",
            "opponent_team": "LAC",
            "game_id": "g",
            "play_id": 9,
            "quarter": 4,
            "clock": "2:00",
            "game_seconds_remaining": 120.0,
            "touchdown": False,
            "desc": "deep ball",
        },
        peer_map,
    )
    assert row is not None
    assert row["peerKey"] == "reception|all"
    assert row["gameClock"] == "Q4 2:00"


def test_play_league_shapes_include_board_peer_keys():
    peers = _with_peer_keys(
        pl.DataFrame(
            {
                "season": [2026] * 20,
                "week": [1] * 19 + [2],
                "game_id": ["g"] * 20,
                "play_id": list(range(20)),
                "play_class": ["reception"] * 20,
                "metric_id": ["receiving_yards"] * 20,
                "value": [10.0] * 19 + [80.0],
                "player_id": ["p"] * 20,
                "player_display_name": ["Star"] * 20,
                "team": ["ARI"] * 20,
                "opponent_team": ["LAC"] * 20,
                "position_code": ["WR"] * 20,
                "position_group": ["pass_catcher"] * 20,
                "quarter": [1] * 20,
                "clock": ["12:00"] * 20,
                "game_seconds_remaining": [3400.0] * 20,
                "touchdown": [False] * 20,
                "desc": ["catch"] * 20,
            }
        )
    )
    board, peer_map = _board_from_peers(peers, 2026, 2)
    keys = _peer_keys_on_board(board)
    shapes = build_play_league_shapes(2026, 2, peer_map, keys)
    assert shapes["scope"] == "play_all_time"
    assert "reception|pos:WR" in shapes["stats"]
    hist = shapes["stats"]["reception|pos:WR"]
    assert hist["representation"] == "histogram"
    assert hist["bins"]
    assert hist["nSample"] == 20
