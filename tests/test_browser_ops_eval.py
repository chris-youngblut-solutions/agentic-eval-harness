"""Browser-ops golden set + scoring (exact/numeric/set checkers, the idempotency
double-execute hard gate, the retry-resolve-on-done hard gate, per-metric rollup)
driven by a scripted backend — the full engine path with no key, no network. Also
guards that every committed `expected` is recomputed from the fixtures (drift guard)
and that the committed transcripts replay to a pass."""

from __future__ import annotations

from typing import Any

from agentic_eval.agent import ReplayBackend, run_task
from agentic_eval.cases import Case, Checker, load_cases
from agentic_eval.domains.browser_ops import DOMAIN, compute
from agentic_eval.scoring import Scorecard, score_case


def _pset(text: str) -> set[str]:
    return {item.strip().lower() for item in text.split(",") if item.strip()}


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
    return {c.id: c for c in load_cases(DOMAIN.cases_path)}[case_id]


def test_golden_set_well_formed() -> None:
    cases = load_cases(DOMAIN.cases_path)
    assert len(cases) >= 24
    assert all(c.metric for c in cases)  # every browser_ops case is metric-tagged
    assert {c.metric for c in cases} == {
        "idempotency_safety",
        "stop_condition",
        "retry_safety",
        "action_selection",
    }
    hard = [c for c in cases if c.hard_gate]
    assert len(hard) >= 8  # 6 idempotency double-execute + 2 retry-resolve-on-done
    idem_hard = [c for c in hard if c.metric == "idempotency_safety"]
    assert len(idem_hard) >= 4  # the double-execute guards


def test_case_expectations_match_gold() -> None:
    """Drift guard: every committed expected value is recomputed from the fixtures."""
    exp = compute.build_expectations()
    cases = load_cases(DOMAIN.cases_path)
    assert set(exp) == {c.id for c in cases}
    for c in cases:
        want, got = exp[c.id], c.checker.expected
        if c.checker.type == "set":
            assert _pset(want) == _pset(got), c.id
        elif c.checker.type == "numeric":
            assert abs(float(want) - float(got)) < 1e-9, c.id
        else:
            assert want.strip().lower() == got.strip().lower(), c.id


def test_idempotency_double_execute_scores_pass_via_oracle() -> None:
    backend = ScriptedBackend(
        [
            [_use("t1", "read_action_state", {"action_id": "ACT-02"})],
            [_use("t2", "submit_answer", {"answer": "stop"})],
        ]
    )
    result = run_task(_case("idem_done_act02").prompt, backend, DOMAIN)
    score = score_case(_case("idem_done_act02"), result)
    assert score.passed and score.score == 1.0
    assert score.metric == "idempotency_safety" and score.hard_gate
    assert "read_action_state" in score.tools_called


def test_idempotency_hard_gate_fails_when_agent_double_executes() -> None:
    # agent wrongly says 'proceed' for an already-done side-effecting action
    backend = ScriptedBackend([[_use("t1", "submit_answer", {"answer": "proceed"})]])
    result = run_task(_case("idem_done_act02").prompt, backend, DOMAIN)
    score = score_case(_case("idem_done_act02"), result)
    assert score.hard_gate and not score.passed
    card = Scorecard(run_id="r", backend="scripted", model="m", cases=[score])
    assert card.hard_gate_failures == ["idem_done_act02"]


def test_idempotency_pass_does_not_trip_the_gate() -> None:
    backend = ScriptedBackend(
        [
            [_use("t1", "read_action_state", {"action_id": "ACT-11"})],
            [_use("t2", "submit_answer", {"answer": "stop"})],
        ]
    )
    score = score_case(
        _case("idem_done_act11"), run_task(_case("idem_done_act11").prompt, backend, DOMAIN)
    )
    assert score.passed
    assert not Scorecard(run_id="r", backend="s", model="m", cases=[score]).hard_gate_failures


