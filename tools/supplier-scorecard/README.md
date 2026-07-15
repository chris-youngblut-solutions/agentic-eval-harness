# Supplier scorecard — retail_ops

A small, stdlib-only Python engine plus a single-file, no-build, offline **Collins**
dashboard that rolls the `retail_ops` per-PO reconciliation corpus up to the **supplier**
level: six retail-buyer KPIs, a weighted composite, a letter grade, a rank, and per-PO
drill atoms — each computed, never assumed, and **byte-for-byte reproducible**.

The engine is a faithful, stdlib-only port of the answer-key roll-ups in
`src/agentic_eval/domains/retail_ops/compute.py`, so the scorecard can **never drift**
from the eval's per-PO answer key — same corpus in, same numbers out.

## The join (why `supplier` needs a roll-up)

`supplier` lives on exactly one fixture — `purchase_orders.jsonl` (`po.supplier`). Every
other record (receipts, ASNs, invoices, deductions, chase state, exceptions) carries
`po_id` only. So **every** KPI is the join `record.po_id → PO.id → PO.supplier`, and every
quantity is normalized to **eaches** (via the SKU pack size) before any comparison — the
#1 false-exception guard. PO-8806 is the deliberate CS-vs-EA trap: the PO is in cases, the
receipt and ASN are already in eaches; normalized, `100 CS × 12 = 1200 EA` matches exactly.

## Metric model (per supplier)

| KPI | Computation | In composite |
|---|---|---|
| **OTIF %** | passed POs / n (on-time **and** fill ≥ 100%) — port of `otif_for_supplier` | ✅ 0.35 |
| **Fill %** | Σ good_ea / Σ ordered_ea (good = received − damaged; **uncapped**) | ✅ 0.20 (capped at 100 for scoring) |
| **ASN accuracy %** | POs where `to_ea(asn.qty) == Σ to_ea(receipt)` / n (missing ASN = inaccurate) | ✅ 0.20 |
| **Exception rate %** | flagged POs / n (excludes the `no_exception` UOM-OK control) | ✅ 0.25 as `clean = 100 − rate` |
| **Deduction validity %** | valid (cited KPI actually failed) / filed | ⬛ contextual (excluded) |
| **Chase responsiveness %** | responsive threads / mapped threads | ⬛ contextual (excluded) |

**Composite** `= 0.35·OTIF + 0.20·min(Fill,100) + 0.20·ASN + 0.25·(100 − Exception)`.
**Grade bands** A ≥ 80, B ≥ 65, C ≥ 50, D ≥ 35, else F (all tunable in one place at the
top of `scorecard.py`).

Deduction validity and chase responsiveness are **genuinely sparse** in this corpus
(SUP-022 has zero deductions; only three of six chase rows map to an in-corpus PO), so they
are surfaced as **coverage-flagged** columns but deliberately **held out of the grade** — a
KPI computed over one thread is not a supplier signal.

## The shipped answer key

Three suppliers over ten POs, clean three-way rank separation:

| Rank | Supplier | Grade | Composite | OTIF | Fill | ASN | Exc | Ded valid | Chase |
|---|---|---|---|---|---|---|---|---|---|
| 1 | SUP-021 | **B** (green LED) | 67.18 | 75.0 | 98.4 | 75.0 | 75.0 | 50% (1/2) | 50% (1/2) |
| 2 | SUP-023 | **C** (amber) | 52.12 | 33.33 | 93.94 | 66.67 | 66.67 | 50% (1/2) | 0% (0/1) |
| 3 | SUP-022 | **D** (red) | 49.84 | 66.67 | 99.2 | 33.33 | 100.0 | n/a (0/0) | n/a (0/0) |

SUP-022 outfills and out-OTIFs SUP-023 yet ranks last: every one of its POs threw an
exception (`clean = 0`) and only one of three ASNs matched — the composite rewards clean,
verifiable delivery, not raw throughput.

## Files

