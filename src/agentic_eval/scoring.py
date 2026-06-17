"""Rubric and scorecard.

Per-case score:
  1.0  correct answer
  0.5  wrong/missing answer, but every expected tool was called (right plan,
       wrong execution — partial credit)
  0.0  otherwise
A `set` checker scores its F1 directly (the basis for precision/recall metrics),
passing only at a perfect set match. A case passes at score 1.0.

Cases may carry a `metric` tag (rolled up per metric) and a `hard_gate` flag (a
failure there fails the whole run, e.g. a safety-bound violation).
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel

from agentic_eval.agent import AgentResult
from agentic_eval.cases import Case, check_answer, grade_answer


class CaseScore(BaseModel):
    case_id: str
    score: float
    passed: bool
    answer: str | None
    stop_reason: str
    turns: int
    tools_called: list[str]
    metric: str | None = None
    hard_gate: bool = False


class MetricRollup(BaseModel):
    metric: str
    n: int
    passed: int
    mean_score: float


class Scorecard(BaseModel):
    run_id: str
    backend: str
    model: str
    cases: list[CaseScore]

    @property
    def passed(self) -> int:
        return sum(1 for c in self.cases if c.passed)

    @property
    def total_score(self) -> float:
        return sum(c.score for c in self.cases)

    @property
    def hard_gate_failures(self) -> list[str]:
        return [c.case_id for c in self.cases if c.hard_gate and not c.passed]

    def by_metric(self) -> list[MetricRollup]:
        order: list[str] = []
        for c in self.cases:
            key = c.metric or "(untagged)"
            if key not in order:
                order.append(key)
        rollups: list[MetricRollup] = []
        for key in order:
            members = [c for c in self.cases if (c.metric or "(untagged)") == key]
            rollups.append(
                MetricRollup(
                    metric=key,
                    n=len(members),
                    passed=sum(1 for c in members if c.passed),
                    mean_score=sum(c.score for c in members) / len(members),
                )
            )
        return rollups

    def summary(self) -> str:
        n = len(self.cases)
        gate = self.hard_gate_failures
        gate_note = f"  HARD-GATE FAIL: {', '.join(gate)}" if gate else ""
        return (
            f"run {self.run_id} [{self.backend}/{self.model}]: "
            f"{self.passed}/{n} passed, score {self.total_score:.1f}/{n}{gate_note}"
        )


def score_case(case: Case, result: AgentResult) -> CaseScore:
    if case.checker.type == "set":
        score = grade_answer(case.checker, result.answer)
        passed = score >= 1.0 - 1e-9
    else:
        correct = check_answer(case.checker, result.answer)
        tools_ok = all(t in result.tools_called for t in case.expected_tools)
        score = 1.0 if correct else (0.5 if tools_ok else 0.0)
        passed = correct
    return CaseScore(
        case_id=case.id,
        score=score,
        passed=passed,
        answer=result.answer,
        stop_reason=result.stop_reason,
        turns=result.turns,
        tools_called=result.tools_called,
        metric=case.metric,
        hard_gate=case.hard_gate,
    )


def save_scorecard(card: Scorecard, history_dir: Path) -> Path:
    history_dir.mkdir(parents=True, exist_ok=True)
    path = history_dir / f"{card.run_id}.json"
    path.write_text(card.model_dump_json(indent=2) + "\n")
    return path


def load_history(history_dir: Path) -> list[Scorecard]:
    cards = [
        Scorecard.model_validate(json.loads(p.read_text()))
        for p in sorted(history_dir.glob("*.json"))
    ]
    return cards


def diff_report(before: Scorecard, after: Scorecard) -> str:
    """Per-case regression report between two runs."""
    lines = [
        f"before: {before.summary()}",
        f"after:  {after.summary()}",
        "",
        f"{'case':<28} {'before':>7} {'after':>7}  change",
        "-" * 56,
    ]
    prior = {c.case_id: c for c in before.cases}
    regressions = improvements = 0
    for case in after.cases:
        old = prior.get(case.case_id)
        old_score = old.score if old else None
        marker = ""
        if old_score is None:
            marker = "new"
        elif case.score < old_score:
            marker, regressions = "REGRESSED", regressions + 1
        elif case.score > old_score:
            marker, improvements = "improved", improvements + 1
        old_text = f"{old_score:.1f}" if old_score is not None else "-"
        lines.append(f"{case.case_id:<28} {old_text:>7} {case.score:>7.1f}  {marker}")
    lines += ["", f"regressions: {regressions}  improvements: {improvements}"]
    return "\n".join(lines)
