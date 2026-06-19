"""Deterministic metric computation over the synthetic fact table.

This is the single source of truth for "what a metric evaluates to" — the tools
(metric_rollup, consistency_check) and the generator (which writes the cases'
expected values) both call it, so the eval's answer key and the tool the agent
calls can never drift. No model, no network: same facts + same metric => same
number, byte-stable.

A metric value is computed by:
1. applying the metric's fixed filter (if any) and any caller-supplied filter,
2. applying the aggregation to the metric's measure column over the surviving
   rows (sum/avg over ``amount``; count over rows; count_distinct over the
   ``customer`` dimension),
3. rounding to a stable precision so the JSON answer is reproducible.
"""

from __future__ import annotations

from agentic_eval.domains.data_semantic.semantic import Fact, Metric

ROUND = 2


def _matches(fact: Fact, filt: tuple[str, str] | None) -> bool:
    if filt is None:
        return True
    dimension, value = filt
    if dimension == "region":
        return fact.region == value
    if dimension == "status":
        return fact.status == value
    if dimension == "customer":
        return fact.customer == value
    raise ValueError(f"unknown filter dimension: {dimension!r}")


def filter_facts(
    facts: list[Fact],
    metric: Metric,
    extra_filter: tuple[str, str] | None = None,
) -> list[Fact]:
    """Rows surviving the metric's fixed filter and an optional caller filter."""
    rows = [f for f in facts if _matches(f, metric.fixed_filter)]
    rows = [f for f in rows if _matches(f, extra_filter)]
    return rows


def compute_metric(
    facts: list[Fact],
    metric: Metric,
    extra_filter: tuple[str, str] | None = None,
) -> float:
    """The metric's value over the (filtered) fact rows. Deterministic."""
    rows = filter_facts(facts, metric, extra_filter)
    if metric.aggregation == "count":
        return float(len(rows))
    if metric.aggregation == "count_distinct":
        return float(len({f.customer for f in rows}))
    if metric.aggregation == "sum":
        return round(sum(f.amount for f in rows), ROUND)
    if metric.aggregation == "avg":
        if not rows:
            return 0.0
        return round(sum(f.amount for f in rows) / len(rows), ROUND)
    raise ValueError(f"unknown aggregation: {metric.aggregation!r}")


def metric_sql(metric: Metric, extra_filter: tuple[str, str] | None = None) -> str:
    """Canonical SQL string for a metric (+ optional filter) over ``facts``.

    A deterministic rendering used for the NL→SQL accuracy metric — exact-match
    checked, so the formatting is fixed and not pretty-printer dependent.
    """
    if metric.aggregation == "count":
        select = "COUNT(*)"
    elif metric.aggregation == "count_distinct":
        select = f"COUNT(DISTINCT {metric.measure})"
    elif metric.aggregation == "sum":
        select = f"SUM({metric.measure})"
    elif metric.aggregation == "avg":
        select = f"AVG({metric.measure})"
    else:
        raise ValueError(f"unknown aggregation: {metric.aggregation!r}")

    clauses: list[tuple[str, str]] = []
    if metric.fixed_filter is not None:
        clauses.append(metric.fixed_filter)
    if extra_filter is not None:
        clauses.append(extra_filter)
    where = ""
    if clauses:
        conds = " AND ".join(f"{dim} = '{val}'" for dim, val in clauses)
        where = f" WHERE {conds}"
    return f"SELECT {select} FROM facts{where}"
