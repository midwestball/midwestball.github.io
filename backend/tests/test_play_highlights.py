"""Play panel classification + empirical play rarity."""

from __future__ import annotations

import numpy as np
import polars as pl

from ballnet.play_highlights import (
    _board_from_peers,
    _combine_completion,
    _fallback_keys,
    _merge_pass_reception_pairs,
    _peer_keys_on_board,
    _score_play,
    _with_peer_keys,
    _with_score_column,
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


def test_classify_special_teams_and_defense_extras():
    pbp = pl.DataFrame(
        {
            "season": [2026] * 6,
            "week": [1] * 6,
            "game_id": ["g1"] * 6,
            "play_id": [10, 11, 12, 13, 14, 15],
            "posteam": ["ARI", "LAC", "ARI", "ARI", "LAC", "LAC"],
            "defteam": ["LAC", "ARI", "LAC", "LAC", "ARI", "ARI"],
            "qtr": [1] * 6,
            "time": ["10:00"] * 6,
            "game_seconds_remaining": [3000.0] * 6,
            "touchdown": [0] * 6,
            "desc": ["kr", "pr", "fg", "punt", "tfl", "ff"],
            "complete_pass": [0] * 6,
            "rush_attempt": [0] * 6,
            "interception": [0] * 6,
            "sack": [0] * 6,
            "return_team": ["ARI", "ARI", None, None, None, None],
            "kickoff_returner_player_id": ["kr1", None, None, None, None, None],
            "kickoff_returner_player_name": ["KickR", None, None, None, None, None],
            "punt_returner_player_id": [None, "pr1", None, None, None, None],
            "punt_returner_player_name": [None, "PuntR", None, None, None, None],
            "return_yards": [40.0, 12.0, None, None, None, None],
            "field_goal_attempt": [0, 0, 1, 0, 0, 0],
            "field_goal_result": [None, None, "made", None, None, None],
            "kicker_player_id": [None, None, "k1", None, None, None],
            "kicker_player_name": [None, None, "Kick", None, None, None],
            "punt_attempt": [0, 0, 0, 1, 0, 0],
            "punter_player_id": [None, None, None, "p1", None, None],
            "punter_player_name": [None, None, None, "Punt", None, None],
            "kick_distance": [None, None, 54.0, 61.0, None, None],
            "tackle_for_loss_1_player_id": [None, None, None, None, "tfl1", None],
            "tackle_for_loss_1_player_name": [None, None, None, None, "TFL", None],
            "yards_gained": [0.0, 0.0, 0.0, 0.0, -6.0, -3.0],
            "fumble_recovery_1_player_id": [None] * 6,
            "fumble_recovery_1_team": [None] * 6,
            "fumbled_1_team": [None] * 6,
            "forced_fumble_player_1_player_id": [None, None, None, None, None, "ff1"],
            "forced_fumble_player_1_player_name": [None, None, None, None, None, "Force"],
            "forced_fumble_player_1_team": [None, None, None, None, None, "ARI"],
            "epa": [0.0, 0.0, 0.0, 0.0, -2.0, -4.5],
        }
    )
    plays = _classify_plays(pbp)
    by = {
        r["play_class"]: r["value"]
        for r in plays.select(["play_class", "value"]).iter_rows(named=True)
    }
    assert by["kick_return"] == 40.0
    assert by["punt_return"] == 12.0
    assert by["field_goal"] == 54.0
    assert by["punt"] == 61.0
    assert by["tackle_for_loss"] == 6.0
    assert by["forced_fumble"] == 4.5
    kr = plays.filter(pl.col("play_class") == "kick_return")
    assert kr["team"].to_list() == ["ARI"]
    assert kr["opponent_team"].to_list() == ["LAC"]


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


def test_epa_mode_flips_defense_and_punt_return():
    frame = pl.DataFrame(
        {
            "play_class": ["rush", "sack", "punt_return", "kick_return"],
            "value": [10.0, 8.0, 20.0, 30.0],
            "epa": [1.5, -2.0, -3.0, 2.5],
        }
    )
    scored = _with_score_column(frame, "epa")
    assert scored["_score"].to_list() == [1.5, 2.0, 3.0, 2.5]
    raw = _with_score_column(frame, "raw")
    assert raw["_score"].to_list() == [10.0, 8.0, 20.0, 30.0]


def test_pass_and_reception_merge_into_one_completion_card():
    pas = {
        "playerId": "qb1",
        "name": "J.McCarthy",
        "position": "QB",
        "positionGroup": "qb",
        "team": "MIN",
        "opponent": "BAL",
        "playClass": "pass",
        "statId": "passing_yards",
        "statLabel": "passing yards",
        "value": 66.0,
        "gameId": "g1",
        "playId": 99,
        "quarter": 4,
        "clock": "08:24",
        "gameClock": "Q4 08:24",
        "touchdown": False,
        "description": "deep",
        "zScore": 2.0,
        "rarityScore": 0.9,
        "favorableCount": 1,
        "peerN": 10,
        "peerKey": "pass|pos:QB",
        "oneInN": 10,
        "rarityTier": 10,
        "rarityMethod": "empirical-inclusive-v2",
    }
    rec = {
        **pas,
        "playerId": "te1",
        "name": "I.Likely",
        "position": "TE",
        "positionGroup": "pass_catcher",
        "playClass": "reception",
        "statId": "receiving_yards",
        "statLabel": "receiving yards",
        "rarityScore": 0.99,
        "favorableCount": 1,
        "peerN": 100,
        "peerKey": "reception|pos:TE",
        "oneInN": 100,
        "rarityTier": 100,
    }
    combined = _combine_completion(pas, rec)
    assert combined["playClass"] == "completion"
    assert combined["passerName"] == "J.McCarthy"
    assert combined["receiverName"] == "I.Likely"
    assert combined["name"] == "J.McCarthy → I.Likely"
    assert combined["value"] == 66.0
    assert combined["statLabel"] == "yard pass"
    # Rarer TE reception drives primary chip / histogram.
    assert combined["peerKey"] == "reception|pos:TE"
    assert combined["rarityTier"] == 100
    assert combined["secondaryPeerKey"] == "pass|pos:QB"
    assert combined["secondaryRole"] == "pass"

    merged = _merge_pass_reception_pairs([pas, rec])
    assert len(merged) == 1
    assert merged[0]["playClass"] == "completion"
