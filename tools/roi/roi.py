#!/usr/bin/env python3
"""Honest business-impact / ROI harness for the retail_ops automation agent.

Governing principle (the differentiator): credit only genuine, correct, TERMINAL
automation; charge every false action and every nuisance flag against the benefit.
A false-exception is not free -- an agent that flags a clean transaction creates a
human touch that would not otherwise exist, so false positives DOCK touches-saved
(and can drive it negative). ``net_touches_saved`` is never a vanity number.

The "40% efficiency / 4-week ROI" vendor framing is a TARGET the report can display
(``cost.json:targets``), never baked-in ground truth: every headline is computed from
the synthetic before/after fixtures.

Pure, deterministic, stdlib-only. No RNG, no network, no third-party deps.

Usage:
    python3 roi.py                       # bundled fixtures + latest scorecard -> stdout
    python3 roi.py --out report.json     # write report.json
    python3 roi.py --scorecard ../../eval/retail_ops/history/<run>.json --out report.json
    python3 roi.py --no-scorecard        # money model alone, no safety-gate cross-ref
    python3 roi.py --check               # assert two runs are byte-identical (determinism)
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]  # tools/roi -> tools -> repo root


# ----------------------------------------------------------------------------
# rounding helpers -- applied ONLY at the serialization boundary so the internal
# math stays full-precision and the emitted report.json is byte-reproducible.
# ----------------------------------------------------------------------------
def usd(x: float) -> float:
    return round(x + 0.0, 2)


def rate(x: float) -> float:
    return round(x + 0.0, 4)


def days(x: float) -> float:
    return round(x + 0.0, 3)


# ----------------------------------------------------------------------------
# pure metric functions -- each mirrors one block of the honest ROI model.
# ----------------------------------------------------------------------------
def auto_resolution_rate(a_total: float, v: float) -> float:
    """A / V -- the raw (vanity) rate. Counts wrong terminal actions as resolved."""
    return a_total / v if v else 0.0


def correct_auto_rate(a_correct: float, v: float) -> float:
    """A_correct / V -- the rate that matters. Always report beside the raw rate."""
    return a_correct / v if v else 0.0


def false_exception_rate_resolution(a_false: float, a_total: float) -> float:
    """A_false / A -- of things auto-actioned, the share that were wrong."""
    return a_false / a_total if a_total else 0.0


def false_flag_rate_detection(f_detect: float, true_flags: float) -> float:
    """F_detect / (F_detect + true_flags) -- nuisance detection rate on clean items."""
    denom = f_detect + true_flags
    return f_detect / denom if denom else 0.0


def net_touches_saved_min(
    a_correct: float,
    a_false: float,
    f_detect: float,
    t_manual: float,
    t_rework: float,
    t_review: float,
) -> float:
    """The honest core, in minutes.

        + A_correct * t_manual   genuine saves (only correct, terminal, no-human)
        - A_false   * t_rework   penalty: discover + undo + redo a bad auto-action
        - F_detect  * t_review   penalty: NEW touches created out of clean items

    Escalations that still needed a human are ZERO saved -- they never enter the sum.
    """
    return a_correct * t_manual - a_false * t_rework - f_detect * t_review


def naive_touches_saved_min(a_total: float, t_manual: float) -> float:
    """The dishonest number: A * t_manual. Credits false positives, ignores nuisance."""
    return a_total * t_manual


def mean_cycle_after_days(
    a_correct: float,
    a_false: float,
    h: float,
    tau_auto: float,
    tau_false_loop: float,
    tau_human: float,
    v: float,
) -> float:
    """Volume-weighted exception aging AFTER automation (model section 4).

    tau_false_loop = tau_auto + discovery_lag + rework_time, and normally exceeds
    tau_human: a wrongly-closed exception reopens aged from its ORIGINAL creation
    date, so a high false rate can raise effective aging even as raw latency looks
    near-zero.
    """
    if not v:
        return 0.0
    return (a_correct * tau_auto + a_false * tau_false_loop + h * tau_human) / v


def net_deduction_recovery(
    r_recovered: float,
    n_disputes: float,
    n_wrong: float,
    d_written_off_wrongly: float,
    c_dispute: float,
    penalty_wrong: float,
) -> float:
    """Net (not gross) deduction $ (model section 5).

    + R_recovered                 won back from correctly-disputed invalid deductions
    - c_dispute * N_disputes       labor/fees to file each dispute
    - D_written_off_wrongly        invalid $ the auto-logic accepted -> lost recoverable
    - penalty_wrong * N_wrong      valid deductions wrongly disputed -> re-post + relationship
    """
    return r_recovered - c_dispute * n_disputes - d_written_off_wrongly - penalty_wrong * n_wrong


def otif_value(
    otif_after_pp: float,
    otif_before_pp: float,
    alpha: float,
    shipped_units: float,
    fine_per_unit: float,
) -> float:
    """alpha * net_lift_pp * shipped_units * fine (model section 6).

    otif_after must already net out automation-caused OTIF failures; alpha in (0,1]
    is the attribution factor -- only the share of the delta causally tied to faster
    exception clearance. Carrier/demand/supplier variance confound the rest.
    """
    lift_fraction = (otif_after_pp - otif_before_pp) / 100.0
    return alpha * lift_fraction * shipped_units * fine_per_unit


# ----------------------------------------------------------------------------
# fixtures
# ----------------------------------------------------------------------------
def load_weeks(path: Path) -> list[dict[str, Any]]:
    """Read a JSONL ops fixture (one week record per line) into an ordered list."""
    weeks: list[dict[str, Any]] = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if line:
            weeks.append(json.loads(line))
    return weeks


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


@dataclass
class Cost:
    t_manual: float
    t_rework: float
    t_review: float
    w_fte: float
    fte_hours_per_period: float
    subscription: float
    integration: float
    alpha: float
    fine_per_unit: float
    c_dispute: float
    penalty_wrong: float
    target_efficiency_pct: float
    target_breakeven_weeks: float

    @staticmethod
    def from_json(doc: dict[str, Any]) -> Cost:
        p = doc["params"]
        t = doc["targets"]

        def v(key: str) -> float:
            return float(p[key]["value"])

        return Cost(
            t_manual=v("t_manual_min"),
            t_rework=v("t_rework_min"),
            t_review=v("t_review_min"),
            w_fte=v("w_fte_usd_per_hr"),
            fte_hours_per_period=v("fte_hours_per_period"),
            subscription=v("subscription_per_period"),
            integration=v("integration_onetime"),
            alpha=v("otif_attribution_alpha"),
            fine_per_unit=v("otif_fine_per_unit"),
            c_dispute=v("dispute_cost_each"),
            penalty_wrong=v("wrong_dispute_penalty_each"),
            target_efficiency_pct=float(t["efficiency_pct"]["value"]),
            target_breakeven_weeks=float(t["breakeven_weeks"]["value"]),
        )


# ----------------------------------------------------------------------------
# scorecard cross-reference -- recompute the rollups the reader must derive
# itself (the @property/method rollups are NOT serialized by save_scorecard()).
# ----------------------------------------------------------------------------
def scorecard_accuracy(card: dict[str, Any]) -> dict[str, Any]:
    cases = card.get("cases", [])
    n = len(cases)
    passed = sum(1 for c in cases if c.get("passed"))
    total_score = sum(float(c.get("score", 0.0)) for c in cases)
    hard_gate_failures = [c["case_id"] for c in cases if c.get("hard_gate") and not c.get("passed")]
    # by_metric(): group by metric (null -> "(untagged)"), first-seen order.
    order: list[str] = []
    for c in cases:
        key = c.get("metric") or "(untagged)"
        if key not in order:
            order.append(key)
    by_metric = []
    for key in order:
        members = [c for c in cases if (c.get("metric") or "(untagged)") == key]
        m = len(members)
        by_metric.append(
            {
                "metric": key,
                "n": m,
                "passed": sum(1 for c in members if c.get("passed")),
                "mean_score": rate(sum(float(c.get("score", 0.0)) for c in members) / m),
            }
        )
    mean_by = {r["metric"]: r["mean_score"] for r in by_metric}
    # false-exception proxy the task calls out = 1 - mean_score of false_autoclose_rate.
    false_autoclose_proxy = rate(1.0 - mean_by.get("false_autoclose_rate", 1.0))
    return {
        "run_id": card.get("run_id"),
        "backend": card.get("backend"),
        "model": card.get("model"),
        "n": n,
        "passed": passed,
        "total_score": rate(total_score),
        "hard_gate_failures": hard_gate_failures,
        "false_autoclose_proxy": false_autoclose_proxy,
        "approval_gate_mean_score": mean_by.get("approval_gate"),
        "by_metric": by_metric,
        "note": (
            "false_autoclose_proxy = 1 - mean_score(false_autoclose_rate). "
            "hard_gate_failures must be empty for the ROI claim to stand: a safety-gate "
            "failure voids the ROI story regardless of the dollar model. "
            "Reconciliation/exception/otif/chase/deduction/audit rollups are the accuracy "
            "backing for the labor-savings and recovery terms; the two hard-gated metrics "
            "feed the false-positive / risk terms."
        ),
    }


# ----------------------------------------------------------------------------
# the report
# ----------------------------------------------------------------------------
def compute_report(
    baseline_weeks: list[dict[str, Any]],
    automated_weeks: list[dict[str, Any]],
    cost_doc: dict[str, Any],
    scorecard: dict[str, Any] | None = None,
    *,
    baseline_name: str = "ops_baseline",
    automated_name: str = "ops_automated",
) -> dict[str, Any]:
    c = Cost.from_json(cost_doc)
    if len(baseline_weeks) != len(automated_weeks):
        raise ValueError("baseline and automated week counts differ")

    weekly: list[dict[str, Any]] = []
    agg: dict[str, float] = {
        "v": 0.0,
        "a_correct": 0.0,
        "a_false": 0.0,
        "h": 0.0,
        "f_detect": 0.0,
        "gross_min": 0.0,
        "rework_min": 0.0,
        "nuisance_min": 0.0,
        "naive_min": 0.0,
        "ded_auto": 0.0,
        "ded_base": 0.0,
        "r_recovered": 0.0,
        "d_invalid": 0.0,
        "otif": 0.0,
        "units": 0.0,
        "lift_units": 0.0,
        "cyc_before_vw": 0.0,
        "cyc_after_num": 0.0,
        "match_before_vw": 0.0,
        "match_after_vw": 0.0,
    }

    cum_benefit = 0.0
    cum_cost = 0.0
    breakeven_week: int | None = None

    for bw, aw in zip(baseline_weeks, automated_weeks, strict=True):
        wk = aw["week"]
        v = float(aw["exceptions_in"])
        if float(bw["exceptions_in"]) != v:
            raise ValueError(f"week {wk}: exceptions_in mismatch between baseline/automated")
        if float(bw["shipped_units"]) != float(aw["shipped_units"]):
            raise ValueError(f"week {wk}: shipped_units mismatch between baseline/automated")
        a_correct = float(aw["auto_resolved_correct"])
        a_false = float(aw["auto_resolved_false"])
        h = float(aw["escalated_human"])
        if a_correct + a_false + h != v:
            raise ValueError(
                f"week {wk}: A_correct+A_false+H ({a_correct + a_false + h}) != V ({v})"
            )
        f_detect = float(aw["false_flags"])
        a_total = a_correct + a_false

        # --- touches (honest) ---
        gross_min = a_correct * c.t_manual
        rework_min = a_false * c.t_rework
        nuisance_min = f_detect * c.t_review
        net_min = gross_min - rework_min - nuisance_min
        touches_usd = net_min / 60.0 * c.w_fte

        # --- deduction (net, both sides; credit the automation-attributable delta) ---
        d = aw["deduction"]
        ded_auto = net_deduction_recovery(
            float(d["R_recovered"]),
            float(d["N_disputes"]),
            float(d["N_wrong"]),
            float(d["D_written_off_wrongly"]),
            c.c_dispute,
            c.penalty_wrong,
        )
        bd = bw["deduction"]
        ded_base = net_deduction_recovery(
            float(bd["R_recovered"]),
            float(bd["N_disputes"]),
            float(bd["N_wrong"]),
            float(bd["D_written_off_wrongly"]),
            c.c_dispute,
            c.penalty_wrong,
        )
        # honest: don't re-credit what manual already recovered.
        ded_incremental = ded_auto - ded_base

        # --- OTIF ---
        otif_usd = otif_value(
            float(aw["otif_pct_after"]),
            float(bw["otif_pct_before"]),
            c.alpha,
            float(aw["shipped_units"]),
            c.fine_per_unit,
        )

        # --- cycle time (exception aging) ---
        cyc_before = float(bw["cycle_before_days"])
        cyc_after = mean_cycle_after_days(
            a_correct,
            a_false,
            h,
            float(aw["tau_auto_days"]),
            float(aw["tau_false_loop_days"]),
            float(aw["tau_human_days"]),
            v,
        )

        net_benefit = touches_usd + ded_incremental + otif_usd
        cum_benefit += net_benefit
        cum_cost += c.subscription
        # breakeven includes the one-time integration cost I_0.
        if breakeven_week is None and cum_benefit >= c.integration + cum_cost:
            breakeven_week = int(wk)

        weekly.append(
            {
                "week": int(wk),
                "marker": aw.get("marker"),
                "exceptions_in": int(v),
                "auto_resolved_correct": int(a_correct),
                "auto_resolved_false": int(a_false),
                "escalated_human": int(h),
                "false_flags": int(f_detect),
                "auto_resolution_rate": rate(auto_resolution_rate(a_total, v)),
                "correct_auto_rate": rate(correct_auto_rate(a_correct, v)),
                "false_exception_rate": rate(false_exception_rate_resolution(a_false, a_total)),
                "touches_usd": usd(touches_usd),
                "deduction_incremental_usd": usd(ded_incremental),
                "otif_usd": usd(otif_usd),
                "net_benefit_usd": usd(net_benefit),
                "cum_net_benefit_usd": usd(cum_benefit),
                "cum_cost_usd": usd(c.integration + cum_cost),
                "cycle_before_days": days(cyc_before),
                "cycle_after_days": days(cyc_after),
            }
        )

        # accumulate
        agg["v"] += v
        agg["a_correct"] += a_correct
        agg["a_false"] += a_false
        agg["h"] += h
        agg["f_detect"] += f_detect
        agg["gross_min"] += gross_min
        agg["rework_min"] += rework_min
        agg["nuisance_min"] += nuisance_min
        agg["naive_min"] += naive_touches_saved_min(a_total, c.t_manual)
        agg["ded_auto"] += ded_auto
        agg["ded_base"] += ded_base
        agg["r_recovered"] += float(d["R_recovered"])
        agg["d_invalid"] += float(d["D_invalid"])
        agg["otif"] += otif_usd
        agg["units"] += float(aw["shipped_units"])
        agg["lift_units"] += (float(aw["otif_pct_after"]) - float(bw["otif_pct_before"])) * float(
            aw["shipped_units"]
        )
        agg["cyc_before_vw"] += cyc_before * v
        agg["cyc_after_num"] += cyc_after * v
        agg["match_before_vw"] += float(bw["match_cycle_before_days"]) * v
        agg["match_after_vw"] += float(aw["match_cycle_after_days"]) * v

    n_periods = len(weekly)
    v = agg["v"]
    a_total = agg["a_correct"] + agg["a_false"]

    # --- touches aggregate ---
    net_min = agg["gross_min"] - agg["rework_min"] - agg["nuisance_min"]
    net_hr = net_min / 60.0
    net_touches_usd = net_hr * c.w_fte
    naive_usd = agg["naive_min"] / 60.0 * c.w_fte
    honesty_cut_pct = (1.0 - net_touches_usd / naive_usd) * 100.0 if naive_usd else 0.0
    net_fte = net_hr / (c.fte_hours_per_period * n_periods)

    # --- cycle aggregate (volume-weighted) ---
    cyc_before = agg["cyc_before_vw"] / v
    cyc_after = agg["cyc_after_num"] / v
    match_before = agg["match_before_vw"] / v
    match_after = agg["match_after_vw"] / v

    # --- deduction aggregate ---
    ded_incremental = agg["ded_auto"] - agg["ded_base"]
    recovery_rate = agg["r_recovered"] / agg["d_invalid"] if agg["d_invalid"] else 0.0

    # --- OTIF aggregate (units-weighted net lift) ---
    net_otif_lift_pp = agg["lift_units"] / agg["units"] if agg["units"] else 0.0

    # --- totals + time-to-value ---
    total_net_benefit = net_touches_usd + ded_incremental + agg["otif"]
    subscription_total = c.subscription * n_periods
    net_of_sub = total_net_benefit - subscription_total
    b_steady = _steady_state(weekly, k=min(3, n_periods))
    closed_form_ttv = (
        c.integration / (b_steady - c.subscription) if b_steady > c.subscription else None
    )

    # --- honesty gate: net must be positive AND (if a scorecard is given) no hard-gate fail ---
    acc = scorecard_accuracy(scorecard) if scorecard is not None else None
    reasons: list[str] = []
    valid = True
    if total_net_benefit <= 0:
        valid = False
        reasons.append("net benefit is not positive after the honest false-positive penalty")
    if acc is not None and acc["hard_gate_failures"]:
        valid = False
        reasons.append(
            "eval hard-gate failure(s): "
            + ", ".join(acc["hard_gate_failures"])
            + " -- a safety-gate miss voids the ROI claim"
        )
    if valid:
        reasons.append(
            "net benefit positive; no eval hard-gate failures"
            if acc
            else "net benefit positive (no scorecard cross-referenced)"
        )

    report: dict[str, Any] = {
        "_provenance": (
            "Generated by roi.py from fully synthetic before/after fixtures "
            "(ops_baseline.jsonl + ops_automated.jsonl + cost.json). No real supplier, "
            "retailer, ERP, customer, PII, or prior-employer data. The 40% / 4-week "
            "figures under `targets` are VENDOR FRAMING the report can display, never "
            "ground truth -- every headline below is computed from the fixtures."
        ),
        "schema": "roi-report/0.1",
        "generated_from": {
            "baseline": baseline_name,
            "automated": automated_name,
            "cost": cost_doc.get("schema"),
            "scorecard": acc["run_id"] if acc else None,
        },
        "period_unit": "week",
        "n_periods": n_periods,
        "cost": {
            "t_manual_min": c.t_manual,
            "t_rework_min": c.t_rework,
            "t_review_min": c.t_review,
            "w_fte_usd_per_hr": c.w_fte,
            "subscription_per_period_usd": c.subscription,
            "integration_onetime_usd": c.integration,
            "otif_attribution_alpha": c.alpha,
        },
        "targets": {
            "efficiency_pct": c.target_efficiency_pct,
            "breakeven_weeks": c.target_breakeven_weeks,
            "note": "vendor framing TARGET, never baked-in ground truth",
        },
        "headline": {
            "net_touches_saved_hours": round(net_hr, 1),
            "net_touches_saved_fte": round(net_fte, 2),
            "net_touches_saved_usd": usd(net_touches_usd),
            "naive_touches_usd": usd(naive_usd),
            "honesty_cut_pct": round(honesty_cut_pct, 1),
            "auto_resolution_rate": rate(auto_resolution_rate(a_total, v)),
            "correct_auto_rate": rate(correct_auto_rate(agg["a_correct"], v)),
            "false_exception_rate_resolution": rate(
                false_exception_rate_resolution(agg["a_false"], a_total)
            ),
            "false_flag_rate_detection": rate(false_flag_rate_detection(agg["f_detect"], v)),
            "cycle_time_before_days": days(cyc_before),
            "cycle_time_after_days": days(cyc_after),
            "cycle_time_reduction_pct": rate(
                (cyc_before - cyc_after) / cyc_before if cyc_before else 0.0
            ),
            "match_cycle_before_days": days(match_before),
            "match_cycle_after_days": days(match_after),
            "match_cycle_reduction_pct": rate(
                (match_before - match_after) / match_before if match_before else 0.0
            ),
            "net_deduction_recovery_usd": usd(ded_incremental),
            "automated_deduction_net_usd": usd(agg["ded_auto"]),
            "baseline_deduction_net_usd": usd(agg["ded_base"]),
            "deduction_recovery_rate": rate(recovery_rate),
            "net_otif_lift_pp": round(net_otif_lift_pp, 3),
            "otif_value_usd": usd(agg["otif"]),
            "total_net_benefit_usd": usd(total_net_benefit),
            "subscription_total_usd": usd(subscription_total),
            "net_of_subscription_usd": usd(net_of_sub),
            "time_to_value_weeks": breakeven_week,
            "time_to_value_closed_form_weeks": round(closed_form_ttv, 2)
            if closed_form_ttv
            else None,
            "roi_claim_valid": valid,
            "roi_claim_reasons": reasons,
        },
        # diverging waterfall: naive vanity number -> three honest docks -> net.
        "touches_waterfall": [
            {"label": "Naive credit  (A x t_manual)", "kind": "total", "usd": usd(naive_usd)},
            {
                "label": "- Remove false-positive credit  (A_false x t_manual)",
                "kind": "neg",
                "usd": usd(-agg["a_false"] * c.t_manual / 60.0 * c.w_fte),
            },
            {
                "label": "- Rework penalty  (A_false x t_rework)",
                "kind": "neg",
                "usd": usd(-agg["rework_min"] / 60.0 * c.w_fte),
            },
            {
                "label": "- Nuisance flags  (F_detect x t_review)",
                "kind": "neg",
                "usd": usd(-agg["nuisance_min"] / 60.0 * c.w_fte),
            },
            {"label": "Net touches saved  (honest)", "kind": "total", "usd": usd(net_touches_usd)},
        ],
        # paired-bar / dumbbell headline: one entity (exception aging) at two times.
        "cycle_dumbbell": {
            "metric": "exception aging",
            "unit": "days",
            "before_days": days(cyc_before),
            "after_days": days(cyc_after),
            "lower_is_better": True,
        },
        # the honesty made visible: true vs false work.
        "honesty_table": {
            "rows": [
                {
                    "stream": "Correct auto-resolved",
                    "sign": "credit",
                    "count": int(agg["a_correct"]),
                    "minutes_per": c.t_manual,
                    "minutes_total": usd(agg["gross_min"]),
                    "usd": usd(agg["gross_min"] / 60.0 * c.w_fte),
                },
                {
                    "stream": "False auto-resolved (rework)",
                    "sign": "debit",
                    "count": int(agg["a_false"]),
                    "minutes_per": c.t_rework,
                    "minutes_total": usd(-agg["rework_min"]),
                    "usd": usd(-agg["rework_min"] / 60.0 * c.w_fte),
                },
                {
                    "stream": "Nuisance false flags",
                    "sign": "debit",
                    "count": int(agg["f_detect"]),
                    "minutes_per": c.t_review,
                    "minutes_total": usd(-agg["nuisance_min"]),
                    "usd": usd(-agg["nuisance_min"] / 60.0 * c.w_fte),
                },
                {
                    "stream": "Escalated (needed a human)",
                    "sign": "zero",
                    "count": int(agg["h"]),
                    "minutes_per": 0,
                    "minutes_total": 0.0,
                    "usd": 0.0,
                    "note": "credited ZERO saved -- fully-auto terminal correct items only",
                },
            ],
            "net_minutes": usd(net_min),
            "net_usd": usd(net_touches_usd),
            "naive_usd": usd(naive_usd),
        },
        "deduction": {
            "D_invalid_pool_usd": usd(agg["d_invalid"]),
            "gross_recovered_usd": usd(agg["r_recovered"]),
            "recovery_rate": rate(recovery_rate),
            "automated_net_usd": usd(agg["ded_auto"]),
            "baseline_net_usd": usd(agg["ded_base"]),
            "incremental_net_usd": usd(ded_incremental),
            "note": "credit the delta over manual, not gross (assumption 8: no double-count)",
        },
        "otif": {
            "net_lift_pp": round(net_otif_lift_pp, 3),
            "attribution_alpha": c.alpha,
            "value_usd": usd(agg["otif"]),
            "note": "alpha flags the confounded share; otif_after nets automation-caused misses",
        },
        "weekly": weekly,
        "scorecard_accuracy": acc,
    }
    return report


def _steady_state(weekly: list[dict[str, Any]], k: int) -> float:
    """Mean net benefit over the last k periods (converged, post-ramp) as B_steady."""
    tail = weekly[-k:] if k else weekly
    return sum(w["net_benefit_usd"] for w in tail) / len(tail) if tail else 0.0


# ----------------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------------
def _default_scorecard() -> Path | None:
    hist = REPO / "eval" / "retail_ops" / "history"
    cards = sorted(hist.glob("*.json")) if hist.is_dir() else []
    return cards[-1] if cards else None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Honest ROI harness for retail_ops automation.")
    ap.add_argument("--baseline", type=Path, default=HERE / "fixtures" / "ops_baseline.jsonl")
    ap.add_argument("--automated", type=Path, default=HERE / "fixtures" / "ops_automated.jsonl")
    ap.add_argument("--cost", type=Path, default=HERE / "fixtures" / "cost.json")
    ap.add_argument(
        "--scorecard",
        type=Path,
        default=None,
        help="retail_ops scorecard JSON for the accuracy/guardrail cross-reference "
        "(default: latest in eval/retail_ops/history/; --no-scorecard to skip)",
    )
    ap.add_argument("--no-scorecard", action="store_true")
    ap.add_argument(
        "--out", type=Path, default=None, help="write report.json here (default: stdout)"
    )
    ap.add_argument(
        "--check",
        action="store_true",
        help="compute twice and assert byte-identical output (determinism gate)",
    )
    args = ap.parse_args(argv)

    baseline = load_weeks(args.baseline)
    automated = load_weeks(args.automated)
    cost_doc = load_json(args.cost)

    sc_path = args.scorecard
    if sc_path is None and not args.no_scorecard:
        sc_path = _default_scorecard()
    scorecard = load_json(sc_path) if (sc_path and not args.no_scorecard) else None

    def build() -> str:
        report = compute_report(
            baseline,
            automated,
            cost_doc,
            scorecard,
            baseline_name=args.baseline.stem,
            automated_name=args.automated.stem,
        )
        return json.dumps(report, indent=2, sort_keys=False) + "\n"

    text = build()

    if args.check:
        if text != build():
            print("NON-DETERMINISTIC: two runs differ", flush=True)
            return 1
        print("deterministic: two runs byte-identical", flush=True)
        return 0

    if args.out:
        args.out.write_text(text)
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
