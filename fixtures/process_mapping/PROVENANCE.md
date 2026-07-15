# Process-mapping fixtures — provenance & data posture

This directory is the `process_mapping` domain's entire world: a fully synthetic,
generic catalog of buyer-side retail/CPG process *maps* plus the messy
multi-source fragments a mapper reconstructs them from. It is methodology-only.
It carries no real company, no real process, no real ERP/portal/EDI system, no
real supplier or retailer, no real deal, deduction, or figure, and no internal
tooling.

## What is here

- `processes.jsonl` — the GOLD process maps (hand-authored source of truth /
  answer key). One line per process: the ordered real steps (id, code, label,
  the one system of record it touches, a fix-before-automate flag, and a reason
  code) and the ordered handoff edges (handoff | decision, the system that
  carries the edge, and an optional decision branch). This is the analog of
  data_semantic's `model.json`: it is hand-authored and is NOT regenerated.
- `sources.jsonl` — the messy FRAGMENTS (the tools' only world). Four per
  process — a synthetic email thread, a spreadsheet snippet, a portal
  click-path, and a tribal-knowledge note. They mention `STEP-##` anchors and
  the evidence a mapper reasons from, but never the gold labels. This is the
  analog of `facts.jsonl`: it is generated deterministically from authored
  literals by `src/agentic_eval/domains/process_mapping/generate.py` and is
  byte-for-byte reproducible (a test guards this).

The gold map (`processes.jsonl`) is read only by `compute.py` (the answer key)
and the tests. No tool ever returns a gold field: the fragment tools expose only
the source inventory and the fragment text. Reconstructing the step set,
inferring each step's system of record, judging its disposition, and ordering the
handoff edges are all the agent's work.

## Synthetic and generic by construction

- **No real process.** The eight process *shapes* (vendor onboarding, item/SKU
  setup, replenishment PO, PO-to-receipt 3-way match, invoice approval/AP, OS&D
  receiving exception, deduction/chargeback, trade-promo settlement) are common
  industry knowledge. Every process instance, step, code, label, system tag,
  disposition, reason, id, edge, and fragment is fabricated, authored only to
  exercise the eval metrics. No real company's process map is reproduced.
- **No real systems or data.** The system-of-record tags (`erp`,
  `supplier_portal`, `spreadsheet`, `email`, `manual`, `edi`, `wms`, `tms`,
  `bi`) are generic category labels, not real products. The fragment text is
  fabricated ops filler with `PROC-##` / `STEP-##` / `SRC-##` MARKER tokens. No
  real supplier, retailer, PO, invoice, ASN, deduction, deal, or figure appears.
- **No operator, customer, account, or platform identifiers.** No harmful
  content.

## Values are illustrative

The step decompositions, system assignments, dispositions, and reason codes are
illustrative constructs authored only to exercise the eval metrics (step
extraction, system coverage, fix-before-automate flagging, handoff
identification, and the ready-to-automate safety gate). They are not operational
process definitions, system-of-record mappings, or automation-readiness
judgments for any real system, and must not be relied on as such.

## Safety posture

The pack treats "mark a fix-before-automate (broken) step as automation-ready /
safe to automate" as a correctness leak that must never pass — the
mapping-layer analog of data_semantic's money-safety consistency gate (never
returning a numeric answer that disagrees with the semantic layer). An FBA step's
safety verdict is `FIX_FIRST`; only an AR step is `READY`. The
`ready_to_automate_safety` cases are hard gates: a failure fails the whole run.

## No field-source leakage

This pack was authored from a synthetic, generic construction only. It does not
incorporate any content from a real process map, discovery artifact, or
production system. Any methodology that informs the domain framing — the
mapping/scoping layer that finds what to fix before automating — is referenced
only in its abstract, non-identifying form. No real customer process map, no
quantitative outcome, and no product internal appears anywhere in this pack.
