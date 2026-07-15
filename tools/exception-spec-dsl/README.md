# exception-spec DSL — retail_ops

A single-file, no-build, offline HTML board for authoring a **per-deployment exception
spec** for the `retail_ops` eval domain, and exporting it to a valid
`fixtures/retail_ops/policy.json` that the eval pack and MCP kit consume **unchanged**.

It is the artifact a Forward Deployed Engineer authors per customer: the one editable
place that holds the business logic which becomes agent behavior — decision rules,
tolerances, exception paths (and exceptions-of-exceptions), hand-to-human fallbacks, and
the approval-gate config. Author here → export `policy.json` → the pack/kit run under it.

## Open it

```sh
# local file, no server, no network
xdg-open tools/exception-spec-dsl/exception-spec.inkspec.html
```

No build step, no dependencies, no CDN, no fonts, no telemetry. All state is in
`localStorage` (namespaced key `exc-spec-dsl-2026-07`); autosaves on every edit.

## Three views

- **Edit** — editable sections for every DSL part: add/remove rows, inputs, selects,
  toggles. Deployment meta, tolerances, decision rules, exception paths (with nested
  guards), fallbacks, the gated-action list, chase ladder, UOM, audit fields, and an
  optional per-customer override layer.
- **Spec** — the live, rendered, human-readable deployment spec (tables, LED disposition
  chips, the chase-ladder timeline). Regenerated on every edit.
- **Validate & export** — a validation panel that flags anything that won't export
  cleanly, the live `policy.json`, and the secondary `exceptions.jsonl` projection.
  Copy / download.

## The round-trip contract

`rules.load_policy` reads **ten keys**; every scalar is a `{token, value, unit}` object
and only `.value` is consumed (plus `otif_window.early_ok`). The DSL captures far more
than those ten keys can express (a full condition→action→terminal rule table, exception
guards, fallbacks, per-action ceilings, per-customer overrides). The export handles this
with two modes:

| Mode | Emits | Loads today? |
|---|---|---|
| **Strict** (default off toggle) | the ten loader keys + `_provenance` + `_schema` | yes — shape-identical to the committed fixture |
| **Carry** (default on) | the above **plus** `_exception_spec` | yes — the loader keeps `_`-prefixed keys in `.raw` and ignores them |

`_exception_spec` is the forward-carry: the richer logic the FDE authored, parked as
metadata for a future data-driven `compute.py` (see `docs/` gap notes). Either mode loads
in the current pack without a code change.

`gated_actions` is **drift-guarded**: the export must equal the eleven-item
`rules.GATED_ACTIONS` frozenset (asserted by `test_corpus`). The list is locked in the UI;
the two special-cased actions (`write_off`, `close_exception`) are shown separately because
`compute.approval_gate` gates them by string literal, **not** via the list.

## Export mapping (DSL → policy.json)

| DSL field | policy.json key | Loader coercion |
|---|---|---|
| `meta.provenance` | `_provenance` | ignored |
| — (constant) | `_schema` | ignored |
| `tolerances.qty_tolerance_pct` | `qty_tolerance_pct` `{token,value,unit}` | `float(value)` |
| `tolerances.price_tolerance_per_case` | `price_tolerance_per_case` | `float(value)` |
| `tolerances.write_off_threshold` | `write_off_threshold` | `float(value)` |
| `tolerances.otif_window` | `otif_window` `{token,value,early_ok,late}` | `str(value)` + `bool(early_ok)` |
| `tolerances.fill_rate_basis` | `fill_rate_basis` | `str(value)` (∈ line\|unit\|case\|value) |
| `tolerances.credit_note_direction` | `credit_note_direction` | `str(value)` |
| `audit_required_fields[]` | `audit_required_fields` | `tuple[str,…]` |
| `gated_actions[].action` (gate≠false) | `gated_actions` | `frozenset[str]` == `GATED_ACTIONS` |
| `chase_ladder.steps[]` | `chase_ladder` `[{index,step,day_offset,tone,…}]` | ordered tuple; `cc`/`route` tolerated |
| `uom[] {sku,pack}` | `uom` `{sku:pack}` | `{str:int}` |
| everything richer | `_exception_spec` (carry mode) | ignored (kept in `.raw`) |

The exception paths **also** project to `exceptions.jsonl` gold rows (the secondary export):
`gold_type` is derived from the marker (`compute.classify_exception`), `gold_disposition`
and `gold_within_tolerance` are the authored labels, and the marker is embedded in benign
filler as `evidence_text`.

## Validation (what blocks a clean export)

Blocking (breaks `load_policy` or the drift test):
- a numeric tolerance whose `value` is not a number;
- `otif_window` missing `value` or a non-bool `early_ok`;
- `gated_actions` not equal to the eleven canonical actions, or containing `write_off` /
  `close_exception`;
- `fill_rate_basis.value` outside `line|unit|case|value`;
- a malformed chase step (non-int `index`/`day_offset`), an empty/non-positive UOM pack,
  an empty audit list, or an exception path whose marker is not a known `MARKER_*`.

Warnings (lint / methodology): a scalar without a `<<TOKEN>>`, an out-of-vocabulary
terminal state, a price-variance-within-tolerance not set to `auto_close`, or a missing
fallback for one of the four hand-to-human classes.

## Round-trip proof

The shipped sample spec is `fixtures/retail_ops/policy.json` reverse-engineered plus the
richer gap-analysis layer. Strict-mode export is byte-shape-identical to the committed
fixture and loads through `rules.load_policy` with every loader-read field equal, and
`frozenset(policy.gated_actions) == rules.GATED_ACTIONS`. Verified both by loading the
export through the real Python loader and by running the DSL's own `buildPolicy()`.

## Design system

Collins (the internal 1972-terminal identity system — stone/copper/oxide, fills-are-LEDs,
day/night). Tokens are inlined; the file follows the Collins contract (text only from the
`--ink*` ramp, `--fill-*` used only for LED dots / chip grounds / rails, one copper primary
action = **Copy policy.json**, oxide reserved for the single critical *BLOCKS EXPORT*
mark). Fails to light, follows OS `prefers-color-scheme`, and the mode button stamps an
explicit `data-mode` on `<html>`.

See `PROVENANCE.md` for the synthetic-data posture.
