from projection_ops.scoring import score
import pytest


def test_negative_skill_and_qb_scores_are_retained():
    assert score("WR", {"receptions": 0, "receiving_yards": -12}) == pytest.approx(-1.2)
    assert score("RB", {"rushing_yards": -5}) == pytest.approx(-0.5)
    assert score("TE", {"receiving_yards": -1}) == pytest.approx(-0.1)
    assert score("QB", {"passing_yards": -10, "interceptions": 1}) == pytest.approx(-2.4)


def test_kicker_and_dst_walls():
    assert score("K", {}) == 0
    assert score("K", {"fg_made_40_49": 1, "pat_made": 2}) == 6
    assert score("DST", {"points_allowed": 99}) == -4
    assert score("DST", {"points_allowed": 0, "def_sacks": 2}) == 12
