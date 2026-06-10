from __future__ import annotations

from agentic_eval.agent import AgentResult
from agentic_eval.cases import Case, Checker, check_answer, load_cases
from agentic_eval.scoring import Scorecard, diff_report, score_case


def _result(answer: str | None, tools_called: list[str], stop: str = "answered") -> AgentResult:
    return AgentResult(
        answer=answer, stop_reason=stop, turns=2, tools_called=tools_called, transcript=[]
    )


CASE = Case(
    id="c1",
    prompt="p",
    checker=Checker(type="numeric", expected="391"),
    expected_tools=["calculator"],
)


def test_golden_set_loads_and_is_well_formed() -> None:
    cases = load_cases()
    assert len(cases) >= 20
    assert all(c.checker.type in ("numeric", "exact", "regex") for c in cases)


def test_checkers() -> None:
    assert check_answer(Checker(type="numeric", expected="6.71"), "about 6.71 units")
    assert not check_answer(Checker(type="numeric", expected="6.71"), "7.5")
    assert check_answer(Checker(type="exact", expected="SK-300-V"), " sk-300-v ")
    assert check_answer(Checker(type="regex", expected=r"IMP-6620"), "part IMP-6620 (Viton)")
    assert not check_answer(Checker(type="numeric", expected="1"), None)


def test_rubric_full_partial_zero() -> None:
    assert score_case(CASE, _result("391", ["calculator"])).score == 1.0
    partial = score_case(CASE, _result("390", ["calculator"]))
    assert partial.score == 0.5 and not partial.passed
    assert score_case(CASE, _result(None, [], stop="stopped_no_answer")).score == 0.0


def test_diff_report_flags_regression() -> None:
    before = Scorecard(
        run_id="a",
        backend="replay",
        model="m",
        cases=[score_case(CASE, _result("391", ["calculator"]))],
    )
    after = Scorecard(
        run_id="b",
        backend="replay",
        model="m",
        cases=[score_case(CASE, _result("999", []))],
    )
    report = diff_report(before, after)
    assert "REGRESSED" in report
    assert "regressions: 1" in report
