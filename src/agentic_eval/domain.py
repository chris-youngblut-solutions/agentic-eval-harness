"""The domain seam.

The engine — the agent loop (agent.py), the runner CLI (runner.py), and the
rubric/scorecard (scoring.py) — is domain-agnostic. Everything domain-specific
(the system prompt, the tool surface, the golden set, the fixtures) is bundled
behind one `Domain` and selected by name with `--domain`.

A domain is a package under `agentic_eval.domains.<name>` that exports a module
attribute `DOMAIN: Domain`. Its golden set lives at `eval/<name>/cases.yaml`;
recorded transcripts and scorecards are namespaced under `eval/<name>/` too, so
domains never collide. Adding a domain is additive — no engine edit required.
"""

from __future__ import annotations

import importlib
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# repo root: src/agentic_eval/domain.py -> parents[2]
ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Domain:
    """A domain's entire agent-facing surface.

    - `system_prompt`: tool-usage guidance for this domain's task agent.
    - `tool_schemas`: the tool definitions the agent may call (submit_answer is
      appended by the engine).
    - `execute_tool(name, input) -> (content, is_error)`: runs a tool for real.
      Must be offline and deterministic so the eval is reproducible.
    """

    name: str
    system_prompt: str
    tool_schemas: list[dict[str, Any]]
    execute_tool: Callable[[str, dict[str, Any]], tuple[str, bool]]

    @property
    def cases_path(self) -> Path:
        return ROOT / "eval" / self.name / "cases.yaml"

    @property
    def transcripts_dir(self) -> Path:
        return ROOT / "eval" / self.name / "transcripts"

    @property
    def history_dir(self) -> Path:
        return ROOT / "eval" / self.name / "history"


def load_domain(name: str) -> Domain:
    """Import `agentic_eval.domains.<name>` and return its `DOMAIN`."""
    try:
        module = importlib.import_module(f"agentic_eval.domains.{name}")
    except ModuleNotFoundError as exc:
        raise ValueError(f"unknown domain: {name!r}") from exc
    domain = getattr(module, "DOMAIN", None)
    if not isinstance(domain, Domain):
        raise ValueError(f"domain {name!r} does not export a DOMAIN")
    return domain
