"""The dimension library: named, reusable scorers a domain pack can compose.

The engine ships mechanical *checkers* (numeric / exact / regex / set-F1, in
``cases.py``) that grade a single submitted answer. A *dimension* is the next
layer up: a pure, named scoring primitive over the structured evidence of a run
— the retrieved ids, the tools called, the citations made — that several domain
packs share. It is to eval scoring what a SQL spine is to data access: every
pack expresses its quality bar by *composing* these primitives instead of
hand-rolling precision/recall/MRR each time.

Three families, all pure and deterministic (no model, no I/O):

- **retrieval quality** — ``precision`` / ``recall`` / ``f1`` over a result set,
  and the rank-aware ``mrr`` / ``average_precision`` / ``ndcg`` over a ranked
  list. ``retrieval_scores`` rolls the lot into one :class:`RetrievalScores`.
- **tool-use correctness** — ``tool_exact_match`` / ``tool_recall`` /
  ``tool_precision`` over the called-tool set, and ``tool_order_match`` for
  whether the expected tools appear as an ordered subsequence of the calls.
- **grounding / citation** — ``citation_grounding`` (are the cited ids drawn
  only from the allowed supporting set — i.e. no fabricated citations),
  ``citation_coverage`` (were the required supporting ids cited), and the
  boolean ``is_grounded`` gate that combines them.

Every function takes plain Python collections so a pack can feed them from a
parsed answer, a tool transcript, or a fixture without importing the engine's
agent types. The two-empty-sets convention matches ``cases.set_f1``: an empty
prediction against an empty gold *agrees* (1.0).
"""

from __future__ import annotations

import math
from collections.abc import Hashable, Iterable, Sequence

from pydantic import BaseModel

__all__ = [
    "RetrievalScores",
    "average_precision",
    "citation_coverage",
    "citation_grounding",
    "f1",
    "is_grounded",
    "mrr",
    "ndcg",
    "precision",
    "recall",
    "retrieval_scores",
    "tool_exact_match",
    "tool_order_match",
    "tool_precision",
    "tool_recall",
]


# --- set-based retrieval quality -------------------------------------------


def precision(predicted: Iterable[Hashable], relevant: Iterable[Hashable]) -> float:
    """Fraction of predicted items that are relevant.

    An empty prediction scores 1.0 only when nothing was relevant (vacuously
    perfect); otherwise an empty prediction scores 0.0.
    """
    pred, rel = set(predicted), set(relevant)
    if not pred:
        return 1.0 if not rel else 0.0
    return len(pred & rel) / len(pred)


def recall(predicted: Iterable[Hashable], relevant: Iterable[Hashable]) -> float:
    """Fraction of relevant items that were predicted.

    An empty relevant set scores 1.0 (there was nothing to recall).
    """
    pred, rel = set(predicted), set(relevant)
    if not rel:
        return 1.0
    return len(pred & rel) / len(rel)


def f1(predicted: Iterable[Hashable], relevant: Iterable[Hashable]) -> float:
    """Harmonic mean of :func:`precision` and :func:`recall`.

    Two empty sets agree (1.0); a non-empty prediction against an empty gold (or
    vice versa) disagree (0.0). Matches ``cases.set_f1`` semantics.
    """
    pred, rel = set(predicted), set(relevant)
    if not pred and not rel:
        return 1.0
    true_positives = len(pred & rel)
    if true_positives == 0:
        return 0.0
    p = true_positives / len(pred)
    r = true_positives / len(rel)
    return 2 * p * r / (p + r)


# --- rank-aware retrieval quality ------------------------------------------


def mrr(ranked: Sequence[Hashable], relevant: Iterable[Hashable]) -> float:
    """Reciprocal rank of the first relevant item in ``ranked`` (1-indexed).

    0.0 when no relevant item appears. This is the single-query reciprocal rank;
    average it across queries for the Mean Reciprocal Rank.
    """
    rel = set(relevant)
    for index, item in enumerate(ranked, start=1):
        if item in rel:
            return 1.0 / index
    return 0.0


def average_precision(ranked: Sequence[Hashable], relevant: Iterable[Hashable]) -> float:
    """Average precision: mean of the precision@k taken at each relevant hit.

    Rewards ranking relevant items early. An empty relevant set scores 1.0.
    Duplicates in ``ranked`` are counted only once (first occurrence).
    """
    rel = set(relevant)
    if not rel:
        return 1.0
    hits = 0
    seen: set[Hashable] = set()
    precision_sum = 0.0
    for index, item in enumerate(ranked, start=1):
        if item in rel and item not in seen:
            hits += 1
            precision_sum += hits / index
        seen.add(item)
    if hits == 0:
        return 0.0
    return precision_sum / len(rel)


