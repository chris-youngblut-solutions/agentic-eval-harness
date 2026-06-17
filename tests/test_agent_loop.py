"""Loop machinery tests against a scripted backend — every stop condition,
plus the record/replay round trip. No network, no key."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import pytest

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


def test_record_writes_full_transcript_then_replays(tmp_path: Path) -> None:
    backend = ScriptedBackend(
        [
            [
                {"type": "text", "text": "Using the calculator."},
                tool_use("t1", "calculator", {"expression": "17 * 23"}),
            ],
            [tool_use("t2", "submit_answer", {"answer": "391"})],
        ]
    )
    record = tmp_path / "case.jsonl"
    result = run_task("What is 17 * 23?", backend, DOMAIN, record_path=record)
    assert result.answer == "391"

    messages = [json.loads(line) for line in record.read_text().splitlines() if line]
    # the recorded file is the full conversation: task, assistant turn, the tool's
    # result, and the submit — not just the assistant turns.
    assert [m["role"] for m in messages] == ["user", "assistant", "user", "assistant"]
    tool_results = [
        block
        for message in messages
        if message["role"] == "user" and isinstance(message["content"], list)
        for block in message["content"]
        if block.get("type") == "tool_result"
    ]
    assert tool_results[0]["content"] == "391"
    assert tool_results[0]["is_error"] is False

    # and the full transcript replays through the identical loop (replay reads
    # the assistant turns; the tool runs again and reproduces the same result).
    replayed = run_task("What is 17 * 23?", ReplayBackend(record), DOMAIN)
    assert replayed.answer == "391"
    assert replayed.tools_called == ["calculator"]


def test_replay_record_regenerates_full_transcript_from_legacy(tmp_path: Path) -> None:
    # a legacy untagged transcript (assistant turns only) ...
    record = tmp_path / "case.jsonl"
    turns = [
        [tool_use("t1", "calculator", {"expression": "2 + 2"})],
        [tool_use("t2", "submit_answer", {"answer": "4"})],
    ]
    record.write_text("".join(json.dumps({"content": t}) + "\n" for t in turns))

    # ... replay+record over the SAME file upgrades it to the full role-tagged form
    # with the tool's observed output (the keyless-regenerate path the CLI documents).
    run_task("2 + 2?", ReplayBackend(record), DOMAIN, record_path=record)
    messages = [json.loads(line) for line in record.read_text().splitlines() if line]
    assert [m["role"] for m in messages] == ["user", "assistant", "user", "assistant"]
    tool_results = [
        block
        for message in messages
        if isinstance(message["content"], list)
        for block in message["content"]
        if block.get("type") == "tool_result"
    ]
    assert tool_results[0]["content"] == "4"


def test_records_transcript_for_non_answered_run(tmp_path: Path) -> None:
    # recording fires for every stop reason, not only `answered`
    record = tmp_path / "case.jsonl"
    backend = ScriptedBackend(
        [[{"type": "text", "text": "It is 4."}]]
    )  # no tool -> stopped_no_answer
    result = run_task("2 + 2?", backend, DOMAIN, record_path=record)
    assert result.stop_reason == "stopped_no_answer"
    messages = [json.loads(line) for line in record.read_text().splitlines() if line]
    assert [m["role"] for m in messages] == ["user", "assistant"]


def test_replay_record_does_not_clobber_on_short_replay(tmp_path: Path) -> None:
    # one non-submit turn: the loop needs a 2nd turn that isn't recorded, so replay
    # raises. The committed transcript must be left intact, not overwritten partial.
    record = tmp_path / "case.jsonl"
    record.write_text(
        json.dumps({"content": [tool_use("t1", "calculator", {"expression": "2 + 2"})]}) + "\n"
    )
    original = record.read_text()
    with pytest.raises(RuntimeError):
        run_task("2 + 2?", ReplayBackend(record), DOMAIN, record_path=record)
    assert record.read_text() == original
