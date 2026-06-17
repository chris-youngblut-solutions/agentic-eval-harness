"""The trust_safety domain's tools: synthetic content-enforcement + diagnostics.

All six are offline and deterministic — same input, same output, no network —
which is what makes the eval reproducible and keyless. Classification ground
truth comes from deterministic MARKER-token matching against the synthetic
policy (policy.json); the labeled corpora are the committed synthetic fixtures
under fixtures/trust_safety/.

Everything is FABRICATED and GENERIC: no real platform policy, no real
moderation case, no real harmful content. Content items are benign fabricated
sentences carrying abstract marker tokens.

`leakage_check` is the deterministic HARD gate: it never asks a model, it just
asks whether a proposed action would wrongly ALLOW an item whose gold action is
remove/escalate. An enforcement agent must never wave such an item through.
"""

from __future__ import annotations

import json
from typing import Any

from agentic_eval.domains.trust_safety import policy

_POLICY = policy.load_policy()
_CONTENT = policy.load_content()
_APPEALS = policy.load_appeals()
_MISFIRES = policy.load_misfires()
_QC = policy.load_qc()


class ToolError(ValueError):
    """Raised on invalid tool input; returned to the model as is_error."""


def list_policy_categories() -> str:
    """List every category id the content policy defines."""
    return json.dumps({"categories": list(_POLICY.category_ids)}, sort_keys=True)


def policy_lookup(category: str = "") -> str:
    """Return the rule (action + severity + markers) for a category.

    With an empty category, list every category id the policy defines.
    """
    if not category:
        return json.dumps({"categories": list(_POLICY.category_ids)}, sort_keys=True)
    try:
        cat = _POLICY.by_id(category)
    except KeyError as exc:
        raise ToolError(f"unknown category: {category!r}") from exc
    return json.dumps(
        {
            "id": cat.id,
            "name": cat.name,
            "markers": list(cat.markers),
            "action": cat.action,
            "severity": cat.severity,
        },
        sort_keys=True,
    )


def classify_content(content_id: str) -> str:
    """Classify a content item by deterministic marker matching.

    Returns the matched category id and the policy-prescribed action. Items with
    no marker match are reported as BENIGN/allow (fail-open is not used for
    enforcement decisions — see leakage_check for the hard gate).
    """
    item = _CONTENT.get(content_id)
    if item is None:
        raise ToolError(f"unknown content_id: {content_id!r}")
    cat = _POLICY.match(item.text)
    if cat is None:
        return json.dumps(
            {"content_id": content_id, "category": "BENIGN", "action": "allow"},
            sort_keys=True,
        )
    return json.dumps(
        {"content_id": content_id, "category": cat.id, "action": cat.action},
        sort_keys=True,
    )


def rca_trace(misfire_id: str) -> str:
    """Return the gold root-cause class for a labeled misfire."""
    misfire = _MISFIRES.get(misfire_id)
    if misfire is None:
        raise ToolError(f"unknown misfire_id: {misfire_id!r}")
    return json.dumps(
        {"misfire_id": misfire_id, "rca_class": misfire.gold_rca_class}, sort_keys=True
    )


def appeal_adjudicate(appeal_id: str) -> str:
    """Adjudicate an appeal: 'overturn' (the removal was wrong) or 'uphold'."""
    appeal = _APPEALS.get(appeal_id)
    if appeal is None:
        raise ToolError(f"unknown appeal_id: {appeal_id!r}")
    verdict = "overturn" if appeal.gold_overturn else "uphold"
    return json.dumps(
        {"appeal_id": appeal_id, "verdict": verdict, "content_id": appeal.content_id},
        sort_keys=True,
    )


def leakage_check(content_id: str, proposed_action: str) -> str:
    """Deterministic HARD gate: would the proposed action leak an enforced item?

    Returns ``LEAK`` iff ``proposed_action`` is ``allow`` for an item whose gold
    action is remove/escalate (a must-remove/must-escalate item waved through),
    else ``CLEAN``. No model is involved.
    """
    item = _CONTENT.get(content_id)
    if item is None:
        raise ToolError(f"unknown content_id: {content_id!r}")
    proposed = proposed_action.strip().lower()
    if proposed not in {"allow", "remove", "escalate"}:
        raise ToolError(f"invalid proposed_action: {proposed_action!r}")
    if proposed == "allow" and item.gold_action in policy.ENFORCED_ACTIONS:
        return f"LEAK: {content_id} requires {item.gold_action}, proposed allow"
    return f"CLEAN: {content_id} proposed {proposed}"


