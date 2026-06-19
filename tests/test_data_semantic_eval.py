"""Data-semantic golden set + scoring (numeric/exact/set checkers, hard gate, per-metric
rollup) driven by a scripted backend — the full engine path with no key, no network."""

from __future__ import annotations

from typing import Any

from agentic_eval.agent import run_task
from agentic_eval.cases import Case, Checker, load_cases
from agentic_eval.domains.data_semantic import DOMAIN
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
    assert all(c.metric for c in cases)  # every data_semantic case is metric-tagged
    assert any(c.hard_gate for c in cases)  # consistency cases are hard gates


def test_nl_mapping_case_scores_pass_via_real_tool() -> None:
    backend = ScriptedBackend(
        [
            [
                _use(
                    "t1",
                    "nl_to_metric",
                    {"question": "What is the total revenue across all orders?"},
                )
            ],
            [_use("t2", "submit_answer", {"answer": "revenue"})],
        ]
    )
    result = run_task(_case("nl_map_revenue").prompt, backend, DOMAIN)
    score = score_case(_case("nl_map_revenue"), result)
    assert score.passed and score.score == 1.0
    assert score.metric == "nl_metric_mapping"
    assert "nl_to_metric" in score.tools_called


def test_metric_value_case_scores_pass_via_real_tool() -> None:
    backend = ScriptedBackend(
        [
            [_use("t1", "metric_rollup", {"metric_id": "revenue", "dimension": "", "value": ""})],
            [_use("t2", "submit_answer", {"answer": "1000"})],
        ]
    )
    result = run_task(_case("metric_revenue_value").prompt, backend, DOMAIN)
    score = score_case(_case("metric_revenue_value"), result)
    assert score.passed and score.score == 1.0
    assert score.metric == "metric_correctness"


def test_sql_case_exact_match_passes() -> None:
    backend = ScriptedBackend(
        [
            [_use("t1", "sql_for_metric", {"metric_id": "revenue", "dimension": "", "value": ""})],
            [_use("t2", "submit_answer", {"answer": "SELECT SUM(amount) FROM facts"})],
        ]
    )
    result = run_task(_case("sql_revenue").prompt, backend, DOMAIN)
    score = score_case(_case("sql_revenue"), result)
    assert score.passed and score.score == 1.0


def test_model_coverage_set_full_match_passes() -> None:
    answer = (
        "revenue, order_count, active_customers, avg_order_value, completed_revenue, west_orders"
    )
    backend = ScriptedBackend(
        [
            [_use("t1", "metric_lookup", {"metric_id": ""})],
            [_use("t2", "submit_answer", {"answer": answer})],
        ]
    )
    result = run_task(_case("model_metrics_set").prompt, backend, DOMAIN)
    score = score_case(_case("model_metrics_set"), result)
    assert score.passed and score.score == 1.0


def test_consistency_audit_partial_match_is_graded_not_passed() -> None:
    # lists only one of the two mismatching values -> partial F1, not a pass
    backend = ScriptedBackend([[_use("t1", "submit_answer", {"answer": "8"})]])
    result = run_task(_case("consistency_audit_set").prompt, backend, DOMAIN)
    score = score_case(_case("consistency_audit_set"), result)
    assert not score.passed
    assert 0.0 < score.score < 1.0  # F1 partial credit


def test_consistency_is_a_hard_gate_failure_when_agent_accepts_wrong_value() -> None:
    # agent wrongly says CONSISTENT for a wrong-metric answer
    backend = ScriptedBackend([[_use("t1", "submit_answer", {"answer": "CONSISTENT"})]])
    result = run_task(_case("consistency_revenue_wrong_is_mismatch").prompt, backend, DOMAIN)
    score = score_case(_case("consistency_revenue_wrong_is_mismatch"), result)
    assert score.hard_gate and not score.passed
    card = Scorecard(run_id="r", backend="scripted", model="m", cases=[score])
    assert card.hard_gate_failures == ["consistency_revenue_wrong_is_mismatch"]


def test_consistency_gate_passes_only_on_exact_verdict_not_negation() -> None:
    # exact verdict passes; a negated answer that merely contains the opposite word
    # must NOT false-pass a correctness hard gate
    ok = ScriptedBackend([[_use("t1", "submit_answer", {"answer": "MISMATCH"})]])
    good = score_case(
        _case("consistency_revenue_wrong_is_mismatch"),
        run_task(_case("consistency_revenue_wrong_is_mismatch").prompt, ok, DOMAIN),
    )
    assert (
        good.passed
        and not Scorecard(run_id="r", backend="s", model="m", cases=[good]).hard_gate_failures
    )
    negated = ScriptedBackend(
        [[_use("t1", "submit_answer", {"answer": "This is CONSISTENT, not a MISMATCH"})]]
    )
    bad = score_case(
        _case("consistency_revenue_wrong_is_mismatch"),
        run_task(_case("consistency_revenue_wrong_is_mismatch").prompt, negated, DOMAIN),
    )
    assert not bad.passed  # would false-pass under bare substring matching


def test_mismatch_diagnosis_case_passes() -> None:
    backend = ScriptedBackend(
        [
            [_use("t1", "mismatch_trace", {"mismatch_id": "x-05"})],
            [_use("t2", "submit_answer", {"answer": "filter_drift"})],
        ]
    )
    result = run_task(_case("mismatch_class_x05").prompt, backend, DOMAIN)
    score = score_case(_case("mismatch_class_x05"), result)
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
