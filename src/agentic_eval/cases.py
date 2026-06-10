"""Golden-set loading and answer checking."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel

CASES_PATH = Path(__file__).resolve().parents[2] / "eval" / "cases.yaml"


class Checker(BaseModel):
    type: Literal["numeric", "exact", "regex"]
    expected: str
    tolerance: float = 0.01


class Case(BaseModel):
    id: str
    prompt: str
    checker: Checker
    expected_tools: list[str]  # every listed tool must have been called
    max_turns: int = 8


def load_cases(path: Path = CASES_PATH) -> list[Case]:
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


def check_answer(checker: Checker, answer: str | None) -> bool:
    if answer is None:
        return False
    answer = answer.strip()
    if checker.type == "numeric":
        got = _extract_number(answer)
        return got is not None and abs(got - float(checker.expected)) <= checker.tolerance
    if checker.type == "exact":
        return answer.lower() == checker.expected.lower()
    return re.search(checker.expected, answer, re.IGNORECASE) is not None
