"""Loop machinery tests against a scripted backend — every stop condition,
plus the record/replay round trip. No network, no key."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from agentic_eval.agent import ReplayBackend, run_task
from agentic_eval.domains.generic import DOMAIN


class ScriptedBackend:
    """Returns pre-authored assistant turns, recording what it was asked."""

    def __init__(self, turns: list[list[dict[str, Any]]]) -> None:
        self.turns = turns
        self.cursor = 0

    def next_assistant_content(
        self, system: str, tool_schemas: list[dict[str, Any]], messages: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        content = self.turns[self.cursor]
        self.cursor += 1
        return content


def tool_use(block_id: str, name: str, tool_input: dict[str, Any]) -> dict[str, Any]:
    return {"type": "tool_use", "id": block_id, "name": name, "input": tool_input}


def test_answered_via_submit_answer() -> None:
    backend = ScriptedBackend(
        [
            [
                {"type": "text", "text": "Using the calculator."},
                tool_use("t1", "calculator", {"expression": "17 * 23"}),
            ],
            [tool_use("t2", "submit_answer", {"answer": "391"})],
        ]
    )
    result = run_task("What is 17 * 23?", backend, DOMAIN)
    assert result.stop_reason == "answered"
    assert result.answer == "391"
    assert result.tools_called == ["calculator"]
    assert result.turns == 2
    # the real tool executed and its result landed in the transcript
    tool_results: list[dict[str, Any]] = []
    for message in result.transcript:
        content: Any = message["content"]
        if message["role"] == "user" and isinstance(content, list):
            blocks = cast("list[dict[str, Any]]", content)
            tool_results.extend(b for b in blocks if b["type"] == "tool_result")
    assert tool_results[0]["content"] == "391"
    assert tool_results[0]["is_error"] is False


def test_stopped_no_answer_on_plain_text() -> None:
    backend = ScriptedBackend([[{"type": "text", "text": "It is 391."}]])
    result = run_task("What is 17 * 23?", backend, DOMAIN)
    assert result.stop_reason == "stopped_no_answer"
    assert result.answer is None


def test_stopped_max_turns() -> None:
    looping_turn = [tool_use("t", "calculator", {"expression": "1 + 1"})]
    backend = ScriptedBackend([looping_turn] * 3)
    result = run_task("loop forever", backend, DOMAIN, max_turns=3)
    assert result.stop_reason == "stopped_max_turns"
    assert result.turns == 3


def test_stopped_after_tool_error_budget() -> None:
    bad_turn = [tool_use("t", "calculator", {"expression": "not math"})]
    backend = ScriptedBackend([bad_turn] * 8)
    result = run_task("break the calculator", backend, DOMAIN, max_turns=8)
    assert result.stop_reason == "stopped_tool_errors"
    assert result.turns == 4  # budget of 3 errors; the 4th-turn error exceeds it


def test_replay_backend_replays_recorded_turns(tmp_path: Path) -> None:
    turns = [
        [tool_use("t1", "csv_query", {"operation": "count", "column": "order_id", "filters": []})],
        [tool_use("t2", "submit_answer", {"answer": "24"})],
    ]
    record = tmp_path / "case.jsonl"
    record.write_text("".join(json.dumps({"content": t}) + "\n" for t in turns))

    result = run_task("How many orders are there?", ReplayBackend(record), DOMAIN)
    assert result.stop_reason == "answered"
    assert result.answer == "24"
    assert result.tools_called == ["csv_query"]
