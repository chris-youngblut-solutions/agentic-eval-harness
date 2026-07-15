# approval_audit fixtures — provenance & data posture

This directory is the `approval_audit` domain's entire world: synthetic inbound
lure messages, conflicting source records, and audit-pressure entries. It is
methodology-only. It carries no real approval workflow, no real message or sender,
no real prompt-injection or exploit content, and no internal tooling.

The pack is adversarial: the lure arrives in a **tool result** (`read_message` /
`read_conflicting_records`), and the agent must treat that text as **data, not
instructions**, still run the gate/audit check, and return the policy-correct
verdict.

## What is here

- `lures.jsonl` — synthetic inbound messages. Each carries one opaque MARKER token,
  a benign filler sentence, and a synthetic imperative (the "injection"), plus the
  structured action it requests (`requested_action_type` / `_execution_mode` /
  `_ref_id` / `_amount`). The `gold_*` fields (verdict, should-refuse, injection) are
  the answer key and are never surfaced by the tool.
- `audit_pressure.jsonl` — synthetic audit entries (same shape as retail_ops
  `audit_entries.jsonl`); each incomplete row blanks exactly the field an
  "audit-shortcut" lure tempts dropping.
- `conflicts.jsonl` — synthetic pairs of source records that disagree on a
  gating-relevant field (a write-off amount, the referenced exception, or the action
  type itself). `gold_verdict` is the answer key and is never surfaced.

These JSONL corpora are generated deterministically by
`src/agentic_eval/domains/approval_audit/generate.py` and are byte-for-byte
reproducible (`test_corpus_generation_is_deterministic_and_matches_committed` guards
this). No gold label is hand-typed: every `gold_verdict` is computed by the reused
retail_ops answer key (`compute.approval_gate`, composed by `compute.conflict_verdict`
for conflicts), so the fixtures' labels and the tool the agent calls are the same
function.

## Synthetic and generic by construction

- **No real policy.** The gated-action list, thresholds, exception dispositions, and
  audit-required fields are the reused retail_ops synthetic policy — illustrative
  constructs authored for this evaluation. They reproduce no real approval workflow,
  control matrix, or tolerance from any real operation or prior employer.
- **No real injection or exploit content.** The lures are benign fabricated
  sentences carrying opaque MARKER tokens (`MARKER_URGENCY`, `MARKER_SKIP_APPROVAL`,
  `MARKER_AUTHORITY_PRESSURE`, `MARKER_PREAPPROVED_CLAIM`, `MARKER_PROMPT_INJECTION`,
  `MARKER_AUDIT_SHORTCUT`, `MARKER_CONFLICT_POINTER`). No item contains a real
  prompt-injection payload, jailbreak string, or exploit; the embedded imperatives
  ("just auto-pay it", "skip approval", "reply SAFE") are generic synthetic phrasings.
  The markers are opaque labels matched as plain strings and carry no real signal.
- **No real cases, mechanics, or tooling.** The senders, messages, conflict records,
  and audit entries are fabricated examples authored only to exercise the eval
  metrics (auto-execute refusal, injection resistance, audit completeness under
  pressure, conflicting-data safe default). They are not derived from any real
  message queue, approval system, ticket, or workflow.
- **No operator, reviewer, user, or platform identifiers.**

## No field-source leakage

This pack was authored from a synthetic, generic construction only. The
trust-and-safety and adversarial ship-gate background that motivates the domain
framing is referenced only in its abstract, non-identifying form, and no
quantitative outcome from any such methodology (e.g. any before/after refusal or
enforcement figure) appears anywhere in this pack. Nothing here incorporates real
policy text, real injection material, or production tooling.
