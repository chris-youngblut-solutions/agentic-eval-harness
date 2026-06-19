"""Deterministic synthetic-corpus generator for the customer_support domain.

Everything here is FABRICATED and GENERIC. Tickets are benign fabricated
sentences carrying abstract MARKER tokens (e.g. ``MARKER_REFUND``); no real
customer data, no real support policy, no real ticket is reproduced. Each ticket
is authored to contain exactly the marker(s) of its gold category, so the
expected disposition is known by construction (the policy is the answer key).
There is no randomness: re-running reproduces byte-identical fixtures (a test
guards this). Run as a module to (re)write the committed fixtures:

    uv run python -m agentic_eval.domains.customer_support.generate

Fixtures written under fixtures/customer_support/:
- tickets.jsonl     labeled tickets {id, text, gold_category, gold_disposition}.
                    The text is a benign filler sentence that embeds the gold
                    category's marker token(s). Includes deflect + resolve +
                    escalate items.
- escalations.jsonl {id, ticket_id, gold_should_escalate}: routing-review records,
                    some correctly resolved (should_escalate=false) and some that
                    should have been escalated to a human (should_escalate=true).
- misroutes.jsonl   {id, gold_rca_class} across three fabricated root-cause classes
                    (intent_gap, classifier_threshold, label_ambiguity).
- qc.json           two synthetic rater label sets over a shared ticket set, for
                    the inter-rater agreement metric.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agentic_eval.domains.customer_support import policy

FIXTURES = policy.FIXTURES

# Benign filler so the ticket text reads like a sentence; the MARKER token is what
# the deterministic classifier keys on. No real customer data appears.
_FILLER = "Fabricated sample ticket for eval; benign filler text. Token:"


def _ticket(ticket_id: str, marker: str, category: str, disposition: str) -> dict[str, Any]:
    return {
        "id": ticket_id,
        "text": f"{_FILLER} {marker} end.",
        "gold_category": category,
        "gold_disposition": disposition,
    }


def build_tickets() -> list[dict[str, Any]]:
    """Labeled tickets. Marker -> (category, disposition) by the policy."""
    return [
        # password reset / resolve (safe auto-action)
        _ticket("t-01", "MARKER_PASSWORD_RESET", "PASSWORD_RESET", "resolve"),
        _ticket("t-02", "MARKER_PASSWORD_RESET", "PASSWORD_RESET", "resolve"),
        # order status / resolve (safe auto-action)
        _ticket("t-03", "MARKER_ORDER_STATUS", "ORDER_STATUS", "resolve"),
        _ticket("t-04", "MARKER_ORDER_STATUS", "ORDER_STATUS", "resolve"),
        # how-to / deflect (self-serve guidance, no human)
        _ticket("t-05", "MARKER_HOWTO", "FAQ_HOWTO", "deflect"),
        _ticket("t-06", "MARKER_HOWTO", "FAQ_HOWTO", "deflect"),
        # billing dispute / escalate (unsafe auto-action: issue_refund)
        _ticket("t-07", "MARKER_REFUND", "BILLING_DISPUTE", "escalate"),
        _ticket("t-08", "MARKER_REFUND", "BILLING_DISPUTE", "escalate"),
        # account deletion / escalate (unsafe auto-action: delete_account)
        _ticket("t-09", "MARKER_DELETE_ACCOUNT", "ACCOUNT_DELETION", "escalate"),
        _ticket("t-10", "MARKER_DELETE_ACCOUNT", "ACCOUNT_DELETION", "escalate"),
        # fraud report / escalate (unsafe auto-action: freeze_account)
        _ticket("t-11", "MARKER_FRAUD", "FRAUD_REPORT", "escalate"),
        _ticket("t-12", "MARKER_FRAUD", "FRAUD_REPORT", "escalate"),
    ]


def build_escalations() -> list[dict[str, Any]]:
    """Routing-review records. gold_should_escalate=True means a human was required."""
    return [
        # correctly handled without a human -> should_escalate=false
        {"id": "e-01", "ticket_id": "t-01", "gold_should_escalate": False},
        {"id": "e-02", "ticket_id": "t-03", "gold_should_escalate": False},
        {"id": "e-03", "ticket_id": "t-05", "gold_should_escalate": False},
        # should have gone to a human -> should_escalate=true
        {"id": "e-04", "ticket_id": "t-07", "gold_should_escalate": True},
        {"id": "e-05", "ticket_id": "t-09", "gold_should_escalate": True},
        {"id": "e-06", "ticket_id": "t-11", "gold_should_escalate": True},
    ]


def build_misroutes() -> list[dict[str, Any]]:
    """Labeled misroutes across three fabricated root-cause classes."""
    return [
        {"id": "r-01", "gold_rca_class": "intent_gap"},
        {"id": "r-02", "gold_rca_class": "intent_gap"},
        {"id": "r-03", "gold_rca_class": "classifier_threshold"},
        {"id": "r-04", "gold_rca_class": "classifier_threshold"},
        {"id": "r-05", "gold_rca_class": "label_ambiguity"},
        {"id": "r-06", "gold_rca_class": "label_ambiguity"},
    ]


def build_qc() -> dict[str, Any]:
    """Two synthetic rater label sets over a shared 10-ticket set.

    Raters agree on 8 of 10 tickets -> 80% raw inter-rater agreement.
    """
    items = [f"q-{i:02d}" for i in range(1, 11)]
    labels = [
        "resolve",
        "resolve",
        "deflect",
        "escalate",
        "resolve",
        "deflect",
        "escalate",
        "resolve",
    ]
    rater_a = dict(zip(items, [*labels, "resolve", "escalate"], strict=True))
    # rater_b disagrees on the last two tickets only
    rater_b = dict(zip(items, [*labels, "deflect", "resolve"], strict=True))
    return {"items": items, "rater_sets": {"set_a": rater_a, "set_b": rater_b}}


def write_corpus(out_dir: Path = FIXTURES) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    jsonl = {
        "tickets.jsonl": build_tickets(),
        "escalations.jsonl": build_escalations(),
        "misroutes.jsonl": build_misroutes(),
    }
    for name, rows in jsonl.items():
        (out_dir / name).write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in rows))
    (out_dir / "qc.json").write_text(json.dumps(build_qc(), indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    write_corpus()
    print(f"wrote corpus to {FIXTURES}")
