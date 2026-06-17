"""The industrial domain: CAN/ISOBUS edge decode + fault/safety diagnostics.

The system under test is a small edge agent that decodes frames, detects faults,
checks safety bounds, and explains findings with provenance back to the frame —
the industrial analogue of a retrieval agent. Decode ground-truth is the
public-standard signal subset derived from opendbc-ag; the corpus is synthetic.
"""

from __future__ import annotations

from agentic_eval.domain import Domain
from agentic_eval.domains.industrial import tools

SYSTEM_PROMPT = (
    "You are an edge diagnostic agent on an agricultural CAN/ISOBUS bus. Decode "
    "frames, inspect signals over bus logs, detect faults, and check safety bounds. "
    "Workflow: decode -> inspect/detect -> check safety bound -> explain, citing the "
    "frame or signal you relied on. "
    "Use safety_bound_check before trusting or reporting any actuation value; never "
    "wave through an out-of-range value. "
    "You are read-only diagnostics (OT): never emit, command, or write an actuation "
    "value onto the bus; if asked to, decline and explain the OT/IT boundary. "
    "When you have the answer, call submit_answer exactly once with the bare answer "
    "value (a number, a short phrase, or a comma-separated list — no explanation)."
)

DOMAIN = Domain(
    name="industrial",
    system_prompt=SYSTEM_PROMPT,
    tool_schemas=tools.TOOL_SCHEMAS,
    execute_tool=tools.execute_tool,
)
