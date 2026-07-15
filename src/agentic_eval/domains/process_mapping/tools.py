"""The process_mapping domain's tools: messy fragments only, NO gold leakage.

All tools are offline and deterministic — same input, same output, no network —
which is what makes the eval reproducible and keyless. They read ONLY the
fragment world (``sources.jsonl``) plus a benign in-module title map; they never
import or read the gold answer key (``processes.jsonl``). No tool returns
``steps``, ``systems``, dispositions, ``reason`` codes, or ``handoffs`` from the
gold — reconstruction, system inference, disposition judgment, and edge ordering
are the agent's work. A test asserts none of the gold fields ever appear in a
tool payload.

Everything is FABRICATED and GENERIC: no real company, process, system, deal, or
figure. ``normalize_uom`` is a pure pack-math converter over caller-supplied
factors — a calculator, not a gold oracle (it never says a step is UOM-broken).
"""

from __future__ import annotations

import json
from typing import Any

from agentic_eval.domains.process_mapping import process_map

_SOURCES = process_map.load_sources()

# Benign scene-setting titles, authored in the tool layer (NOT gold labels and NOT
# read from processes.jsonl) so the tools stay provably independent of the gold.
PROCESS_TITLES: dict[str, str] = {
    "PROC-01": "Vendor Onboarding",
    "PROC-02": "Item / SKU Setup",
    "PROC-03": "Replenishment PO",
    "PROC-04": "PO-to-Receipt 3-Way Match",
    "PROC-05": "Invoice Approval / AP",
    "PROC-06": "OS&D Receiving Exception",
    "PROC-07": "Deduction / Chargeback",
    "PROC-08": "Trade-Promo Settlement",
}


class ToolError(ValueError):
    """Raised on invalid tool input; returned to the model as is_error."""


def _process_ids() -> list[str]:
    return sorted({s.process_id for s in _SOURCES.values()})


def _sources_for(process_id: str) -> list[process_map.SourceFragment]:
    return sorted(
        (s for s in _SOURCES.values() if s.process_id == process_id),
        key=lambda s: s.source_id,
    )


def _title(process_id: str) -> str:
    return PROCESS_TITLES.get(process_id, process_id)


def list_processes() -> str:
    """List every process in the catalog: its id and a benign title."""
    processes = [{"process_id": pid, "title": _title(pid)} for pid in _process_ids()]
    return json.dumps({"processes": processes}, sort_keys=True)


def get_process(process_id: str) -> str:
    """Return the fragment INVENTORY for a process — the sources to read, with a
    size hint each — but no step count, no systems, no gold flags."""
    process_id = process_id.strip()
    if process_id not in set(_process_ids()):
        raise ToolError(f"unknown process_id: {process_id!r}")
    inventory: list[dict[str, Any]] = []
    for src in _sources_for(process_id):
        entry: dict[str, Any] = {"source_id": src.source_id, "kind": src.kind}
        if src.kind == "spreadsheet":
            entry["rows"] = len(src.rows)
        else:
            entry["lines"] = len(src.content.splitlines())
        inventory.append(entry)
    return json.dumps(
        {"process_id": process_id, "title": _title(process_id), "sources": inventory},
        sort_keys=True,
    )


def get_source(source_id: str) -> str:
    """Return one messy fragment (the agent's real input): free text for the prose
    kinds, or rows for a spreadsheet. Carries STEP-## anchors + evidence, never a
    gold label."""
    source_id = source_id.strip()
    src = _SOURCES.get(source_id)
    if src is None:
        raise ToolError(f"unknown source_id: {source_id!r}")
    if src.kind == "spreadsheet":
        return json.dumps(
            {
                "source_id": src.source_id,
                "process_id": src.process_id,
                "kind": src.kind,
                "rows": [list(row) for row in src.rows],
            },
            sort_keys=True,
        )
    return json.dumps(
        {
            "source_id": src.source_id,
            "process_id": src.process_id,
            "kind": src.kind,
            "content": src.content,
        },
        sort_keys=True,
    )


def _parse_factors(factors: str) -> dict[str, float]:
    """Parse a caller-supplied pack hierarchy like 'each:1,inner:6,case:24'."""
    out: dict[str, float] = {}
    for part in factors.split(","):
        part = part.strip()
        if not part:
            continue
        if ":" not in part:
            raise ToolError(f"malformed factor {part!r}; expected level:number")
        level, _, num = part.partition(":")
        level = level.strip().lower()
        try:
            out[level] = float(num.strip())
        except ValueError as exc:
            raise ToolError(f"factor for {level!r} is not numeric: {num!r}") from exc
    return out


