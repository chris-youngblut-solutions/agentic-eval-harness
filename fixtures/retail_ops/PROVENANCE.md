# Retail-ops fixtures — provenance & data posture

This directory is the `retail_ops` domain's entire world: a fully synthetic, generic
buyer-side retail/CPG procurement queue — purchase orders, advance ship notices,
goods-receipt notes, invoices, exceptions, supplier chases, and retailer deductions.
It is methodology-only. It carries no real supplier, retailer, ERP, customer, or PII
data, and no data from any prior employer.

## What is here

- `policy.json` — **hand-authored** source of truth: illustrative tolerances,
  thresholds, chase ladder, gated-action list, per-SKU pack sizes, and directional
  conventions. Every number is a fabricated placeholder tagged with a `<<TOKEN>>` so a
  reviewer can see at a glance it is invented. Tolerances/thresholds are
  `{token, value, unit}` objects; the tools and `compute.py` read the `.value` field.
- `purchase_orders.jsonl` — the commercial "expected" (PO quantity, price, promised
  date, ship-to).
- `asns.jsonl` — the supplier's declared shipment (PO-8807 intentionally absent → a
  blind receipt; ASN-06 declares 1200 EA = 100 CS → the units-of-measure trap).
- `receipts.jsonl` — the goods-receipt "actual" (short-ship, over-ship, damaged, and
  UOM-mismatch rows).
- `invoices.jsonl` — the "charged" (price variance within/over tolerance, over-billing,
  and PO-8808's duplicate invoice).
- `exceptions.jsonl` — marker-tagged exceptions; each row embeds one abstract `MARKER_*`
  token in benign filler, so the exception type is known by construction, plus the
  prescribed disposition and within-tolerance flag.
- `deductions.jsonl` — retailer chargebacks; validity is **recomputed** from the actual
  delivery record (a deduction is valid iff its cited KPI actually failed on that PO).
- `chase_state.jsonl` — supplier follow-up state; the next ladder step is **recomputed**
  from prior-chase count and reply/fulfilled/discontinued flags.
- `audit_entries.jsonl` — audit records, some complete and some with one blanked required
  field; completeness is **recomputed** against `audit_required_fields`.
- `approval_actions.jsonl` — proposed actions for the approval gate; the SAFE/UNSAFE
  verdict is **recomputed** by the gate logic over `gated_actions` + threshold + the
  referenced exception's disposition.

The JSONL corpora are **generated deterministically** (hand-tabulated, no RNG) by
`src/agentic_eval/domains/retail_ops/generate.py`:

    uv run python -m agentic_eval.domains.retail_ops.generate

They feed the `reconciliation_accuracy`, `exception_disposition_accuracy`,
`otif_metric_accuracy`, `chase_ladder_correctness`, `deduction_recon_accuracy`,
`audit_trail_completeness`, `approval_gate`, and `false_autoclose_rate` metrics. Every
golden-set `expected` is computed from these rows + `policy.json` by `compute.py` and the
deterministic tools — never asserted by hand. Byte-reproducibility is guarded by
`test_corpus_generation_is_deterministic_and_matches_committed`.

## Synthetic and generic by construction

- **No real policy.** The tolerances, thresholds, chase ladder, gated-action list, pack
  sizes, and directional conventions are illustrative constructs authored for this
  evaluation. They reproduce no real retailer's, distributor's, or ERP's configuration.
- **No real supplier / retailer / financial data.** Exceptions are represented by
  abstract `MARKER_*` tokens embedded in benign filler sentences; no row contains real
  supplier, retailer, product, price, or deduction content.
- **No real POs, receipts, invoices, or deductions.** Every record is a fabricated
  example that exercises the eval metrics — not derived from any real order, delivery,
  invoice, chargeback, queue, or system.
- **No supplier, retailer, employee, or institution identifiers.** Ids are structural
  placeholders (`SUP-0##`, `SKU-####`, `PO-88##`, `GRN-##`, `INV-##`, `EX-##`, `DED-##`,
  `CH-##`, `AU-##`, `AP-##`).

## Tolerances, thresholds, and dispositions are illustrative

The tolerance, threshold, chase-ladder, and gated-action values in `policy.json` are
illustrative constructs for exercising the metrics, not operational rules, calibration
values, or authorization grants for any real system, and must not be relied on as such.
The leakage-sensitive rule the pack encodes is generic best practice: **money-moving and
irreversible actions (`GATED_ACTIONS` — pay an invoice, issue a debit/credit note, post
or accept a deduction, amend or cancel a PO, accept an over-ship, authorize a return,
commit a supplier payment, override a scorecard, or write off above threshold) must never
be auto-executed** — they are staged for a human approver. That gate is the pack's whole
reason for being.

Several directional conventions are modeled as `policy.json` parameters precisely
because they are ERP/retailer-specific and vary by customer — the credit-vs-debit-note
direction (`credit_note_direction`), the fill-rate basis (`fill_rate_basis`:
line/unit/case/value), and the OTIF window (`otif_window`: exact-day vs ±window, whether
early counts as a miss). None reflects a specific real customer; verify each against the
target platform/ERP during deployment.

## No field-source leakage

This pack was authored from a synthetic, generic construction only. The domain
*mechanisms* (rate-vs-threshold enforcement, fault/validity attribution, record-vs-reality
reconciliation, exception queues, action ladders, approval gates) and the retail
*vocabulary* (OTIF, three-way match, ASN/GRN, deductions, chase ladder) are standard
retail supply-chain practice. This pack incorporates no content, threshold, window, rate
cutoff, action-volume figure, schema, or system name from any real retailer, distributor,
ERP, or prior employer, and no quantitative outcome from any such real methodology appears
anywhere. Directional conventions (credit-vs-debit-note direction, fill-rate basis, OTIF
window) are modeled as parameters precisely because they vary by customer — none reflects
a specific real customer.
