"""The plan-act-observe loop.

The loop is backend-agnostic: a ModelBackend returns assistant content blocks
(plain dicts in API wire shape). LiveBackend calls the Claude API; ReplayBackend
returns recorded blocks, which lets CI exercise the identical loop with no key
and no network. Tools execute for real in both cases — they are deterministic.

Recording belongs to run_task, not the backend: given a record_path it persists
the full conversation (the user task, every assistant turn, and the user turns
carrying the tools' tool_result outputs) as role-tagged JSONL. Replay reads back
only the assistant turns and re-executes the tools, so the observed outputs are
reproduced rather than trusted — which means `eval --backend replay --record`
regenerates a faithful, fully-observable transcript with no key.

Stop conditions, all explicit:
1. the model calls submit_answer  -> done (the only success path)
2. max_turns model calls consumed -> stopped_max_turns
3. tool-error budget exhausted    -> stopped_tool_errors
4. the model stops calling tools  -> stopped_no_answer (end_turn without submit)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Protocol

from pydantic import BaseModel

from agentic_eval.domain import Domain

SUBMIT_ANSWER_SCHEMA: dict[str, Any] = {
    "name": "submit_answer",
    "description": "Submit the final answer and stop. Call exactly once, when done.",
    "strict": True,
    "input_schema": {
        "type": "object",
        "properties": {
            "answer": {
                "type": "string",
                "description": "The bare answer: a number or short phrase, no explanation.",
            }
        },
        "required": ["answer"],
        "additionalProperties": False,
    },
}

MAX_TOKENS = 4096
DEFAULT_MAX_TURNS = 8
TOOL_ERROR_BUDGET = 3


class AgentResult(BaseModel):
    answer: str | None
    stop_reason: str  # answered | stopped_max_turns | stopped_tool_errors | stopped_no_answer
    turns: int
    tools_called: list[str]
    transcript: list[dict[str, Any]]


class ModelBackend(Protocol):
    def next_assistant_content(
        self, system: str, tool_schemas: list[dict[str, Any]], messages: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Return the next assistant turn's content blocks (API wire dicts)."""
        ...


class LiveBackend:
    """Calls the Claude API and returns the assistant turn. Recording is handled
    by run_task, so any backend (including replay) can produce a transcript."""

    def __init__(self, model: str) -> None:
        import anthropic  # imported here so replay-only environments don't need a key

        self.client = anthropic.Anthropic()
        self.model = model

    def next_assistant_content(
        self, system: str, tool_schemas: list[dict[str, Any]], messages: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        response = self.client.messages.create(
            model=self.model,
            max_tokens=MAX_TOKENS,
            system=system,
            tools=tool_schemas,  # type: ignore[arg-type]
            messages=messages,  # type: ignore[arg-type]
        )
        return [block.to_dict() for block in response.content]


class ReplayBackend:
    """Returns the assistant turns from a recorded transcript, in order. Reads
    assistant turns only — the tool_result (user) turns, when present, are
    recomputed live by the tools on replay. Legacy transcripts whose lines are
    untagged ``{"content": ...}`` are read as assistant turns."""

    def __init__(self, record_path: Path) -> None:
        self.turns: list[list[dict[str, Any]]] = []
        for line in record_path.read_text().splitlines():
            if not line:
                continue
            message = json.loads(line)
            if message.get("role", "assistant") == "assistant":
                self.turns.append(message["content"])
        self.cursor = 0

    def next_assistant_content(
        self, system: str, tool_schemas: list[dict[str, Any]], messages: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        if self.cursor >= len(self.turns):
            raise RuntimeError("replay exhausted: the loop asked for more turns than recorded")
        content = self.turns[self.cursor]
        self.cursor += 1
        return content


def _write_transcript(path: Path, messages: list[dict[str, Any]]) -> None:
    """Persist the conversation as role-tagged JSONL — one message per line: the
    user task, each assistant turn, and the user turns carrying tool_result
    outputs. An answered run ends on the assistant `submit_answer` turn (no
    trailing tool_result). Replay reads the assistant turns; the tool_result
    turns make the recorded run a faithful, fully-observable transcript."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        for message in messages:
            f.write(json.dumps(message, sort_keys=True) + "\n")


def run_task(
    task: str,
    backend: ModelBackend,
    domain: Domain,
    max_turns: int = DEFAULT_MAX_TURNS,
    record_path: Path | None = None,
) -> AgentResult:
    tool_schemas = [*domain.tool_schemas, SUBMIT_ANSWER_SCHEMA]
    messages: list[dict[str, Any]] = [{"role": "user", "content": task}]
    tools_called: list[str] = []
    tool_errors = 0
    result: AgentResult | None = None

    try:
        for turn in range(1, max_turns + 1):
            content = backend.next_assistant_content(domain.system_prompt, tool_schemas, messages)
            messages.append({"role": "assistant", "content": content})
            tool_uses = [b for b in content if b.get("type") == "tool_use"]

            if not tool_uses:
                result = AgentResult(
                    answer=None,
                    stop_reason="stopped_no_answer",
                    turns=turn,
                    tools_called=tools_called,
                    transcript=messages,
                )
                return result

            results: list[dict[str, Any]] = []
            for block in tool_uses:
                name = str(block["name"])
                tool_input = dict(block["input"])
                if name == "submit_answer":
                    result = AgentResult(
                        answer=str(tool_input.get("answer", "")),
                        stop_reason="answered",
                        turns=turn,
                        tools_called=tools_called,
                        transcript=messages,
                    )
                    return result
                tools_called.append(name)
                output, is_error = domain.execute_tool(name, tool_input)
                if is_error:
                    tool_errors += 1
                results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block["id"],
                        "content": output,
                        "is_error": is_error,
                    }
                )
            messages.append({"role": "user", "content": results})

            if tool_errors > TOOL_ERROR_BUDGET:
                result = AgentResult(
                    answer=None,
                    stop_reason="stopped_tool_errors",
                    turns=turn,
                    tools_called=tools_called,
                    transcript=messages,
                )
                return result

        result = AgentResult(
            answer=None,
            stop_reason="stopped_max_turns",
            turns=max_turns,
            tools_called=tools_called,
            transcript=messages,
        )
        return result
    finally:
        # Persist only on a normal exit. If the loop raised (e.g. a replay ran
        # short, or a live API error), `result` is None and we leave any existing
        # transcript untouched rather than overwrite it with a partial one — which
        # matters because `eval --backend replay --record` records over the same
        # file it is replaying.
        if record_path is not None and result is not None:
            _write_transcript(record_path, messages)
