"""process_mapping domain tools + gold/source loaders + fragment generator — all
keyless and deterministic. Everything exercised here is synthetic and generic
(fabricated retail/CPG buyer-side process shapes); no real company, process, or
data. The load-bearing property tested here is NO GOLD LEAKAGE: no tool payload
ever carries a gold field (steps / systems / disposition / reason / handoffs)."""

from __future__ import annotations

import json
from typing import Any, cast

import pytest

from agentic_eval.domains.process_mapping import generate, process_map, tools

# The gold fields that must NEVER surface in a tool payload (the agent's work).
FORBIDDEN_KEYS: frozenset[str] = frozenset(
    {"fix_before_automate", "reason", "system", "systems", "handoffs", "steps", "disposition"}
)


def _all_keys(obj: Any) -> set[str]:
    """Recursively collect every dict key in a parsed JSON payload."""
    found: set[str] = set()
    if isinstance(obj, dict):
        for key, value in cast(dict[str, Any], obj).items():
            found.add(str(key))
            found |= _all_keys(value)
    elif isinstance(obj, list):
        for value in cast(list[Any], obj):
            found |= _all_keys(value)
    return found


def test_gold_and_sources_load() -> None:
    gold = process_map.load_gold()
    srcs = process_map.load_sources()
    assert set(gold) == {f"PROC-0{i}" for i in range(1, 9)}
    assert len(srcs) == 32
    assert all(len([s for s in srcs.values() if s.process_id == pid]) == 4 for pid in gold)


def test_list_processes_lists_eight_with_titles() -> None:
    out = json.loads(tools.list_processes())
    procs = out["processes"]
    assert len(procs) == 8
    assert procs[0] == {"process_id": "PROC-01", "title": "Vendor Onboarding"}
    assert [p["process_id"] for p in procs] == sorted(p["process_id"] for p in procs)


def test_get_process_returns_fragment_inventory_only() -> None:
    out = json.loads(tools.get_process("PROC-04"))
    assert out["process_id"] == "PROC-04"
    assert out["title"] == "PO-to-Receipt 3-Way Match"
    kinds = {s["kind"] for s in out["sources"]}
    assert kinds == {"email_thread", "spreadsheet", "portal_clickpath", "tribal_note"}
    # a spreadsheet carries a row count; the prose kinds carry a line count
    for src in out["sources"]:
        assert ("rows" in src) == (src["kind"] == "spreadsheet")
        assert ("lines" in src) == (src["kind"] != "spreadsheet")


def test_get_source_text_and_spreadsheet_shapes() -> None:
    text = json.loads(tools.get_source("SRC-401"))
    assert text["kind"] == "email_thread"
    assert "STEP-44" in text["content"] and "content" in text
    sheet = json.loads(tools.get_source("SRC-402"))
    assert sheet["kind"] == "spreadsheet"
    assert sheet["rows"][0] == ["step_code", "note"]
    assert any("STEP-43" in cell for row in sheet["rows"] for cell in row)


def test_no_tool_payload_leaks_a_gold_field() -> None:
    payloads: list[str] = [tools.list_processes()]
    for pid in process_map.load_gold():
        payloads.append(tools.get_process(pid))
    for sid in process_map.load_sources():
        payloads.append(tools.get_source(sid))
    for payload in payloads:
        leaked = _all_keys(json.loads(payload)) & FORBIDDEN_KEYS
        assert not leaked, f"gold field leaked in tool payload: {leaked}"


def test_tools_are_deterministic() -> None:
    assert tools.get_process("PROC-07") == tools.get_process("PROC-07")
    assert tools.get_source("SRC-704") == tools.get_source("SRC-704")
    assert tools.list_processes() == tools.list_processes()


def test_get_process_errors_on_unknown_id() -> None:
    with pytest.raises(tools.ToolError):
        tools.get_process("PROC-99")
    content, is_error = tools.execute_tool("get_process", {"process_id": "PROC-99"})
    assert is_error and "unknown process_id" in content


def test_get_source_errors_on_unknown_id() -> None:
    with pytest.raises(tools.ToolError):
        tools.get_source("SRC-999")
    content, is_error = tools.execute_tool("get_source", {"source_id": "SRC-999"})
    assert is_error and "unknown source_id" in content


def test_normalize_uom_is_a_pure_converter() -> None:
    # two cases of 24 eaches each -> 48 eaches
    assert (
        json.loads(tools.normalize_uom("2", "case", "each", "each:1,inner:6,case:24"))["quantity"]
        == 48.0
    )
    # eaches up to cases
    assert (
        json.loads(tools.normalize_uom("48", "each", "case", "each:1,case:24"))["quantity"] == 2.0
    )


def test_normalize_uom_ambiguous_on_incomplete_hierarchy() -> None:
    out = json.loads(tools.normalize_uom("2", "pallet", "each", "each:1,case:24"))
    assert out["result"] == "AMBIGUOUS"
    assert "pallet" in out["note"]
    # AMBIGUOUS payload is not a gold leak either
    assert not _all_keys(out) & FORBIDDEN_KEYS


def test_normalize_uom_errors_on_non_numeric_quantity() -> None:
    content, is_error = tools.execute_tool(
        "normalize_uom",
        {"quantity": "lots", "from_level": "case", "to_level": "each", "factors": "each:1,case:24"},
    )
    assert is_error and "not numeric" in content


def test_sources_generation_is_deterministic_and_matches_committed() -> None:
    committed = [
        json.loads(line) for line in process_map.SOURCES_PATH.read_text().splitlines() if line
    ]
    assert generate.build_sources() == committed, "committed sources.jsonl is stale; regenerate"
