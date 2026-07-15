#!/usr/bin/env python3
"""Deterministic generator for the ROI harness synthetic before/after fixtures.

Emits three files into ``./fixtures``:

    ops_baseline.jsonl   BEFORE -- manual operation. One ``MARKER_WK##`` record per line.
    ops_automated.jsonl  AFTER  -- automated run. True-vs-false labels per line.
    cost.json            rate / time / price deck (``<<TOKEN>>`` scalars) + vendor targets.

Fully synthetic. NO RNG: the 8-week series is a hand-authored ramp encoded as explicit
per-week control arrays, so a re-run is byte-identical -- the determinism the whole ROI
story leans on. ``SEED`` is a provenance stamp, not an entropy source; the generator is
deterministic *by construction*, which is strictly stronger than seeded pseudo-randomness.

The ramp is the honest part of the data: week 1 runs ~54% raw auto / ~16.7% false / a
*negative* deduction delta while the model is still tuning; steady state (wk 7-8) reaches
~79% raw auto / ~4.5% false. That shape is what makes time-to-value honest -- the report
must not quote the steady-state rate as if it held from day one.

Usage:
    python3 generate.py            # (re)write the three fixtures under ./fixtures
    python3 generate.py --check    # regenerate in-memory and assert on-disk == fresh
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"

# Provenance stamp only. No pseudo-random draw is taken anywhere in this file; the
# series below is authored, not sampled. Recorded so a future stochastic variant can
# pin its RNG to reproduce this exact baseline.
SEED = 20260711
WEEKS = 8

# --- the shared 8-week queue (identical in both files; roi.py asserts the match) -----
# Volume of exceptions arriving each week, and the shipment volume behind OTIF.
EXCEPTIONS_IN = [2000, 2100, 2200, 2400, 2500, 2300, 2150, 2050]
SHIPPED_UNITS = [190000, 195000, 200000, 215000, 220000, 205000, 198000, 192000]
# Same true recoverable invalid-deduction pool in both worlds (automation changes how
# much gets recovered, not how much was wrongly taken).
D_INVALID = [8000, 8200, 8300, 8600, 8800, 8400, 8100, 7900]

# --- BEFORE: manual operation --------------------------------------------------------
CYCLE_BEFORE_DAYS = [5.6, 5.7, 5.5, 5.8, 6.0, 5.7, 5.5, 5.4]
MATCH_CYCLE_BEFORE_DAYS = [3.6, 3.5, 3.7, 3.8, 3.9, 3.6, 3.5, 3.4]
OTIF_PCT_BEFORE = [93.2, 93.0, 93.1, 92.8, 92.5, 92.9, 93.2, 93.3]
# Manual deduction handling: conservative disputing, no wrong disputes, steady write-off.
BASE_R_RECOVERED = 3400
BASE_N_DISPUTES = 20
BASE_N_WRONG = 0
BASE_D_WRITTEN_OFF = 1600

# --- AFTER: automated run (the honest core) ------------------------------------------
# TERMINAL, no-human actions the agent got RIGHT (credited at t_manual)...
AUTO_RESOLVED_CORRECT = [900, 1080, 1280, 1520, 1720, 1660, 1610, 1560]
# ...and WRONG (auto-closed something it should not have -> charged at t_rework).
AUTO_RESOLVED_FALSE = [180, 170, 150, 140, 120, 95, 80, 70]
# escalated_human is derived (V - correct - false): still needed a person, credited zero.
# Nuisance flags raised on clean items -> new review touches at t_review.
FALSE_FLAGS = [140, 120, 100, 90, 80, 60, 55, 50]
# Aging constants. tau_false_loop > tau_human by design: a wrongly-closed exception
# reopens aged from its ORIGINAL creation date, so a high false rate raises effective aging.
TAU_AUTO_DAYS = 0.25
TAU_HUMAN_DAYS = 4.5
TAU_FALSE_LOOP_DAYS = [14.0, 13.0, 12.0, 11.0, 10.0, 9.0, 8.5, 8.0]
MATCH_CYCLE_AFTER_DAYS = [3.4, 3.0, 2.6, 2.2, 1.9, 1.6, 1.4, 1.3]
# OTIF after already nets automation-CAUSED misses (early weeks barely beat manual).
OTIF_PCT_AFTER = [93.3, 93.4, 93.8, 94.0, 94.1, 94.4, 94.6, 94.7]
# Automated deduction handling: disputes harder (more recovered) but eats wrong-dispute
# penalties early in the ramp before it is tuned.
AUTO_R_RECOVERED = [4200, 5200, 6100, 7000, 7600, 7200, 6900, 6700]
AUTO_N_DISPUTES = [42, 46, 50, 54, 56, 52, 50, 48]
AUTO_N_WRONG = [6, 5, 4, 3, 3, 2, 2, 2]
AUTO_D_WRITTEN_OFF = [1800, 1500, 1300, 1100, 1000, 900, 850, 800]


def _marker(week: int) -> str:
    return f"MARKER_WK{week:02d}"


def baseline_records() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for i in range(WEEKS):
        rows.append(
            {
                "week": i + 1,
                "marker": _marker(i + 1),
                "exceptions_in": EXCEPTIONS_IN[i],
                "cycle_before_days": CYCLE_BEFORE_DAYS[i],
                "match_cycle_before_days": MATCH_CYCLE_BEFORE_DAYS[i],
                "otif_pct_before": OTIF_PCT_BEFORE[i],
                "shipped_units": SHIPPED_UNITS[i],
                "deduction": {
                    "D_invalid": D_INVALID[i],
                    "R_recovered": BASE_R_RECOVERED,
                    "N_disputes": BASE_N_DISPUTES,
                    "N_wrong": BASE_N_WRONG,
                    "D_written_off_wrongly": BASE_D_WRITTEN_OFF,
                },
            }
        )
    return rows


def automated_records() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for i in range(WEEKS):
        correct = AUTO_RESOLVED_CORRECT[i]
        false = AUTO_RESOLVED_FALSE[i]
        escalated = EXCEPTIONS_IN[i] - correct - false  # derived; self-checks the invariant
        if escalated < 0:
            raise ValueError(f"week {i + 1}: correct+false exceed exceptions_in")
        rows.append(
            {
                "week": i + 1,
                "marker": _marker(i + 1),
                "exceptions_in": EXCEPTIONS_IN[i],
                "auto_resolved_correct": correct,
                "auto_resolved_false": false,
                "escalated_human": escalated,
                "false_flags": FALSE_FLAGS[i],
                "tau_auto_days": TAU_AUTO_DAYS,
                "tau_false_loop_days": TAU_FALSE_LOOP_DAYS[i],
                "tau_human_days": TAU_HUMAN_DAYS,
                "match_cycle_after_days": MATCH_CYCLE_AFTER_DAYS[i],
                "otif_pct_after": OTIF_PCT_AFTER[i],
                "shipped_units": SHIPPED_UNITS[i],
                "deduction": {
                    "D_invalid": D_INVALID[i],
                    "R_recovered": AUTO_R_RECOVERED[i],
                    "N_disputes": AUTO_N_DISPUTES[i],
                    "N_wrong": AUTO_N_WRONG[i],
                    "D_written_off_wrongly": AUTO_D_WRITTEN_OFF[i],
                },
            }
        )
    return rows


def cost_deck() -> dict[str, Any]:
    """The rate/time/price deck. Mirrors fixtures/retail_ops/policy.json posture: every
    scalar is a {token, value, unit} object and only ``.value`` is ever read."""
    return {
        "_provenance": (
            "Fully synthetic illustrative cost/rate deck for the retail_ops ROI harness. "
            "NOT any real customer's, vendor's, or prior employer's labor rate, "
            "subscription price, integration cost, deduction-dispute fee, OTIF fine "
            "schedule, or attribution factor. Every scalar is a fabricated placeholder "
            "tagged with a <<TOKEN>> so a reviewer can see at a glance it is invented. "
            "Only .value is read by roi.py. Re-source every value per deployment."
        ),
        "schema": "roi-cost/0.1",
        "currency": "USD",
        "period_unit": "week",
        "params": {
            "t_manual_min": {
                "token": "<<T_MANUAL_MIN>>",
                "value": 12,
                "unit": "minutes",
                "note": "avg human handle time per exception",
            },
            "t_rework_min": {
                "token": "<<T_REWORK_MIN>>",
                "value": 25,
                "unit": "minutes",
                "note": "discover + reverse + re-handle one bad auto-action; > t_manual by design",
            },
            "t_review_min": {
                "token": "<<T_REVIEW_MIN>>",
                "value": 5,
                "unit": "minutes",
                "note": "review + dismiss one nuisance false flag",
            },
            "w_fte_usd_per_hr": {
                "token": "<<W_FTE>>",
                "value": 45,
                "unit": "usd_per_hour",
                "note": "fully-loaded ops labor rate (benefits/overhead), not base wage",
            },
            "fte_hours_per_period": {
                "token": "<<FTE_HRS_WK>>",
                "value": 40,
                "unit": "hours_per_week",
                "note": "one FTE-week of capacity",
            },
            "subscription_per_period": {
                "token": "<<SUB_WK>>",
                "value": 4500,
                "unit": "usd_per_week",
                "note": "software subscription cost per week (~19.5k/mo)",
            },
            "integration_onetime": {
                "token": "<<INTEGRATION>>",
                "value": 30000,
                "unit": "usd",
                "note": "one-time integration / FDE deployment cost (I_0)",
            },
            "otif_attribution_alpha": {
                "token": "<<ALPHA>>",
                "value": 0.6,
                "unit": "factor_0_1",
                "note": (
                    "share of the OTIF delta causally tied to faster exception clearance; "
                    "carrier/demand/supplier variance confound the rest"
                ),
            },
            "otif_fine_per_unit": {
                "token": "<<OTIF_FINE>>",
                "value": 1.5,
                "unit": "usd_per_unit",
                "note": "chargeback fine or margin per shipped unit tied to an OTIF miss",
            },
            "dispute_cost_each": {
                "token": "<<C_DISPUTE>>",
                "value": 45,
                "unit": "usd_per_dispute",
                "note": "labor/fees to file one deduction dispute",
            },
            "wrong_dispute_penalty_each": {
                "token": "<<PEN_WRONG>>",
                "value": 220,
                "unit": "usd_per_wrong_dispute",
                "note": "valid deduction wrongly disputed: chargeback re-post + relationship cost",
            },
        },
        "targets": {
            "efficiency_pct": {
                "token": "<<TARGET_EFF>>",
                "value": 40,
                "unit": "percent",
                "note": "VENDOR FRAMING TARGET the report can display, never baked-in ground truth",
            },
            "breakeven_weeks": {
                "token": "<<TARGET_TTV>>",
                "value": 4,
                "unit": "weeks",
                "note": "VENDOR FRAMING TARGET the report can display, never baked-in ground truth",
            },
        },
    }


def _validate(baseline: list[dict[str, Any]], automated: list[dict[str, Any]]) -> None:
    """Author-time self-check: the two files must describe the same queue, and the
    core accounting identity A_correct + A_false + H == V must hold every week."""
    if len(baseline) != WEEKS or len(automated) != WEEKS:
        raise ValueError("week count mismatch")
    for b, a in zip(baseline, automated, strict=True):
        if b["exceptions_in"] != a["exceptions_in"]:
            raise ValueError(f"week {a['week']}: exceptions_in differs between files")
        if b["shipped_units"] != a["shipped_units"]:
            raise ValueError(f"week {a['week']}: shipped_units differs between files")
        total = a["auto_resolved_correct"] + a["auto_resolved_false"] + a["escalated_human"]
        if total != a["exceptions_in"]:
            raise ValueError(f"week {a['week']}: A_correct+A_false+H ({total}) != V")


def _jsonl(rows: list[dict[str, Any]]) -> str:
    return "".join(json.dumps(r) + "\n" for r in rows)


def _json(doc: dict[str, Any]) -> str:
    return json.dumps(doc, indent=2) + "\n"


def build() -> dict[str, str]:
    """Return the {filename: text} map without touching disk (used by --check)."""
    baseline = baseline_records()
    automated = automated_records()
    _validate(baseline, automated)
    return {
        "ops_baseline.jsonl": _jsonl(baseline),
        "ops_automated.jsonl": _jsonl(automated),
        "cost.json": _json(cost_deck()),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Generate the synthetic ROI fixtures (deterministic).")
    ap.add_argument(
        "--check",
        action="store_true",
        help="regenerate in-memory and assert the on-disk fixtures are byte-identical",
    )
    args = ap.parse_args(argv)
    files = build()

    if args.check:
        for name, text in files.items():
            path = FIXTURES / name
            if not path.exists():
                print(f"MISSING: {name}", flush=True)
                return 1
            if path.read_text() != text:
                print(f"STALE: {name} differs from a fresh generate", flush=True)
                return 1
        print(f"fixtures up to date ({len(files)} files, seed {SEED})", flush=True)
        return 0

    FIXTURES.mkdir(parents=True, exist_ok=True)
    for name, text in files.items():
        (FIXTURES / name).write_text(text)
    print(f"wrote {len(files)} fixtures to {FIXTURES} (seed {SEED}, {WEEKS} weeks)", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
