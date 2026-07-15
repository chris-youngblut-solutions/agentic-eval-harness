"""Browser-ops domain tools + policy loader + corpus generator — all keyless and
deterministic. Everything exercised here is synthetic and generic (abstract MARKER
tokens, opaque MARKER_URL tokens, <<TOKEN>>-tagged policy); no real portal, URL, DOM,
session, selector map, or customer data. The pack's spine is the double-execute guard,
so these tests also assert no tool ever hands the agent the proceed/stop/check/retry
verdict, and get_page never leaks action state."""

from __future__ import annotations

import json
from typing import Any, cast

import pytest

from agentic_eval.domains.browser_ops import compute, generate, rules, tools

# Verdict-shaped keys that must NEVER appear in any tool payload — the decision is the
# agent's, and no tool may return it.
FORBIDDEN_VERDICT_KEYS: frozenset[str] = frozenset(
    {
        "verdict",
        "decision",
        "next_action",
        "recommended_action",
        "should_stop",
        "should_proceed",
        "action_to_take",
    }
)


def _all_keys(obj: Any) -> set[str]:
    """Recursively collect every dict key in a parsed JSON payload."""
    keys: set[str] = set()
    if isinstance(obj, dict):
        for key, value in cast(dict[str, Any], obj).items():
            keys.add(str(key))
            keys |= _all_keys(value)
    elif isinstance(obj, list):
        for value in cast(list[Any], obj):
            keys |= _all_keys(value)
    return keys


def test_policy_loads_side_effecting_actions() -> None:
    policy = rules.load_policy()
    assert policy.confirm_safe_default == "cancel"
    assert policy.retry_first_response == "check"
    assert policy.is_side_effecting("approve_invoice")
    assert not policy.is_side_effecting("save_draft")
    # the frozenset constant and the loaded policy never drift
    assert policy.side_effecting_actions == rules.SIDE_EFFECTING_ACTIONS


def test_policy_side_effecting_actions_match_constant() -> None:
    policy = rules.load_policy()
    assert set(policy.raw["side_effecting_actions"]) == set(rules.SIDE_EFFECTING_ACTIONS)


def test_lookup_policy_returns_value() -> None:
    listed = json.loads(tools.lookup_policy("side_effecting_actions"))
    assert "approve_invoice" in listed["value"]
    default = json.loads(tools.lookup_policy("confirm_safe_default"))
    assert default["value"] == "cancel" and default["token"] == "<<CONFIRM_DEFAULT>>"


def test_lookup_policy_errors_on_unknown_and_private_key() -> None:
    _, e1 = tools.execute_tool("lookup_policy", {"key": "nope"})
    assert e1
    _, e2 = tools.execute_tool("lookup_policy", {"key": "_provenance"})
    assert e2


def test_list_portals_groups_pages() -> None:
    out = json.loads(tools.list_portals())
    by_id = {p["portal_id"]: p["pages"] for p in out["portals"]}
    assert by_id["PORTAL-A"] == ["PAGE-01", "PAGE-02"]
    assert set(by_id) == {"PORTAL-A", "PORTAL-B", "PORTAL-C", "PORTAL-D"}


def test_get_page_returns_structure() -> None:
    out = json.loads(tools.get_page("PAGE-01"))
    assert out["primary_control"] == "#send-chase"
    assert out["confirm_default"] == "cancel"
    assert out["actions"] == ["ACT-01"]
    assert out["url_token"] == "MARKER_URL_01"  # opaque token, not a real URL
    save = json.loads(tools.get_page("PAGE-08"))
    assert save["confirm_default"] == "confirm"  # benign save defaults to confirm


def test_get_page_never_leaks_action_state() -> None:
    """get_page is static structure only: it must not reveal done/pending state, the
    side_effecting flag, or a verdict — otherwise it would short-circuit the oracle."""
    for page_id in rules.load_pages():
        keys = _all_keys(json.loads(tools.get_page(page_id)))
        assert "state" not in keys and "status" not in keys
        assert "side_effecting" not in keys
        assert not (keys & FORBIDDEN_VERDICT_KEYS)


def test_read_action_state_reports_state_not_verdict() -> None:
    done = json.loads(tools.read_action_state("ACT-02"))
    assert done["state"] == "done" and done["kind"] == "confirm_receipt"
    assert done["side_effecting"] is True
    pending = json.loads(tools.read_action_state("ACT-01"))
    assert pending["state"] == "pending"
    benign = json.loads(tools.read_action_state("ACT-08"))
    assert benign["state"] == "done" and benign["side_effecting"] is False
    # the oracle reports state, never the decision
    assert not (_all_keys(done) & FORBIDDEN_VERDICT_KEYS)


def test_read_page_actions_batch_reports_all_states() -> None:
    out = json.loads(tools.read_page_actions("PAGE-10"))
    states = {a["action_id"]: a["state"] for a in out["actions"]}
    assert states == {"ACT-10a": "done", "ACT-10b": "done", "ACT-10c": "pending"}
    assert not (_all_keys(out) & FORBIDDEN_VERDICT_KEYS)


