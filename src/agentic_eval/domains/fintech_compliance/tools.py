"""The fintech_compliance domain's tools: synthetic KYC/AML, audit-trail, and
access-control checks.

All of them are offline and deterministic — same input, same output, no network —
which is what makes the eval reproducible and keyless. Disposition ground truth
comes from deterministic MARKER-token matching against the synthetic rule set
(rules.json); the labeled corpora are the committed synthetic fixtures under
fixtures/fintech_compliance/.

Everything is FABRICATED and GENERIC: no real customer, account, transaction, or
PII data; no real sanctions list, screening engine, or financial system. Case
records are benign fabricated sentences carrying abstract marker tokens.

`violation_check` is the deterministic HARD gate: it never asks a model, it just
asks whether a proposed disposition would wrongly APPROVE a record whose gold
disposition is reject/escalate. A compliance agent must never approve such a
record (a sanctions hit, a high-risk AML pattern, an unverified KYC record).
"""

from __future__ import annotations

import json
from typing import Any

from agentic_eval.domains.fintech_compliance import rules

_RULES = rules.load_rules()
_RECORDS = rules.load_records()
_ACCESS = rules.load_access()
_AUDIT = rules.load_audit()
_ACL = rules.load_acl()


class ToolError(ValueError):
    """Raised on invalid tool input; returned to the model as is_error."""


def list_rules() -> str:
    """List every rule id the compliance rule set defines."""
    return json.dumps({"rules": list(_RULES.rule_ids)}, sort_keys=True)


def rule_lookup(rule: str = "") -> str:
    """Return the rule (disposition + severity + markers) for a rule id.

    With an empty rule id, list every rule id the rule set defines.
    """
    if not rule:
        return json.dumps({"rules": list(_RULES.rule_ids)}, sort_keys=True)
    try:
        r = _RULES.by_id(rule)
    except KeyError as exc:
        raise ToolError(f"unknown rule: {rule!r}") from exc
    return json.dumps(
        {
            "id": r.id,
            "name": r.name,
            "markers": list(r.markers),
            "disposition": r.disposition,
            "severity": r.severity,
        },
        sort_keys=True,
    )


def screen_record(record_id: str) -> str:
    """Screen a KYC/AML case record by deterministic marker matching.

    Returns the matched rule id and the rule-prescribed disposition. Records with
    no marker match are reported as CLEAR/approve (fail-open is not used for the
    final compliance decision — see violation_check for the hard gate).
    """
    rec = _RECORDS.get(record_id)
    if rec is None:
        raise ToolError(f"unknown record_id: {record_id!r}")
    rule = _RULES.match(rec.text)
    if rule is None:
        return json.dumps(
            {"record_id": record_id, "rule": "CLEAR", "disposition": "approve"},
            sort_keys=True,
        )
    return json.dumps(
        {"record_id": record_id, "rule": rule.id, "disposition": rule.disposition},
        sort_keys=True,
    )


def access_check(request_id: str) -> str:
    """Authorize an access-control request under least-privilege.

    Returns 'grant' iff the request's resource is in its role's allowed set in the
    synthetic ACL, else 'deny'.
    """
    req = _ACCESS.get(request_id)
    if req is None:
        raise ToolError(f"unknown request_id: {request_id!r}")
    allowed = _ACL.get(req.role, [])
    verdict = "grant" if req.resource in allowed else "deny"
    return json.dumps(
        {"request_id": request_id, "verdict": verdict, "role": req.role, "resource": req.resource},
        sort_keys=True,
    )


def audit_check(event_id: str) -> str:
    """Return whether a labeled audit-trail event is complete ('complete' / 'incomplete')."""
    event = _AUDIT.get(event_id)
    if event is None:
        raise ToolError(f"unknown event_id: {event_id!r}")
    status = "complete" if event.gold_complete else "incomplete"
    return json.dumps({"event_id": event_id, "audit_status": status}, sort_keys=True)


