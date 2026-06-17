"""Trust & Safety golden set + scoring (set F1, hard gate, per-metric rollup) driven by a
scripted backend — the full engine path with no key, no network."""

from __future__ import annotations

from typing import Any

from agentic_eval.agent import run_task
from agentic_eval.cases import Case, Checker, load_cases
from agentic_eval.domains.trust_safety import DOMAIN
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
    assert all(c.metric for c in cases)  # every trust_safety case is metric-tagged
    assert any(c.hard_gate for c in cases)  # leakage cases are hard gates


def test_classify_case_scores_pass_via_real_tool() -> None:
    backend = ScriptedBackend(
        [
            [_use("t1", "classify_content", {"content_id": "c-04"})],
            [_use("t2", "submit_answer", {"answer": "remove"})],
        ]
    )
    result = run_task(_case("enforce_spam_action").prompt, backend, DOMAIN)
    score = score_case(_case("enforce_spam_action"), result)
    assert score.passed and score.score == 1.0
    assert score.metric == "enforcement_accuracy"
    assert "classify_content" in score.tools_called


def test_policy_coverage_set_full_match_passes() -> None:
    answer = "BENIGN, SPAM, HARASSMENT, GRAPHIC_VIOLENCE, MISINFO, SELF_HARM"
    backend = ScriptedBackend(
        [
            [_use("t1", "policy_lookup", {"category": ""})],
            [_use("t2", "submit_answer", {"answer": answer})],
        ]
    )
    result = run_task(_case("policy_categories_set").prompt, backend, DOMAIN)
    score = score_case(_case("policy_categories_set"), result)
    assert score.passed and score.score == 1.0


def test_leakage_set_partial_match_is_graded_not_passed() -> None:
    # misses c-12 -> partial F1, not a pass
    backend = ScriptedBackend([[_use("t1", "submit_answer", {"answer": "c-04, c-08"})]])
    result = run_task(_case("leakage_audit_set").prompt, backend, DOMAIN)
    score = score_case(_case("leakage_audit_set"), result)
    assert not score.passed
    assert 0.0 < score.score < 1.0  # F1 partial credit


def test_leakage_is_a_hard_gate_failure_when_agent_wrongly_allows() -> None:
    # agent wrongly says CLEAN for an allow of a must-escalate item
    backend = ScriptedBackend([[_use("t1", "submit_answer", {"answer": "CLEAN"})]])
    result = run_task(_case("leakage_self_harm_allow_is_leak").prompt, backend, DOMAIN)
    score = score_case(_case("leakage_self_harm_allow_is_leak"), result)
    assert score.hard_gate and not score.passed
    card = Scorecard(run_id="r", backend="scripted", model="m", cases=[score])
    assert card.hard_gate_failures == ["leakage_self_harm_allow_is_leak"]


def test_leakage_gate_passes_only_on_exact_verdict_not_negation() -> None:
    # exact verdict passes; a negated answer that merely contains the opposite word
    # must NOT false-pass a safety hard gate
    ok = ScriptedBackend([[_use("t1", "submit_answer", {"answer": "LEAK"})]])
    good = score_case(
        _case("leakage_self_harm_allow_is_leak"),
        run_task(_case("leakage_self_harm_allow_is_leak").prompt, ok, DOMAIN),
    )
    assert (
        good.passed
        and not Scorecard(run_id="r", backend="s", model="m", cases=[good]).hard_gate_failures
    )
    negated = ScriptedBackend(
        [[_use("t1", "submit_answer", {"answer": "This is CLEAN, not a LEAK"})]]
    )
    bad = score_case(
        _case("leakage_self_harm_allow_is_leak"),
        run_task(_case("leakage_self_harm_allow_is_leak").prompt, negated, DOMAIN),
    )
    assert not bad.passed  # would false-pass under bare substring matching


def test_appeal_overturn_case_passes() -> None:
    backend = ScriptedBackend(
        [
            [_use("t1", "appeal_adjudicate", {"appeal_id": "a-04"})],
            [_use("t2", "submit_answer", {"answer": "overturn"})],
        ]
    )
    result = run_task(_case("appeal_overturn_wrong_removal").prompt, backend, DOMAIN)
    score = score_case(_case("appeal_overturn_wrong_removal"), result)
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
