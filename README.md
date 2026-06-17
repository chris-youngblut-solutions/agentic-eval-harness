# agentic-eval-harness

> One agentic plan-act-observe loop over real tools, plus the eval harness that scores
> it — across pluggable domain packs. Partial-credit rubric, per-metric rollups, hard
> gates, and regression tracking across runs. Apache-2.0 OR MIT. Status: 0.1.0.

## What

An agent loop on the Anthropic SDK (`claude-opus-4-8` by default) with offline,
deterministic tools and explicit stop conditions: a `submit_answer` tool call (the
only success path), a turn cap, and a tool-error budget. The harness runs a domain's
golden set against the loop, scores each case, writes a scorecard to
`eval/<domain>/history/`, and diffs runs.

The engine is domain-agnostic; everything domain-specific is a **domain pack** selected
with `--domain`. Three ship in the box:

- **`generic`** — `calculator` (AST-evaluated arithmetic), `file_search` + `read_file`
  (a committed document corpus), `csv_query` (filtered aggregations over an orders
  table). 22 cases.
- **`industrial`** — a CAN/ISOBUS edge decode + diagnostics agent: `decode_frame`,
  `query_signal`, `fault_check`, `safety_bound_check` (a deterministic safety gate),
  `sensor_fuse`. Decode ground-truth is a curated public-standard signal subset derived
  from the MIT-licensed [opendbc-ag](https://github.com/in-loop/opendbc-ag); the bus
  logs are a synthetic corpus (no real machine, operator, or farm data). 17 cases.
- **`trust_safety`** — a content-enforcement agent over a fully synthetic, generic
  policy: `policy_lookup`, `classify_content`, `rca_trace`, `appeal_adjudicate`,
  `leakage_check` (a deterministic safety gate), `qc_sample`. Methodology-only —
  the policy, content items (benign sentences carrying abstract MARKER tokens),
  appeals, misfires, and QC rater sets are all fabricated; no real platform policy,
  moderation case, or harmful content (no real policy text, no real toxic content).
  18 cases.

The loop is backend-agnostic: `live` calls the API (optionally recording the full
conversation — model turns plus the tools' outputs — to JSONL); `replay` re-runs the
recorded model turns through the identical loop and tool code with no key and no
network. Tools execute for real in both — they are deterministic, so a replayed run
reproduces its scorecard, and the recorded outputs, exactly.

## Run

Requires [uv](https://docs.astral.sh/uv/); the live backend requires
`ANTHROPIC_API_KEY` in the environment.

```sh
git clone https://github.com/in-loop/agentic-eval-harness && cd agentic-eval-harness
uv sync --all-extras
uv run pytest          # 64 tests: engine, tools, scoring, all domains, replay — no key needed
```

With `ANTHROPIC_API_KEY` set (every command takes `--domain`, default `generic`):

```sh
uv run agentic-eval run "What is the mounting bolt torque for the HX-300 pump?"
uv run agentic-eval eval --domain industrial --record   # a domain's golden set, live, records full transcripts
uv run agentic-eval eval --domain industrial --backend replay   # re-score from transcripts (no key)
uv run agentic-eval eval --domain industrial --backend replay --record  # regenerate transcripts keyless
uv run agentic-eval report --domain industrial          # per-case diff of the two most recent scorecards
```

`eval` prints one line per case, a per-metric rollup, and a summary
(`N/M passed, score S/M`), and writes `eval/<domain>/history/<run-id>.json`.

## Eval design

- **Domains** (`src/agentic_eval/domains/<name>/`): each pack exports a `Domain`
  (system prompt + tool schemas + tool executor); its golden set is
  `eval/<name>/cases.yaml` and its fixtures live under `fixtures/<name>/`. The engine
  (loop, runner, scoring) never changes when a domain is added.
- **Cases**: every expected value is derived from the committed fixtures (the fixtures
  are the answer key). A checker per case — `numeric` (tolerance), `exact`, `regex`, or
  `set` (F1 against an expected item set, the basis for precision/recall) — plus the
  tools the case is expected to use. Cases may carry a `metric` tag and a `hard_gate`.
- **Rubric** (`src/agentic_eval/scoring.py`): per-case score 1.0 (correct answer),
  0.5 (wrong answer but every expected tool called — right plan, wrong execution),
  0.0 otherwise; `set` cases score their F1. Pass = 1.0. No LLM judging — every check
  is mechanical (which keeps the whole path keyless-testable).
- **Metrics + hard gates**: cases roll up per `metric` (e.g. `signal_decode_accuracy`,
  `fault_detection`, `safety_bound_adherence`); a failed `hard_gate` case (e.g. a
  safety-bound violation) fails the whole run regardless of the pass count.
- **Regression tracking**: each run appends a scorecard to `eval/<domain>/history/`;
  `agentic-eval report` diffs the last two (per-case deltas, regressions named).
  `--min-pass N` makes `eval` exit nonzero below a floor, for CI gating.
- **Reproducibility**: fixtures are committed; tools are pure functions of them;
  `--record` captures the full conversation (model turns + tool outputs), so a scored
  run replays byte-for-byte — and `eval --backend replay --record` regenerates the
  transcripts with no key.

## Limits

- Committed scorecards and transcripts are present for all three domains (live runs,
  `claude-opus-4-8`); `eval --backend replay` reproduces them with no key, and the
  recorded transcripts include the tools' outputs.
- CI runs lint / type / tests; the loop, scoring, regression diff, and replay are
  covered by the test suite via scripted/replay backends (no key, no network).
- The `industrial` corpus is synthetic; decode ground-truth is a curated public-standard
  signal subset (opendbc-ag, MIT). It contains no real machine serials, operator/farm
  identifiers, or proprietary/OEM signal definitions (see `fixtures/industrial/PROVENANCE.md`).
  Per-signal `safety_bound` values are illustrative operational limits authored for the
  eval, not specifications for any real machine. Latency (p50/p95) is a live-run metric
  and is not part of the keyless golden set.
- The `trust_safety` pack is methodology-only: the policy taxonomy, content items, appeals,
  misfires, and QC rater sets are all fabricated and generic (see
  `fixtures/trust_safety/PROVENANCE.md`). It reproduces no real platform's content policy,
  policy text, moderation cases, tooling, or harmful content — content items are abstract
  MARKER tokens in benign filler sentences. Prescribed actions and severities are
  illustrative constructs for exercising the metrics, not operational rules for any system.
- The toolset is offline by design (reproducibility over breadth): no web access,
  no mutation, fixed committed fixtures per domain.
- Scores are model-version sensitive — the scorecard records the model id; compare
  runs only within the same model.
- Single-agent, single-task loop. No multi-agent coordination, no streaming, no
  conversation memory across tasks.

## Development

```sh
pre-commit install   # one-time after clone
just check           # fmt + lint + test
```

## License

Licensed under either of:

- Apache License, Version 2.0 ([LICENSE-APACHE](LICENSE-APACHE) or
  <http://www.apache.org/licenses/LICENSE-2.0>)
- MIT license ([LICENSE-MIT](LICENSE-MIT) or
  <http://opensource.org/licenses/MIT>)

at your option.

### Contribution

Unless you explicitly state otherwise, any contribution intentionally
submitted for inclusion in this project by you, as defined in the
Apache-2.0 license, shall be dual licensed as above, without any
additional terms or conditions.