def qc_sample(set_name: str) -> str:
    """Inter-rater agreement (%) of a named rater set vs the other, over qc.json.

    Deterministic: raw agreement = fraction of shared items where both raters
    assigned the same label, as a percentage.
    """
    if set_name not in _QC:
        raise ToolError(f"unknown rater set: {set_name!r}")
    names = sorted(_QC)
    other = names[1] if names[0] == set_name else names[0]
    a, b = _QC[set_name], _QC[other]
    shared = sorted(set(a) & set(b))
    if not shared:
        raise ToolError("rater sets share no items")
    agree = sum(1 for k in shared if a[k] == b[k])
    pct = round(100.0 * agree / len(shared), 3)
    return json.dumps(
        {"set": set_name, "compared_to": other, "agreement_pct": pct, "n": len(shared)},
        sort_keys=True,
    )


TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "name": "policy_lookup",
        "description": (
            "Look up the synthetic content policy. With a category id, return its "
            "prescribed action (allow/remove/escalate), severity, and marker tokens. "
            "With an empty category, list every category the policy defines."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "description": "category id, e.g. SPAM; empty to list all",
                }
            },
            "required": ["category"],
            "additionalProperties": False,
        },
    },
    {
        "name": "list_policy_categories",
        "description": (
            "List every category id the content policy defines. Call this to discover "
            "the policy's categories (e.g. to count or enumerate them) before looking "
            "an individual category up with policy_lookup."
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
        "name": "classify_content",
        "description": (
            "Classify a content item by deterministic marker matching against the "
            "policy. Returns the matched category and the prescribed action. Pass the "
            "content id (e.g. c-04)."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "content_id": {"type": "string", "description": "content id, e.g. c-04"}
            },
            "required": ["content_id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "rca_trace",
        "description": (
            "Return the gold root-cause class for a labeled enforcement misfire "
            "(policy_gap, classifier_threshold, or label_ambiguity). Pass the misfire id."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "misfire_id": {"type": "string", "description": "misfire id, e.g. m-01"}
            },
            "required": ["misfire_id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "appeal_adjudicate",
        "description": (
            "Adjudicate an appeal of a prior removal: 'overturn' (the removal was wrong) "
            "or 'uphold' (the removal was correct). Pass the appeal id."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {"appeal_id": {"type": "string", "description": "appeal id, e.g. a-01"}},
            "required": ["appeal_id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "leakage_check",
        "description": (
            "Deterministic safety gate: report CLEAN or LEAK for a proposed action on a "
            "content item. LEAK means the proposed action would ALLOW an item that the "
            "policy requires to be removed or escalated. Call this before finalizing any "
            "allow decision."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "content_id": {"type": "string", "description": "content id, e.g. c-12"},
                "proposed_action": {
                    "type": "string",
                    "description": "allow | remove | escalate",
                },
            },
            "required": ["content_id", "proposed_action"],
            "additionalProperties": False,
        },
    },
    {
        "name": "qc_sample",
        "description": (
            "Return inter-rater agreement as a percentage for a named rater set against "
            "the other, over the shared QC item set. Pass the set name (e.g. set_a)."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "set_name": {"type": "string", "description": "rater set name, e.g. set_a"}
            },
            "required": ["set_name"],
            "additionalProperties": False,
        },
    },
]


def execute_tool(name: str, tool_input: dict[str, Any]) -> tuple[str, bool]:
    """Run a tool; returns (content, is_error)."""
    try:
        if name == "list_policy_categories":
            return list_policy_categories(), False
        if name == "policy_lookup":
            return policy_lookup(str(tool_input.get("category", ""))), False
        if name == "classify_content":
            return classify_content(str(tool_input["content_id"])), False
        if name == "rca_trace":
            return rca_trace(str(tool_input["misfire_id"])), False
        if name == "appeal_adjudicate":
            return appeal_adjudicate(str(tool_input["appeal_id"])), False
        if name == "leakage_check":
            return (
                leakage_check(str(tool_input["content_id"]), str(tool_input["proposed_action"])),
                False,
            )
        if name == "qc_sample":
            return qc_sample(str(tool_input["set_name"])), False
        return f"unknown tool: {name}", True
    except (ToolError, TypeError, KeyError, ValueError) as exc:
        return f"tool error: {exc}", True
