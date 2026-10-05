import numpy as np
from projection_ops.config import POSITIONS
from projection_ops.quality import row_crps, _cluster_ci, release_decision, disclosure_caveats


def test_crps_rewards_exact_draws_and_cluster_ci_is_deterministic():
    y = np.array([1.0, 2.0])
    exact = np.array([[1.0, 1.0], [2.0, 2.0]])
    noisy = np.array([[0.0, 2.0], [0.0, 4.0]])
    assert np.all(row_crps(exact, y) < row_crps(noisy, y))
    delta = np.array([0.1, 0.2, 0.3, 0.4])
    clusters = np.array(["a", "a", "b", "b"])
    a = _cluster_ci(delta, clusters, 50, np.random.default_rng(1))
    b = _cluster_ci(delta, clusters, 50, np.random.default_rng(1))
    assert a == b and a[0] > 0


def _report(**overrides):
    positions = {}
    for p in POSITIONS:
        positions[p] = {
            "position": p,
            "passed": True,
            "deltaCrps": 0.05,
            "playerCluster95": [0.01, 0.09],
            "seasonWeekCluster95": [0.01, 0.09],
            "coverageHardStop": False,
            "tailHardStop": False,
        }
    for p, values in overrides.items():
        positions[p].update(values)
    return {"positions": positions}


def test_thin_k_dst_margin_is_approved_with_disclosure():
    decision = release_decision(
        _report(
            K={"passed": False, "deltaCrps": 0.0116, "playerCluster95": [-0.013, 0.038]},
            DST={"passed": False, "deltaCrps": 0.0130, "playerCluster95": [-0.014, 0.037]},
        )
    )
    assert decision["approved"] is True
    assert decision["blocked"] == []
    assert [d["position"] for d in decision["disclosures"]] == ["DST", "K"]
    assert all(
        d["status"] == "initial_deployment" and d["gatePassed"] is False
        for d in decision["disclosures"]
    )
    assert decision["disclosures"][0]["playerCluster95"] == [-0.014, 0.037]
    assert disclosure_caveats(decision) == [
        "DST is an initial CRPS-forest deployment without complete head-to-head selection evidence.",
        "K is an initial CRPS-forest deployment without complete head-to-head selection evidence.",
    ]


def test_promoted_position_failure_blocks_release():
    decision = release_decision(_report(RB={"passed": False, "playerCluster95": [-0.02, 0.02]}))
    assert decision["approved"] is False
    assert "RB" in decision["blocked"] and "RB" in decision["promotedBlocked"]


def test_calibration_hard_stop_blocks_even_an_initial_deployment_position():
    for field in ("coverageHardStop", "tailHardStop"):
        decision = release_decision(_report(K={"passed": False, field: True}))
        assert decision["approved"] is False, field
        assert "K" in decision["blocked"]


def test_missing_position_is_refused_rather_than_silently_approved():
    report = _report()
    del report["positions"]["DST"]
    try:
        release_decision(report)
    except RuntimeError as exc:
        assert "DST" in str(exc)
    else:
        raise AssertionError("missing position must raise")


def test_passing_initial_deployment_position_keeps_the_conservative_label():
    decision = release_decision(_report())
    assert decision["approved"] is True
    assert all(
        d["status"] == "initial_deployment" and d["gatePassed"] is True
        for d in decision["disclosures"]
    )
    assert disclosure_caveats(decision) == []
