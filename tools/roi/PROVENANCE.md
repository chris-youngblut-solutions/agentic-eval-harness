# ROI harness — provenance & data posture

This tool and every number it ships are **fully synthetic and generic**, matching the posture
of `fixtures/retail_ops/` (see `fixtures/retail_ops/PROVENANCE.md`). It carries no real
supplier, retailer, ERP, customer, employer, or PII data, and no quantitative outcome from any
real automation deployment.

## What is here

- `generate.py` — a **deterministic, no-RNG generator**. The 8-week series is a hand-authored
  ramp encoded as explicit per-week control arrays, so a re-run is byte-identical (`generate.py
  --check` asserts it). `SEED` is a provenance stamp, not an entropy source; no pseudo-random
  draw is taken anywhere.
- `fixtures/ops_baseline.jsonl` — the **BEFORE** dataset: a manual supply-chain exception
  operation over 8 weeks, one record per line. Every exception is human-resolved. Each week is
  tagged with a `MARKER_WK##` token so a reviewer can see at a glance it is invented.
- `fixtures/ops_automated.jsonl` — the **AFTER** dataset: the automated agent run over the same
  weeks and the same queue, with the **true-vs-false split** (`auto_resolved_correct` vs
  `auto_resolved_false`), the escalations that still needed a human, and the nuisance
  `false_flags`. Ramp-shaped by construction (early weeks below steady state). The identity
  `auto_resolved_correct + auto_resolved_false + escalated_human == exceptions_in` holds every
  week (asserted at generation time and again in `roi.py`).
- `fixtures/cost.json` — the labor/rate/price deck. Every scalar is a fabricated placeholder
  tagged with a `<<TOKEN>>`; only `.value` is read.
- `roi.py` — the pure, deterministic compute module + CLI. No network, no external assets.
- `report.json` — the emitted report (a byte-function of the three fixtures + a scorecard).
- `build_view.py`, `roi-report.inkspec.html` — the refresh step and the single-file report
  view. No build, no network, no CDN, no remote fonts, no fetch/XHR/WebSocket; the report data
  is inlined in a `<script type="application/json">` block.
- `tests/test_roi.py` — proves the honesty property, determinism, and the safety-gate flip.

## The numbers are illustrative, not measured

The volumes, true/false splits, cycle-time constants, OTIF rates, deduction pools, labor rate,
subscription price, integration cost, dispute fees, and OTIF attribution factor are
**illustrative constructs** authored to exercise the ROI metrics and to demonstrate the honest
false-positive penalty. They reproduce no real customer's, vendor's, or prior employer's
operating figures, pricing, or outcomes, and must not be relied on as calibration values,
benchmarks, or a promise for any real deployment. Re-source every input per deployment.

## The 40% / 4-week figures are TARGET framing, not ground truth

The `targets` block in `cost.json` (40% efficiency, 4-week ROI) is the common **vendor
framing** — carried explicitly so the report can display *target vs computed truth*. It is
**never** used as an input to any headline. Every headline (net touches saved, cycle-time cut,
deduction recovery, OTIF lift, time-to-value) is computed from the before/after fixtures by
`roi.py`. In the shipped sample the honest, ramp-aware breakeven is **week 5**, not the 4-week
target — the harness quotes the honest number.

## The honest model can produce an unflattering result — on purpose

The model is built so that false positives, nuisance flags, escalations, wrong-dispute
penalties, and automation-caused OTIF misses all count **against** the benefit. A deployment
with a high raw auto-rate but a high false rate can net **less** value than a conservative one
(this is exactly what `tests/test_roi.py::test_honesty_property` asserts), and the safety gate
can **void** the ROI claim outright — an `approval_gate` / `false_autoclose_rate` hard-gate
failure sets `roi_claim_valid = false` regardless of the dollar model. Nothing here is
engineered to guarantee a positive number.

## No field-source leakage

This harness was authored from a synthetic, generic construction only. The domain mechanisms
(exception queues, three-way match, deduction disputes, OTIF, breakeven analysis) and the
retail vocabulary are standard supply-chain and unit-economics practice. It incorporates no
content, threshold, rate, price, volume, schema, or system name from any real retailer,
distributor, ERP, vendor, or prior employer, and no quantitative outcome from any such real
methodology appears anywhere.
