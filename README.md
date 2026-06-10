# agentic-eval-harness

> One agentic plan-act-observe loop over four real tools, plus the eval harness that
> scores it: a 22-case golden set, a partial-credit rubric, and regression tracking
> across runs. Apache-2.0 OR MIT. Status: 0.1.0.

## What

An agent loop on the Anthropic SDK (`claude-opus-4-8` by default) with four offline,
deterministic tools — `calculator` (AST-evaluated arithmetic), `file_search` +
`read_file` (a committed document corpus), `csv_query` (filtered aggregations over a
committed orders table) — and explicit stop conditions: a `submit_answer` tool call
(the only success path), a turn cap, and a tool-error budget. The harness runs the
golden set against the loop, scores each case (1.0 correct answer / 0.5 right tools
wrong answer / 0.0), writes a scorecard to `eval/history/`, and diffs runs.

The loop is backend-agnostic: `live` calls the API (optionally recording each
assistant turn to JSONL); `replay` re-runs recorded turns through the identical loop
and tool code with no key and no network. Tools execute for real in both — they are
deterministic, so a replayed run reproduces its scorecard exactly.

## Run

Requires [uv](https://docs.astral.sh/uv/); the live backend requires
`ANTHROPIC_API_KEY` in the environment.

```sh
git clone https://github.com/in-loop/agentic-eval-harness && cd agentic-eval-harness
uv sync --all-extras
uv run pytest                      # 16 tests: tools, every stop condition, rubric, replay

uv run agentic-eval run "What is the mounting bolt torque for the HX-300 pump?"
uv run agentic-eval eval --record  # full golden set, live, records transcripts
uv run agentic-eval eval --backend replay   # re-score from recorded transcripts (no key)
uv run agentic-eval report         # per-case diff of the two most recent scorecards
```

`eval` prints one line per case and a summary
(`N/22 passed, score S/22`), and writes `eval/history/<run-id>.json`.

## Eval design

- **Cases** (`eval/cases.yaml`): 22 cases — single-tool arithmetic, document lookup,
  table aggregation, and multi-step combinations. Every expected value is derived
  from the committed fixtures; a checker per case (`numeric` with tolerance, `exact`,
  `regex`) plus the tools the case is expected to use.
- **Rubric** (`src/agentic_eval/scoring.py`): per-case score 1.0 (correct answer),
  0.5 (wrong answer but every expected tool called — right plan, wrong execution),
  0.0 otherwise. Pass = 1.0. No LLM judging — every check is mechanical.
- **Regression tracking**: each run appends a scorecard to `eval/history/`;
  `agentic-eval report` diffs the last two (per-case deltas, regressions named).
  `--min-pass N` makes `eval` exit nonzero below a floor, for CI gating.
- **Reproducibility**: fixtures are committed; tools are pure functions of them;
  `--record` captures model turns so a scored run can be replayed byte-for-byte.

## Limits

- No live scorecard is committed yet: the first `eval --record` run against the API
  is pending an API key in this workspace. The harness machinery (loop, scoring,
  regression diff, replay) is fully covered by the test suite via scripted backends.
- CI runs lint/type/tests only. The replay-eval smoke step lands together with the
  first recorded transcripts.
- The toolset is offline by design (reproducibility over breadth): no web access,
  no mutation, one fixed corpus and table.
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