def ndcg(ranked: Sequence[Hashable], relevant: Iterable[Hashable]) -> float:
    """Normalized DCG with binary relevance over the ranked list.

    Uses the log2(rank+1) discount; the ideal ranking places every relevant item
    first. An empty relevant set scores 1.0. Duplicates count once.
    """
    rel = set(relevant)
    if not rel:
        return 1.0
    dcg = 0.0
    seen: set[Hashable] = set()
    for index, item in enumerate(ranked, start=1):
        if item in rel and item not in seen:
            dcg += 1.0 / math.log2(index + 1)
        seen.add(item)
    ideal_n = min(len(rel), len({*ranked}))
    if ideal_n == 0:
        return 0.0
    idcg = sum(1.0 / math.log2(i + 1) for i in range(1, ideal_n + 1))
    return dcg / idcg


class RetrievalScores(BaseModel):
    """The full retrieval-quality vector for one ranked result against a gold set."""

    precision: float
    recall: float
    f1: float
    mrr: float
    average_precision: float
    ndcg: float


def retrieval_scores(ranked: Sequence[Hashable], relevant: Iterable[Hashable]) -> RetrievalScores:
    """Compute every retrieval dimension at once over a ranked result list.

    The set metrics ignore order; the rank-aware ones honor it — so a pack can
    pick whichever bar it wants (e.g. gate on ``recall``, report ``mrr``).
    """
    rel = set(relevant)
    return RetrievalScores(
        precision=precision(ranked, rel),
        recall=recall(ranked, rel),
        f1=f1(ranked, rel),
        mrr=mrr(ranked, rel),
        average_precision=average_precision(ranked, rel),
        ndcg=ndcg(ranked, rel),
    )


# --- tool-use correctness --------------------------------------------------


def tool_exact_match(called: Iterable[str], expected: Iterable[str]) -> bool:
    """True iff the *set* of called tools equals the expected set (order-free)."""
    return set(called) == set(expected)


def tool_recall(called: Iterable[str], expected: Iterable[str]) -> float:
    """Fraction of expected tools that were called (right plan coverage)."""
    return recall(called, expected)


def tool_precision(called: Iterable[str], expected: Iterable[str]) -> float:
    """Fraction of called tools that were expected (penalizes extraneous calls)."""
    return precision(called, expected)


def tool_order_match(called: Sequence[str], expected: Sequence[str]) -> bool:
    """True iff ``expected`` appears as an ordered (not necessarily contiguous)
    subsequence of ``called``.

    Lets a pack assert "the agent looked up the policy *before* it classified"
    without demanding the agent make *no other* calls in between. An empty
    expected sequence is trivially satisfied.
    """
    it = iter(called)
    return all(any(step == call for call in it) for step in expected)


# --- grounding / citation --------------------------------------------------


def citation_grounding(cited: Iterable[Hashable], supporting: Iterable[Hashable]) -> float:
    """Fraction of the agent's citations that are real supporting sources.

    Answers "of the ids the agent cited, what fraction are drawn from the allowed
    supporting set?" — i.e. 1.0 means no fabricated/hallucinated citation. Citing
    nothing is vacuously grounded (1.0): there is no hallucinated citation to
    penalize. (This is citation precision but with the *no-citations* case scored
    as perfect rather than the retrieval-precision 0.0 — grounding asks about the
    citations that exist, not about coverage.)
    """
    cite = set(cited)
    if not cite:
        return 1.0
    return len(cite & set(supporting)) / len(cite)


def citation_coverage(cited: Iterable[Hashable], required: Iterable[Hashable]) -> float:
    """Recall of citations against the set of sources that *should* be cited.

    Answers "of the sources needed to support this answer, what fraction did the
    agent actually cite?" No required sources → 1.0.
    """
    return recall(cited, required)


def is_grounded(
    cited: Iterable[Hashable],
    supporting: Iterable[Hashable],
    required: Iterable[Hashable] | None = None,
    *,
    min_grounding: float = 1.0,
    min_coverage: float = 1.0,
) -> bool:
    """Boolean grounding gate: no hallucinated citations and (optionally) full
    coverage of the required sources.

    ``min_grounding`` bounds :func:`citation_grounding` (default 1.0 = zero
    fabricated cites). When ``required`` is given, ``min_coverage`` bounds
    :func:`citation_coverage` (default 1.0 = every required source cited). A pack
    can loosen either bound to allow partial grounding.
    """
    grounded = citation_grounding(cited, supporting) >= min_grounding - 1e-9
    if required is None:
        return grounded
    covered = citation_coverage(cited, required) >= min_coverage - 1e-9
    return grounded and covered
