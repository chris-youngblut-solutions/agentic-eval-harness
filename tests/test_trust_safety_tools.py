"""Trust & Safety domain tools + policy loader + corpus generator — all keyless and
deterministic. Everything exercised here is synthetic and generic (abstract MARKER
tokens, benign filler text); no real platform policy or harmful content."""

from __future__ import annotations

import json

import pytest

from agentic_eval.domains.trust_safety import generate, policy, tools


def test_policy_loads_six_categories() -> None:
    pol = policy.load_policy()
    assert pol.category_ids == (
        "BENIGN",
        "SPAM",
        "HARASSMENT",
        "GRAPHIC_VIOLENCE",
        "MISINFO",
        "SELF_HARM",
    )
    assert pol.by_id("SELF_HARM").action == "escalate"
    assert pol.by_id("SELF_HARM").severity == "high"


def test_policy_lookup_lists_all_when_empty() -> None:
    out = json.loads(tools.policy_lookup(""))
    assert len(out["categories"]) == 6
    assert "SELF_HARM" in out["categories"]


def test_policy_lookup_returns_rule_for_category() -> None:
    out = json.loads(tools.policy_lookup("SPAM"))
    assert out["action"] == "remove"
    assert "MARKER_BULK_PROMO" in out["markers"]


def test_policy_lookup_errors_on_unknown_category() -> None:
    content, is_error = tools.execute_tool("policy_lookup", {"category": "NOPE"})
    assert is_error and "unknown category" in content


def test_classify_content_matches_marker_to_action() -> None:
    spam = json.loads(tools.classify_content("c-04"))
    assert spam["category"] == "SPAM" and spam["action"] == "remove"
    crisis = json.loads(tools.classify_content("c-12"))
    assert crisis["category"] == "SELF_HARM" and crisis["action"] == "escalate"
    benign = json.loads(tools.classify_content("c-01"))
    assert benign["category"] == "BENIGN" and benign["action"] == "allow"


def test_classify_content_errors_on_unknown_id() -> None:
    content, is_error = tools.execute_tool("classify_content", {"content_id": "c-99"})
    assert is_error and "unknown content_id" in content


def test_classify_every_item_matches_its_gold_action() -> None:
    items = policy.load_content()
    for cid, item in items.items():
        got = json.loads(tools.classify_content(cid))
        assert got["action"] == item.gold_action, cid


def test_leakage_check_clean_and_leak() -> None:
    # allowing a must-escalate item leaks; allowing a must-remove item leaks
    assert tools.leakage_check("c-12", "allow").startswith("LEAK")
    assert tools.leakage_check("c-08", "allow").startswith("LEAK")
    # the correct enforcement action is clean; allowing a benign item is clean
    assert tools.leakage_check("c-12", "escalate").startswith("CLEAN")
    assert tools.leakage_check("c-08", "remove").startswith("CLEAN")
    assert tools.leakage_check("c-01", "allow").startswith("CLEAN")


def test_leakage_check_errors_on_bad_action_and_id() -> None:
    bad_action, e1 = tools.execute_tool(
        "leakage_check", {"content_id": "c-01", "proposed_action": "nuke"}
    )
    assert e1 and "invalid proposed_action" in bad_action
    bad_id, e2 = tools.execute_tool(
        "leakage_check", {"content_id": "c-99", "proposed_action": "allow"}
    )
    assert e2 and "unknown content_id" in bad_id


def test_appeal_adjudicate_uphold_and_overturn() -> None:
    assert json.loads(tools.appeal_adjudicate("a-01"))["verdict"] == "uphold"
    assert json.loads(tools.appeal_adjudicate("a-04"))["verdict"] == "overturn"


def test_appeal_adjudicate_errors_on_unknown_id() -> None:
    with pytest.raises(tools.ToolError):
        tools.appeal_adjudicate("a-99")


def test_rca_trace_returns_gold_class() -> None:
    assert json.loads(tools.rca_trace("m-01"))["rca_class"] == "policy_gap"
    assert json.loads(tools.rca_trace("m-03"))["rca_class"] == "classifier_threshold"
    assert json.loads(tools.rca_trace("m-05"))["rca_class"] == "label_ambiguity"


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
        "content.jsonl": generate.build_content(),
        "appeals.jsonl": generate.build_appeals(),
        "misfires.jsonl": generate.build_misfires(),
    }
    for name, rows in jsonl.items():
        committed = [
            json.loads(line) for line in (generate.FIXTURES / name).read_text().splitlines() if line
        ]
        assert rows == committed, f"committed {name} is stale; regenerate"
    committed_qc = json.loads((generate.FIXTURES / "qc.json").read_text())
    assert generate.build_qc() == committed_qc, "committed qc.json is stale; regenerate"
