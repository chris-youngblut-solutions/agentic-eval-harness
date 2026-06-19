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
"""
