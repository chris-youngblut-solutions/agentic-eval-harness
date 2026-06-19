"""Deterministic synthetic-corpus generator for the data_semantic domain.

Everything here is FABRICATED and GENERIC. The fact table is a tiny synthetic
star schema (region/status/customer/amount); the NL questions are authored
phrasings that each embed exactly one gold metric's synonym token; the
metric-mismatch cases are labeled across three fabricated diagnosis classes. No
real company data model, metric catalog, BI semantic layer, or operational
figure is reproduced. There is no randomness: re-running reproduces
byte-identical fixtures (a test guards this). Run as a module to (re)write the
committed fixtures:

    uv run python -m agentic_eval.domains.data_semantic.generate

Fixtures written under fixtures/data_semantic/:
- facts.jsonl       the synthetic fact rows {region, status, customer, amount}.
                    The metrics' only world; every metric value is computed from
                    these (model.json is the answer key).
- nl_questions.jsonl {id, text, gold_metric}: NL phrasings, each embedding one
                    gold metric's synonym so the NL->metric mapping is known by
                    construction.
- mismatches.jsonl  {id, gold_class} across three fabricated metric-mismatch
                    diagnosis classes (wrong_grain, double_count, filter_drift).

model.json is hand-authored (the source semantic model / answer key) and is NOT
regenerated here.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agentic_eval.domains.data_semantic import semantic

FIXTURES = semantic.FIXTURES


def build_facts() -> list[dict[str, Any]]:
    """A tiny synthetic fact table. Hand-tabulated so the metrics resolve to
    clean, human-checkable values:

      revenue (sum amount)          = 1000
      order_count (count)           = 8
      active_customers (distinct)   = 4   (cust-a..cust-d)
      avg_order_value               = 125.0
      completed_revenue (status=completed sum) = 600
      west_orders (region=west count)          = 4
    """
    rows = [
        {"region": "west", "status": "completed", "customer": "cust-a", "amount": 100.0},
        {"region": "west", "status": "completed", "customer": "cust-b", "amount": 200.0},
        {"region": "west", "status": "pending", "customer": "cust-a", "amount": 150.0},
        {"region": "west", "status": "cancelled", "customer": "cust-c", "amount": 50.0},
        {"region": "east", "status": "completed", "customer": "cust-c", "amount": 300.0},
        {"region": "east", "status": "pending", "customer": "cust-d", "amount": 100.0},
        {"region": "east", "status": "cancelled", "customer": "cust-b", "amount": 75.0},
        {"region": "east", "status": "pending", "customer": "cust-d", "amount": 25.0},
    ]
    return rows


def build_nl_questions() -> list[dict[str, Any]]:
    """NL phrasings, each embedding exactly one gold metric's synonym token."""
    return [
        {
            "id": "q-01",
            "text": "What is the total revenue across all orders?",
            "gold_metric": "revenue",
        },
        {
            "id": "q-02",
            "text": "How many orders were placed in total?",
            "gold_metric": "order_count",
        },
        {
            "id": "q-03",
            "text": "How many distinct customers do we have?",
            "gold_metric": "active_customers",
        },
        {
            "id": "q-04",
            "text": "What is the average order value overall?",
            "gold_metric": "avg_order_value",
        },
        {
            "id": "q-05",
            "text": "What is the completed revenue?",
            "gold_metric": "completed_revenue",
        },
        {"id": "q-06", "text": "How many west orders are there?", "gold_metric": "west_orders"},
        {"id": "q-07", "text": "Give me the total sales figure.", "gold_metric": "revenue"},
        {
            "id": "q-08",
            "text": "What is the number of orders we processed?",
            "gold_metric": "order_count",
        },
    ]


def build_mismatches() -> list[dict[str, Any]]:
    """Labeled metric-mismatch diagnosis cases across three fabricated classes."""
    return [
        {"id": "x-01", "gold_class": "wrong_grain"},
        {"id": "x-02", "gold_class": "wrong_grain"},
        {"id": "x-03", "gold_class": "double_count"},
        {"id": "x-04", "gold_class": "double_count"},
        {"id": "x-05", "gold_class": "filter_drift"},
        {"id": "x-06", "gold_class": "filter_drift"},
    ]


def write_corpus(out_dir: Path = FIXTURES) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    jsonl = {
        "facts.jsonl": build_facts(),
        "nl_questions.jsonl": build_nl_questions(),
        "mismatches.jsonl": build_mismatches(),
    }
    for name, rows in jsonl.items():
        (out_dir / name).write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in rows))


if __name__ == "__main__":
    write_corpus()
    print(f"wrote corpus to {FIXTURES}")
