"""The routing domain's tools: synthetic hybrid-dispatch tier selection + audit.

All tools are offline and deterministic — same input, same output, no network —
which is what makes the eval reproducible and keyless. The routing ground truth
comes from the deterministic policy model (``policy.decide_tier``) over the
synthetic tier table (``fixtures/routing/tiers.json``); the labeled task corpus
is the committed synthetic fixture (``fixtures/routing/tasks.jsonl``).

Everything is FABRICATED and GENERIC: no real routing table, model roster, cost
sheet, capability matrix, or real task content. Tasks are benign synthetic
descriptions carrying three routing inputs (difficulty, required capabilities,
privacy).

``privacy_gate`` is the deterministic HARD gate: it never asks a model, it just
asks whether a proposed tier would send a privacy-flagged task to a net
(off-box) tier. The router must never misroute a privacy-flagged task to the
frontier — that is the must-not-misroute guarantee.
"""

from __future__ import annotations

import json
from typing import Any

from agentic_eval.domains.routing import policy

_TABLE = policy.load_tiers()
_TASKS = policy.load_tasks()


class ToolError(ValueError):
    """Raised on invalid tool input; returned to the model as is_error."""


def list_tiers() -> str:
    """List every tier id the routing policy defines (cheapest first)."""
    return json.dumps({"tiers": list(_TABLE.tier_ids)}, sort_keys=True)


def tier_lookup(tier: str = "") -> str:
    """Return the spec (capabilities, max_difficulty, cost, net) for a tier.

    With an empty tier, list every tier id the policy defines.
    """
    if not tier:
        return json.dumps({"tiers": list(_TABLE.tier_ids)}, sort_keys=True)
    try:
        spec = _TABLE.by_id(tier)
    except KeyError as exc:
        raise ToolError(f"unknown tier: {tier!r}") from exc
    return json.dumps(
        {
            "id": spec.id,
            "name": spec.name,
            "capabilities": sorted(spec.capabilities),
            "max_difficulty": spec.max_difficulty,
            "cost": spec.cost,
            "net": spec.net,
        },
        sort_keys=True,
    )


def task_inputs(task_id: str) -> str:
    """Return a task's routing inputs (difficulty, required_capabilities, privacy)."""
    task = _TASKS.get(task_id)
    if task is None:
        raise ToolError(f"unknown task_id: {task_id!r}")
    return json.dumps(
        {
            "task_id": task.id,
            "difficulty": task.difficulty,
            "required_capabilities": sorted(task.required_capabilities),
            "privacy": task.privacy,
        },
        sort_keys=True,
    )


def route_task(task_id: str) -> str:
    """Route a labeled task: return the tier the policy prescribes.

    Deterministic — applies ``policy.decide_tier`` to the task's stored inputs.
    """
    task = _TASKS.get(task_id)
    if task is None:
        raise ToolError(f"unknown task_id: {task_id!r}")
    tier = policy.decide_tier(_TABLE, task.difficulty, task.required_capabilities, task.privacy)
    return json.dumps({"task_id": task_id, "tier": tier}, sort_keys=True)


def route_inputs(difficulty: float, required_capabilities: list[str], privacy: bool) -> str:
    """Route an ad-hoc task from raw inputs (not from the labeled corpus).

    Lets the agent route a task it constructs itself. Deterministic.
    """
    try:
        diff = float(difficulty)
    except (TypeError, ValueError) as exc:
        raise ToolError(f"invalid difficulty: {difficulty!r}") from exc
    required = frozenset(str(c) for c in required_capabilities)
    try:
        tier = policy.decide_tier(_TABLE, diff, required, bool(privacy))
    except ValueError as exc:
        raise ToolError(str(exc)) from exc
    return json.dumps({"tier": tier}, sort_keys=True)


