# newdeploy — per-customer FDE deployment scaffolder

`newdeploy <slug>` stamps a per-customer deployment kit under `deployments/<slug>/` so
**deployment #2 is faster than deployment #1** — the land-and-expand tempo ("build reusable
templates and runbooks so each deployment is faster"). It seeds each deployment from an
inert template tree and **unifies three companion artifacts** into one folder:

- **MCP connector kit** ([retail-ops-mcp-kit](https://github.com/chris-youngblut-solutions/retail-ops-mcp-kit),
  referenced *by name*): `connector-config.env.example` + `.mcp.json` wire the four servers
  to the customer's SaaS dialects.
- **exception-spec DSL** (`tools/exception-spec-dsl`): the board is copied **in full**
  (self-contained, single-file) — the one place the FDE authors this customer's rules.
- **ROI harness** (`tools/roi`): `roi-baseline.json` + `roi/ops_*.jsonl` + `roi-report.inkspec.html`.

## Usage

```sh
newdeploy <slug> [--customer NAME] [--out DIR]
                 [--erp SYS] [--supplier SYS] [--email SYS] [--sheets SYS]
                 [--isolate-board] [--force]
newdeploy --list-systems
```

- `<slug>` — required, lowercase kebab-case (`^[a-z0-9]+(-[a-z0-9]+)*$`); becomes `{{SLUG}}`.
- `--customer NAME` — display name; default = title-cased slug.
- `--out DIR` — parent dir for `<slug>/` (default `./deployments`).
- `--erp/--supplier/--email/--sheets` — SaaS dialect per server, **validated against the
  allowlist** (invalid values fail the stamp). Defaults match the kit.
- `--isolate-board` — rewrite the board's `localStorage` key to `exc-spec-<slug>` so two
  deployments opened in one browser don't collide. Otherwise the board is copied **verbatim**.
- `--force` — overwrite a non-empty target (default: refuse, don't clobber).
- `--list-systems` — print the four servers / env vars / allowlists / defaults and exit.

```sh
$ python newdeploy.py --list-systems
$ python newdeploy.py acme-foods --customer "ACME Foods" --erp netsuite --supplier coupa
```

## Determinism

The CLI **never reads the clock** (no `import datetime`/`time`). Date fields stamp as the
fill-in placeholder `____-__-__` the FDE fills at go-live — per the no-Date-in-scripts constraint.
Given the same inputs it produces byte-identical output.

## Two token layers (never conflated)

| Layer | Form | Who fills it | When |
|---|---|---|---|
| **scaffolding** | `{{UPPER_SNAKE}}` | `newdeploy`, once, in `.tmpl` files | stamp time |
| **authoring** | `<<UPPER_SNAKE>>` | the FDE, inside the board / cost deck | author time |

`newdeploy` substitutes `{{SLUG}}`, `{{CUSTOMER}}`, `{{DATE:fill-in}}`, `{{ERP_SYSTEM}}`,
`{{SUPPLIER_SYSTEM}}`, `{{EMAIL_SYSTEM}}`, `{{SHEETS_SYSTEM}}`, `{{APPROVAL_TOKEN_VAR}}`,
`{{GENERATOR}}` — and **leaves every `<<TOKEN>>` intact** (that is the deliverable's editable surface).

Substitution runs over `.tmpl` files only; copied artifacts (the board, its sidecars, the ROI
report/decks) stay verbatim. Logic lives in exactly one place (this CLI); templates stay inert.

## Output layout (`deployments/<slug>/`)

```
README.md                     stamped   deployment index
runbook.md                    stamped   Phase 0->6 go-live -> expansion runbook + gates
scoping-checklist.md          stamped   tolerances / gated-actions / systems / approval-owners
connector-config.env.example  stamped   four *_SYSTEM dialects + approval-token placeholder
.mcp.json                     stamped   host wiring snippet for the four MCP servers
roi-baseline.json             seeded    ROI cost deck (every scalar an <<TOKEN>>)
exception-spec.inkspec.html   copied    the board — FDE authors the spec here
fixtures/retail_ops/          created   export target (board writes policy.json here)
roi/ops_baseline.jsonl        seeded    BEFORE weekly ops data
roi/ops_automated.jsonl       seeded    AFTER weekly ops data (true-vs-false)
roi/roi-report.inkspec.html   copied    Collins ROI report
refs/                         copied    read-only board README/PROVENANCE + sample export
```

## Self-containment & the drift-guard

- The board is copied **in full** and re-checked to be self-contained (no external
  `<script src>`, `<link rel=stylesheet>`, or `http(s)://` asset). The MCP kit is referenced by
  name — never vendored — so this repo stays self-contained without duplicating the servers.
- `newdeploy` never touches the exported `policy.json` shape: the frozen 11 `gated_actions`
  (`== rules.GATED_ACTIONS`) and the exclusion of `write_off` / `close_exception` are the FDE's to
  keep clean at export. The seeded `refs/sample-export.policy.json` is the committed reference.

## Why the board is copied verbatim (a reconciled design call)

Two source specs disagreed about the board: one proposed tokenizing the domain
(`{{DOMAIN}}` / `{{STORAGE_NS}}`), the other said copy the board byte-for-byte. Ground truth
settles it — `retail_ops` appears in the board's title, eyebrow, provenance line, and worked
sample (7 occurrences), so tokenizing "the domain" would corrupt the board's
synthetic-provenance text. The board is therefore **verbatim by default**. The only genuinely
per-deployment string is the `localStorage` key (`exc-spec-dsl-2026-07`): two deployments open
in one browser would otherwise share state. `--isolate-board` makes **exactly one** surgical
edit — that key → `exc-spec-<slug>` — and nothing else; it never touches the exported
`policy.json`, so the drift-guard is unaffected. Reversible: drop the flag for a byte-identical
copy.

## The one manual step `newdeploy` does NOT do

It stamps the **blank** board and the **seed** decks. It does **not** author the `<<TOKEN>>`
business values, does **not** run the export, and does **not** inject
`RETAIL_OPS_MCP_APPROVAL_TOKEN` — those are the FDE's supervised, per-customer acts. The CLI never
authors business logic or holds a live credential.

## Tests

```sh
python -m pytest tools/newdeploy/tests -q
```
