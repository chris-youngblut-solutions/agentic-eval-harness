"""The agent's tools. All four are offline and deterministic: same input,
same output, no network — which is what makes the eval reproducible."""

from __future__ import annotations

import ast
import contextlib
import csv
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

FIXTURES_DIR = Path(__file__).resolve().parents[2] / "fixtures"

TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "name": "calculator",
        "description": (
            "Evaluate an arithmetic expression. Call this for any calculation "
            "instead of computing mentally. Supports + - * / // % ** and parentheses."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {"expression": {"type": "string", "description": "e.g. (17.5 * 4) - 3"}},
            "required": ["expression"],
            "additionalProperties": False,
        },
    },
    {
        "name": "file_search",
        "description": (
            "Search the document corpus for lines matching a pattern (regex or plain "
            "substring, case-insensitive). Call this first when a question concerns "
            "the corpus documents (manuals, notes). Returns file paths with matching lines."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {"pattern": {"type": "string", "description": "regex or substring"}},
            "required": ["pattern"],
            "additionalProperties": False,
        },
    },
    {
        "name": "read_file",
        "description": (
            "Read one document from the corpus by its relative path (as returned by "
            "file_search). Returns the full text."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "relative path, e.g. pumps/hx-300.md"}
            },
            "required": ["path"],
            "additionalProperties": False,
        },
    },
    {
        "name": "csv_query",
        "description": (
            "Aggregate over the orders table (orders.csv: order_id, region, category, "
            "quantity, unit_price, status). Call this for any question about orders. "
            "Applies the filters, then runs the operation over the given column."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": ["count", "sum", "avg", "min", "max"],
                },
                "column": {
                    "type": "string",
                    "description": "column to aggregate (ignored for count)",
                    "enum": ["order_id", "region", "category", "quantity", "unit_price", "status"],
                },
                "filters": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "column": {
                                "type": "string",
                                "enum": [
                                    "order_id",
                                    "region",
                                    "category",
                                    "quantity",
                                    "unit_price",
                                    "status",
                                ],
                            },
                            "op": {"type": "string", "enum": ["eq", "ne", "gt", "lt", "ge", "le"]},
                            "value": {"type": "string"},
                        },
                        "required": ["column", "op", "value"],
                        "additionalProperties": False,
                    },
                },
            },
            "required": ["operation", "column", "filters"],
            "additionalProperties": False,
        },
    },
]

_BIN_OPS: dict[type[ast.operator], Callable[[float, float], float]] = {
    ast.Add: lambda a, b: a + b,
    ast.Sub: lambda a, b: a - b,
    ast.Mult: lambda a, b: a * b,
    ast.Div: lambda a, b: a / b,
    ast.FloorDiv: lambda a, b: a // b,
    ast.Mod: lambda a, b: a % b,
    ast.Pow: lambda a, b: a**b,
}

_CMP_OPS: dict[str, Callable[[Any, Any], bool]] = {
    "eq": lambda a, b: bool(a == b),
    "ne": lambda a, b: bool(a != b),
    "gt": lambda a, b: bool(a > b),
    "lt": lambda a, b: bool(a < b),
    "ge": lambda a, b: bool(a >= b),
    "le": lambda a, b: bool(a <= b),
}


class ToolError(ValueError):
    """Raised on invalid tool input; returned to the model as is_error."""


def _eval_node(node: ast.expr) -> float:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return float(node.value)
    if isinstance(node, ast.BinOp) and type(node.op) in _BIN_OPS:
        return _BIN_OPS[type(node.op)](_eval_node(node.left), _eval_node(node.right))
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        value = _eval_node(node.operand)
        return -value if isinstance(node.op, ast.USub) else value
    raise ToolError(f"unsupported expression element: {ast.dump(node)}")


def calculator(expression: str) -> str:
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        raise ToolError(f"not a valid expression: {exc}") from exc
    result = _eval_node(tree.body)
    return f"{result:.10g}"


def file_search(pattern: str, fixtures_dir: Path = FIXTURES_DIR) -> str:
    corpus = fixtures_dir / "corpus"
    try:
        rx = re.compile(pattern, re.IGNORECASE)
    except re.error:
        rx = re.compile(re.escape(pattern), re.IGNORECASE)
    hits: list[str] = []
    for path in sorted(corpus.rglob("*")):
        if not path.is_file():
            continue
        for n, line in enumerate(path.read_text().splitlines(), 1):
            if rx.search(line):
                hits.append(f"{path.relative_to(corpus)}:{n}: {line.strip()}")
    return "\n".join(hits) if hits else "(no matches)"


def read_file(path: str, fixtures_dir: Path = FIXTURES_DIR) -> str:
    corpus = (fixtures_dir / "corpus").resolve()
    target = (corpus / path).resolve()
    if not target.is_relative_to(corpus):
        raise ToolError("path escapes the corpus")
    if not target.is_file():
        raise ToolError(f"no such file: {path}")
    return target.read_text()


def csv_query(
    operation: str,
    column: str,
    filters: list[dict[str, str]],
    fixtures_dir: Path = FIXTURES_DIR,
) -> str:
    with (fixtures_dir / "orders.csv").open(newline="") as f:
        rows = list(csv.DictReader(f))

    def matches(row: dict[str, str]) -> bool:
        for flt in filters:
            cell = row[flt["column"]]
            wanted: Any = flt["value"]
            cell_value: Any = cell
            with contextlib.suppress(ValueError):
                cell_value, wanted = float(cell), float(wanted)
            if not _CMP_OPS[flt["op"]](cell_value, wanted):
                return False
        return True

    selected = [r for r in rows if matches(r)]
    if operation == "count":
        return str(len(selected))
    if not selected:
        raise ToolError("no rows match the filters")
    values = [float(r[column]) for r in selected]
    result = {
        "sum": sum(values),
        "avg": sum(values) / len(values),
        "min": min(values),
        "max": max(values),
    }[operation]
    return f"{result:.10g}"


def execute_tool(name: str, tool_input: dict[str, Any]) -> tuple[str, bool]:
    """Run a tool; returns (content, is_error)."""
    try:
        if name == "calculator":
            return calculator(**tool_input), False
        if name == "file_search":
            return file_search(**tool_input), False
        if name == "read_file":
            return read_file(**tool_input), False
        if name == "csv_query":
            return csv_query(**tool_input), False
        return f"unknown tool: {name}", True
    except (ToolError, TypeError, KeyError) as exc:
        return f"tool error: {exc}", True