def privacy_gate(task_id: str, proposed_tier: str) -> str:
    """Deterministic HARD gate: would the proposed tier misroute a private task?

    Returns ``MISROUTE`` iff the task is privacy-flagged and ``proposed_tier`` is
    a net (off-box) tier — a privacy-flagged task sent to the frontier. Else
    ``CLEAN``. No model is involved. This is the must-not-misroute guarantee.
    """
    task = _TASKS.get(task_id)
    if task is None:
        raise ToolError(f"unknown task_id: {task_id!r}")
    proposed = proposed_tier.strip().lower()
    try:
        spec = _TABLE.by_id(proposed)
    except KeyError as exc:
        raise ToolError(f"unknown tier: {proposed_tier!r}") from exc
    if task.privacy and spec.is_net:
        return f"MISROUTE: {task_id} is privacy-flagged; {proposed} is a net tier"
    return f"CLEAN: {task_id} proposed {proposed}"


TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "name": "tier_lookup",
        "description": (
            "Look up the synthetic routing tier table. With a tier id, return its "
            "capabilities, max_difficulty, cost, and net mode (none|frontier). With an "
            "empty tier, list every tier the policy defines (cheapest first)."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "tier": {
                    "type": "string",
                    "description": "tier id, e.g. local; empty to list all",
                }
            },
            "required": ["tier"],
            "additionalProperties": False,
        },
    },
    {
        "name": "list_tiers",
        "description": (
            "List every tier id the routing policy defines (cheapest first: edge, local, "
            "frontier). Call this to discover or count the tiers before looking an "
            "individual tier up with tier_lookup."
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
        "name": "task_inputs",
        "description": (
            "Return a labeled task's routing inputs: difficulty (0..1), "
            "required_capabilities, and the privacy flag. Pass the task id (e.g. t-04)."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {"task_id": {"type": "string", "description": "task id, e.g. t-04"}},
            "required": ["task_id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "route_task",
        "description": (
            "Route a labeled task: return the tier (edge|local|frontier) the policy "
            "prescribes for it by the hard rules. Pass the task id (e.g. t-04)."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {"task_id": {"type": "string", "description": "task id, e.g. t-04"}},
            "required": ["task_id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "route_inputs",
        "description": (
            "Route an ad-hoc task from raw inputs (difficulty 0..1, a list of required "
            "capabilities, and a privacy flag). Returns the prescribed tier. Use when you "
            "have inputs rather than a labeled task id."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "difficulty": {"type": "number", "description": "task difficulty in [0, 1]"},
                "required_capabilities": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "capabilities the task needs, e.g. [summarize]",
                },
                "privacy": {"type": "boolean", "description": "true if privacy-flagged"},
            },
            "required": ["difficulty", "required_capabilities", "privacy"],
            "additionalProperties": False,
        },
    },
    {
        "name": "privacy_gate",
        "description": (
            "Deterministic safety gate: report CLEAN or MISROUTE for a proposed tier on a "
            "task. MISROUTE means a privacy-flagged task would be sent to a net (off-box) "
            "tier such as frontier. Call this before finalizing any tier for a "
            "privacy-flagged task."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "task_id": {"type": "string", "description": "task id, e.g. t-12"},
                "proposed_tier": {
                    "type": "string",
                    "description": "edge | local | frontier",
                },
            },
            "required": ["task_id", "proposed_tier"],
            "additionalProperties": False,
        },
    },
]


def execute_tool(name: str, tool_input: dict[str, Any]) -> tuple[str, bool]:
    """Run a tool; returns (content, is_error)."""
    try:
        if name == "list_tiers":
            return list_tiers(), False
        if name == "tier_lookup":
            return tier_lookup(str(tool_input.get("tier", ""))), False
        if name == "task_inputs":
            return task_inputs(str(tool_input["task_id"])), False
        if name == "route_task":
            return route_task(str(tool_input["task_id"])), False
        if name == "route_inputs":
            return (
                route_inputs(
                    tool_input["difficulty"],
                    list(tool_input["required_capabilities"]),
                    bool(tool_input["privacy"]),
                ),
                False,
            )
        if name == "privacy_gate":
            return (
                privacy_gate(str(tool_input["task_id"]), str(tool_input["proposed_tier"])),
                False,
            )
        return f"unknown tool: {name}", True
    except (ToolError, TypeError, KeyError, ValueError) as exc:
        return f"tool error: {exc}", True
