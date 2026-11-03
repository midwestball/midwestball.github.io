import numpy as np
import polars as pl
import pytest

from ballnet.catalog.registry import stats_for_group
from ballnet.density import build_league_density, empirical_percentile
from ballnet.highlights import HighlightStat, _score_stat
from ballnet.scoring import snap_one_in_n
from ballnet.stage_c import _scale_ngs_percents, _share_ytd
from ballnet.jsonio import write_json


def test_midrank_ties_orientation_and_singleton():
    values = [{"value": 1, "count": 1}, {"value": 2, "count": 2}, {"value": 5, "count": 1}]
    assert empirical_percentile(1, values, higher_is_better=True) == 12.5
    assert empirical_percentile(2, values, higher_is_better=True) == 50
    assert empirical_percentile(5, values, higher_is_better=False) == 12.5
    assert empirical_percentile(10, [{"value": 10, "count": 3}], higher_is_better=True) == 50
    assert empirical_percentile(10, [{"value": 10, "count": 1}], higher_is_better=True) is None


def test_histogram_preserves_negative_outlier_and_share_above_old_wall():
    stat = next(s for s in stats_for_group("backfield") if s.id == "target_share")
    hist = build_league_density(np.array([-0.05, 0.1, 0.2, 0.45, 0.5]), stat)
    assert sum(b["count"] for b in hist["bins"]) == 5
    assert hist["x_min"] <= -0.05 and hist["x_max"] >= 0.5
    assert empirical_percentile(0.45, hist["value_counts"], higher_is_better=True) == 70


def test_rarity_is_empirical_inclusive_and_rounds_down():
    peers = pl.DataFrame({"_value": [0.0] * 99 + [2.0]})
    week = pl.DataFrame({"_value": [2.0], "player_id": ["p"]})
    spec = HighlightStat("test", "Test", True, lambda frame: frame)
    row = _score_stat(peers, week, "qb", spec)[0]
    assert row["peerN"] == 100 and row["favorableCount"] == 1
    assert row["oneInN"] == 100 and row["rarityTier"] == 100
    assert snap_one_in_n(100 / 3) == 20
    assert snap_one_in_n(1.9) == 1


def test_missing_week_cannot_create_a_full_season_share():
    frame = pl.DataFrame({"targets": [5.0, 5.0], "target_share": [0.25, None]})
    assert frame.select(_share_ytd("targets", "target_share", "share")).item() is None
    zero = pl.DataFrame({"targets": [5.0, 0.0], "target_share": [0.25, 0.0]})
    assert zero.select(_share_ytd("targets", "target_share", "share")).item() is None


def test_ngs_source_percentage_units_do_not_depend_on_magnitude():
    panel = pl.DataFrame({"ngs_pass_aggressiveness": [0.5, 1.0, 2.0]})
    values = _scale_ngs_percents(panel)["ngs_pass_aggressiveness"].to_list()
    assert values == pytest.approx([0.005, 0.01, 0.02])


def test_invalid_json_does_not_replace_existing_file(tmp_path):
    path = tmp_path / "data.json"
    path.write_text('{"old":true}', encoding="utf-8")
    with pytest.raises(ValueError):
        write_json(path, {"value": float("nan")})
    assert path.read_text(encoding="utf-8") == '{"old":true}'
    assert sorted(p.name for p in tmp_path.iterdir()) == ["data.json"]