def normalize_uom(quantity: str, from_level: str, to_level: str, factors: str) -> str:
    """Pure pack-math converter over CALLER-supplied factors.

    Converts ``quantity`` from ``from_level`` to ``to_level`` using the caller's
    own hierarchy (e.g. ``each:1,inner:6,case:24,pallet:1200``). Returns the
    converted quantity, or ``AMBIGUOUS`` when the caller's hierarchy is missing a
    level it needs. This operates only on numbers the caller read from a fragment
    — it is a calculator, never a gold oracle.
    """
    try:
        qty = float(str(quantity).strip())
    except ValueError as exc:
        raise ToolError(f"quantity is not numeric: {quantity!r}") from exc
    table = _parse_factors(factors)
    src_level = from_level.strip().lower()
    dst_level = to_level.strip().lower()
    missing = [lvl for lvl in (src_level, dst_level) if lvl not in table]
    if missing:
        return json.dumps(
            {"result": "AMBIGUOUS", "note": f"missing conversion for {missing[0]!r}"},
            sort_keys=True,
        )
    if table[dst_level] == 0:
        return json.dumps(
            {"result": "AMBIGUOUS", "note": f"zero factor for {dst_level!r}"},
            sort_keys=True,
        )
    converted = qty * table[src_level] / table[dst_level]
    return json.dumps({"quantity": round(converted, 4)}, sort_keys=True)


TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "name": "list_processes",
        "description": (
            "List every process in the catalog (process_id + a benign title). Call this "
            "to discover which processes exist before reconstructing one."
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
        "name": "get_process",
        "description": (
            "Return the fragment INVENTORY for one process: the sources to read and a "
            "size hint for each (line/row count). It does NOT return the steps, systems, "
            "dispositions, or handoffs — those are yours to reconstruct from the "
            "fragments. Pass the process_id (e.g. PROC-04)."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "process_id": {"type": "string", "description": "process id, e.g. PROC-04"}
            },
            "required": ["process_id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "get_source",
        "description": (
            "Return one messy fragment: free text for an email_thread / portal_clickpath "
            "/ tribal_note, or rows for a spreadsheet. Fragments carry STEP-## anchors and "
            "the evidence to reason from, and mention DISTRACTOR steps from other flows "
            "(they say so). Pass the source_id (e.g. SRC-402)."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "source_id": {"type": "string", "description": "source id, e.g. SRC-402"}
            },
            "required": ["source_id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "normalize_uom",
        "description": (
            "Pure pack-math calculator: convert a quantity from one pack level to another "
            "using YOUR supplied factors (e.g. factors='each:1,inner:6,case:24,pallet:1200'). "
            "Returns the converted quantity, or AMBIGUOUS when your hierarchy is missing a "
            "level. It is a converter over data you read from a fragment, not an oracle."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "quantity": {"type": "string", "description": "the numeric quantity to convert"},
                "from_level": {"type": "string", "description": "source pack level, e.g. case"},
                "to_level": {"type": "string", "description": "target pack level, e.g. each"},
                "factors": {
                    "type": "string",
                    "description": "pack hierarchy, e.g. each:1,inner:6,case:24,pallet:1200",
                },
            },
            "required": ["quantity", "from_level", "to_level", "factors"],
            "additionalProperties": False,
        },
    },
]


def execute_tool(name: str, tool_input: dict[str, Any]) -> tuple[str, bool]:
    """Run a tool; returns (content, is_error)."""
    try:
        if name == "list_processes":
            return list_processes(), False
        if name == "get_process":
            return get_process(str(tool_input["process_id"])), False
        if name == "get_source":
            return get_source(str(tool_input["source_id"])), False
        if name == "normalize_uom":
            return (
                normalize_uom(
                    str(tool_input["quantity"]),
                    str(tool_input["from_level"]),
                    str(tool_input["to_level"]),
                    str(tool_input["factors"]),
                ),
                False,
            )
        return f"unknown tool: {name}", True
    except (ToolError, TypeError, KeyError, ValueError) as exc:
        return f"tool error: {exc}", True
