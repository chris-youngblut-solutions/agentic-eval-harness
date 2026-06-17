"""Golden-set loading and answer checking."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel


class Checker(BaseModel):
    type: Literal["numeric", "exact", "regex", "set"]
    expected: str
    tolerance: float = 0.01


class Case(BaseModel):
    id: str
    prompt: str
    checker: Checker
    expected_tools: list[str]  # every listed tool must have been called
    max_turns: int = 8
    metric: str | None = None  # which domain metric this case exercises (for rollup)
    hard_gate: bool = False  # a failure here fails the whole run (e.g. safety bounds)


def load_cases(path: Path) -> list[Case]:
    raw = yaml.safe_load(path.read_text())
    cases = [Case.model_validate(c) for c in raw["cases"]]
    ids = [c.id for c in cases]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate case ids")
    return cases


def _extract_number(text: str) -> float | None:
    match = re.search(r"-?\d+(?:,\d{3})*(?:\.\d+)?", text)
    if match is None:
        return None
    return float(match.group(0).replace(",", ""))


def _parse_set(text: str) -> set[str]:
    return {item.strip().lower() for item in text.split(",") if item.strip()}


def set_f1(expected: str, answer: str) -> float:
    """F1 of the answer's item set vs the expected set (the basis for precision/recall
    metrics). Two empty sets agree (1.0); a non-empty against an empty disagree (0.0)."""
    want, got = _parse_set(expected), _parse_set(answer)
    if not want and not got:
        return 1.0
    true_positives = len(want & got)
    if true_positives == 0:
        return 0.0
    precision = true_positives / len(got)
    recall = true_positives / len(want)
    return 2 * precision * recall / (precision + recall)


def grade_answer(checker: Checker, answer: str | None) -> float:
    """Graded score in [0, 1]. For set checkers this is the F1; for the others it is
    1.0 / 0.0 mirroring check_answer."""
    if answer is None:
        return 0.0
    if checker.type == "set":
        return set_f1(checker.expected, answer)
    return 1.0 if check_answer(checker, answer) else 0.0


def check_answer(checker: Checker, answer: str | None) -> bool:
    if answer is None:
        return False
    answer = answer.strip()
    if checker.type == "numeric":
        got = _extract_number(answer)
        return got is not None and abs(got - float(checker.expected)) <= checker.tolerance
    if checker.type == "exact":
        return answer.lower() == checker.expected.lower()
    if checker.type == "set":
        return set_f1(checker.expected, answer) >= 1.0 - 1e-9
    return re.search(checker.expected, answer, re.IGNORECASE) is not None
