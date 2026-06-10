# ADR 0001 — Own the agent loop; no framework

**Status:** accepted (2026-06-10)

## Context

The repo exists to demonstrate a shipped agentic feature and the eval discipline
around it. The loop could be assembled on an agent framework (LangChain, the SDK's
beta tool runner) or written directly on the Messages API.

## Decision

Direct on the Messages API: a manual tool-use loop (under 70 lines) with explicit
stop conditions, plus a `ModelBackend` protocol so the model can be swapped for a
recorded transcript.

## Consequences

- The parts the eval measures — stop conditions, tool-error budget, the
  record/replay seam — are in this repo's code, not behind a framework API.
- The replay backend (CI without a key) only works because the loop is owned: the
  seam sits exactly at the model boundary.
- Cost: features a framework would give for free (streaming, parallel tool
  execution, retries beyond the SDK's) are out of scope and listed in README Limits.
