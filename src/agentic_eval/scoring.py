"""Rubric and scorecard.

Per-case score:
  1.0  correct answer
  0.5  wrong/missing answer, but every expected tool was called (right plan,
       wrong execution — partial credit)
  0.0  otherwise
A case passes at score 1.0.
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel

from agentic_eval.agent import AgentResult
from agentic_eval.cases import Case, check_answer

HISTORY_DIR = Path(__file__).resolve().parents[2] / "eval" / "history"


class CaseScore(BaseModel):
    case_id: str
    score: float
    passed: bool
    answer: str | None
    stop_reason: str
    turns: int
    tools_called: list[str]


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

    def summary(self) -> str:
        n = len(self.cases)
        return (
            f"run {self.run_id} [{self.backend}/{self.model}]: "
            f"{self.passed}/{n} passed, score {self.total_score:.1f}/{n}"
        )


def score_case(case: Case, result: AgentResult) -> CaseScore:
    correct = check_answer(case.checker, result.answer)
    tools_ok = all(t in result.tools_called for t in case.expected_tools)
    score = 1.0 if correct else (0.5 if tools_ok else 0.0)
    return CaseScore(
        case_id=case.id,
        score=score,
        passed=correct,
        answer=result.answer,
        stop_reason=result.stop_reason,
        turns=result.turns,
        tools_called=result.tools_called,
    )


def save_scorecard(card: Scorecard, history_dir: Path = HISTORY_DIR) -> Path:
    history_dir.mkdir(parents=True, exist_ok=True)
    path = history_dir / f"{card.run_id}.json"
    path.write_text(card.model_dump_json(indent=2) + "\n")
    return path


def load_history(history_dir: Path = HISTORY_DIR) -> list[Scorecard]:
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