| File | What it is |
|---|---|
| `scorecard.py` | pure, deterministic, stdlib-only engine (loaders + KPI math + composite/grade/rank) + CLI → `scorecard.json` |
| `scorecard.json` | the emitted scorecard (also inlined into the dashboard; guarded by a regression test) |
| `build_view.py` | re-inlines `scorecard.json` into the dashboard (the refresh step) |
| `supplier-scorecard.inkspec.html` | the single-file Collins dashboard (ranked table + LEDs + charts + drill) |
| `tests/test_scorecard.py` | determinism + the full answer key + a hand-computed aggregate + self-containment |
| `PROVENANCE.md` | synthetic-data posture + no-drift port note |

The engine reads the shared, committed corpus at `../../fixtures/retail_ops/*.jsonl`
(configurable via `--fixtures`) — the same fixtures the eval scores against, so there is
one source of truth and nothing to vendor.

## Build order / run it

```sh
# 1. compute the numbers — deterministic, byte-identical every run
python3 scorecard.py                 # -> scorecard.json

# 2. re-inline scorecard.json into the self-contained dashboard
python3 build_view.py

# 3. open it — offline, no server, no network
xdg-open supplier-scorecard.inkspec.html
```

CLI variants:

```sh
python3 scorecard.py --stdout                    # print JSON, write nothing
python3 scorecard.py -o /tmp/sc.json             # custom output path
python3 scorecard.py --fixtures DIR              # score an alternate (synthetic) corpus
python3 scorecard.py --check                     # compute twice, assert byte-identical
python3 build_view.py --from-json                # re-inline committed scorecard.json (no recompute)
python3 build_view.py --check                    # CI guard: nonzero if the dashboard is stale
```

Under the harness environment, prefix with `uv run` (e.g. `uv run python scorecard.py`).

## Test

```sh
uv run pytest -q                     # from this dir (21 tests)
# or standalone, no pytest:  python3 tests/test_scorecard.py
```

The suite pins the full per-supplier answer key (all six KPIs × three suppliers), a
**hand-computed** aggregate independent of the engine's own roll-up (SUP-021 good 5904 /
ordered 6000 → 98.4% fill; OTIF 3/4 = 75.0), the composite grade + rank, the per-PO drill
atoms (the UOM trap, the damage-vs-three-way split, price-within-tolerance), byte-stable
determinism, the committed `scorecard.json` regression, and the dashboard's
self-containment (zero external refs; the inlined data equals `scorecard.json`;
`build_view` is idempotent).

## What the dashboard shows

- **Overview tiles** — supplier / PO counts, best + worst, grade distribution, qty tolerance.
- **Supplier ranking** — the graded table with a status **LED + grade letter** (colour is
  never the only channel), the four composite KPIs each with a status glyph, and the two
  contextual columns carrying their coverage fraction. Click a row to drill in.
- **OTIF by supplier** — a ranked horizontal bar (length = magnitude) against the 95% SLA
  reference line, with a direct value label + status word on every bar.
- **KPI profile — small multiples** — one panel per composite KPI, suppliers in a shared
  rank order so you read a supplier's profile across a row; a table-view toggle mirrors it.
- **Supplier drill** — the per-PO atoms behind the roll-up (ordered / received / good eaches,
  on-time, fill, OTIF, ASN match, three-way verdict, exception type) — every quantity in eaches.
- **Export JSON** — the one copper primary action downloads the embedded `scorecard.json`.

## Design system

Collins (stone / copper / oxide, fills-are-marks, day↔night). Tokens are inlined; the file
follows the Collins contract — text only from the `--ink*` ramp, `--fill-*` only for LED
dots / bar marks / chip grounds, one copper primary action (**Export JSON**), oxide reserved
for the identity badge, `--sys-accent` owns focus + row selection. Charts follow the dataviz
discipline: **supplier identity is never hue-encoded** (Collins ships a 5-tone *status*
scale, not a categorical palette); bar **length** carries magnitude, while **status fill +
status word + glyph** are three redundant channels for SLA pass/fail (colorblind-safe);
small multiples on a shared supplier order replace a rainbow scatter; direct value labels are
mandatory (fills are sub-3:1 marks by design); every chart has a table view. Fails to light,
follows OS `prefers-color-scheme`, and the mode button stamps `data-mode` on `<html>`.

See `PROVENANCE.md` for the synthetic-data posture.
