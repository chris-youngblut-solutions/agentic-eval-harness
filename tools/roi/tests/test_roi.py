#!/usr/bin/env python3
"""Tests for the honest ROI harness.

The load-bearing test is ``test_honesty_property``: a scenario with MORE false
positives must yield LOWER net touches-saved than one with fewer, EVEN THOUGH its
raw auto-resolution rate is higher. That is the whole differentiator -- if this
property ever breaks, the model has quietly become a vanity calculator again.

Run standalone (``python3 tests/test_roi.py``) or under pytest
(``pytest tools/roi/tests/test_roi.py``). No network, no key, stdlib only.
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import roi  # noqa: E402

FIXTURES = HERE.parent / "fixtures"


# ----------------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------------
def _cost() -> dict[str, Any]:
    return roi.load_json(FIXTURES / "cost.json")


def _week_pair(
    v: int, correct: int, false: int, f_detect: int
) -> tuple[dict[str, Any], dict[str, Any]]:
    """A neutral 1-week baseline/automated pair where deduction and OTIF contribute
    ZERO (identical both sides), so net benefit is a pure function of the touches math.
    That isolates the honest false-positive penalty for the property test."""
    escalated = v - correct - false
    ded = {
        "D_invalid": 0,
        "R_recovered": 0,
        "N_disputes": 0,
        "N_wrong": 0,
        "D_written_off_wrongly": 0,
    }
    baseline = {
        "week": 1,
        "marker": "MARKER_WK01",
        "exceptions_in": v,
        "cycle_before_days": 5.0,
        "match_cycle_before_days": 3.0,
        "otif_pct_before": 95.0,
        "shipped_units": 1000,
        "deduction": dict(ded),
    }
    automated = {
        "week": 1,
        "marker": "MARKER_WK01",
        "exceptions_in": v,
        "auto_resolved_correct": correct,
        "auto_resolved_false": false,
        "escalated_human": escalated,
        "false_flags": f_detect,
        "tau_auto_days": 0.25,
        "tau_false_loop_days": 14.0,
        "tau_human_days": 4.5,
        "match_cycle_after_days": 3.0,
        "otif_pct_after": 95.0,  # zero OTIF lift -> benefit is touches-only
        "shipped_units": 1000,
        "deduction": dict(ded),
    }
    return baseline, automated


# ----------------------------------------------------------------------------
# the honesty property (the differentiator)
# ----------------------------------------------------------------------------
def test_honesty_property_pure() -> None:
    """Pure-function level: more false positives + higher raw rate -> lower net touches."""
    t_manual, t_rework, t_review = 12.0, 25.0, 5.0
    v = 1000.0

    # A: few false positives, LOWER raw auto-rate.
    a_correct, a_false, a_fdetect = 600.0, 20.0, 10.0
    raw_a = roi.auto_resolution_rate(a_correct + a_false, v)
    net_a = roi.net_touches_saved_min(a_correct, a_false, a_fdetect, t_manual, t_rework, t_review)

    # B: many false positives, HIGHER raw auto-rate.
    b_correct, b_false, b_fdetect = 650.0, 200.0, 60.0
    raw_b = roi.auto_resolution_rate(b_correct + b_false, v)
    net_b = roi.net_touches_saved_min(b_correct, b_false, b_fdetect, t_manual, t_rework, t_review)

    assert raw_b > raw_a, f"B should have the higher raw rate ({raw_b} vs {raw_a})"
    assert net_b < net_a, f"but B must save LESS honestly ({net_b} vs {net_a})"
    # concretely: A nets 6650 min, B nets 2500 min despite 0.85 vs 0.62 raw.
    assert net_a == 6650.0
    assert net_b == 2500.0


def test_honesty_property_report() -> None:
    """Same property end-to-end through compute_report headlines."""
    cost = _cost()
    b_low, a_low = _week_pair(v=1000, correct=600, false=20, f_detect=10)
    b_high, a_high = _week_pair(v=1000, correct=650, false=200, f_detect=60)

    low = roi.compute_report([b_low], [a_low], cost, scorecard=None)
    high = roi.compute_report([b_high], [a_high], cost, scorecard=None)

    raw_low = low["headline"]["auto_resolution_rate"]
    raw_high = high["headline"]["auto_resolution_rate"]
    net_low = low["headline"]["net_touches_saved_usd"]
    net_high = high["headline"]["net_touches_saved_usd"]

    assert raw_high > raw_low, "the false-heavy run has the higher raw auto-rate"
    assert net_high < net_low, "yet it saves fewer honest dollars"
    # the naive number would REWARD the false-heavy run -- prove the harness does not.
    assert high["headline"]["naive_touches_usd"] > low["headline"]["naive_touches_usd"]
    assert low["headline"]["roi_claim_valid"] is True  # low run still nets positive


def test_escalations_credited_zero() -> None:
    """Escalations never enter the touches sum: moving volume correct->escalated only
    lowers the saved number, never raises it."""
    t = (12.0, 25.0, 5.0)
    full_auto = roi.net_touches_saved_min(1000, 0, 0, *t)
    half_escalated = roi.net_touches_saved_min(500, 0, 0, *t)
    assert half_escalated < full_auto
    assert half_escalated == 500 * 12.0


# ----------------------------------------------------------------------------
# determinism
# ----------------------------------------------------------------------------
def test_determinism_on_fixtures() -> None:
    baseline = roi.load_weeks(FIXTURES / "ops_baseline.jsonl")
    automated = roi.load_weeks(FIXTURES / "ops_automated.jsonl")
    cost = _cost()
    scorecard = roi.load_json(roi._default_scorecard())  # type: ignore[arg-type]
    first = json.dumps(roi.compute_report(baseline, automated, cost, scorecard), sort_keys=True)
    second = json.dumps(roi.compute_report(baseline, automated, cost, scorecard), sort_keys=True)
    assert first == second


def test_fixture_invariant_holds() -> None:
    """A_correct + A_false + H == exceptions_in for every generated week."""
    for a in roi.load_weeks(FIXTURES / "ops_automated.jsonl"):
        total = a["auto_resolved_correct"] + a["auto_resolved_false"] + a["escalated_human"]
        assert total == a["exceptions_in"], f"week {a['week']} breaks the invariant"


# ----------------------------------------------------------------------------
# the shipped marquee numbers (guards the sample the README/view quote)
# ----------------------------------------------------------------------------
def test_marquee_numbers() -> None:
    baseline = roi.load_weeks(FIXTURES / "ops_baseline.jsonl")
    automated = roi.load_weeks(FIXTURES / "ops_automated.jsonl")
    scorecard = roi.load_json(roi._default_scorecard())  # type: ignore[arg-type]
    h = roi.compute_report(baseline, automated, _cost(), scorecard)["headline"]

    assert h["net_touches_saved_usd"] == 80520.0
    assert h["net_touches_saved_fte"] == 5.59
    assert h["naive_touches_usd"] == 111015.0
    assert h["honesty_cut_pct"] == 27.5
    assert h["auto_resolution_rate"] == 0.6969  # honest raw = 69.7%, not a rounded 70
    assert h["correct_auto_rate"] == 0.6401
    assert h["false_exception_rate_resolution"] == 0.0815
    assert h["cycle_time_reduction_pct"] == 0.6173
    assert h["net_deduction_recovery_usd"] == 10600.0
    assert h["net_otif_lift_pp"] == 1.053
    assert h["total_net_benefit_usd"] == 106424.5
    assert h["net_of_subscription_usd"] == 70424.5
    assert h["time_to_value_weeks"] == 5  # ramp-aware; quoted over the 2.25 closed form
    assert h["time_to_value_closed_form_weeks"] == 2.25
    assert h["roi_claim_valid"] is True


# ----------------------------------------------------------------------------
# the safety gate that governs the ROI claim
# ----------------------------------------------------------------------------
def test_gate_flip_voids_claim() -> None:
    baseline = roi.load_weeks(FIXTURES / "ops_baseline.jsonl")
    automated = roi.load_weeks(FIXTURES / "ops_automated.jsonl")
    cost = _cost()
    scorecard = roi.load_json(roi._default_scorecard())  # type: ignore[arg-type]

    # clean: the ROI claim stands, proxy is 0, no hard-gate failures.
    clean = roi.compute_report(baseline, automated, cost, scorecard)
    assert clean["headline"]["roi_claim_valid"] is True
    assert clean["scorecard_accuracy"]["false_autoclose_proxy"] == 0.0
    assert clean["scorecard_accuracy"]["hard_gate_failures"] == []

    # force the false-autoclose hard gate to fail -> proxy flips 0.0 -> 1.0, claim voids.
    broken = copy.deepcopy(scorecard)
    hits = 0
    for case in broken["cases"]:
        if case["case_id"] == "gate_autoclose_mustreview":
            case["passed"] = False
            case["score"] = 0.0
            hits += 1
    assert hits == 1, "fixture scorecard should contain exactly one gate_autoclose_mustreview case"

    voided = roi.compute_report(baseline, automated, cost, broken)
    assert voided["headline"]["roi_claim_valid"] is False
    assert voided["scorecard_accuracy"]["false_autoclose_proxy"] == 1.0
    assert "gate_autoclose_mustreview" in voided["scorecard_accuracy"]["hard_gate_failures"]
    # the dollar model is unchanged -- a safety miss voids the claim regardless of $$.
    assert voided["headline"]["total_net_benefit_usd"] == clean["headline"]["total_net_benefit_usd"]


# ----------------------------------------------------------------------------
# standalone runner (no pytest required)
# ----------------------------------------------------------------------------
def _main() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failures = 0
    for t in tests:
        try:
            t()
            print(f"PASS  {t.__name__}")
        except AssertionError as e:
            failures += 1
            print(f"FAIL  {t.__name__}: {e}")
    print(f"\n{len(tests) - failures}/{len(tests)} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(_main())
