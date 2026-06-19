"""Routing domain tools + policy model + corpus generator — all keyless and
deterministic. Everything exercised here is synthetic and generic (abstract tier
table, benign synthetic task descriptions); no real routing table or task content.

The policy model reimplements the documented hard-rules contract of the
hybrid-dispatch router (local|frontier), extended with a third on-device 'edge'
tier — see fixtures/routing/PROVENANCE.md."""

from __future__ import annotations

import json

import pytest

from agentic_eval.domains.routing import generate, policy, tools


def test_tier_table_loads_three_tiers_cheapest_first() -> None:
    table = policy.load_tiers()
    assert table.tier_ids == ("edge", "local", "frontier")
    # cheapest first: cost is monotonically non-decreasing
    costs = [table.by_id(t).cost for t in table.tier_ids]
    assert costs == sorted(costs)
    # only frontier is a net (off-box) tier
    assert table.by_id("frontier").is_net
    assert not table.by_id("edge").is_net
    assert not table.by_id("local").is_net


def test_tier_lookup_lists_all_when_empty() -> None:
    out = json.loads(tools.tier_lookup(""))
    assert out["tiers"] == ["edge", "local", "frontier"]


def test_list_tiers_is_a_zero_arg_discovery_tool() -> None:
    content, is_error = tools.execute_tool("list_tiers", {})
    assert not is_error
    out = json.loads(content)
    assert out["tiers"] == ["edge", "local", "frontier"]


def test_tier_lookup_returns_spec_for_tier() -> None:
    out = json.loads(tools.tier_lookup("local"))
    assert out["net"] == "none"
    assert "summarize" in out["capabilities"]
    assert out["max_difficulty"] == 0.6


def test_tier_lookup_errors_on_unknown_tier() -> None:
    content, is_error = tools.execute_tool("tier_lookup", {"tier": "cloud9"})
    assert is_error and "unknown tier" in content


# --- the policy model: the answer key, mirroring Router.decide rule order ---


def test_easy_edge_capable_task_routes_edge() -> None:
    table = policy.load_tiers()
    assert policy.decide_tier(table, 0.1, frozenset({"classify"}), False) == "edge"


def test_edge_capability_miss_escalates_to_local() -> None:
    # summarize is not on edge -> escalate to local even though easy
    table = policy.load_tiers()
    assert policy.decide_tier(table, 0.2, frozenset({"summarize"}), False) == "local"


def test_difficulty_over_local_band_escalates_to_frontier() -> None:
    table = policy.load_tiers()
    # locally-capable but difficulty 0.9 > local's 0.6 band -> frontier
    assert policy.decide_tier(table, 0.9, frozenset({"classify"}), False) == "frontier"


def test_frontier_only_capability_routes_frontier() -> None:
    table = policy.load_tiers()
    assert policy.decide_tier(table, 0.2, frozenset({"vision"}), False) == "frontier"


def test_privacy_pins_non_net_even_when_hard() -> None:
    table = policy.load_tiers()
    # privacy + hard summarize: local is capable & non-net -> local, NEVER frontier
    tier = policy.decide_tier(table, 0.95, frozenset({"summarize"}), True)
    assert tier == "local"
    assert not table.by_id(tier).is_net


def test_privacy_pins_edge_when_edge_capable() -> None:
    table = policy.load_tiers()
    assert policy.decide_tier(table, 0.1, frozenset({"classify"}), True) == "edge"


def test_privacy_never_routes_a_capability_miss_to_net() -> None:
    table = policy.load_tiers()
    # privacy + vision (frontier-only): cannot route privately -> surfaced, not leaked
    with pytest.raises(ValueError, match="cannot route privately"):
        policy.decide_tier(table, 0.2, frozenset({"vision"}), True)


def test_decide_tier_rejects_out_of_range_difficulty() -> None:
    table = policy.load_tiers()
    with pytest.raises(ValueError, match=r"difficulty must be in"):
        policy.decide_tier(table, 1.5, frozenset({"chat"}), False)


# --- tools over the labeled corpus ---


def test_route_task_matches_gold_for_every_task() -> None:
    tasks = policy.load_tasks()
    for tid, task in tasks.items():
        out = json.loads(tools.route_task(tid))
        assert out["tier"] == task.gold_tier, tid


def test_task_inputs_returns_routing_inputs() -> None:
    out = json.loads(tools.task_inputs("t-12"))
    assert out["privacy"] is True
    assert out["required_capabilities"] == ["classify"]


def test_route_task_errors_on_unknown_id() -> None:
    content, is_error = tools.execute_tool("route_task", {"task_id": "t-99"})
    assert is_error and "unknown task_id" in content


def test_route_inputs_routes_ad_hoc_task() -> None:
    out = json.loads(tools.route_inputs(0.8, ["summarize"], False))
    assert out["tier"] == "frontier"


def test_route_inputs_privacy_never_net() -> None:
    out = json.loads(tools.route_inputs(0.99, ["summarize"], True))
    assert out["tier"] == "local"


# --- the privacy_gate hard gate (must-not-misroute) ---


def test_privacy_gate_misroute_and_clean() -> None:
    # a privacy-flagged task to a net tier misroutes
    assert tools.privacy_gate("t-14", "frontier").startswith("MISROUTE")
    assert tools.privacy_gate("t-12", "frontier").startswith("MISROUTE")
    # a privacy-flagged task to a non-net tier is clean
    assert tools.privacy_gate("t-14", "local").startswith("CLEAN")
    assert tools.privacy_gate("t-12", "edge").startswith("CLEAN")
    # a NON-private task to frontier is clean (no privacy constraint)
    assert tools.privacy_gate("t-09", "frontier").startswith("CLEAN")


def test_privacy_gate_errors_on_bad_tier_and_id() -> None:
    bad_tier, e1 = tools.execute_tool("privacy_gate", {"task_id": "t-12", "proposed_tier": "moon"})
    assert e1 and "unknown tier" in bad_tier
    bad_id, e2 = tools.execute_tool(
        "privacy_gate", {"task_id": "t-99", "proposed_tier": "frontier"}
    )
    assert e2 and "unknown task_id" in bad_id


def test_every_privacy_task_stays_off_net() -> None:
    # the structural must-not-misroute guarantee over the whole corpus
    tasks = policy.load_tasks()
    table = policy.load_tiers()
    for task in tasks.values():
        if task.privacy:
            assert not table.by_id(task.gold_tier).is_net, task.id


def test_corpus_generation_is_deterministic_and_matches_committed() -> None:
    rows = generate.build_tasks()
    committed = [
        json.loads(line)
        for line in (generate.FIXTURES / "tasks.jsonl").read_text().splitlines()
        if line
    ]
    assert rows == committed, "committed tasks.jsonl is stale; regenerate"
