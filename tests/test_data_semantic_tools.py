"""Data-semantic domain tools + semantic loader + corpus generator — all keyless and
deterministic. Everything exercised here is synthetic and generic (a fabricated metric
model over a tiny star schema); no real company data model or data."""

from __future__ import annotations

import json

import pytest

from agentic_eval.domains.data_semantic import compute, generate, semantic, tools


def test_model_loads_six_metrics() -> None:
    model = semantic.load_model()
    assert model.metric_ids == (
        "revenue",
        "order_count",
        "active_customers",
        "avg_order_value",
        "completed_revenue",
        "west_orders",
    )
    assert model.by_id("revenue").aggregation == "sum"
    assert model.by_id("active_customers").aggregation == "count_distinct"
    assert model.by_id("completed_revenue").fixed_filter == ("status", "completed")


def test_metric_lookup_lists_all_when_empty() -> None:
    out = json.loads(tools.metric_lookup(""))
    assert len(out["metrics"]) == 6
    assert "revenue" in out["metrics"]


def test_list_metrics_is_a_zero_arg_discovery_tool() -> None:
    # Reachable discovery affordance (the strict schema forbids the empty-id call),
    # so an agent can enumerate metrics without guessing ids.
    content, is_error = tools.execute_tool("list_metrics", {})
    assert not is_error
    out = json.loads(content)
    assert len(out["metrics"]) == 6
    assert "completed_revenue" in out["metrics"]


def test_metric_lookup_returns_definition() -> None:
    out = json.loads(tools.metric_lookup("completed_revenue"))
    assert out["aggregation"] == "sum"
    assert out["measure"] == "amount"
    assert out["fixed_filter"] == {"dimension": "status", "value": "completed"}


def test_metric_lookup_errors_on_unknown_metric() -> None:
    content, is_error = tools.execute_tool("metric_lookup", {"metric_id": "nope"})
    assert is_error and "unknown metric" in content


def test_nl_to_metric_maps_each_question_to_its_gold() -> None:
    questions = semantic.load_nl_questions()
    for qid, q in questions.items():
        got = json.loads(tools.nl_to_metric(q.text))
        assert got["metric"] == q.gold_metric, qid


def test_nl_to_metric_returns_unmapped_when_no_synonym() -> None:
    out = json.loads(tools.nl_to_metric("Tell me an unrelated fact about the weather."))
    assert out["metric"] == "UNMAPPED"


def test_metric_rollup_computes_known_values() -> None:
    assert json.loads(tools.metric_rollup("revenue"))["value"] == 1000.0
    assert json.loads(tools.metric_rollup("order_count"))["value"] == 8.0
    assert json.loads(tools.metric_rollup("active_customers"))["value"] == 4.0
    assert json.loads(tools.metric_rollup("avg_order_value"))["value"] == 125.0
    assert json.loads(tools.metric_rollup("completed_revenue"))["value"] == 600.0
    assert json.loads(tools.metric_rollup("west_orders"))["value"] == 4.0


def test_metric_rollup_honors_extra_filter() -> None:
    assert json.loads(tools.metric_rollup("revenue", "region", "west"))["value"] == 500.0
    assert json.loads(tools.metric_rollup("order_count", "status", "completed"))["value"] == 3.0
    assert json.loads(tools.metric_rollup("active_customers", "region", "west"))["value"] == 3.0


def test_metric_rollup_errors_on_unknown_metric_and_dimension() -> None:
    bad_metric, e1 = tools.execute_tool("metric_rollup", {"metric_id": "nope"})
    assert e1 and "unknown metric" in bad_metric
    bad_dim, e2 = tools.execute_tool(
        "metric_rollup", {"metric_id": "revenue", "dimension": "color", "value": "red"}
    )
    assert e2 and "unknown filter dimension" in bad_dim


def test_sql_for_metric_renders_canonical_sql() -> None:
    assert json.loads(tools.sql_for_metric("revenue"))["sql"] == "SELECT SUM(amount) FROM facts"
    assert (
        json.loads(tools.sql_for_metric("completed_revenue"))["sql"]
        == "SELECT SUM(amount) FROM facts WHERE status = 'completed'"
    )
    assert (
        json.loads(tools.sql_for_metric("active_customers"))["sql"]
        == "SELECT COUNT(DISTINCT customer) FROM facts"
    )
    assert (
        json.loads(tools.sql_for_metric("west_orders", "status", "completed"))["sql"]
        == "SELECT COUNT(*) FROM facts WHERE region = 'west' AND status = 'completed'"
    )


def test_consistency_check_consistent_and_mismatch() -> None:
    # the metric's own value is consistent; a wrong value (the order count) mismatches
    assert tools.consistency_check("revenue", "1000").startswith("CONSISTENT")
    assert tools.consistency_check("revenue", "8").startswith("MISMATCH")
    # a filtered metric answered with the unfiltered total mismatches
    assert tools.consistency_check("completed_revenue", "1000").startswith("MISMATCH")
    assert tools.consistency_check("completed_revenue", "600").startswith("CONSISTENT")


def test_consistency_check_errors_on_non_numeric_and_unknown_metric() -> None:
    bad_value, e1 = tools.execute_tool(
        "consistency_check", {"metric_id": "revenue", "proposed_value": "lots"}
    )
    assert e1 and "not numeric" in bad_value
    bad_metric, e2 = tools.execute_tool(
        "consistency_check", {"metric_id": "nope", "proposed_value": "1"}
    )
    assert e2 and "unknown metric" in bad_metric


def test_mismatch_trace_returns_gold_class() -> None:
    assert json.loads(tools.mismatch_trace("x-01"))["class"] == "wrong_grain"
    assert json.loads(tools.mismatch_trace("x-03"))["class"] == "double_count"
    assert json.loads(tools.mismatch_trace("x-05"))["class"] == "filter_drift"


def test_mismatch_trace_errors_on_unknown_id() -> None:
    with pytest.raises(tools.ToolError):
        tools.mismatch_trace("x-99")


def test_compute_metric_matches_rollup_tool() -> None:
    # the shared compute module is the single source of truth: tool and answer key agree
    model = semantic.load_model()
    facts = semantic.load_facts()
    for mid in model.metric_ids:
        metric = model.by_id(mid)
        direct = compute.compute_metric(facts, metric)
        via_tool = json.loads(tools.metric_rollup(mid))["value"]
        assert direct == via_tool, mid


def test_corpus_generation_is_deterministic_and_matches_committed() -> None:
    jsonl = {
        "facts.jsonl": generate.build_facts(),
        "nl_questions.jsonl": generate.build_nl_questions(),
        "mismatches.jsonl": generate.build_mismatches(),
    }
    for name, rows in jsonl.items():
        committed = [
            json.loads(line) for line in (generate.FIXTURES / name).read_text().splitlines() if line
        ]
        assert rows == committed, f"committed {name} is stale; regenerate"
