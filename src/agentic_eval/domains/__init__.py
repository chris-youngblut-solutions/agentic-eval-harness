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
"""
