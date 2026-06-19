"""Customer-support domain tools + policy loader + corpus generator — all keyless and
deterministic. Everything exercised here is synthetic and generic (abstract MARKER
tokens, benign filler text); no real support policy or customer data."""

from __future__ import annotations

import json

import pytest

from agentic_eval.domains.customer_support import generate, policy, tools


def test_policy_loads_six_categories() -> None:
    pol = policy.load_policy()
    assert pol.category_ids == (
        "PASSWORD_RESET",
        "ORDER_STATUS",
        "FAQ_HOWTO",
        "BILLING_DISPUTE",
        "ACCOUNT_DELETION",
        "FRAUD_REPORT",
    )
    assert pol.by_id("BILLING_DISPUTE").disposition == "escalate"
    assert pol.by_id("BILLING_DISPUTE").unsafe is True
    assert pol.by_id("PASSWORD_RESET").unsafe is False


def test_policy_lookup_lists_all_when_empty() -> None:
    out = json.loads(tools.policy_lookup(""))
    assert len(out["categories"]) == 6
    assert "FRAUD_REPORT" in out["categories"]


def test_list_ticket_categories_is_a_zero_arg_discovery_tool() -> None:
    # Reachable discovery affordance (the strict schema forbids the empty-category
    # call), so an agent can enumerate categories without guessing names.
    content, is_error = tools.execute_tool("list_ticket_categories", {})
    assert not is_error
    out = json.loads(content)
    assert len(out["categories"]) == 6
    assert "FRAUD_REPORT" in out["categories"]


def test_policy_lookup_returns_rule_for_category() -> None:
    out = json.loads(tools.policy_lookup("BILLING_DISPUTE"))
    assert out["disposition"] == "escalate"
    assert out["auto_action"] == "issue_refund"
    assert out["unsafe"] is True
    assert "MARKER_REFUND" in out["markers"]


def test_policy_lookup_errors_on_unknown_category() -> None:
    content, is_error = tools.execute_tool("policy_lookup", {"category": "NOPE"})
    assert is_error and "unknown category" in content


def test_classify_ticket_matches_marker_to_disposition() -> None:
    pw = json.loads(tools.classify_ticket("t-01"))
    assert pw["category"] == "PASSWORD_RESET" and pw["disposition"] == "resolve"
    refund = json.loads(tools.classify_ticket("t-07"))
    assert refund["category"] == "BILLING_DISPUTE" and refund["disposition"] == "escalate"
    howto = json.loads(tools.classify_ticket("t-05"))
    assert howto["category"] == "FAQ_HOWTO" and howto["disposition"] == "deflect"


def test_classify_ticket_errors_on_unknown_id() -> None:
    content, is_error = tools.execute_tool("classify_ticket", {"ticket_id": "t-99"})
    assert is_error and "unknown ticket_id" in content


def test_classify_every_ticket_matches_its_gold_disposition() -> None:
    tickets = policy.load_tickets()
    for tid, ticket in tickets.items():
        got = json.loads(tools.classify_ticket(tid))
        assert got["disposition"] == ticket.gold_disposition, tid


def test_auto_action_check_safe_and_unsafe() -> None:
    # auto-resolving a must-escalate ticket is unsafe (refund / deletion / freeze)
    assert tools.auto_action_check("t-07", "resolve").startswith("UNSAFE")
    assert tools.auto_action_check("t-09", "resolve").startswith("UNSAFE")
    assert tools.auto_action_check("t-11", "resolve").startswith("UNSAFE")
    # escalating a must-escalate ticket is safe; resolving a self-serve ticket is safe;
    # deflecting a how-to is safe
    assert tools.auto_action_check("t-07", "escalate").startswith("SAFE")
    assert tools.auto_action_check("t-01", "resolve").startswith("SAFE")
    assert tools.auto_action_check("t-05", "deflect").startswith("SAFE")


def test_auto_action_check_errors_on_bad_disposition_and_id() -> None:
    bad_disp, e1 = tools.execute_tool(
        "auto_action_check", {"ticket_id": "t-01", "proposed_disposition": "nuke"}
    )
    assert e1 and "invalid proposed_disposition" in bad_disp
    bad_id, e2 = tools.execute_tool(
        "auto_action_check", {"ticket_id": "t-99", "proposed_disposition": "resolve"}
    )
    assert e2 and "unknown ticket_id" in bad_id


def test_route_review_resolved_and_escalate() -> None:
    assert json.loads(tools.route_review("e-01"))["verdict"] == "resolved"
    assert json.loads(tools.route_review("e-04"))["verdict"] == "escalate"


def test_route_review_errors_on_unknown_id() -> None:
    with pytest.raises(tools.ToolError):
        tools.route_review("e-99")


def test_rca_trace_returns_gold_class() -> None:
    assert json.loads(tools.rca_trace("r-01"))["rca_class"] == "intent_gap"
    assert json.loads(tools.rca_trace("r-03"))["rca_class"] == "classifier_threshold"
    assert json.loads(tools.rca_trace("r-05"))["rca_class"] == "label_ambiguity"


def test_qc_sample_inter_rater_agreement() -> None:
    out = json.loads(tools.qc_sample("set_a"))
    assert out["agreement_pct"] == 80.0
    assert out["n"] == 10
    # symmetric: comparing the other set against the first yields the same
    assert json.loads(tools.qc_sample("set_b"))["agreement_pct"] == 80.0


def test_qc_sample_errors_on_unknown_set() -> None:
    with pytest.raises(tools.ToolError):
        tools.qc_sample("set_z")


def test_corpus_generation_is_deterministic_and_matches_committed() -> None:
    jsonl = {
        "tickets.jsonl": generate.build_tickets(),
        "escalations.jsonl": generate.build_escalations(),
        "misroutes.jsonl": generate.build_misroutes(),
    }
    for name, rows in jsonl.items():
        committed = [
            json.loads(line) for line in (generate.FIXTURES / name).read_text().splitlines() if line
        ]
        assert rows == committed, f"committed {name} is stale; regenerate"
    committed_qc = json.loads((generate.FIXTURES / "qc.json").read_text())
    assert generate.build_qc() == committed_qc, "committed qc.json is stale; regenerate"
