"""The plan-act-observe loop.

The loop is backend-agnostic: a ModelBackend returns assistant content blocks
(plain dicts in API wire shape). LiveBackend calls the Claude API; ReplayBackend
returns recorded blocks, which lets CI exercise the identical loop with no key
and no network. Tools execute for real in both cases — they are deterministic.

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
    """Calls the Claude API. Optionally records each assistant turn to a JSONL
    file so the run can be replayed later without a key."""

    def __init__(self, model: str, record_path: Path | None = None) -> None:
        import anthropic  # imported here so replay-only environments don't need a key

        self.client = anthropic.Anthropic()
        self.model = model
        self.record_path = record_path
        if record_path is not None:
            record_path.parent.mkdir(parents=True, exist_ok=True)
            record_path.write_text("")

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
        content = [block.to_dict() for block in response.content]
        if self.record_path is not None:
            with self.record_path.open("a") as f:
                f.write(json.dumps({"content": content}, sort_keys=True) + "\n")
        return content


class ReplayBackend:
    """Returns assistant turns recorded by LiveBackend, in order."""

    def __init__(self, record_path: Path) -> None:
        self.turns: list[list[dict[str, Any]]] = [
            json.loads(line)["content"] for line in record_path.read_text().splitlines() if line
        ]
        self.cursor = 0

    def next_assistant_content(
        self, system: str, tool_schemas: list[dict[str, Any]], messages: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        if self.cursor >= len(self.turns):
            raise RuntimeError("replay exhausted: the loop asked for more turns than recorded")
        content = self.turns[self.cursor]
        self.cursor += 1
        return content


def run_task(
    task: str,
    backend: ModelBackend,
    domain: Domain,
    max_turns: int = DEFAULT_MAX_TURNS,
) -> AgentResult:
    tool_schemas = [*domain.tool_schemas, SUBMIT_ANSWER_SCHEMA]
    messages: list[dict[str, Any]] = [{"role": "user", "content": task}]
    tools_called: list[str] = []
    tool_errors = 0

    for turn in range(1, max_turns + 1):
        content = backend.next_assistant_content(domain.system_prompt, tool_schemas, messages)
        messages.append({"role": "assistant", "content": content})
        tool_uses = [b for b in content if b.get("type") == "tool_use"]

        if not tool_uses:
            return AgentResult(
                answer=None,
                stop_reason="stopped_no_answer",
                turns=turn,
                tools_called=tools_called,
                transcript=messages,
            )

        results: list[dict[str, Any]] = []
        for block in tool_uses:
            name = str(block["name"])
            tool_input = dict(block["input"])
            if name == "submit_answer":
                return AgentResult(
                    answer=str(tool_input.get("answer", "")),
                    stop_reason="answered",
                    turns=turn,
                    tools_called=tools_called,
                    transcript=messages,
                )
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
            return AgentResult(
                answer=None,
                stop_reason="stopped_tool_errors",
                turns=turn,
                tools_called=tools_called,
                transcript=messages,
            )

    return AgentResult(
        answer=None,
        stop_reason="stopped_max_turns",
        turns=max_turns,
        tools_called=tools_called,
        transcript=messages,
    )
