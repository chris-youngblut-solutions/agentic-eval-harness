from __future__ import annotations

import pytest

from agentic_eval import tools


def test_calculator_basic() -> None:
    assert tools.calculator("17 * 23") == "391"
    assert tools.calculator("(250 - 86) * 3 + 41") == "533"
    assert tools.calculator("-4 + 2**3") == "4"


def test_calculator_rejects_non_arithmetic() -> None:
    with pytest.raises(tools.ToolError):
        tools.calculator("__import__('os').system('true')")
    with pytest.raises(tools.ToolError):
        tools.calculator("open('/etc/passwd')")


def test_file_search_finds_torque() -> None:
    out = tools.file_search("bolt torque")
    assert "hx-300.md" in out and "24 Nm" in out
    assert "hx-500.md" in out and "32 Nm" in out


def test_read_file_blocks_traversal() -> None:
    with pytest.raises(tools.ToolError):
        tools.read_file("../orders.csv")


def test_csv_query_matches_hand_counts() -> None:
    completed = tools.csv_query(
        "count", "order_id", [{"column": "status", "op": "eq", "value": "completed"}]
    )
    assert completed == "19"
    west_avg = tools.csv_query(
        "avg",
        "quantity",
        [
            {"column": "status", "op": "eq", "value": "completed"},
            {"column": "region", "op": "eq", "value": "west"},
        ],
    )
    assert abs(float(west_avg) - 6.7142857) < 1e-4


def test_csv_query_numeric_filter() -> None:
    big = tools.csv_query("count", "order_id", [{"column": "quantity", "op": "ge", "value": "10"}])
    assert big == "4"  # rows 1003, 1008, 1014, 1019


def test_execute_tool_returns_error_flag() -> None:
    content, is_error = tools.execute_tool("calculator", {"expression": "nope nope"})
    assert is_error and "tool error" in content
    content, is_error = tools.execute_tool("no_such_tool", {})
    assert is_error
