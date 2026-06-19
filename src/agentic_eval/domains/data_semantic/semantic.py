"""Deterministic loader for the synthetic semantic layer
(fixtures/data_semantic/model.json) and the committed JSONL fixtures.

The semantic layer is a FABRICATED, GENERIC model: a small star schema (one
fact table over a couple of dimensions) plus a set of named *metrics*. Each
metric is a typed definition — a measure column, an aggregation
(sum | count | count_distinct | avg), an optional grain (group-by dimension),
and an optional fixed filter — keyed by a stable metric id (e.g. ``revenue``,
``order_count``, ``active_customers``). The model.json is the source of truth
and the answer key: every metric value, every NL→metric mapping, and every
canonical SQL string is *computed* from it, never asserted by hand.

A natural-language question is "mapped" to a metric by deterministic phrase
matching against that metric's synonym tokens — there is no model and no real
NL parser. That phrase-match property is what lets the synthetic corpus carry a
computed ground truth: every question is authored to contain exactly the
synonym(s) of its gold metric, so the expected mapping is known by
construction.

``consistency_check`` is the correctness-sensitive gate: a numeric answer that
does not equal the semantic layer's own computed value for the requested metric
is a CORRECTNESS leak (a wrong-metric / double-count / mis-aggregation answer)
and must never be waved through.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agentic_eval.domain import ROOT

FIXTURES = ROOT / "fixtures" / "data_semantic"
MODEL_PATH = FIXTURES / "model.json"

Aggregation = str  # "sum" | "count" | "count_distinct" | "avg"

# aggregations that collapse rows: a metric answer must equal the model's own
# computed value, never a raw row count or an un-aggregated total.
ROLLUP_AGGREGATIONS: frozenset[str] = frozenset({"sum", "count", "count_distinct", "avg"})


@dataclass(frozen=True)
class Metric:
    id: str
    name: str
    measure: str  # fact column the aggregation is applied to ("*" for count)
    aggregation: Aggregation
    synonyms: tuple[str, ...]  # phrase tokens that map an NL question to this metric
    fixed_filter: tuple[str, str] | None  # (dimension, value) baked into the metric


@dataclass(frozen=True)
class Fact:
    region: str
    status: str
    customer: str
    amount: float


@dataclass(frozen=True)
class NLQuestion:
    id: str
    text: str
    gold_metric: str


@dataclass(frozen=True)
class Mismatch:
    id: str
    gold_class: str


@dataclass(frozen=True)
class SemanticModel:
    metrics: tuple[Metric, ...]

    def by_id(self, metric_id: str) -> Metric:
        for metric in self.metrics:
            if metric.id == metric_id:
                return metric
        raise KeyError(f"unknown metric {metric_id!r}")

    @property
    def metric_ids(self) -> tuple[str, ...]:
        return tuple(metric.id for metric in self.metrics)

    def map_question(self, text: str) -> Metric | None:
        """Return the metric whose synonym token appears in ``text``.

        Deterministic: scans metrics in model order and returns the first whose
        synonym is a substring of the question text (case-insensitively).
        Returns ``None`` when no synonym matches.
        """
        haystack = text.lower()
        for metric in self.metrics:
            if any(syn.lower() in haystack for syn in metric.synonyms):
                return metric
        return None


def _metric_from_raw(raw: dict[str, Any]) -> Metric:
    raw_filter = raw.get("fixed_filter")
    fixed_filter: tuple[str, str] | None = None
    if raw_filter:
        fixed_filter = (str(raw_filter["dimension"]), str(raw_filter["value"]))
    return Metric(
        id=str(raw["id"]),
        name=str(raw["name"]),
        measure=str(raw["measure"]),
        aggregation=str(raw["aggregation"]),
        synonyms=tuple(str(s) for s in raw["synonyms"]),
        fixed_filter=fixed_filter,
    )


def load_model(path: Path = MODEL_PATH) -> SemanticModel:
    """Load the synthetic semantic model (metrics over the star schema)."""
    raw: dict[str, Any] = json.loads(path.read_text())
    return SemanticModel(metrics=tuple(_metric_from_raw(m) for m in raw["metrics"]))


def _read_jsonl(name: str) -> list[dict[str, Any]]:
    path = FIXTURES / name
    if not path.is_file():
        raise FileNotFoundError(f"no such fixture: {name!r}")
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def load_facts(path: Path | None = None) -> list[Fact]:
    """Load the synthetic fact rows (the metrics' only world)."""
    rows = (
        [json.loads(line) for line in path.read_text().splitlines() if line]
        if path is not None
        else _read_jsonl("facts.jsonl")
    )
    return [
        Fact(
            region=str(r["region"]),
            status=str(r["status"]),
            customer=str(r["customer"]),
            amount=float(r["amount"]),
        )
        for r in rows
    ]


def load_nl_questions(path: Path | None = None) -> dict[str, NLQuestion]:
    """Load labeled NL questions, keyed by id."""
    rows = (
        [json.loads(line) for line in path.read_text().splitlines() if line]
        if path is not None
        else _read_jsonl("nl_questions.jsonl")
    )
    questions = [
        NLQuestion(id=str(r["id"]), text=str(r["text"]), gold_metric=str(r["gold_metric"]))
        for r in rows
    ]
    return {q.id: q for q in questions}


def load_mismatches(path: Path | None = None) -> dict[str, Mismatch]:
    """Load labeled metric-mismatch cases (for the diagnosis metric), keyed by id."""
    rows = (
        [json.loads(line) for line in path.read_text().splitlines() if line]
        if path is not None
        else _read_jsonl("mismatches.jsonl")
    )
    mismatches = [Mismatch(id=str(r["id"]), gold_class=str(r["gold_class"])) for r in rows]
    return {m.id: m for m in mismatches}
