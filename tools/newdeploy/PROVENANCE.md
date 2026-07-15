# newdeploy — provenance & data posture

`newdeploy` is a **scaffolder**: it stamps a per-customer deployment kit from an inert template
tree plus three already-built, in-repo source artifacts. It creates no customer data and embeds
none. It carries no real supplier, retailer, ERP, customer, employer, or PII data, matching the
posture of the artifacts it unifies (see each source's own `PROVENANCE.md`).

## What is here

- `newdeploy.py` — the CLI. Stdlib only. **Deterministic by construction**: it never reads the
  clock (no `import datetime`/`time`/`calendar`); dates stamp as the fill-in `____-__-__`, so the
  same inputs produce byte-identical output.
- `templates/` — five inert `.tmpl` files (`connector-config.env.example`, `mcp.host.json`,
  `runbook.md`, `scoping-checklist.md`, `README.md`). Substitution logic lives only in the CLI.
- `tests/` — the test suite.
- `README.md` — usage, the two token layers, and the verbatim-board reconciliation.
- `PROVENANCE.md` — this file.

## The sample deployment is synthetic

The worked example in the docs and any `deployments/acme-grocers/` you stamp uses a **fabricated
illustrative customer** — "ACME Grocers" / slug `acme-grocers`. It is not any real retailer,
grocer, distributor, customer, or prior employer, and the systems selected for it (`netsuite`,
`coupa`, …) are illustrative dialect choices, not a real integration. `deployments/` is
git-ignored working output, not committed data.

## It references its sources; it does not vendor or invent them

- **Exception-spec board (item 4)** and its sidecars are copied **verbatim** from
  `tools/exception-spec-dsl/`; every business number in them stays a `<<TOKEN>>` placeholder for
  the FDE to author. `newdeploy` edits at most one line (the `localStorage` key, only under
  `--isolate-board`) and never the exported `policy.json`.
- **ROI decks (item 5)** are seeded **verbatim** from `tools/roi/fixtures/` (`cost.json` →
  `roi-baseline.json`, the two `ops_*.jsonl` seeds) plus `roi/roi-report.inkspec.html`.
- **MCP connector kit (item 1)** is referenced **by name only**
  (`frameworks/agents/retail-ops-mcp-kit`); the four servers are not vendored. Only the connector
  wiring is stamped, and `RETAIL_OPS_MCP_APPROVAL_TOKEN` is left an operator-injected placeholder —
  never a real value.

If a source artifact is missing, `newdeploy` **stops and reports** (exit 3); it never hand-writes
or fabricates a board, deck, or policy.
