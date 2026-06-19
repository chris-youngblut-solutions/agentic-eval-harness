"""Tests for the reusable dimension library.

Covers each scorer's contract (including the empty-set edge cases that the set
checker and the dimension library must agree on), the rank-aware ordering
metrics, and one end-to-end demonstration that a domain pack can *compose* the
library over a real recorded run — the point of the library existing.
"""

from __future__ import annotations

import math
from typing import Any

from agentic_eval import dimensions as dim
from agentic_eval.cases import set_f1


def _close(a: float, b: float) -> bool:
    return math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-9)


# --- set retrieval quality -------------------------------------------------


def test_precision_recall_f1_basic() -> None:
    predicted = ["a", "b", "c"]  # b, c relevant; a is a false positive
    relevant = ["b", "c", "d"]  # d missed
    assert _close(dim.precision(predicted, relevant), 2 / 3)
    assert _close(dim.recall(predicted, relevant), 2 / 3)
    assert _close(dim.f1(predicted, relevant), 2 / 3)


def test_empty_set_conventions() -> None:
    # two empties agree (matches cases.set_f1)
    assert dim.f1([], []) == 1.0
    assert dim.precision([], []) == 1.0
    assert dim.recall([], []) == 1.0
    # non-empty vs empty disagree
    assert dim.f1(["a"], []) == 0.0
    assert dim.f1([], ["a"]) == 0.0
    # empty prediction, nothing relevant -> vacuously perfect precision
    assert dim.precision([], ["a"]) == 0.0
    # empty relevant -> perfect recall
    assert dim.recall(["a"], []) == 1.0


def test_dimension_f1_agrees_with_set_checker() -> None:
    # The set checker (cases.set_f1) and the library f1 are the same metric.
    cases = [
        ("a, b, c", "a, b, c"),
        ("a, b, c", "a, b"),
        ("a, b", "a, b, c, d"),
        ("", ""),
        ("a", ""),
    ]
    for expected, answer in cases:
        want = {x.strip().lower() for x in expected.split(",") if x.strip()}
        got = {x.strip().lower() for x in answer.split(",") if x.strip()}
        assert _close(dim.f1(got, want), set_f1(expected, answer))


def test_perfect_and_disjoint() -> None:
    assert dim.f1(["x", "y"], ["y", "x"]) == 1.0
    assert dim.f1(["x"], ["y"]) == 0.0


# --- rank-aware retrieval quality ------------------------------------------


def test_mrr_first_relevant_rank() -> None:
    assert _close(dim.mrr(["a", "b", "c"], ["b"]), 1 / 2)
    assert dim.mrr(["a", "b", "c"], ["a"]) == 1.0
    assert dim.mrr(["a", "b", "c"], ["z"]) == 0.0


def test_average_precision_rewards_early_hits() -> None:
    early = dim.average_precision(["a", "b", "x", "y"], ["a", "b"])
    late = dim.average_precision(["x", "y", "a", "b"], ["a", "b"])
    assert early == 1.0
    assert late < early
    # AP = mean of precision@k at each hit: (1/3 + 2/4) / 2
    assert _close(late, (1 / 3 + 2 / 4) / 2)


def test_ndcg_ordering_and_bounds() -> None:
    ideal = dim.ndcg(["a", "b", "c"], ["a", "b"])
    worse = dim.ndcg(["c", "a", "b"], ["a", "b"])
    assert _close(ideal, 1.0)
    assert 0.0 < worse < 1.0
    # explicit DCG/IDCG for the worse ranking
    dcg = 1 / math.log2(3) + 1 / math.log2(4)
    idcg = 1 / math.log2(2) + 1 / math.log2(3)
    assert _close(worse, dcg / idcg)


def test_rank_metrics_dedupe_and_empty_gold() -> None:
    # duplicate relevant id counts once
    assert _close(dim.average_precision(["a", "a", "b"], ["a", "b"]), (1 / 1 + 2 / 3) / 2)
    # empty relevant set -> 1.0 across rank metrics
    assert dim.average_precision(["a"], []) == 1.0
    assert dim.ndcg(["a"], []) == 1.0
    assert dim.mrr(["a"], []) == 0.0  # no relevant item to find