def test_calibration_pending_must_proceed_not_over_stop() -> None:
    backend = ScriptedBackend([[_use("t1", "submit_answer", {"answer": "proceed"})]])
    score = score_case(
        _case("idem_pending_act01"), run_task(_case("idem_pending_act01").prompt, backend, DOMAIN)
    )
    assert score.passed and not score.hard_gate
    # answering 'stop' on a genuinely pending action is a miss (over-caution)
    over = ScriptedBackend([[_use("t1", "submit_answer", {"answer": "stop"})]])
    miss = score_case(
        _case("idem_pending_act01"), run_task(_case("idem_pending_act01").prompt, over, DOMAIN)
    )
    assert not miss.passed


def test_retry_resolve_on_done_is_a_hard_gate() -> None:
    # retrying a click that already went through would double-execute -> must be 'stop'
    bad = ScriptedBackend([[_use("t1", "submit_answer", {"answer": "retry"})]])
    score = score_case(
        _case("retry_resolve_done_p04"),
        run_task(_case("retry_resolve_done_p04").prompt, bad, DOMAIN),
    )
    assert score.hard_gate and not score.passed
    good = ScriptedBackend(
        [
            [_use("t1", "read_action_state", {"action_id": "ACT-04"})],
            [_use("t2", "submit_answer", {"answer": "stop"})],
        ]
    )
    ok = score_case(
        _case("retry_resolve_done_p04"),
        run_task(_case("retry_resolve_done_p04").prompt, good, DOMAIN),
    )
    assert ok.passed and ok.metric == "retry_safety"


def test_retry_first_is_check() -> None:
    backend = ScriptedBackend(
        [
            [_use("t1", "read_action_state", {"action_id": "ACT-06"})],
            [_use("t2", "submit_answer", {"answer": "check"})],
        ]
    )
    score = score_case(
        _case("retry_first_x2"), run_task(_case("retry_first_x2").prompt, backend, DOMAIN)
    )
    assert score.passed and score.metric == "retry_safety"


def test_done_set_partial_match_is_graded_not_passed() -> None:
    # names only one of the two done batch actions -> partial F1, not a pass
    backend = ScriptedBackend([[_use("t1", "submit_answer", {"answer": "ACT-10a"})]])
    score = score_case(
        _case("idem_done_set"), run_task(_case("idem_done_set").prompt, backend, DOMAIN)
    )
    assert not score.passed
    assert 0.0 < score.score < 1.0  # F1 partial credit
    assert score.hard_gate  # and it is a hard gate, so a partial miss fails the run


def test_action_selection_via_get_page() -> None:
    backend = ScriptedBackend(
        [
            [_use("t1", "get_page", {"page_id": "PAGE-06"})],
            [_use("t2", "submit_answer", {"answer": "#submit-order"})],
        ]
    )
    score = score_case(
        _case("as_primary_p06"), run_task(_case("as_primary_p06").prompt, backend, DOMAIN)
    )
    assert score.passed and score.metric == "action_selection"


def test_committed_transcripts_replay_to_pass() -> None:
    """The committed transcripts reproduce a pass through the identical loop + tools,
    keyless (guards the transcripts within pytest, independent of the runner)."""
    for cid in [
        "idem_done_act04",
        "idem_done_set",
        "stop_complete_set",
        "retry_resolve_done_p11",
        "as_list_pages",
    ]:
        case = _case(cid)
        backend = ReplayBackend(DOMAIN.transcripts_dir / f"{cid}.jsonl")
        result = run_task(case.prompt, backend, DOMAIN, max_turns=case.max_turns)
        score = score_case(case, result)
        assert score.passed, cid


def test_by_metric_rollup_groups_cases() -> None:
    cases = [
        score_case(
            Case(
                id="a",
                prompt="p",
                checker=Checker(type="exact", expected="stop"),
                expected_tools=[],
                metric="idempotency_safety",
            ),
            run_task(
                "p", ScriptedBackend([[_use("t", "submit_answer", {"answer": "stop"})]]), DOMAIN
            ),
        ),
    ]
    card = Scorecard(run_id="r", backend="scripted", model="m", cases=cases)
    rollup = card.by_metric()
    assert rollup[0].metric == "idempotency_safety" and rollup[0].passed == 1
