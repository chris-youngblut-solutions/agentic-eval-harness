# Design

## Architecture

```
src/agentic_eval/                     ENGINE (domain-agnostic)
  runner.py        CLI (run | eval | report), all take --domain
  agent.py         plan-act-observe loop; ModelBackend protocol; run_task(task, backend, domain)
                     LiveBackend   -> Anthropic API (records JSONL with --record)
                     ReplayBackend -> recorded turns, no key, no network
  domain.py        Domain(name, system_prompt, tool_schemas, execute_tool); load_domain(name)
  cases.py         golden-set loading; checkers (numeric/exact/regex/set); metric/hard_gate
  scoring.py       rubric, scorecard, per-metric rollup, hard gates, history, regression diff
  domains/
    generic/       tools.py (calculator/file_search/read_file/csv_query) + DOMAIN     22 cases
    industrial/    tools.py (decode_frame/query_signal/fault_check/
                     safety_bound_check/sensor_fuse) + codec.py + generate.py + DOMAIN  17 cases
    trust_safety/  tools.py (policy_lookup/classify_content/rca_trace/appeal_adjudicate/
                     leakage_check/qc_sample) + policy.py + generate.py + DOMAIN         18 cases

fixtures/<domain>/        committed fixtures (the tools' only world)
eval/<domain>/cases.yaml  prompt + checker + expected tools + metric + hard_gate
eval/<domain>/transcripts/  recorded assistant turns (one JSONL per case)
eval/<domain>/history/      one scorecard JSON per run
```

## Decisions

- **Own the loop; no agent framework.** The loop is under 70 lines over the Messages API
  (manual tool-use loop per the API docs). A framework would hide exactly the part
  this repo exists to demonstrate: stop conditions, error budgets, tool plumbing,
  and the seam that makes replay possible.
- **One engine, N domain packs.** Everything domain-specific (system prompt, tools,
  golden set, fixtures) lives behind a `Domain` selected with `--domain`; the engine
  never changes when a domain is added. `generic` is the reference baseline;
  `industrial` is a CAN/ISOBUS edge decode + diagnostics agent whose decode
  ground-truth is a curated public-standard signal subset (opendbc-ag, MIT) over a
  synthetic corpus; `trust_safety` is a content-enforcement agent over a fully
  synthetic, generic policy (methodology-only — abstract MARKER tokens, benign filler,
  no real policy or harmful content). Adding a domain is additive, not a fork.
- **Metric tags + hard gates.** Cases carry a `metric` (rolled up per metric in the
  scorecard) and an optional `hard_gate`. A failed hard-gate case (e.g. a safety-bound
  violation in the industrial pack) fails the whole run regardless of the pass count —
  the eval analogue of a non-negotiable safety property.
- **`set` checker for precision/recall.** Beyond numeric/exact/regex, a `set` checker
  scores the F1 of the answer's item set against an expected set — the mechanical basis
  for fault-detection precision/recall without an LLM judge.
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

Built and tested: the engine (loop, runner, scoring), the domain seam, three domain
packs (generic + industrial + trust_safety — tools, golden sets, fixtures), the rubric
with per-metric rollups + hard gates, regression tracking, record/replay, CLI, CI
(lint/type/tests); 57 keyless tests. Pending: the first live run and its committed
scorecard + transcripts per domain (needs `ANTHROPIC_API_KEY`; one command:
`uv run agentic-eval eval --domain <name> --record`). The industrial corpus is synthetic
and its decode ground-truth is public-standard only (see `fixtures/industrial/PROVENANCE.md`);
safety bounds are illustrative; latency (p50/p95) is a live-only metric, not in the
keyless golden set. The trust_safety pack is methodology-only — the policy, content
items, appeals, misfires, and QC sets are fabricated and generic, reproducing no real
platform policy or harmful content (see `fixtures/trust_safety/PROVENANCE.md`); its
prescribed actions and severities are illustrative constructs. Not built: multi-agent
coordination, streaming, memory, online tools — out of scope for a reproducible eval
subject.
