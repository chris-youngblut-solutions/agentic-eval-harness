"""Domain packs. Each subpackage exports `DOMAIN: agentic_eval.domain.Domain`.

Built-in domains:
- `generic`      — calculator + document corpus + orders CSV (the original golden set).
- `industrial`   — CAN/ISOBUS edge decode + fault/safety diagnostics over a
  synthetic corpus, with public-standard decode ground-truth from opendbc-ag.
- `trust_safety` — content-policy enforcement + diagnostics over a fully synthetic,
  generic policy (methodology-only: abstract MARKER tokens, no real policy or
  harmful content).
- `customer_support` — agent-assist triage/routing (resolution / deflection /
  escalation correctness) over a fully synthetic, generic support action policy
  (methodology-only: abstract MARKER tokens, no real policy, ticket, or customer
  data); hard-gates auto-resolving a must-escalate ticket (unsafe auto-action).
"""
