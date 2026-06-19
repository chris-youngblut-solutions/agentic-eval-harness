"""Domain packs. Each subpackage exports `DOMAIN: agentic_eval.domain.Domain`.

Built-in domains:
- `generic`      — calculator + document corpus + orders CSV (the original golden set).
- `industrial`   — CAN/ISOBUS edge decode + fault/safety diagnostics over a
  synthetic corpus, with public-standard decode ground-truth from opendbc-ag.
- `trust_safety` — content-policy enforcement + diagnostics over a fully synthetic,
  generic policy (methodology-only: abstract MARKER tokens, no real policy or
  harmful content).
- `fintech_compliance` — KYC/AML screening, audit-trail completeness, and
  access-control adherence over a fully synthetic, generic compliance rule set
  (methodology-only: abstract MARKER tokens, no real customer/account/PII data,
  no real sanctions list).
"""
