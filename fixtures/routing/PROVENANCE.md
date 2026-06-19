# Routing fixtures — provenance & data posture

This directory is the `routing` domain's entire world: a fully synthetic,
generic hybrid-dispatch tier table plus a synthetic labeled task corpus. It is
methodology-only. It carries no real routing table, model roster, cost sheet,
capability matrix, or real task content.

## What is here

- `tiers.json` — a FABRICATED, GENERIC routing tier table. Three tiers ordered
  cheapest → priciest (`edge`, `local`, `frontier`), each with a capability set,
  an inclusive `max_difficulty` band, a relative `cost`, and a `net` mode
  (`none` for on-box `edge`/`local`, `frontier` for the off-box tier). A
  privacy-flagged task must never route to a `net != none` tier.
- `tasks.jsonl` — synthetic labeled tasks. Each carries the three routing inputs
  (`difficulty`, `required_capabilities`, `privacy`) plus a `gold_tier` that is
  *computed* from `tiers.json` by the policy model, not asserted by hand.

`tiers.json` is hand-authored (the source tier table / answer key). The task
corpus is generated deterministically from it by
`src/agentic_eval/domains/routing/generate.py` and is byte-for-byte reproducible
(`test_corpus_generation_is_deterministic_and_matches_committed` guards this).

## Relationship to the hybrid-dispatch router (DEP note)

This pack encodes the **documented hard-rules contract** of the hybrid-dispatch
router at `~/C1-10P/frameworks/openweights-finetuning/internals/hybrid-dispatch`
(`hybrid_dispatch.router.Router.decide`), whose rule order is:

1. **privacy** → local, with `net_mode="none"` asserted; the frontier arm is
   never constructed or called for a privacy-flagged request.
2. **capability-miss** → frontier.
3. **difficulty < threshold** → local.
4. otherwise → cost tiebreak (local is cheaper).

The upstream router ships **two lanes** (`local` | `frontier`). This eval models
a **third tier**, `edge`, below `local` (cheapest, smallest capability set,
`net == none`), and a two-band difficulty schedule, as a forward-compatible
*extension* of the same rule order — capability-miss escalates upward to the
cheapest satisfying tier, difficulty escalates to the cheapest admitting tier,
and privacy pins to the cheapest non-net tier (`edge` if it satisfies, else
`local`), never the net tier. The two-lane subset of this model
(`edge` collapsed out) reproduces the upstream router's behavior exactly.

**Dependency posture:** the eval does not import or call the upstream router; it
reimplements the documented contract in `policy.decide_tier` so the pack is
self-contained and the upstream package need not be installed. If the upstream
router later lands a native `edge` lane, reconcile `tiers.json` and `policy.py`
with the shipped contract and regenerate the corpus.

## Synthetic and generic by construction

- **No real routing table or model roster.** The tier ids, names, capability
  sets, difficulty bands, and cost weights are illustrative constructs authored
  for this evaluation. They reproduce no real router's configuration, no real
  model's capability profile, and no real cost or latency figure.
- **No real task content.** Tasks are benign synthetic one-line descriptions
  carrying three abstract routing inputs (a difficulty scalar, a capability
  list, a privacy flag). No item contains real prompt content, user data, or any
  identifier.
- **No operator, model-endpoint, key, or provider identifiers.** No endpoint
  URL, API key, or provider account appears here or anywhere in the pack. The
  upstream router reads `ANTHROPIC_API_KEY` from the environment at call time;
  this eval touches no network and needs no key.

## Difficulty band, capabilities, and costs are illustrative

The `max_difficulty` bands, per-tier capability sets, and `cost` weights in
`tiers.json` are illustrative constructs authored only to exercise the tier,
escalation, cost-efficiency, and privacy-misroute metrics. They are not
operational thresholds, calibration values, or routing rules for any real
system, and must not be relied on as such. The `frontier` tier is the only
`net != none` tier and is treated as misroute-sensitive: a privacy-flagged task
must never be routed there.

## No field-source leakage

This pack was authored from a synthetic, generic construction plus the public
documented contract of the in-workspace hybrid-dispatch router only. It does not
incorporate any real routing configuration, production model roster, cost sheet,
or quantitative routing outcome. No before/after routing-quality figure appears
anywhere in this pack.
