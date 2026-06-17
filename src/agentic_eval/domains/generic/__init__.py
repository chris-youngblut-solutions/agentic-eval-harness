"""The generic domain: arithmetic + a small document corpus + an orders CSV.

This is the original golden set, kept as a domain-agnostic baseline so the engine
always has a reference suite that exercises every tool kind (compute, search,
read, tabular aggregate).
"""

from __future__ import annotations

from agentic_eval.domain import Domain
from agentic_eval.domains.generic import tools

SYSTEM_PROMPT = (
    "You are a task agent. Solve the user's task using the tools provided. "
    "Plan briefly, act with tools, observe results, repeat as needed. "
    "Use the calculator for arithmetic instead of computing mentally. "
    "When you have the answer, call submit_answer exactly once with the bare "
    "answer value (a number or a short phrase, no explanation)."
)

DOMAIN = Domain(
    name="generic",
    system_prompt=SYSTEM_PROMPT,
    tool_schemas=tools.TOOL_SCHEMAS,
    execute_tool=tools.execute_tool,
)
