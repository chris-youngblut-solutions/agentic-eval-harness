"""Fintech-compliance domain tools + rule loader + corpus generator — all keyless and
deterministic. Everything exercised here is synthetic and generic (abstract MARKER
tokens, benign filler text); no real customer, account, transaction, or PII data, no
real sanctions list, and no real financial system."""

from __future__ import annotations

import json

import pytest

from agentic_eval.domains.fintech_compliance import generate, rules, tools


def test_rules_load_six_rules() -> None:
    rs = rules.load_rules()
    assert rs.rule_ids == (
        "CLEAR",
        "KYC_UNVERIFIED",
        "AML_PATTERN",
        "PEP",
        "SANCTIONS",
        "HIGH_RISK_GEO",
    )
    assert rs.by_id("SANCTIONS").disposition == "escalate"
    assert rs.by_id("SANCTIONS").severity == "high"


def test_rule_lookup_lists_all_when_empty() -> None:
    out = json.loads(tools.rule_lookup(""))
    assert len(out["rules"]) == 6
    assert "SANCTIONS" in out["rules"]


def test_list_rules_is_a_zero_arg_discovery_tool() -> None:
    # Reachable discovery affordance (the strict schema forbids the empty-rule call),
    # so an agent can enumerate rules without guessing names.
    content, is_error = tools.execute_tool("list_rules", {})
    assert not is_error
    out = json.loads(content)
    assert len(out["rules"]) == 6
    assert "SANCTIONS" in out["rules"]


def test_rule_lookup_returns_rule_for_id() -> None:
    out = json.loads(tools.rule_lookup("AML_PATTERN"))
    assert out["disposition"] == "reject"
    assert "MARKER_STRUCTURING" in out["markers"]


def test_rule_lookup_errors_on_unknown_rule() -> None:
    content, is_error = tools.execute_tool("rule_lookup", {"rule": "NOPE"})
    assert is_error and "unknown rule" in content


def test_screen_record_matches_marker_to_disposition() -> None:
    aml = json.loads(tools.screen_record("r-06"))
    assert aml["rule"] == "AML_PATTERN" and aml["disposition"] == "reject"
    sanctions = json.loads(tools.screen_record("r-10"))
    assert sanctions["rule"] == "SANCTIONS" and sanctions["disposition"] == "escalate"
    clear = json.loads(tools.screen_record("r-01"))
    assert clear["rule"] == "CLEAR" and clear["disposition"] == "approve"


def test_screen_record_errors_on_unknown_id() -> None:
    content, is_error = tools.execute_tool("screen_record", {"record_id": "r-99"})
    assert is_error and "unknown record_id" in content


def test_screen_every_record_matches_its_gold_disposition() -> None:
    records = rules.load_records()
    for rid, rec in records.items():
        got = json.loads(tools.screen_record(rid))
        assert got["disposition"] == rec.gold_disposition, rid


def test_violation_check_clean_and_violation() -> None:
    # approving a must-escalate sanctions record is a violation; ditto a must-reject AML record
    assert tools.violation_check("r-10", "approve").startswith("VIOLATION")
    assert tools.violation_check("r-06", "approve").startswith("VIOLATION")
    # the correct disposition is clean; approving a clear record is clean
    assert tools.violation_check("r-10", "escalate").startswith("CLEAN")
    assert tools.violation_check("r-06", "reject").startswith("CLEAN")
    assert tools.violation_check("r-01", "approve").startswith("CLEAN")


def test_violation_check_errors_on_bad_action_and_id() -> None:
    bad_action, e1 = tools.execute_tool(
        "violation_check", {"record_id": "r-01", "proposed_disposition": "nuke"}
    )
    assert e1 and "invalid proposed_disposition" in bad_action
    bad_id, e2 = tools.execute_tool(
        "violation_check", {"record_id": "r-99", "proposed_disposition": "approve"}
    )
    assert e2 and "unknown record_id" in bad_id


def test_access_check_grant_and_deny() -> None:
    assert json.loads(tools.access_check("ac-01"))["verdict"] == "grant"
    assert json.loads(tools.access_check("ac-04"))["verdict"] == "deny"


def test_access_check_every_request_matches_gold_grant() -> None:
    reqs = rules.load_access()
    for rid, req in reqs.items():
        verdict = json.loads(tools.access_check(rid))["verdict"]
        assert (verdict == "grant") == req.gold_grant, rid


def test_access_check_errors_on_unknown_id() -> None:
    with pytest.raises(tools.ToolError):
        tools.access_check("ac-99")


def test_audit_check_complete_and_incomplete() -> None:
    assert json.loads(tools.audit_check("au-01"))["audit_status"] == "complete"
    assert json.loads(tools.audit_check("au-04"))["audit_status"] == "incomplete"


def test_audit_check_errors_on_unknown_id() -> None:
    with pytest.raises(tools.ToolError):
        tools.audit_check("au-99")


def test_corpus_generation_is_deterministic_and_matches_committed() -> None:
    jsonl = {
        "records.jsonl": generate.build_records(),
        "access.jsonl": generate.build_access(),
        "audit.jsonl": generate.build_audit(),
    }
    for name, rows in jsonl.items():
        committed = [
            json.loads(line) for line in (generate.FIXTURES / name).read_text().splitlines() if line
        ]
        assert rows == committed, f"committed {name} is stale; regenerate"
    committed_acl = json.loads((generate.FIXTURES / "acl.json").read_text())
    assert generate.build_acl() == committed_acl, "committed acl.json is stale; regenerate"