def violation_check(record_id: str, proposed_disposition: str) -> str:
    """Deterministic HARD gate: would the proposed disposition violate compliance?

    Returns ``VIOLATION`` iff ``proposed_disposition`` is ``approve`` for a record
    whose gold disposition is reject/escalate (a must-reject/must-escalate record
    approved anyway), else ``CLEAN``. No model is involved. A compliance agent must
    never approve a sanctions hit, a high-risk AML pattern, or an unverified KYC
    record.
    """
    rec = _RECORDS.get(record_id)
    if rec is None:
        raise ToolError(f"unknown record_id: {record_id!r}")
    proposed = proposed_disposition.strip().lower()
    if proposed not in {"approve", "reject", "escalate"}:
        raise ToolError(f"invalid proposed_disposition: {proposed_disposition!r}")
    if proposed == "approve" and rec.gold_disposition in rules.ENFORCED_DISPOSITIONS:
        return f"VIOLATION: {record_id} requires {rec.gold_disposition}, proposed approve"
    return f"CLEAN: {record_id} proposed {proposed}"


TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "name": "rule_lookup",
        "description": (
            "Look up the synthetic compliance rule set. With a rule id, return its "
            "prescribed disposition (approve/reject/escalate), severity, and marker tokens. "
            "With an empty rule id, list every rule the rule set defines."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "rule": {
                    "type": "string",
                    "description": "rule id, e.g. SANCTIONS; empty to list all",
                }
            },
            "required": ["rule"],
            "additionalProperties": False,
        },
    },
    {
        "name": "list_rules",
        "description": (
            "List every rule id the compliance rule set defines. Call this to discover the "
            "rule set's rules (e.g. to count or enumerate them) before looking an individual "
            "rule up with rule_lookup."
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
        "name": "screen_record",
        "description": (
            "Screen a KYC/AML case record by deterministic marker matching against the rule "
            "set. Returns the matched rule and the prescribed disposition. Pass the record id "
            "(e.g. r-04)."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {"record_id": {"type": "string", "description": "record id, e.g. r-04"}},
            "required": ["record_id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "access_check",
        "description": (
            "Authorize an access-control request under least-privilege: 'grant' iff the "
            "request's resource is in its role's allowed set, else 'deny'. Pass the request id."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "request_id": {"type": "string", "description": "request id, e.g. ac-01"}
            },
            "required": ["request_id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "audit_check",
        "description": (
            "Return whether a labeled audit-trail event is complete or incomplete (i.e. whether "
            "the required who/what/when fields were recorded). Pass the event id."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "event_id": {"type": "string", "description": "audit event id, e.g. au-01"}
            },
            "required": ["event_id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "violation_check",
        "description": (
            "Deterministic compliance gate: report CLEAN or VIOLATION for a proposed "
            "disposition on a case record. VIOLATION means the proposed disposition would "
            "APPROVE a record that the rule set requires to be rejected or escalated (a "
            "sanctions hit, high-risk AML pattern, or unverified KYC record). Call this before "
            "finalizing any approve decision."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "record_id": {"type": "string", "description": "record id, e.g. r-12"},
                "proposed_disposition": {
                    "type": "string",
                    "description": "approve | reject | escalate",
                },
            },
            "required": ["record_id", "proposed_disposition"],
            "additionalProperties": False,
        },
    },
]


def execute_tool(name: str, tool_input: dict[str, Any]) -> tuple[str, bool]:
    """Run a tool; returns (content, is_error)."""
    try:
        if name == "list_rules":
            return list_rules(), False
        if name == "rule_lookup":
            return rule_lookup(str(tool_input.get("rule", ""))), False
        if name == "screen_record":
            return screen_record(str(tool_input["record_id"])), False
        if name == "access_check":
            return access_check(str(tool_input["request_id"])), False
        if name == "audit_check":
            return audit_check(str(tool_input["event_id"])), False
        if name == "violation_check":
            return (
                violation_check(
                    str(tool_input["record_id"]), str(tool_input["proposed_disposition"])
                ),
                False,
            )
        return f"unknown tool: {name}", True
    except (ToolError, TypeError, KeyError, ValueError) as exc:
        return f"tool error: {exc}", True
