# Customer-support fixtures — provenance & data posture

This directory is the `customer_support` domain's entire world: a fully
synthetic, generic support action taxonomy plus synthetic labeled corpora. It is
methodology-only. It carries no real support policy, no real tickets, no real
customer data, and no internal tooling.

## What is here

- `policy.json` — a FABRICATED, GENERIC support action taxonomy. Each category
  keys on abstract MARKER tokens (e.g. `MARKER_REFUND`), prescribes a disposition
  (resolve / escalate / deflect), names the auto-action it would imply, and flags
  whether that auto-action is `unsafe` (irreversible / high-risk and therefore
  human-only).
- `tickets.jsonl` — synthetic labeled tickets. Each ticket's `text` is a benign
  fabricated sentence that embeds the gold category's marker token.
- `escalations.jsonl` — synthetic routing-review records over handled tickets
  (some correctly resolved, some that should have gone to a human).
- `misroutes.jsonl` — synthetic labeled routing misroutes across three fabricated
  root-cause classes (`intent_gap`, `classifier_threshold`, `label_ambiguity`).
- `qc.json` — two synthetic rater label sets over a shared ticket set, for the
  inter-rater agreement metric.

`policy.json` is hand-authored (the source taxonomy / answer key). The JSONL
corpora and `qc.json` are generated deterministically from it by
`src/agentic_eval/domains/customer_support/generate.py` and are byte-for-byte
reproducible (`test_corpus_generation_is_deterministic_and_matches_committed`
guards this).

## Synthetic and generic by construction

- **No real support policy.** The taxonomy, category names, dispositions, and
  auto-actions are illustrative constructs authored for this evaluation. They
  reproduce no real company's support policy, runbook, macro set, or routing
  taxonomy, and no real policy text.
- **No real tickets or customer data.** Tickets are represented by abstract
  MARKER tokens embedded in benign filler sentences. No ticket contains a real
  customer message, record, or identifier. The markers are opaque labels; the
  deterministic classifier matches on the marker string, not on any real signal.
- **No real CRM mechanics, queue mechanics, classifier internals, or tooling.**
  The routing-review records, misroutes, and root-cause classes are fabricated
  examples that exercise the eval metrics. They are not derived from any real
  support workflow, ticket, queue, or system.
- **No operator, agent, customer, or company identifiers.**

## Dispositions and auto-actions are illustrative

The prescribed dispositions (resolve / escalate / deflect) and auto-actions in
`policy.json` are illustrative constructs authored for this evaluation, used only
to exercise the resolution, deflection, escalation, and unsafe-auto-action
metrics. They are not operational rules, runbooks, or thresholds for any real
system, and must not be relied on as such. Categories whose auto-action is
irreversible / high-risk (a refund, an account deletion, an account freeze) are
flagged `unsafe` and prescribed `escalate`: a must-escalate ticket must never be
auto-resolved.

## No field-source leakage

This pack was authored from a synthetic, generic construction only. It does not
incorporate any content from real support material, internal policy, or
production tooling. Any methodology that informs the domain framing is referenced
only in its abstract, non-identifying form, and no quantitative outcome from such
methodology (e.g. any real deflection-rate or escalation-rate figure) appears
anywhere in this pack.
