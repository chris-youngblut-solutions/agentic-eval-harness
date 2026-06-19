"""Domain packs. Each subpackage exports `DOMAIN: agentic_eval.domain.Domain`.

Built-in domains:
- `generic`      — calculator + document corpus + orders CSV (the original golden set).
- `industrial`   — CAN/ISOBUS edge decode + fault/safety diagnostics over a
  synthetic corpus, with public-standard decode ground-truth from opendbc-ag.
- `trust_safety` — content-policy enforcement + diagnostics over a fully synthetic,
  generic policy (methodology-only: abstract MARKER tokens, no real policy or
  harmful content).
- `routing`      — hybrid-dispatch tier selection (edge|local|frontier) over a fully
  synthetic, generic tier table; encodes the documented hard-rules contract of the
  in-workspace hybrid-dispatch router with a must-not-misroute privacy hard gate.
"""
