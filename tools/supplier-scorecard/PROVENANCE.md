# Supplier scorecard — provenance & data posture

This tool and every number it ships are **fully synthetic and generic**, matching the
posture of `fixtures/retail_ops/` (see `fixtures/retail_ops/PROVENANCE.md`). It carries no
real supplier, retailer, ERP, customer, employer, or PII data, and no quantitative outcome
from any real supply-chain operation or automation deployment.

## What is here

- `scorecard.py` — the pure, deterministic, stdlib-only engine + CLI. No network, no RNG, no
  external assets, no third-party dependencies.
- `scorecard.json` — the emitted scorecard: a **byte-function of the committed corpus**.
  Re-running the engine reproduces it exactly (`scorecard.py --check` asserts two runs are
  byte-identical; a test guards the committed file against drift).
- `build_view.py`, `supplier-scorecard.inkspec.html` — the refresh step and the single-file
  Collins dashboard. No build, no CDN, no remote fonts, no `fetch` / `XHR` / WebSocket; the
  scorecard data is inlined in a `<script type="application/json">` block, so the file opens
  offline with no network.
- `tests/test_scorecard.py` — proves determinism, the full per-supplier answer key, a
  hand-computed aggregate, and the dashboard's self-containment.

The corpus itself is **not vendored** here: the engine reads the shared, committed fixtures
at `../../fixtures/retail_ops/*.jsonl` — the same files the eval scores against. There is one
source of truth for the synthetic world, and nothing is duplicated.

## Faithful port — the scorecard cannot drift from the answer key

The KPI math is a **faithful, stdlib-only port** of the roll-ups in
`src/agentic_eval/domains/retail_ops/compute.py` (`otif_for_supplier`, `otif_for_po`,
`three_way_match`, the ASN / deduction / exception checks, and `to_ea`). The port changes
only the *shape* (one self-contained module, no dependency on the harness package), never the
*arithmetic*: every quantity is normalized to eaches with the same pack sizes, the same
rounding (2 dp), the same OTIF / fill / ASN definitions, and the same three-way verdict
precedence. Because both paths consume the same policy and the same records, the scorecard's
per-supplier numbers are the roll-up of the eval's per-PO answer key — they are recomputed
here, never transcribed, and cannot silently diverge.

## The numbers are illustrative, not measured

The volumes, pack sizes, tolerances, delivery dates, damage quantities, deduction pools, and
chase states are **illustrative constructs** authored to exercise the KPI math and the
UOM-normalization guard (e.g. PO-8806's CS-vs-EA trap, PO-8809's damage-splits-fill case,
PO-8808's duplicate invoice). They reproduce no real customer's, vendor's, or prior
employer's operating figures, tolerances, or outcomes, and must not be relied on as
calibration values, benchmarks, or a promise for any real deployment. Re-source every input
per deployment.

## The composite weights + grade bands are a modeling choice, stated openly

The composite blend (`0.35 OTIF + 0.20 fill + 0.20 ASN + 0.25 clean`) and the A–F bands are a
**transparent, tunable design choice** carried at the top of `scorecard.py`, not an industry
standard. They are deliberately stressed so a small teaching corpus separates into three
grades; they encode no real retailer's scorecard weighting. Deduction validity and chase
responsiveness are excluded from the grade **on purpose** — they are too sparse in this
corpus to be a supplier signal, and are surfaced as coverage-flagged context instead.

## No field-source leakage

This tool was authored from a synthetic, generic construction only. The domain mechanisms
(three-way match, OTIF / fill, ASN accuracy, deduction validity, exception rate, chase
ladders, supplier scorecards) and the retail vocabulary are standard supply-chain practice.
It incorporates no content, threshold, rate, price, volume, schema, weighting, or system name
from any real retailer, distributor, ERP, vendor, or prior employer, and no quantitative
outcome from any such real methodology appears anywhere.
