# Design

## Architecture

```
eval/cases.yaml          22 cases: prompt + checker + expected tools
        │
        ▼
src/agentic_eval/
  runner.py        CLI (run | eval | report)
  agent.py         plan-act-observe loop; ModelBackend protocol
                     LiveBackend   -> Anthropic API (records JSONL with --record)
                     ReplayBackend -> recorded turns, no key, no network
  tools.py         calculator / file_search / read_file / csv_query (+ schemas)
  cases.py         golden-set loading, checkers (numeric/exact/regex)
  scoring.py       rubric, scorecard, history, regression diff
fixtures/          committed corpus + orders.csv (the tools' only world)
eval/transcripts/  recorded assistant turns (one JSONL per case)
eval/history/      one scorecard JSON per run
```

## Decisions

- **Own the loop; no agent framework.** The loop is ~90 lines over the Messages API
  (manual tool-use loop per the API docs). A framework would hide exactly the part
  this repo exists to demonstrate: stop conditions, error budgets, tool plumbing,
  and the seam that makes replay possible.
- **`submit_answer` as a tool, not free text.** The final answer arrives as a strict-
  schema tool call, so scoring never parses prose. An assistant turn with no tool
  call is an explicit failure mode (`stopped_no_answer`), not a success path.
- **Backend seam for replay.** The only nondeterministic component is the model.
  Recording its turns (wire-shape content blocks, JSONL) and replaying them through
  the identical loop + tool code gives CI a deterministic full-path execution with
  no key. Tools re-execute for real on replay; they are pure functions of committed
  fixtures, so results match the recording.
- **Mechanical checkers only.** Numeric-with-tolerance, exact, regex. LLM-as-judge
  adds a second model's variance to the thing being measured; for closed-form tasks
  it is unnecessary.
- **Partial credit encodes diagnosis.** 0.5 for "right tools, wrong answer"
  separates planning failures from execution failures in the diff report.
- **Request surface** (per the current API docs): `model`, `max_tokens=4096`,
  `system`, `tools` (strict schemas), `messages`. No sampling parameters (removed on
  opus-4.7+), no `thinking` field. Default model `claude-opus-4-8`; `--model` overrides,
  and the scorecard records it.

## Pinned versions (resolved 2026-06-10, locked in uv.lock)

| Component | Version |
|---|---|
| Python | 3.13 (uv-pinned) |
| anthropic | latest at lock (see uv.lock) |
| pydantic | 2.x |
| pyyaml | 6.x |

## Honesty boundary

Built and tested: the loop, four tools, golden set, rubric, regression tracking,
record/replay, CLI, CI (lint/type/tests). Pending: the first live run and its
committed scorecard + transcripts (needs `ANTHROPIC_API_KEY`; one command:
`uv run agentic-eval eval --record`). Not built: multi-agent coordination,
streaming, memory, online tools — out of scope for a reproducible eval subject.
