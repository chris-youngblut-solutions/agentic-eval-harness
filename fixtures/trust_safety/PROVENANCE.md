# Trust & Safety fixtures — provenance & data posture

This directory is the `trust_safety` domain's entire world: a fully synthetic,
generic content-policy taxonomy plus synthetic labeled corpora. It is
methodology-only. It carries no real platform policy, no real moderation cases,
no real harmful content, and no internal tooling.

## What is here

- `policy.json` — a FABRICATED, GENERIC content-policy taxonomy. Each category
  keys on abstract MARKER tokens (e.g. `MARKER_BULK_PROMO`), prescribes an action
  (allow / remove / escalate), and carries a severity.
- `content.jsonl` — synthetic labeled content items. Each item's `text` is a
  benign fabricated sentence that embeds the gold category's marker token.
- `appeals.jsonl` — synthetic appeals over prior removals (some uphold, some
  overturn).
- `misfires.jsonl` — synthetic labeled enforcement misfires across three
  fabricated root-cause classes (`policy_gap`, `classifier_threshold`,
  `label_ambiguity`).
- `qc.json` — two synthetic rater label sets over a shared item set, for the
  inter-rater agreement metric.

`policy.json` is hand-authored (the source taxonomy / answer key). The JSONL
corpora and `qc.json` are generated deterministically from it by
`src/agentic_eval/domains/trust_safety/generate.py` and are byte-for-byte
reproducible (`test_corpus_generation_is_deterministic_and_matches_committed`
guards this).

## Synthetic and generic by construction

- **No real platform policy.** The taxonomy, category names, prescribed actions,
  and severities are illustrative constructs authored for this evaluation. They
  reproduce no real platform's content policy, community guidelines, or
  trust-and-safety taxonomy, and no real policy text.
- **No real harmful content.** Content items are represented by abstract MARKER
  tokens embedded in benign filler sentences. No item contains actual toxic,
  graphic, harassing, or self-harm content. The markers are opaque labels; the
  deterministic classifier matches on the marker string, not on any real signal.
- **No real moderation cases, queue mechanics, classifier internals, or tooling.**
  The appeals, misfires, and root-cause classes are fabricated examples that
  exercise the eval metrics. They are not derived from any real moderation
  workflow, ticket, queue, or system.
- **No operator, reviewer, user, or platform identifiers.**

## Actions and severities are illustrative

The prescribed actions (allow / remove / escalate) and severities in
`policy.json` are illustrative constructs authored for this evaluation, used only
to exercise the enforcement, leakage, and escalation metrics. They are not
operational rules, calibration values, or thresholds for any real system, and
must not be relied on as such. High-severity escalate categories (e.g. a
self-harm-style category) prescribe route-to-support and are treated as
leakage-sensitive: a must-remove/must-escalate item must never be allowed.

## No field-source leakage

This pack was authored from a synthetic, generic construction only. It does not
incorporate any content from real moderation material, internal policy, or
production tooling. Any methodology that informs the domain framing is referenced
only in its abstract, non-identifying form, and no quantitative outcome from such
methodology (e.g. any before/after enforcement-quality figure) appears anywhere
in this pack.
