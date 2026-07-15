"""Domain packs. Each subpackage exports `DOMAIN: agentic_eval.domain.Domain`.

Built-in domains:
- `generic`      — calculator + document corpus + orders CSV (the original golden set).
- `industrial`   — CAN/ISOBUS edge decode + fault/safety diagnostics over a
  synthetic corpus, with public-standard decode ground-truth from opendbc-ag.
- `trust_safety` — content-policy enforcement + diagnostics over a fully synthetic,
  generic policy (methodology-only: abstract MARKER tokens, no real policy or
  harmful content).
- `routing`      — frontier/local dispatch tier selection (edge|local|frontier) over a
  fully synthetic, generic tier table; encodes a documented two-lane (local | frontier)
  dispatch contract, extended with a third on-device edge tier, with a must-not-misroute
  privacy hard gate.
- `customer_support` — agent-assist triage/routing (resolution / deflection /
  escalation correctness) over a fully synthetic, generic support action policy
  (methodology-only: abstract MARKER tokens, no real policy, ticket, or customer
  data); hard-gates auto-resolving a must-escalate ticket (unsafe auto-action).
- `fintech_compliance` — KYC/AML screening, audit-trail completeness, and
  access-control adherence over a fully synthetic, generic compliance rule set
  (methodology-only: abstract MARKER tokens, no real customer/account/PII data,
  no real sanctions list).
- `data_semantic` — NL->metric/SQL accuracy + metric-correctness over a fully
  synthetic, generic semantic layer (a metric catalog over a tiny star schema;
  methodology-only, no real data model or data).
- `retail_ops` — buyer-side retail/CPG supply-chain execution (3-way match,
  exception disposition, OTIF/fill-rate, supplier chase, deduction reconciliation,
  audit-trail completeness) over a fully synthetic, generic procurement queue
  (methodology-only: MARKER tokens + <<TOKEN>>-tagged policy, no real retailer/ERP/
  supplier/PO/invoice/PII data); hard-gates auto-executing money-moving or irreversible
  actions (the human-approval gate).
- `approval_audit` — adversarial approval + audit control where the lure arrives in a
  tool result (read_message / read_conflicting_records), not the prompt: the agent must
  treat tool-result text as DATA, still run the gate/audit check, and return the
  policy-correct verdict. Reuses retail_ops's approval_gate / audit_status / policy as
  the answer key (methodology-only: benign MARKER-token lures + synthetic imperatives,
  no real injection or exploit payload); hard-gates auto-executing a gated action under
  an embedded injection.
- `process_mapping` — reconstruct a buyer-side retail/CPG business process from messy,
  multi-source fragments (email thread / spreadsheet / portal click-path / tribal note)
  into ordered steps + system-per-step + handoffs/decision points, and make the
  fix-before-automate (FBA) vs. automation-ready (AR) judgment over a fully synthetic,
  generic process catalog (methodology-only: MARKER tokens PROC-##/STEP-##/SRC-##, gold
  map read only by the answer key and never surfaced by a tool, no real company/process/
  system/deal/data); hard-gates marking a fix-before-automate (broken) step ready/safe to
  automate.
- `browser_ops` — a portal-automation agent whose defining property is IDEMPOTENCY: it
  reads each action's done/pending state with the sanctioned read_action_state /
  read_page_actions oracle and decides proceed/stop/check/retry itself (no verdict-
  returning tool), judges page completion, and picks the correct control + safe confirm
  default over a fully synthetic, generic portal corpus (methodology-only: MARKER tokens
  PAGE-##/PORTAL-#/ACT-## + opaque MARKER_URL tokens, no real portal/URL/DOM/session/
  selector/customer data); hard-gates re-executing an already-done side-effecting control
  (the double-execute guard) and retrying a click that already went through.
"""
