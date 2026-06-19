# Data-semantic fixtures — provenance & data posture

This directory is the `data_semantic` domain's entire world: a fully synthetic,
generic semantic layer (a metric catalog over a tiny star schema) plus synthetic
labeled corpora. It is methodology-only. It carries no real company data model,
no real metric catalog, no real BI semantic layer, no real data, and no internal
tooling.

## What is here

- `model.json` — a FABRICATED, GENERIC semantic model. Each metric has an id, a
  measure column, an aggregation (sum / count / count_distinct / avg), synonym
  tokens that deterministically map an NL question to it, and an optional fixed
  filter (grain). This is the source of truth / answer key.
- `facts.jsonl` — the synthetic fact table (`region`, `status`, `customer`,
  `amount`). The metrics' only world; every metric value is computed from these.
- `nl_questions.jsonl` — synthetic labeled NL questions. Each question's `text`
  is an authored phrasing that embeds exactly one gold metric's synonym token.
- `mismatches.jsonl` — synthetic labeled metric-mismatch cases across three
  fabricated diagnosis classes (`wrong_grain`, `double_count`, `filter_drift`).

`model.json` is hand-authored (the source semantic model / answer key). The JSONL
corpora are generated deterministically from authored literals by
`src/agentic_eval/domains/data_semantic/generate.py` and are byte-for-byte
reproducible (`test_corpus_generation_is_deterministic_and_matches_committed`
guards this).

## Synthetic and generic by construction

- **No real data model.** The schema, metric names, measures, aggregations, and
  grains are illustrative constructs authored for this evaluation. They reproduce
  no real company's data model, dbt project, metric catalog, or BI semantic
  layer.
- **No real data.** The fact rows are tabulated fabricated values chosen so the
  metrics resolve to clean, human-checkable numbers (revenue 1000, order_count 8,
  active_customers 4, avg_order_value 125, completed_revenue 600, west_orders 4).
  No real customers, revenue, or operational figures appear.
- **No real metric-mismatch incidents or tooling.** The mismatch cases and
  root-cause classes are fabricated examples that exercise the diagnosis metric.
  They are not derived from any real analytics incident, ticket, or system.
- **No operator, customer, account, or platform identifiers.**

## Values are illustrative

The metric definitions and computed values are illustrative constructs authored
only to exercise the NL→metric/SQL accuracy and metric-correctness eval metrics.
They are not operational figures, definitions, or thresholds for any real system,
and must not be relied on as such. The `consistency_check` gate treats a numeric
answer that disagrees with the semantic layer's own computed value as a
correctness leak (a wrong-metric / double-count / mis-aggregation answer that must
never be returned as correct).

## No field-source leakage

This pack was authored from a synthetic, generic construction only. It does not
incorporate any content from a real data model, internal metric catalog, or
production analytics tooling. Any methodology that informs the domain framing is
referenced only in its abstract, non-identifying form, and no quantitative
outcome from such methodology appears anywhere in this pack.