def test_retrieval_scores_rollup() -> None:
    scores = dim.retrieval_scores(["a", "b", "c"], ["a", "b"])
    assert scores.recall == 1.0
    assert _close(scores.precision, 2 / 3)
    assert scores.mrr == 1.0
    assert _close(scores.ndcg, 1.0)
    assert 0.0 <= scores.average_precision <= 1.0


# --- tool-use correctness --------------------------------------------------


def test_tool_set_metrics() -> None:
    called = ["policy_lookup", "classify_content", "calculator"]
    expected = ["policy_lookup", "classify_content"]
    assert not dim.tool_exact_match(called, expected)  # extra calculator
    assert dim.tool_exact_match(["policy_lookup", "classify_content"], expected)
    assert dim.tool_recall(called, expected) == 1.0
    assert _close(dim.tool_precision(called, expected), 2 / 3)


def test_tool_order_subsequence() -> None:
    called = ["policy_lookup", "fetch", "classify_content", "leakage_check"]
    # expected order preserved even with intervening calls
    assert dim.tool_order_match(called, ["policy_lookup", "classify_content"])
    assert dim.tool_order_match(called, ["policy_lookup", "leakage_check"])
    # wrong order fails
    assert not dim.tool_order_match(called, ["classify_content", "policy_lookup"])
    # empty expected is trivially satisfied
    assert dim.tool_order_match(called, [])
    # a step never called fails
    assert not dim.tool_order_match(called, ["policy_lookup", "missing"])


# --- grounding / citation --------------------------------------------------


def test_citation_grounding_and_coverage() -> None:
    supporting = ["doc-1", "doc-2", "doc-3"]
    # cited a real and a fabricated source
    assert _close(dim.citation_grounding(["doc-1", "doc-99"], supporting), 1 / 2)
    # cited only real sources
    assert dim.citation_grounding(["doc-1", "doc-2"], supporting) == 1.0
    # coverage of the required subset
    assert _close(dim.citation_coverage(["doc-1"], ["doc-1", "doc-2"]), 1 / 2)
    # citing nothing is vacuously grounded but not covering
    assert dim.citation_grounding([], supporting) == 1.0
    assert dim.citation_coverage([], ["doc-1"]) == 0.0


def test_is_grounded_gate() -> None:
    supporting = ["doc-1", "doc-2"]
    # clean + fully covers required
    assert dim.is_grounded(["doc-1", "doc-2"], supporting, required=["doc-1"])
    # a fabricated citation fails the default zero-hallucination bar
    assert not dim.is_grounded(["doc-1", "doc-99"], supporting)
    # loosen grounding bound to tolerate the fabricated cite
    assert dim.is_grounded(["doc-1", "doc-99"], supporting, min_grounding=0.5)
    # missing a required source fails coverage
    assert not dim.is_grounded(["doc-1"], supporting, required=["doc-1", "doc-2"])
    # without a required set, only grounding gates
    assert dim.is_grounded(["doc-1"], supporting)


# --- a domain pack composing the library over a real run -------------------


def test_pack_composes_dimensions_over_a_recorded_run() -> None:
    """End-to-end: drive the trust_safety pack with a scripted backend, then
    score the run with dimension primitives — exactly how a pack would express a
    retrieval/tool-use quality bar on top of the engine."""
    from test_agent_loop import ScriptedBackend, tool_use

    from agentic_eval.agent import run_task
    from agentic_eval.domains.trust_safety import DOMAIN

    # A scripted backend: look up the policy, classify an item, then submit.
    turns: list[list[dict[str, Any]]] = [
        [tool_use("t1", "list_policy_categories", {})],
        [tool_use("t2", "classify_content", {"content_id": "c-01"})],
        [tool_use("t3", "submit_answer", {"answer": "done"})],
    ]

    result = run_task("classify c-01", ScriptedBackend(turns), DOMAIN, max_turns=5)
    assert result.stop_reason == "answered"

    # Compose the library over the run's structured evidence.
    expected_tools = ["list_policy_categories", "classify_content"]
    assert dim.tool_recall(result.tools_called, expected_tools) == 1.0
    assert dim.tool_order_match(result.tools_called, expected_tools)
    assert dim.tool_exact_match(result.tools_called, expected_tools)
