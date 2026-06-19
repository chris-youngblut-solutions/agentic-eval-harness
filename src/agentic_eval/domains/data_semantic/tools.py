"""The data_semantic domain's tools: NL->metric/SQL + metric computation over a
synthetic semantic layer.

All tools are offline and deterministic — same input, same output, no network —
which is what makes the eval reproducible and keyless. The NL->metric mapping is
deterministic synonym matching against the synthetic model (model.json); metric
values are computed from the committed synthetic fact table (facts.jsonl) by the
shared `compute` module, so the tool the agent calls and the eval's answer key
can never drift.

Everything is FABRICATED and GENERIC: no real data model, no real metric
catalog, no real BI semantic layer, no real data.

`consistency_check` is the deterministic correctness gate: it never asks a
model, it just asks whether a proposed numeric answer equals the semantic
layer's own computed value for the requested metric. A metric answer that
mismatches the definition (wrong metric, double-count, mis-aggregation) must
never be waved through as correct.
"""

from __future__ import annotations

import json
from typing import Any

from agentic_eval.domains.data_semantic import compute, semantic

_MODEL = semantic.load_model()
_FACTS = semantic.load_facts()
_MISMATCHES = semantic.load_mismatches()

# dimensions a caller may filter a rollup by
_FILTER_DIMENSIONS = frozenset({"region", "status", "customer"})

# match tolerance for the consistency gate (answers are rounded to 2 dp)
_EPS = 0.5


class ToolError(ValueError):
    """Raised on invalid tool input; returned to the model as is_error."""


def _parse_filter(dimension: str, value: str) -> tuple[str, str] | None:
    dimension = dimension.strip()
    value = value.strip()
    if not dimension and not value:
        return None
    if not dimension or not value:
        raise ToolError("filter needs both a dimension and a value")
    if dimension not in _FILTER_DIMENSIONS:
        raise ToolError(f"unknown filter dimension: {dimension!r}")
    return (dimension, value)


def list_metrics() -> str:
    """List every metric id the semantic layer defines."""
    return json.dumps({"metrics": list(_MODEL.metric_ids)}, sort_keys=True)


def metric_lookup(metric_id: str = "") -> str:
    """Return the definition (measure + aggregation + grain) for a metric.

    With an empty metric id, list every metric id the semantic layer defines.
    """
    if not metric_id:
        return json.dumps({"metrics": list(_MODEL.metric_ids)}, sort_keys=True)
    try:
        metric = _MODEL.by_id(metric_id)
    except KeyError as exc:
        raise ToolError(f"unknown metric: {metric_id!r}") from exc
    out: dict[str, Any] = {
        "id": metric.id,
        "name": metric.name,
        "measure": metric.measure,
        "aggregation": metric.aggregation,
    }
    if metric.fixed_filter is not None:
        out["fixed_filter"] = {
            "dimension": metric.fixed_filter[0],
            "value": metric.fixed_filter[1],
        }
    return json.dumps(out, sort_keys=True)


def nl_to_metric(question: str) -> str:
    """Map a natural-language question to a metric id by deterministic synonym
    matching against the semantic model. Returns ``UNMAPPED`` when no synonym
    matches (the agent should not guess a metric)."""
    metric = _MODEL.map_question(question)
    if metric is None:
        return json.dumps({"metric": "UNMAPPED"}, sort_keys=True)
    return json.dumps({"metric": metric.id}, sort_keys=True)


def metric_rollup(metric_id: str, dimension: str = "", value: str = "") -> str:
    """Compute a metric's value over the fact table, with an optional filter.

    Returns the metric id, the aggregation used, and the computed value.
    Deterministic: same model + same facts => same value.
    """
    try:
        metric = _MODEL.by_id(metric_id)
    except KeyError as exc:
        raise ToolError(f"unknown metric: {metric_id!r}") from exc
    extra = _parse_filter(dimension, value)
    val = compute.compute_metric(_FACTS, metric, extra)
    return json.dumps(
        {"metric": metric.id, "aggregation": metric.aggregation, "value": val},
        sort_keys=True,
    )


def sql_for_metric(metric_id: str, dimension: str = "", value: str = "") -> str:
    """Return the canonical SQL string for a metric (+ optional filter)."""
    try:
        metric = _MODEL.by_id(metric_id)
    except KeyError as exc:
        raise ToolError(f"unknown metric: {metric_id!r}") from exc
    extra = _parse_filter(dimension, value)
    return json.dumps(
        {"metric": metric.id, "sql": compute.metric_sql(metric, extra)}, sort_keys=True
    )


def mismatch_trace(mismatch_id: str) -> str:
    """Return the gold diagnosis class for a labeled metric-mismatch case."""
    case = _MISMATCHES.get(mismatch_id)
    if case is None:
        raise ToolError(f"unknown mismatch_id: {mismatch_id!r}")
    return json.dumps({"mismatch_id": mismatch_id, "class": case.gold_class}, sort_keys=True)


