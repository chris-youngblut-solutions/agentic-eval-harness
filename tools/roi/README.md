# ROI / business-impact harness — retail_ops

A small, stdlib-only Python module plus a single-file, no-build, offline **Collins** report
that turns a synthetic before/after ops dataset into the numbers a Forward Deployed Engineer
owes the economic buyer: **touches saved (net FTE-hours)**, **cycle-time cut**,
**auto-resolution rate**, **false-exception rate**, **deduction $ recovered**, **OTIF lift**,
and **time-to-value (weeks to breakeven)** — each computed, never assumed.

## The honest-ROI principle (the differentiator)

A false-exception is **not free**. An agent that flags — or auto-closes — a clean
transaction creates a human touch that would not otherwise exist. So false positives
**dock** touches-saved (and can drive the number negative):

```
net_touches_saved =  A_correct × t_manual      (genuine, correct, TERMINAL saves)
                   − A_false   × t_rework       (discover + undo + redo; t_rework > t_manual)
                   − F_detect  × t_review       (NEW touches created out of clean items)
```

Two honesty rules are baked in:

- **Escalations that still needed a human count as ZERO saved** — only fully-auto, terminal,
  correct items are credited.
- **A higher raw auto-rate purchased with false positives is negative-yield capacity.** The
  report always shows `correct_auto_rate` beside the raw `auto_resolution_rate`, and the
  touches waterfall shows the vanity number being docked down to the honest net.

The **"40% efficiency / 4-week ROI"** vendor framing is a **target** the report can display
(`cost.json:targets`), **never** baked-in ground truth. Every headline is computed from the
fixtures.

## Files

| File | What it is |
|---|---|
| `generate.py` | deterministic (no-RNG) generator that emits the three fixtures |
| `fixtures/ops_baseline.jsonl` | BEFORE — manual operation, 8 weeks (one `MARKER_WK##` record per line) |
| `fixtures/ops_automated.jsonl` | AFTER — automated run, per week with **true-vs-false** labels |
| `fixtures/cost.json` | labor rate, handle/rework/review times, subscription, integration, α, targets (`<<TOKEN>>`) |
| `roi.py` | pure compute module (one function per metric) + CLI → `report.json` |
| `report.json` | the emitted report (also inlined into the view) |
| `build_view.py` | re-inlines `report.json` into the HTML view (the refresh step) |
| `roi-report.inkspec.html` | the single-file Collins report (stat tiles + charts + honesty ledger) |
| `tests/test_roi.py` | the honesty-property + determinism + safety-gate tests |
| `PROVENANCE.md` | synthetic-data posture |

## Build order / run it

```sh
# 1. (re)generate the synthetic fixtures — deterministic, byte-identical every run
python3 generate.py

# 2. recompute the numbers (uses the bundled fixtures + the latest retail_ops scorecard)
python3 roi.py --out report.json

# 3. re-inline report.json into the self-contained HTML view
python3 build_view.py

# 4. open it — offline, no server, no network
xdg-open roi-report.inkspec.html
```

CLI variants:

```sh
python3 roi.py --scorecard ../../eval/retail_ops/history/<run>.json --out report.json
python3 roi.py --no-scorecard --out report.json   # money model only, no eval cross-ref
python3 roi.py --check                             # compute twice, assert byte-identical
python3 generate.py --check                        # assert on-disk fixtures == a fresh generate
```

Stdlib only — no dependencies, no network, no RNG. `report.json` is a byte-function of the
three fixtures + the scorecard, so `--check` (and re-running `generate.py`) reproduce it
exactly.

## Test

```sh
pytest tools/roi/tests/test_roi.py      # or, standalone: python3 tests/test_roi.py
```

The load-bearing test is `test_honesty_property`: a scenario with **more false positives**
yields a **lower** net touches-saved than one with fewer — **even though its raw
auto-resolution rate is higher**. Concretely, a run at 0.85 raw auto (200 false) nets 2,500
saved-minutes while a cleaner run at 0.62 raw auto (20 false) nets 6,650. If that inequality
ever flips, the model has silently become a vanity calculator. The suite also pins the
shipped marquee numbers, the determinism, and the safety-gate flip.

## What the report shows

- **Impact** — a gate banner, eight stat tiles (net touches saved, cycle-time cut, deduction
  recovered, time-to-value, the honest auto-rate pair, false-exception rate, OTIF lift,
  net-of-subscription), a before→after dumbbell, the honesty waterfall, a ramp-aware
  breakeven line chart, and a target-vs-truth callout.
- **Honesty ledger** — the **true-vs-false work** table (correct credited at `t_manual`;
  false charged at `t_rework`; nuisance at `t_review`; escalations at **zero**), the waterfall
  as a table, the deduction split (net, not gross), and the weekly ramp.
- **Method & provenance** — the formulas, the eval scorecard cross-reference and the safety
  gate that governs the claim, the cost deck, provenance, and the raw `report.json`.

## The safety gate governs the ROI claim

`roi.py` cross-references a `retail_ops` scorecard. It recomputes the rollups the reader must
derive itself (the scorecard file serializes only model fields — the `passed` /
`total_score` / `hard_gate_failures` / `by_metric` rollups are **not** in the file; the
example run carries 34 case objects, counted dynamically), and:

- the **false-exception proxy** = `1 − mean_score(false_autoclose_rate)`;
- a single `approval_gate` or `false_autoclose_rate` **hard-gate failure voids the ROI claim**
  regardless of the dollar model — `roi_claim_valid` flips to `false` and the banner flips to
  the oxide critical flag.

The reconciliation / exception / OTIF / chase / deduction / audit rollups are the accuracy
backing for the labor-savings and recovery terms; the two hard-gated metrics feed the
false-positive / risk terms.

## The honesty proof, in the shipped sample

Raw auto-resolution reads a strong **69.7%**, but honesty docks the touches number **27.5%
below** the naive `$111,015` to a net **`$80,520`** (**5.59 FTE**). The vendor's **4-week**
target is beaten by the optimistic no-ramp closed form (**2.25 wk**) — yet the honest,
**ramp-aware** breakeven is **week 5**, so the report quotes 5, not 4. Total net benefit is
**`$106,424.50`**, **`$70,424.50`** net of the 8-week subscription. Exception aging is cut
**61.7%**; deduction recovery nets **`$10,600`** incremental (weeks 1–2 run *negative* while
the agent over-disputes); OTIF lifts **+1.05 pp** (`$15,304.50` at α = 0.6). All figures are
computed from the fixtures.

## Design system

Collins (stone / copper / oxide, fills-are-LEDs, day↔night). Tokens are inlined; the file
follows the Collins contract — text only from the `--ink*` ramp, `--fill-*` only for LED
dots / chart marks / chip grounds, one copper primary action (**Copy report.json**), oxide
reserved for the identity badge and the single critical **ROI CLAIM VOID** flag. Charts
follow the dataviz discipline: a **sequential** dumbbell for before→after (one hue + neutral,
not two categorical hues — which would lie that it is two entities), a **diverging** waterfall
with sign triply-encoded (bar direction + color + signed label) so color is redundant and
colorblind-safe, thin 2px marks, recessive grid, direct value labels, and a table view of
every chart. Fails to light; follows OS `prefers-color-scheme`; the mode button stamps
`data-mode` on `<html>`.

See `PROVENANCE.md` for the synthetic-data posture.
