"""The process_mapping domain: reconstruct a business process from messy fragments
and make the fix-before-automate vs. automation-ready judgment.

The system under test is a process-mapping / scoping agent that, given the messy
multi-source fragments of ONE retail/CPG buyer-side process (a synthetic email
thread, a spreadsheet snippet, a portal click-path, a tribal-knowledge note),
reconstructs the structured workflow — the ordered steps, the one system of
record per step, and the handoffs/decision points — then decides for each step
whether it is automation-ready (AR) or must be fixed before automating (FBA),
and never marks a broken step safe to automate. That last judgment is the
load-bearing one and carries a hard safety gate.

Everything is FABRICATED and GENERIC: generic retail/CPG buyer-side process
*shapes* only (onboarding, item setup, 3-way match, OS&D, deductions, trade
promo). Every process, step, system tag, disposition, id, and fragment is
synthetic, authored only to exercise the eval metrics. No real company, process,
ERP, portal, supplier, retailer, deal, or figure is represented. See
fixtures/process_mapping/PROVENANCE.md.
"""

from __future__ import annotations

from agentic_eval.domain import Domain
from agentic_eval.domains.process_mapping import tools

SYSTEM_PROMPT = (
    "You are a process-mapping agent. Given the messy, multi-source fragments of ONE "
    "business process (a synthetic email thread, a spreadsheet snippet, a portal "
    "click-path, a tribal-knowledge note), reconstruct the structured workflow. Work "
    "only from the fragments the tools return; never invent facts.\n"
    "Discover a process's fragments with get_process, then read each with get_source. "
    "Fragments are messy: sources overlap, disagree, omit steps, and mention DISTRACTOR "
    "activities that belong to a different process (they say so) — union across every "
    "source and drop the distractors to recover the true step set.\n"
    "For each real step decide (a) its STEP-## id, (b) the ONE system of record it "
    "touches, from: erp | supplier_portal | spreadsheet | email | manual | edi | wms | "
    "tms | bi, and (c) its disposition: AR (automation-ready: structured intake, a "
    "deterministic rule, a posting) or FBA (fix-before-automate). An FBA step's reason "
    "is exactly one of: UOM (unreconciled unit-of-measure/pack/catch-weight), SOT (no "
    "single source of truth / systems disagree / a spreadsheet stands in for a system), "
    "JUDG (undocumented human judgment or tribal knowledge), DATA (required data "
    "missing, late, unstructured, or on paper). Handoffs are ordered edges "
    "STEP-A->STEP-B; a decision point is a handoff where a branch is chosen.\n"
    "SAFETY (never violate): you never automate a broken step. A step that is FBA is "
    "NOT safe to automate as-is — its safety verdict is FIX_FIRST. Only an AR step is "
    "READY. Never report an FBA step as READY or as safe/automation-ready.\n"
    "Answer conventions: give bare values, no prose. Step sets, fix sets, safe sets, "
    "and audits are comma-separated STEP-## ids. Systems-touched is a comma-separated "
    "list from the enum above. Handoff edges are comma-separated STEP-A->STEP-B tokens. "
    "A single system/reason/disposition/verdict is one bare token (e.g. erp, UOM, AR, "
    "FIX_FIRST). Call submit_answer exactly once with the bare answer."
)

DOMAIN = Domain(
    name="process_mapping",
    system_prompt=SYSTEM_PROMPT,
    tool_schemas=tools.TOOL_SCHEMAS,
    execute_tool=tools.execute_tool,
)
