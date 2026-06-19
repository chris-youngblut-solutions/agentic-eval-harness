"""Customer-support golden set + scoring (set F1, hard gate, per-metric rollup) driven by
a scripted backend — the full engine path with no key, no network."""

from __future__ import annotations

from typing import Any

from agentic_eval.agent import run_task
from agentic_eval.cases import Case, Checker, load_cases
from agentic_eval.domains.customer_support import DOMAIN
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
    assert len(cases) >= 15
    assert all(c.metric for c in cases)  # every customer_support case is metric-tagged
    assert any(c.hard_gate for c in cases)  # auto-action cases are hard gates


def test_classify_case_scores_pass_via_real_tool() -> None:
    backend = ScriptedBackend(
        [
            [_use("t1", "classify_ticket", {"ticket_id": "t-07"})],
            [_use("t2", "submit_answer", {"answer": "escalate"})],
        ]
    )
    result = run_task(_case("resolve_refund_disposition").prompt, backend, DOMAIN)
    score = score_case(_case("resolve_refund_disposition"), result)
    assert score.passed and score.score == 1.0
    assert score.metric == "resolution_accuracy"
    assert "classify_ticket" in score.tools_called


def test_policy_coverage_set_full_match_passes() -> None:
    answer = (
        "PASSWORD_RESET, ORDER_STATUS, FAQ_HOWTO, BILLING_DISPUTE, ACCOUNT_DELETION, FRAUD_REPORT"
    )
    backend = ScriptedBackend(
        [
            [_use("t1", "policy_lookup", {"category": ""})],
            [_use("t2", "submit_answer", {"answer": answer})],
        ]
    )
    result = run_task(_case("policy_categories_set").prompt, backend, DOMAIN)
    score = score_case(_case("policy_categories_set"), result)
    assert score.passed and score.score == 1.0


def test_auto_action_set_partial_match_is_graded_not_passed() -> None:
    # misses t-11 -> partial F1, not a pass
    backend = ScriptedBackend([[_use("t1", "submit_answer", {"answer": "t-07, t-09"})]])
    result = run_task(_case("auto_action_audit_set").prompt, backend, DOMAIN)
    score = score_case(_case("auto_action_audit_set"), result)
    assert not score.passed
    assert 0.0 < score.score < 1.0  # F1 partial credit


def test_auto_action_is_a_hard_gate_failure_when_agent_wrongly_resolves() -> None:
    # agent wrongly says SAFE for a resolve of a must-escalate ticket
    backend = ScriptedBackend([[_use("t1", "submit_answer", {"answer": "SAFE"})]])
    result = run_task(
        _case("auto_action_account_deletion_resolve_is_unsafe").prompt, backend, DOMAIN
    )
    score = score_case(_case("auto_action_account_deletion_resolve_is_unsafe"), result)
    assert score.hard_gate and not score.passed
    card = Scorecard(run_id="r", backend="scripted", model="m", cases=[score])
    assert card.hard_gate_failures == ["auto_action_account_deletion_resolve_is_unsafe"]


def test_auto_action_gate_passes_only_on_exact_verdict_not_negation() -> None:
    # exact verdict passes; a negated answer that merely contains the opposite word
    # must NOT false-pass a safety hard gate
    ok = ScriptedBackend([[_use("t1", "submit_answer", {"answer": "UNSAFE"})]])
    good = score_case(
        _case("auto_action_account_deletion_resolve_is_unsafe"),
        run_task(_case("auto_action_account_deletion_resolve_is_unsafe").prompt, ok, DOMAIN),
    )
    assert (
        good.passed
        and not Scorecard(run_id="r", backend="s", model="m", cases=[good]).hard_gate_failures
    )
    negated = ScriptedBackend(
        [[_use("t1", "submit_answer", {"answer": "This is SAFE, not UNSAFE"})]]
    )
    bad = score_case(
        _case("auto_action_account_deletion_resolve_is_unsafe"),
        run_task(_case("auto_action_account_deletion_resolve_is_unsafe").prompt, negated, DOMAIN),
    )
    assert not bad.passed  # would false-pass under bare substring matching


def test_route_escalate_case_passes() -> None:
    backend = ScriptedBackend(
        [
            [_use("t1", "route_review", {"escalation_id": "e-04"})],
            [_use("t2", "submit_answer", {"answer": "escalate"})],
        ]
    )
    result = run_task(_case("route_escalate_required").prompt, backend, DOMAIN)
    score = score_case(_case("route_escalate_required"), result)
    assert score.passed


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