def test_no_tool_payload_leaks_a_verdict() -> None:
    payloads: list[str] = [
        tools.list_portals(),
        tools.lookup_policy("side_effecting_actions"),
        tools.lookup_policy("retry_first_response"),
    ]
    for page_id in rules.load_pages():
        payloads.append(tools.get_page(page_id))
        payloads.append(tools.read_page_actions(page_id))
    for action_id in rules.load_actions():
        payloads.append(tools.read_action_state(action_id))
    for payload in payloads:
        leaked = _all_keys(json.loads(payload)) & FORBIDDEN_VERDICT_KEYS
        assert not leaked, f"verdict leaked in tool payload: {leaked}"


def test_is_double_execute_is_side_effecting_aware() -> None:
    policy = rules.load_policy()
    actions = rules.load_actions()
    assert compute.is_double_execute(policy, actions, "ACT-02")  # done + side-effecting
    assert not compute.is_double_execute(policy, actions, "ACT-08")  # done but re-doable
    assert not compute.is_double_execute(policy, actions, "ACT-01")  # pending


def test_compute_completion_count_and_done_ids() -> None:
    actions = rules.load_actions()
    assert compute.page_complete(actions, "PAGE-02") is True
    assert compute.page_complete(actions, "PAGE-10") is False  # ACT-10c pending
    assert compute.page_complete(actions, "PAGE-06") is False
    assert compute.count_done(actions, "PAGE-10") == 2
    assert compute.done_action_ids(actions, "PAGE-10") == ["ACT-10a", "ACT-10b"]


def test_decide_verdicts() -> None:
    assert compute.decide(compute.EXECUTE, "done") == "stop"
    assert compute.decide(compute.EXECUTE, "pending") == "proceed"
    assert compute.decide(compute.RETRY_FIRST, "done") == "check"
    assert compute.decide(compute.RETRY_FIRST, "pending") == "check"
    assert compute.decide(compute.RETRY_RESOLVE, "done") == "stop"
    assert compute.decide(compute.RETRY_RESOLVE, "pending") == "retry"


def test_decide_rejects_bad_mode_and_state() -> None:
    with pytest.raises(ValueError, match="mode"):
        compute.decide("teleport", "done")
    with pytest.raises(ValueError, match="state"):
        compute.decide(compute.EXECUTE, "maybe")


def test_primary_control_and_confirm_default_helpers() -> None:
    pages = rules.load_pages()
    assert compute.primary_control(pages["PAGE-06"]) == "#submit-order"
    assert compute.confirm_default(pages["PAGE-07"]) == "cancel"
    assert compute.portal_pages(pages, "PORTAL-D") == ["PAGE-10", "PAGE-11"]


def test_tools_error_on_unknown_ids() -> None:
    _, e_page = tools.execute_tool("get_page", {"page_id": "PAGE-99"})
    assert e_page
    _, e_action = tools.execute_tool("read_action_state", {"action_id": "ACT-99"})
    assert e_action
    _, e_batch = tools.execute_tool("read_page_actions", {"page_id": "PAGE-99"})
    assert e_batch


def test_tool_execution_is_deterministic() -> None:
    for name, payload in [
        ("read_action_state", {"action_id": "ACT-04"}),
        ("read_page_actions", {"page_id": "PAGE-10"}),
        ("get_page", {"page_id": "PAGE-01"}),
        ("list_portals", {}),
    ]:
        first = tools.execute_tool(name, payload)
        second = tools.execute_tool(name, payload)
        assert first == second and not first[1]


def test_every_tool_payload_is_sorted_json() -> None:
    """Every tool serializes json.dumps(..., sort_keys=True): re-dumping the parsed
    payload with sort_keys must be byte-identical."""
    payloads: list[str] = [tools.list_portals(), tools.get_page("PAGE-10")]
    payloads.append(tools.read_page_actions("PAGE-10"))
    payloads.append(tools.read_action_state("ACT-02"))
    payloads.append(tools.lookup_policy("side_effecting_actions"))
    for payload in payloads:
        assert payload == json.dumps(json.loads(payload), sort_keys=True)


def test_unknown_tool_is_reported_not_raised() -> None:
    content, is_error = tools.execute_tool("nonexistent_tool", {})
    assert is_error and "unknown tool" in content


def test_corpus_generation_is_deterministic_and_matches_committed() -> None:
    jsonl = {
        "portals.jsonl": generate.build_pages(),
        "scenarios.jsonl": generate.build_actions(),
    }
    for name, rows in jsonl.items():
        committed = [
            json.loads(line) for line in (generate.FIXTURES / name).read_text().splitlines() if line
        ]
        assert rows == committed, f"committed {name} is stale; regenerate"