def consistency_check(
    metric_id: str, proposed_value: str, dimension: str = "", value: str = ""
) -> str:
    """Deterministic correctness gate: does the proposed value match the metric?

    Returns ``CONSISTENT`` iff ``proposed_value`` equals the semantic layer's own
    computed value for ``metric_id`` (within rounding), else ``MISMATCH``. A
    mismatch is a wrong-metric / double-count / mis-aggregation answer that must
    never be waved through as correct. No model is involved.
    """
    try:
        metric = _MODEL.by_id(metric_id)
    except KeyError as exc:
        raise ToolError(f"unknown metric: {metric_id!r}") from exc
    try:
        proposed = float(str(proposed_value).replace(",", "").strip())
    except ValueError as exc:
        raise ToolError(f"proposed_value is not numeric: {proposed_value!r}") from exc
    extra = _parse_filter(dimension, value)
    truth = compute.compute_metric(_FACTS, metric, extra)
    if abs(proposed - truth) <= _EPS:
        return f"CONSISTENT: {metric_id} = {truth}"
    return f"MISMATCH: {metric_id} = {truth}, proposed {proposed}"


TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "name": "metric_lookup",
        "description": (
            "Look up the synthetic semantic layer. With a metric id, return its "
            "definition (measure, aggregation, and any fixed grain/filter). With an "
            "empty metric id, list every metric the model defines."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "metric_id": {
                    "type": "string",
                    "description": "metric id, e.g. revenue; empty to list all",
                }
            },
            "required": ["metric_id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "list_metrics",
        "description": (
            "List every metric id the semantic layer defines. Call this to discover the "
            "model's metrics (e.g. to count or enumerate them) before looking an "
            "individual metric up with metric_lookup."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
            "additionalProperties": False,
        },
    },
    {
        "name": "nl_to_metric",
        "description": (
            "Map a natural-language question to a metric id by deterministic synonym "
            "matching against the semantic model. Returns UNMAPPED if no metric matches "
            "(do not guess). Pass the question text."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {"question": {"type": "string", "description": "the NL question"}},
            "required": ["question"],
            "additionalProperties": False,
        },
    },
    {
        "name": "metric_rollup",
        "description": (
            "Compute a metric's value over the fact table, optionally filtered by a "
            "dimension (region | status | customer) and value. Returns the computed "
            "value. Pass the metric id; leave dimension/value empty for the unfiltered "
            "metric."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "metric_id": {"type": "string", "description": "metric id, e.g. revenue"},
                "dimension": {
                    "type": "string",
                    "description": "optional filter dimension: region|status|customer (empty=none)",
                },
                "value": {
                    "type": "string",
                    "description": "optional filter value, e.g. west (empty for none)",
                },
            },
            "required": ["metric_id", "dimension", "value"],
            "additionalProperties": False,
        },
    },
    {
        "name": "sql_for_metric",
        "description": (
            "Return the canonical SQL string for a metric, optionally filtered by a "
            "dimension (region | status | customer) and value. Pass the metric id; leave "
            "dimension/value empty for the unfiltered metric."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "metric_id": {"type": "string", "description": "metric id, e.g. revenue"},
                "dimension": {
                    "type": "string",
                    "description": "optional filter dimension (empty for none)",
                },
                "value": {
                    "type": "string",
                    "description": "optional filter value (empty for none)",
                },
            },
            "required": ["metric_id", "dimension", "value"],
            "additionalProperties": False,
        },
    },
    {
        "name": "mismatch_trace",
        "description": (
            "Return the gold diagnosis class for a labeled metric-mismatch case "
            "(wrong_grain, double_count, or filter_drift). Pass the mismatch id."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "mismatch_id": {"type": "string", "description": "mismatch id, e.g. x-01"}
            },
            "required": ["mismatch_id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "consistency_check",
        "description": (
            "Deterministic correctness gate: report CONSISTENT or MISMATCH for a proposed "
            "numeric value against a metric. MISMATCH means the proposed value does not "
            "equal the semantic layer's computed value (a wrong-metric / double-count / "
            "mis-aggregation answer). Call this before finalizing any numeric metric "
            "answer. Pass the metric id, the proposed value, and any filter used."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "metric_id": {"type": "string", "description": "metric id, e.g. revenue"},
                "proposed_value": {"type": "string", "description": "the numeric answer to verify"},
                "dimension": {
                    "type": "string",
                    "description": "optional filter dimension used (empty for none)",
                },
                "value": {
                    "type": "string",
                    "description": "optional filter value used (empty for none)",
                },
            },
            "required": ["metric_id", "proposed_value", "dimension", "value"],
            "additionalProperties": False,
        },
    },
]


def execute_tool(name: str, tool_input: dict[str, Any]) -> tuple[str, bool]:
    """Run a tool; returns (content, is_error)."""
    try:
        if name == "list_metrics":
            return list_metrics(), False
        if name == "metric_lookup":
            return metric_lookup(str(tool_input.get("metric_id", ""))), False
        if name == "nl_to_metric":
            return nl_to_metric(str(tool_input["question"])), False
        if name == "metric_rollup":
            return (
                metric_rollup(
                    str(tool_input["metric_id"]),
                    str(tool_input.get("dimension", "")),
                    str(tool_input.get("value", "")),
                ),
                False,
            )
        if name == "sql_for_metric":
            return (
                sql_for_metric(
                    str(tool_input["metric_id"]),
                    str(tool_input.get("dimension", "")),
                    str(tool_input.get("value", "")),
                ),
                False,
            )
        if name == "mismatch_trace":
            return mismatch_trace(str(tool_input["mismatch_id"])), False
        if name == "consistency_check":
            return (
                consistency_check(
                    str(tool_input["metric_id"]),
                    str(tool_input["proposed_value"]),
                    str(tool_input.get("dimension", "")),
                    str(tool_input.get("value", "")),
                ),
                False,
            )
        return f"unknown tool: {name}", True
    except (ToolError, TypeError, KeyError, ValueError) as exc:
        return f"tool error: {exc}", True
