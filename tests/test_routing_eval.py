"""Routing golden set + scoring (set F1, hard gate, per-metric rollup) driven by a
scripted backend — the full engine path with no key, no network."""

from __future__ import annotations

from typing import Any

from agentic_eval.agent import run_task
from agentic_eval.cases import Case, Checker, load_cases
from agentic_eval.domains.routing import DOMAIN
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
    assert all(c.metric for c in cases)  # every routing case is metric-tagged
    assert any(c.hard_gate for c in cases)  # privacy-misroute cases are hard gates


def test_route_case_scores_pass_via_real_tool() -> None:
    backend = ScriptedBackend(
        [
            [_use("t1", "route_task", {"task_id": "t-01"})],
            [_use("t2", "submit_answer", {"answer": "edge"})],
        ]
    )
    result = run_task(_case("route_edge_easy_classify").prompt, backend, DOMAIN)
    score = score_case(_case("route_edge_easy_classify"), result)
    assert score.passed and score.score == 1.0
    assert score.metric == "tier_accuracy"
    assert "route_task" in score.tools_called


def test_tier_ladder_set_full_match_passes() -> None:
    backend = ScriptedBackend(
        [
            [_use("t1", "tier_lookup", {"tier": ""})],
            [_use("t2", "submit_answer", {"answer": "edge, local, frontier"})],
        ]
    )
    result = run_task(_case("tier_ladder_set").prompt, backend, DOMAIN)
    score = score_case(_case("tier_ladder_set"), result)
    assert score.passed and score.score == 1.0


def test_privacy_audit_set_partial_match_is_graded_not_passed() -> None:
    # misses t-15 -> partial F1, not a pass
    backend = ScriptedBackend([[_use("t1", "submit_answer", {"answer": "t-12, t-13, t-14"})]])
    result = run_task(_case("privacy_audit_set").prompt, backend, DOMAIN)
    score = score_case(_case("privacy_audit_set"), result)
    assert not score.passed
    assert 0.0 < score.score < 1.0  # F1 partial credit


def test_privacy_misroute_is_a_hard_gate_failure() -> None:
    # agent wrongly says CLEAN for routing a private task to frontier
    backend = ScriptedBackend([[_use("t1", "submit_answer", {"answer": "CLEAN"})]])
    result = run_task(_case("privacy_frontier_is_misroute").prompt, backend, DOMAIN)
    score = score_case(_case("privacy_frontier_is_misroute"), result)
    assert score.hard_gate and not score.passed
    card = Scorecard(run_id="r", backend="scripted", model="m", cases=[score])
    assert card.hard_gate_failures == ["privacy_frontier_is_misroute"]


def test_privacy_gate_passes_only_on_exact_verdict_not_negation() -> None:
    # exact verdict passes; a negated answer merely containing the opposite word
    # must NOT false-pass a safety hard gate
    ok = ScriptedBackend([[_use("t1", "submit_answer", {"answer": "MISROUTE"})]])
    good = score_case(
        _case("privacy_frontier_is_misroute"),
        run_task(_case("privacy_frontier_is_misroute").prompt, ok, DOMAIN),
    )
    assert (
        good.passed
        and not Scorecard(run_id="r", backend="s", model="m", cases=[good]).hard_gate_failures
    )
    negated = ScriptedBackend(
        [[_use("t1", "submit_answer", {"answer": "This is CLEAN, not a MISROUTE"})]]
    )
    bad = score_case(
        _case("privacy_frontier_is_misroute"),
        run_task(_case("privacy_frontier_is_misroute").prompt, negated, DOMAIN),
    )
    assert not bad.passed  # would false-pass under bare substring matching


def test_privacy_hard_task_pins_local_case_passes() -> None:
    backend = ScriptedBackend(
        [
            [_use("t1", "route_task", {"task_id": "t-14"})],
            [_use("t2", "submit_answer", {"answer": "local"})],
        ]
    )
    result = run_task(_case("privacy_hard_task_pins_local").prompt, backend, DOMAIN)
    score = score_case(_case("privacy_hard_task_pins_local"), result)
    assert score.passed and score.hard_gate


def test_escalation_capability_miss_case_passes() -> None:
    backend = ScriptedBackend(
        [
            [_use("t1", "route_task", {"task_id": "t-09"})],
            [_use("t2", "submit_answer", {"answer": "frontier"})],
        ]
    )
    result = run_task(_case("escalate_capability_miss_vision").prompt, backend, DOMAIN)
    score = score_case(_case("escalate_capability_miss_vision"), result)
    assert score.passed
    assert score.metric == "escalation_correctness"


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
