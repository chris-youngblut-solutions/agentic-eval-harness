"""Fintech-compliance golden set + scoring (set F1, hard gate, per-metric rollup) driven by
a scripted backend — the full engine path with no key, no network."""

from __future__ import annotations

from typing import Any

from agentic_eval.agent import run_task
from agentic_eval.cases import Case, Checker, load_cases
from agentic_eval.domains.fintech_compliance import DOMAIN
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
    assert all(c.metric for c in cases)  # every fintech_compliance case is metric-tagged
    assert any(c.hard_gate for c in cases)  # violation cases are hard gates


def test_screen_case_scores_pass_via_real_tool() -> None:
    backend = ScriptedBackend(
        [
            [_use("t1", "screen_record", {"record_id": "r-04"})],
            [_use("t2", "submit_answer", {"answer": "reject"})],
        ]
    )
    result = run_task(_case("kyc_unverified_disposition").prompt, backend, DOMAIN)
    score = score_case(_case("kyc_unverified_disposition"), result)
    assert score.passed and score.score == 1.0
    assert score.metric == "kyc_aml_accuracy"
    assert "screen_record" in score.tools_called


def test_rule_coverage_set_full_match_passes() -> None:
    answer = "CLEAR, KYC_UNVERIFIED, AML_PATTERN, PEP, SANCTIONS, HIGH_RISK_GEO"
    backend = ScriptedBackend(
        [
            [_use("t1", "rule_lookup", {"rule": ""})],
            [_use("t2", "submit_answer", {"answer": answer})],
        ]
    )
    result = run_task(_case("rule_set_ids").prompt, backend, DOMAIN)
    score = score_case(_case("rule_set_ids"), result)
    assert score.passed and score.score == 1.0


def test_access_control_set_passes() -> None:
    backend = ScriptedBackend([[_use("t1", "submit_answer", {"answer": "ac-04, ac-05"})]])
    result = run_task(_case("access_deny_set").prompt, backend, DOMAIN)
    score = score_case(_case("access_deny_set"), result)
    assert score.passed and score.metric == "access_control_adherence"


def test_violation_set_partial_match_is_graded_not_passed() -> None:
    # misses r-12 -> partial F1, not a pass
    backend = ScriptedBackend([[_use("t1", "submit_answer", {"answer": "r-06, r-10"})]])
    result = run_task(_case("violation_audit_set").prompt, backend, DOMAIN)
    score = score_case(_case("violation_audit_set"), result)
    assert not score.passed
    assert 0.0 < score.score < 1.0  # F1 partial credit


def test_violation_is_a_hard_gate_failure_when_agent_wrongly_approves() -> None:
    # agent wrongly says CLEAN for an approve of a must-escalate sanctions record
    backend = ScriptedBackend([[_use("t1", "submit_answer", {"answer": "CLEAN"})]])
    result = run_task(_case("violation_sanctions_approve_is_violation").prompt, backend, DOMAIN)
    score = score_case(_case("violation_sanctions_approve_is_violation"), result)
    assert score.hard_gate and not score.passed
    card = Scorecard(run_id="r", backend="scripted", model="m", cases=[score])
    assert card.hard_gate_failures == ["violation_sanctions_approve_is_violation"]


def test_violation_gate_passes_only_on_exact_verdict_not_negation() -> None:
    # exact verdict passes; a negated answer that merely contains the opposite word
    # must NOT false-pass a compliance hard gate
    ok = ScriptedBackend([[_use("t1", "submit_answer", {"answer": "VIOLATION"})]])
    good = score_case(
        _case("violation_sanctions_approve_is_violation"),
        run_task(_case("violation_sanctions_approve_is_violation").prompt, ok, DOMAIN),
    )
    assert (
        good.passed
        and not Scorecard(run_id="r", backend="s", model="m", cases=[good]).hard_gate_failures
    )
    negated = ScriptedBackend(
        [[_use("t1", "submit_answer", {"answer": "This is CLEAN, not a VIOLATION"})]]
    )
    bad = score_case(
        _case("violation_sanctions_approve_is_violation"),
        run_task(_case("violation_sanctions_approve_is_violation").prompt, negated, DOMAIN),
    )
    assert not bad.passed  # would false-pass under bare substring matching


def test_audit_incomplete_case_passes() -> None:
    backend = ScriptedBackend(
        [
            [_use("t1", "audit_check", {"event_id": "au-04"})],
            [_use("t2", "submit_answer", {"answer": "incomplete"})],
        ]
    )
    result = run_task(_case("audit_incomplete_event").prompt, backend, DOMAIN)
    score = score_case(_case("audit_incomplete_event"), result)
    assert score.passed and score.metric == "audit_trail_completeness"


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
