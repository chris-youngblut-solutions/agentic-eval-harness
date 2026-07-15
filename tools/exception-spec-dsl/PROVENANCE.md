# exception-spec DSL — provenance & data posture

This tool and the spec it ships are **fully synthetic and generic**, matching the posture
of `fixtures/retail_ops/` (see `fixtures/retail_ops/PROVENANCE.md`). It carries no real
supplier, retailer, ERP, customer, employer, or PII data.

## What is here

- `exception-spec.inkspec.html` — the single-file authoring board. No build step, no
  network, no external assets (no CDN, no remote fonts, no fetch/XHR/WebSocket). All state
  is local (`localStorage`). Export is copy-to-clipboard or a `data:` URI download.
- `README.md` — how to open it, the round-trip contract, and the export mapping.
- `PROVENANCE.md` — this file.

## The bundled sample is synthetic

The spec the board loads on first open is `fixtures/retail_ops/policy.json` reverse-
engineered into the DSL, plus the richer gap-analysis layer (rule table, exception guards,
fallbacks, per-customer override scaffold). Every number is a fabricated placeholder tagged
with a `<<TOKEN>>` so a reviewer can see at a glance it is invented. The tolerances,
thresholds, chase ladder, gated-action list, pack sizes, and directional conventions are
illustrative constructs authored for this evaluation domain — they reproduce no real
retailer's, distributor's, or ERP's configuration, and must not be relied on as
operational rules, calibration values, or authorization grants for any real system.

The exception evidence the secondary export emits is abstract `MARKER_*` tokens in benign
filler sentences — no row contains real supplier, retailer, product, price, or deduction
content. Ids are structural placeholders (`SKU-####`, `PO-88##`, `EX-##`, `AP-##`).

## Directional conventions are parameters on purpose

Several conventions are modeled as editable spec fields precisely because they are
ERP/retailer-specific and vary by customer — the credit-vs-debit-note direction, the
fill-rate basis (line/unit/case/value), and the OTIF window (exact-day vs ±window, whether
early counts as a miss). None reflects a specific real customer; each is meant to be
verified against the target platform/ERP during a real deployment.

## No field-source leakage

The tool encodes generic best practice only: money-moving and irreversible actions
(`GATED_ACTIONS`) must never be auto-executed — they are staged for a human approver. The
domain mechanisms (rate-vs-threshold enforcement, exception queues, action ladders,
approval gates) and the retail vocabulary (OTIF, three-way match, ASN/GRN, deductions,
chase ladder) are standard supply-chain practice. This tool incorporates no content,
threshold, window, rate cutoff, schema, or system name from any real retailer,
distributor, ERP, or prior employer.
