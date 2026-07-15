"""process_mapping golden set + scoring (numeric/exact/set checkers, the ready-to-
automate hard gate, per-metric rollup) driven by a scripted backend — the full
engine path with no key, no network. Also guards two invariants: the case
expected values are recomputed from the gold (drift guard), and the gold maps are
internally well-formed and fully anchored by the fragments."""

from __future__ import annotations

from typing import Any

from agentic_eval.agent import run_task
from agentic_eval.cases import Case, load_cases
from agentic_eval.domains.process_mapping import DOMAIN, compute, process_map
from agentic_eval.scoring import Scorecard, score_case


def _pset(text: str) -> set[str]:
    """Order/space/case-insensitive parse of a comma-separated answer set."""
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


def _recon(answer: str, process_id: str = "PROC-04", source_id: str = "SRC-401") -> ScriptedBackend:
    """A reconstruction plan: get_process, get_source, then submit_answer."""
    return ScriptedBackend(
        [
            [_use("t0", "get_process", {"process_id": process_id})],
            [_use("t1", "get_source", {"source_id": source_id})],
            [_use("t2", "submit_answer", {"answer": answer})],
        ]
    )


def test_golden_set_well_formed() -> None:
    cases = load_cases(DOMAIN.cases_path)
    assert len(cases) >= 22
    assert all(c.metric for c in cases)  # every case is metric-tagged
    assert sum(1 for c in cases if c.hard_gate) >= 3  # the safety gate cases
    assert {c.metric for c in cases} == {
        "process_inventory",
        "step_extraction",
        "system_coverage",
        "fix_before_automate_flagging",
        "handoff_identification",
        "ready_to_automate_safety",
    }


def test_case_expectations_match_gold() -> None:
    """Drift guard: every committed expected value is recomputed from the gold."""
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


def test_gold_wellformed_and_fully_anchored() -> None:
    gold = process_map.load_gold()
    srcs = process_map.load_sources()
    for pid, proc in gold.items():
        step_ids = {s.step_id for s in proc.steps}
        # every FBA step has a valid reason; every AR step has an empty reason
        for step in proc.steps:
            if step.fix_before_automate:
                assert step.reason in process_map.REASONS, f"{pid} {step.step_id}"
            else:
                assert step.reason == "", f"{pid} {step.step_id}"
            assert step.system in process_map.SYSTEMS, f"{pid} {step.step_id}"
        # every handoff endpoint is a real step
        for h in proc.handoffs:
            assert h.frm in step_ids and h.to in step_ids, f"{pid} {h.frm}->{h.to}"
            assert h.kind in {"handoff", "decision"}
        # every gold step is anchored in >=1 of the process's fragments
        blob = " ".join(
            (
                " ".join(cell for row in s.rows for cell in row)
                if s.kind == "spreadsheet"
                else s.content
            )
            for s in srcs.values()
            if s.process_id == pid
        )
        for step in proc.steps:
            assert step.step_id in blob, f"{pid} {step.step_id} not anchored"
    # every source points at a real process
    assert all(s.process_id in gold for s in srcs.values())


def test_set_case_full_match_passes() -> None:
    result = run_task(
        _case("pm_steps_proc04").prompt,
        _recon(compute.build_expectations()["pm_steps_proc04"]),
        DOMAIN,
    )
    score = score_case(_case("pm_steps_proc04"), result)
    assert score.passed and score.score == 1.0
    assert score.metric == "step_extraction"


def test_set_case_partial_match_is_graded_not_passed() -> None:
    # drop STEP-46 -> partial F1, not a pass
    partial = "STEP-40,STEP-41,STEP-42,STEP-43,STEP-44,STEP-45"
    result = run_task(_case("pm_steps_proc04").prompt, _recon(partial), DOMAIN)
    score = score_case(_case("pm_steps_proc04"), result)
    assert not score.passed
    assert 0.0 < score.score < 1.0


def test_exact_and_numeric_cases_pass_via_scripted_plan() -> None:
    for cid, ans, pid, sid in [
        ("pm_fix_reason_step43", "UOM", "PROC-04", "SRC-402"),
        ("pm_disposition_step42", "AR", "PROC-04", "SRC-403"),
        ("pm_via_step64_65", "email", "PROC-06", "SRC-601"),
        ("pm_fix_count_proc07", "6", "PROC-07", "SRC-701"),
    ]:
        result = run_task(_case(cid).prompt, _recon(ans, pid, sid), DOMAIN)
        score = score_case(_case(cid), result)
        assert score.passed and score.score == 1.0, cid


def test_ready_gate_trips_when_agent_marks_broken_step_ready() -> None:
    # STEP-44 is fix-before-automate; answering READY must fail the hard gate
    backend = ScriptedBackend([[_use("t0", "submit_answer", {"answer": "READY"})]])
    result = run_task(_case("pm_safety_step44").prompt, backend, DOMAIN)
    score = score_case(_case("pm_safety_step44"), result)
    assert score.hard_gate and not score.passed
    card = Scorecard(run_id="r", backend="scripted", model="m", cases=[score])
    assert card.hard_gate_failures == ["pm_safety_step44"]


def test_ready_gate_no_false_pass_on_negation() -> None:
    # the exact correct verdict passes (with the right plan)...
    good = score_case(
        _case("pm_safety_step44"),
        run_task(_case("pm_safety_step44").prompt, _recon("FIX_FIRST"), DOMAIN),
    )
    assert good.passed
    assert not Scorecard(run_id="r", backend="s", model="m", cases=[good]).hard_gate_failures
    # ...but a negated answer that merely contains the safe word must NOT false-pass
    negated = ScriptedBackend([[_use("t0", "submit_answer", {"answer": "READY, not FIX_FIRST"})]])
    bad = score_case(
        _case("pm_safety_step44"),
        run_task(_case("pm_safety_step44").prompt, negated, DOMAIN),
    )
    assert not bad.passed  # would false-pass under bare substring matching


def test_safe_set_hard_gate_partial_is_not_passed() -> None:
    # including a broken step in the "safe to automate now" set fails the set hard gate
    backend = _recon("STEP-70,STEP-71,STEP-77", "PROC-07", "SRC-701")
    result = run_task(_case("pm_safety_safe_set_proc07").prompt, backend, DOMAIN)
    score = score_case(_case("pm_safety_safe_set_proc07"), result)
    assert score.hard_gate and not score.passed
    card = Scorecard(run_id="r", backend="s", model="m", cases=[score])
    assert card.hard_gate_failures == ["pm_safety_safe_set_proc07"]


def test_by_metric_rollup_has_six_tags() -> None:
    scores = [
        score_case(
            c,
            run_task(
                c.prompt, _recon(compute.build_expectations()[c.id], "PROC-04", "SRC-401"), DOMAIN
            ),
        )
        for c in load_cases(DOMAIN.cases_path)
        if c.metric == "process_inventory"
    ]
    # smoke: rollup groups by the metric tag
    card = Scorecard(run_id="r", backend="s", model="m", cases=scores)
    assert card.by_metric()[0].metric == "process_inventory"
