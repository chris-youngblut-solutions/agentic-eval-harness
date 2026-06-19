# Fintech-compliance fixtures — provenance & data posture

This directory is the `fintech_compliance` domain's entire world: a fully
synthetic, generic financial-compliance rule taxonomy plus synthetic labeled
corpora. It is methodology-only. It carries no real customer, account,
transaction, or PII data, no real sanctions list, no real SAR/CTR filings, and no
internal screening tooling.

## What is here

- `rules.json` — a FABRICATED, GENERIC compliance rule taxonomy. Each rule keys
  on abstract MARKER tokens (e.g. `MARKER_SANCTIONS_HIT`), prescribes a
  disposition (approve / reject / escalate), and carries a severity.
- `records.jsonl` — synthetic labeled KYC/AML case records. Each record's `text`
  is a benign fabricated sentence that embeds the gold rule's marker token.
- `access.jsonl` — synthetic access-control requests (role, resource), some
  authorized and some not, for the least-privilege adherence metric.
- `acl.json` — the synthetic role -> allowed-resources access-control matrix
  (least-privilege answer key for `access.jsonl`).
- `audit.jsonl` — synthetic audit-trail events, some complete and some with a
  missing required field, for the audit-completeness metric.

`rules.json` and `acl.json` are hand-authored (the source taxonomy / answer key).
The JSONL corpora are generated deterministically from them by
`src/agentic_eval/domains/fintech_compliance/generate.py` and are byte-for-byte
reproducible (`test_corpus_generation_is_deterministic_and_matches_committed`
guards this).

## Synthetic and generic by construction

- **No real compliance policy.** The taxonomy, rule names, prescribed
  dispositions, severities, and the ACL are illustrative constructs authored for
  this evaluation. They reproduce no real institution's compliance policy, KYC/AML
  program, sanctions screening configuration, or risk model, and no real policy
  text.
- **No real customer / financial data.** Case records are represented by abstract
  MARKER tokens embedded in benign filler sentences. No record contains actual
  customer identity, account, transaction, PII, or sanctions-list content. The
  markers are opaque labels; the deterministic screener matches on the marker
  string, not on any real signal.
- **No real cases, queues, screening internals, or tooling.** The access
  requests, audit events, and dispositions are fabricated examples that exercise
  the eval metrics. They are not derived from any real compliance workflow, case,
  filing, queue, or system.
- **No customer, employee, officer, or institution identifiers.**

## Dispositions and severities are illustrative

The prescribed dispositions (approve / reject / escalate), severities, and the
access-control matrix in `rules.json` / `acl.json` are illustrative constructs
authored for this evaluation, used only to exercise the KYC/AML, audit-trail,
access-control, and violation metrics. They are not operational rules,
calibration values, risk thresholds, or authorization grants for any real system,
and must not be relied on as such. High-severity escalate rules (e.g. a
sanctions- or PEP-style rule) prescribe route-to-officer and are treated as
leakage-sensitive: a must-reject/must-escalate record must never be approved.

## No field-source leakage

This pack was authored from a synthetic, generic construction only. It does not
incorporate any content from real compliance material, internal policy,
production screening tooling, or any privileged financial source. Any methodology
that informs the domain framing is referenced only in its abstract,
non-identifying form, and no quantitative outcome from such methodology appears
anywhere in this pack.
