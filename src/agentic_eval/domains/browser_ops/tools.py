"""The browser_ops domain's tools: portal discovery, page structure, and the
action-state oracle that powers the idempotency / retry decisions.

All tools are offline and deterministic — same input, same output, no network —
which is what makes the eval reproducible and keyless. Every value is read from the
committed synthetic fixtures (fixtures/browser_ops/) via the shared ``rules`` /
``compute`` modules, so the tool the agent calls and the eval's answer key can never
drift. Reads are confined to the pack's fixtures directory.

Everything is FABRICATED and GENERIC: no real portal, URL, DOM, session, selector
map, or customer data appears anywhere. See fixtures/browser_ops/PROVENANCE.md.

``read_action_state`` (single action) and ``read_page_actions`` (a whole page) are
the SANCTIONED state oracles: they report an action's ``done``/``pending`` state and
its static kind, but never a verdict. ``get_page`` deliberately returns page
structure ONLY — the primary-control selector, the safe confirm default, and the
list of action ids — and NEVER the action state or a "next action" recommendation,
so it cannot hand the agent the idempotency answer. There is intentionally NO
verdict-returning gate tool: the agent must read the state and make the
proceed/stop/check/retry decision itself, which is what the checker grades.
"""

from __future__ import annotations

import json
from typing import Any

from agentic_eval.domains.browser_ops import compute, rules

_POLICY = rules.load_policy()
_PAGES = rules.load_pages()
_ACTIONS = rules.load_actions()


class ToolError(ValueError):
    """Raised on invalid tool input; returned to the model as is_error."""


def lookup_policy(key: str) -> str:
    """Return a configured policy value (side_effecting_actions, confirm_safe_default,
    retry_first_response)."""
    try:
        out = _POLICY.lookup(key)
    except KeyError as exc:
        raise ToolError(f"unknown policy key: {key!r}") from exc
    return json.dumps(out, sort_keys=True)


def list_portals() -> str:
    """List every portal and the ids of the pages it contains — discovery only."""
    portal_ids = sorted({p.portal_id for p in _PAGES.values()})
    portals = [{"portal_id": pid, "pages": compute.portal_pages(_PAGES, pid)} for pid in portal_ids]
    return json.dumps({"portals": portals}, sort_keys=True)


def get_page(page_id: str) -> str:
    """Return a page's STATIC structure only: primary-control selector, safe confirm
    default, and the ids of the actions on it. No action state, no verdict."""
    page = _PAGES.get(page_id)
    if page is None:
        raise ToolError(f"unknown page_id: {page_id!r}")
    action_ids = [a.id for a in compute.actions_for_page(_ACTIONS, page_id)]
    return json.dumps(
        {
            "page_id": page.id,
            "portal_id": page.portal_id,
            "title": page.title,
            "url_token": page.url_token,
            "primary_control": compute.primary_control(page),
            "confirm_default": compute.confirm_default(page),
            "actions": action_ids,
        },
        sort_keys=True,
    )


def read_action_state(action_id: str) -> str:
    """The sanctioned state oracle for ONE action: its done|pending state plus its
    static kind and whether that kind is side-effecting. Never returns a verdict."""
    action = _ACTIONS.get(action_id)
    if action is None:
        raise ToolError(f"unknown action_id: {action_id!r}")
    return json.dumps(
        {
            "action_id": action.id,
            "page_id": action.page_id,
            "kind": action.kind,
            "state": action.state,
            "side_effecting": _POLICY.is_side_effecting(action.kind),
        },
        sort_keys=True,
    )


def read_page_actions(page_id: str) -> str:
    """The sanctioned state oracle for a WHOLE page: every action's done|pending
    state (plus kind + side_effecting). Never returns a verdict, a completion flag,
    or a count — those are the agent's to compute."""
    if page_id not in _PAGES:
        raise ToolError(f"unknown page_id: {page_id!r}")
    actions = [
        {
            "action_id": a.id,
            "kind": a.kind,
            "state": a.state,
            "side_effecting": _POLICY.is_side_effecting(a.kind),
        }
        for a in compute.actions_for_page(_ACTIONS, page_id)
    ]
    return json.dumps({"page_id": page_id, "actions": actions}, sort_keys=True)


TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "name": "list_portals",
        "description": (
            "List every portal and the ids of the pages it contains. Call this to "
            "discover which pages belong to a portal before operating them."
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
        "name": "get_page",
        "description": (
            "Return a page's STATIC structure: its primary-control CSS selector, the safe "
            "default button for a confirm dialog (confirm_default), and the ids of the "
            "actions queued on it. It does NOT return action state or any 'next action' "
            "recommendation — read state with read_action_state / read_page_actions. Pass "
            "the page id, e.g. PAGE-01."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {"page_id": {"type": "string", "description": "page id, e.g. PAGE-01"}},
            "required": ["page_id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "read_action_state",
        "description": (
            "Read one action's current idempotency state: 'done' (its side effect has "
            "already fired — re-executing would repeat it) or 'pending' (not yet executed), "
            "plus the action kind and whether that kind is side-effecting. This is the "
            "oracle for the proceed/stop and retry decisions; it never tells you the "
            "decision itself. Pass the action id, e.g. ACT-02."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "action_id": {"type": "string", "description": "action id, e.g. ACT-02"}
            },
            "required": ["action_id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "read_page_actions",
        "description": (
            "Read the state of every action queued on a page at once: each action's id, "
            "kind, done|pending state, and side_effecting flag. Use this to judge page "
            "completion, count done actions, or list the already-done actions. It returns "
            "raw state only — no completion flag, count, or verdict. Pass the page id, e.g. "
            "PAGE-10."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {"page_id": {"type": "string", "description": "page id, e.g. PAGE-10"}},
            "required": ["page_id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "lookup_policy",
        "description": (
            "Return a configured policy value rather than guessing. Keys: "
            "side_effecting_actions (the money-moving/irreversible action kinds whose "
            "re-execution is a double-execute), confirm_safe_default (the safe default "
            "button for a destructive confirm dialog), retry_first_response (the correct "
            "move on a timed-out first attempt)."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "key": {"type": "string", "description": "policy key, e.g. side_effecting_actions"}
            },
            "required": ["key"],
            "additionalProperties": False,
        },
    },
]


def execute_tool(name: str, tool_input: dict[str, Any]) -> tuple[str, bool]:
    """Run a tool; returns (content, is_error)."""
    try:
        if name == "list_portals":
            return list_portals(), False
        if name == "get_page":
            return get_page(str(tool_input["page_id"])), False
        if name == "read_action_state":
            return read_action_state(str(tool_input["action_id"])), False
        if name == "read_page_actions":
            return read_page_actions(str(tool_input["page_id"])), False
        if name == "lookup_policy":
            return lookup_policy(str(tool_input["key"])), False
        return f"unknown tool: {name}", True
    except (ToolError, TypeError, KeyError, ValueError) as exc:
        return f"tool error: {exc}", True
