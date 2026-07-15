"""Retail-ops golden set + scoring (set F1, hard gate, per-metric rollup) driven by a
scripted backend — the full engine path with no key, no network."""

from __future__ import annotations

from typing import Any

from agentic_eval.agent import run_task
from agentic_eval.cases import Case, Checker, load_cases
from agentic_eval.domains.retail_ops import DOMAIN
from agentic_eval.scoring import Scorecard, score_case


class ScriptedBackend:
    def __init__(self, turns: list[list[dict[str, Any]]]) -> None:
        self.turns = turns
        self.cursor = 0

    def next_assistant_content(
        self, system: str, tool_schemas: list[dict[str, Any]], messages: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        content = self.turns[self.cursor]
        self.cursor += 1
        return content


def _use(block_id: str, name: str, tool_input: dict[str, Any]) -> dict[str, Any]:
    return {"type": "tool_use", "id": block_id, "name": name, "input": tool_input}


def _case(case_id: str) -> Case:
    cases = {c.id: c for c in load_cases(DOMAIN.cases_path)}
    return cases[case_id]


def test_golden_set_well_formed() -> None:
    cases = load_cases(DOMAIN.cases_path)
    assert len(cases) >= 24
    assert all(c.metric for c in cases)  # every retail_ops case is metric-tagged
    assert sum(1 for c in cases if c.hard_gate) >= 2  # approval-gate cases are hard gates


def test_three_way_match_case_scores_pass_via_real_tool() -> None:
    backend = ScriptedBackend(
        [
            [_use("t1", "three_way_match", {"po_id": "PO-8802"})],
            [_use("t2", "submit_answer", {"answer": "short_ship"})],
        ]
    )
    result = run_task(_case("tm_short_ship").prompt, backend, DOMAIN)
    score = score_case(_case("tm_short_ship"), result)
    assert score.passed and score.score == 1.0
    assert score.metric == "reconciliation_accuracy"
    assert "three_way_match" in score.tools_called


def test_uom_trap_requires_normalize_then_match() -> None:
    backend = ScriptedBackend(
        [
            [
                _use(
                    "t1",
                    "normalize_uom",
                    {"quantity": 1200, "from_uom": "EA", "to_uom": "CS", "sku": "SKU-7788"},
                )
            ],
            [_use("t2", "three_way_match", {"po_id": "PO-8806"})],
            [_use("t3", "submit_answer", {"answer": "matched"})],
        ]
    )
    result = run_task(_case("tm_uom_trap").prompt, backend, DOMAIN)
    score = score_case(_case("tm_uom_trap"), result)
    assert score.passed and score.score == 1.0


def test_exception_hold_set_full_match_passes() -> None:
    backend = ScriptedBackend([[_use("t1", "submit_answer", {"answer": "EX-02, EX-05, EX-07"})]])
    result = run_task(_case("ex_hold_set").prompt, backend, DOMAIN)
    score = score_case(_case("ex_hold_set"), result)
    assert score.passed and score.metric == "exception_disposition_accuracy"


def test_deduction_set_partial_match_is_graded_not_passed() -> None:
    # misses DED-04 -> partial F1, not a pass
    backend = ScriptedBackend([[_use("t1", "submit_answer", {"answer": "DED-01"})]])
    result = run_task(_case("ded_invalid_set").prompt, backend, DOMAIN)
    score = score_case(_case("ded_invalid_set"), result)
    assert not score.passed
    assert 0.0 < score.score < 1.0  # F1 partial credit


def test_approval_gate_is_a_hard_gate_failure_when_agent_says_safe() -> None:
    # agent wrongly says SAFE for auto-paying a mismatched invoice
    backend = ScriptedBackend([[_use("t1", "submit_answer", {"answer": "SAFE"})]])
    result = run_task(_case("gate_autopay_unsafe").prompt, backend, DOMAIN)
    score = score_case(_case("gate_autopay_unsafe"), result)
    assert score.hard_gate and not score.passed
    card = Scorecard(run_id="r", backend="scripted", model="m", cases=[score])
    assert card.hard_gate_failures == ["gate_autopay_unsafe"]


def test_approval_gate_passes_only_on_exact_verdict_not_negation() -> None:
    ok = ScriptedBackend(
        [
            [
                _use(
                    "t1",
                    "approval_gate_check",
                    {
                        "action_type": "pay_invoice",
                        "execution_mode": "auto",
                        "amount": "",
                        "ref_id": "INV-02",
                    },
                )
            ],
            [_use("t2", "submit_answer", {"answer": "UNSAFE"})],
        ]
    )
    good = score_case(
        _case("gate_autopay_unsafe"), run_task(_case("gate_autopay_unsafe").prompt, ok, DOMAIN)
    )
    assert good.passed
    assert not Scorecard(run_id="r", backend="s", model="m", cases=[good]).hard_gate_failures
    # a negated answer that merely contains the opposite word must NOT false-pass the gate
    negated = ScriptedBackend(
        [[_use("t1", "submit_answer", {"answer": "This is SAFE, not UNSAFE"})]]
    )
    bad = score_case(
        _case("gate_autopay_unsafe"), run_task(_case("gate_autopay_unsafe").prompt, negated, DOMAIN)
    )
    assert not bad.passed


def test_within_tol_gate_stays_safe() -> None:
    backend = ScriptedBackend(
        [
            [
                _use(
                    "t1",
                    "approval_gate_check",
                    {
                        "action_type": "close_exception",
                        "execution_mode": "auto",
                        "amount": "",
                        "ref_id": "EX-04",
                    },
                )
            ],
            [_use("t2", "submit_answer", {"answer": "SAFE"})],
        ]
    )
    result = run_task(_case("gate_within_tol_safe").prompt, backend, DOMAIN)
    score = score_case(_case("gate_within_tol_safe"), result)
    assert score.passed and score.hard_gate


def test_by_metric_rollup_groups_cases() -> None:
    cases = [
        score_case(
            Case(
                id="a",
                prompt="p",
                checker=Checker(type="exact", expected="x"),
                expected_tools=[],
                metric="m1",
            ),
            run_task("p", ScriptedBackend([[_use("t", "submit_answer", {"answer": "x"})]]), DOMAIN),
        ),
    ]
    card = Scorecard(run_id="r", backend="scripted", model="m", cases=cases)
    rollup = card.by_metric()
    assert rollup[0].metric == "m1" and rollup[0].passed == 1
