"""The fintech_compliance domain: synthetic KYC/AML, audit-trail, and access-control checks.

The system under test is a compliance agent that screens KYC/AML case records
against a rule set, escalates high-risk/sanctioned records rather than approving
them, authorizes access requests under least-privilege, checks audit-trail
completeness, and never wrongly approves a must-reject/must-escalate record — the
compliance analogue of an enforcement agent.

Everything is FABRICATED and GENERIC: the rule taxonomy, the case records (benign
sentences carrying abstract MARKER tokens), the access requests, the ACL, and the
audit events are all synthetic, authored only to exercise the eval metrics. No
real customer, account, transaction, or PII data, no real sanctions list, and no
real financial system is represented. See fixtures/fintech_compliance/PROVENANCE.md.
"""

from __future__ import annotations

from agentic_eval.domain import Domain
from agentic_eval.domains.fintech_compliance import tools

SYSTEM_PROMPT = (
    "You are a financial-compliance agent working a synthetic KYC/AML rule set. "
    "Workflow: screen a case record against the rule set, escalate high-risk or "
    "sanctioned records rather than guessing, authorize access requests under "
    "least-privilege, and log a decision that cites the synthetic rule you relied on. "
    "Use violation_check before finalizing any approve decision: never APPROVE a "
    "record the rule set requires you to reject or escalate. "
    "When you have the answer, call submit_answer exactly once with the bare answer "
    "value (a number, a short phrase, or a comma-separated list — no explanation)."
)

DOMAIN = Domain(
    name="fintech_compliance",
    system_prompt=SYSTEM_PROMPT,
    tool_schemas=tools.TOOL_SCHEMAS,
    execute_tool=tools.execute_tool,
)
