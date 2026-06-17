"""The trust_safety domain: synthetic content-policy enforcement + diagnostics.

The system under test is a content-enforcement agent that classifies items
against a policy, escalates borderline/high-severity items, adjudicates appeals,
traces enforcement misfires to a root cause, and never wrongly allows a
must-remove/must-escalate item — the enforcement analogue of a retrieval agent.

Everything is FABRICATED and GENERIC: the policy taxonomy, the content items
(benign sentences carrying abstract MARKER tokens), the appeals, the misfires,
and the QC rater sets are all synthetic, authored only to exercise the eval
metrics. No real platform policy, moderation case, tooling, or harmful content
is represented. See fixtures/trust_safety/PROVENANCE.md.
"""

from __future__ import annotations

from agentic_eval.domain import Domain
from agentic_eval.domains.trust_safety import tools

SYSTEM_PROMPT = (
    "You are a content-enforcement agent working a synthetic moderation policy. "
    "Workflow: classify an item against the policy, escalate borderline or "
    "high-severity items rather than guessing, and log a decision that cites the "
    "synthetic policy category you relied on. "
    "Use leakage_check before finalizing any allow decision: never ALLOW an item "
    "the policy requires you to remove or escalate. "
    "When you have the answer, call submit_answer exactly once with the bare answer "
    "value (a number, a short phrase, or a comma-separated list — no explanation)."
)

DOMAIN = Domain(
    name="trust_safety",
    system_prompt=SYSTEM_PROMPT,
    tool_schemas=tools.TOOL_SCHEMAS,
    execute_tool=tools.execute_tool,
)
