"""Deterministic synthetic task-corpus generator for the routing domain.

Everything here is FABRICATED and GENERIC. Each task is a synthetic routable
unit of work described by three inputs — ``difficulty`` in ``[0, 1]``, a set of
``required_capabilities``, and a ``privacy`` flag — and its gold tier is
*computed* by the routing-policy model (``policy.decide_tier``), not asserted by
hand: the tier table is the answer key. There is no randomness; re-running
reproduces byte-identical fixtures (a test guards this). Run as a module to
(re)write the committed corpus:

    uv run python -m agentic_eval.domains.routing.generate

Fixture written under fixtures/routing/:
- tasks.jsonl   labeled tasks {id, description, difficulty, required_capabilities,
                privacy, gold_tier}. gold_tier is derived from the tier table.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agentic_eval.domains.routing import policy

FIXTURES = policy.FIXTURES

# (id, description, difficulty, required_capabilities, privacy)
# Descriptions are benign synthetic task summaries. The three routing inputs are
# what the policy keys on; gold_tier is computed below.
_TASKS: list[tuple[str, str, float, list[str], bool]] = [
    # --- easy, edge-capable -> edge (cheapest tier that satisfies + admits) ---
    (
        "t-01",
        "Classify a short synthetic log line into one of three buckets.",
        0.10,
        ["classify"],
        False,
    ),
    (
        "t-02",
        "Extract a fabricated order id from a one-line synthetic message.",
        0.15,
        ["extract"],
        False,
    ),
    ("t-03", "Answer a trivial synthetic chat prompt with a single token.", 0.05, ["chat"], False),
    # --- medium difficulty, edge-capable cap but over edge's band -> local ---
    ("t-04", "Classify a longer synthetic record; medium difficulty.", 0.45, ["classify"], False),
    (
        "t-05",
        "Summarize a synthetic paragraph (summarize not on edge) -> local.",
        0.30,
        ["summarize"],
        False,
    ),
    (
        "t-06",
        "Rerank a small synthetic candidate list (rerank not on edge) -> local.",
        0.50,
        ["rerank"],
        False,
    ),
    # --- hard difficulty, locally-capable cap but over local's band -> frontier ---
    (
        "t-07",
        "Summarize a hard synthetic passage; difficulty over local's band.",
        0.80,
        ["summarize"],
        False,
    ),
    (
        "t-08",
        "Classify a very hard synthetic item; difficulty over local's band.",
        0.90,
        ["classify"],
        False,
    ),
    # --- capability-miss: needs a frontier-only capability -> frontier ---
    (
        "t-09",
        "Describe a synthetic image (vision is frontier-only) -> frontier.",
        0.20,
        ["vision"],
        False,
    ),
    (
        "t-10",
        "Run a synthetic multi-tool plan (tool_use is frontier-only) -> frontier.",
        0.40,
        ["tool_use"],
        False,
    ),
    (
        "t-11",
        "Process a synthetic long-context doc (long_context frontier-only) -> frontier.",
        0.55,
        ["long_context"],
        False,
    ),
    # --- privacy hard cases: must NEVER route frontier (the must-not-misroute gate) ---
    # privacy + edge-capable + easy -> edge (cheapest non-net capable)
    (
        "t-12",
        "PRIVACY: classify a sensitive synthetic record on-box only.",
        0.10,
        ["classify"],
        True,
    ),
    # privacy + needs summarize (not on edge) -> local (still non-net)
    (
        "t-13",
        "PRIVACY: summarize a sensitive synthetic note on-box only.",
        0.30,
        ["summarize"],
        True,
    ),
    # privacy + HARD (difficulty over local band) but private -> still local, NOT frontier
    (
        "t-14",
        "PRIVACY: hard synthetic summarize task, but privacy pins it local.",
        0.95,
        ["summarize"],
        True,
    ),
    # privacy + capability the local tier HAS but is hard -> local, never frontier
    (
        "t-15",
        "PRIVACY: hard synthetic rerank, privacy pins it local not frontier.",
        0.88,
        ["rerank"],
        True,
    ),
    # --- multi-capability, non-private ---
    (
        "t-16",
        "Synthetic task needing chat+classify+extract, easy -> edge.",
        0.20,
        ["chat", "classify", "extract"],
        False,
    ),
    (
        "t-17",
        "Synthetic task needing classify+summarize, medium -> local.",
        0.40,
        ["classify", "summarize"],
        False,
    ),
    (
        "t-18",
        "Synthetic task needing summarize+vision -> frontier (vision-miss).",
        0.30,
        ["summarize", "vision"],
        False,
    ),
]


def build_tasks() -> list[dict[str, Any]]:
    """Labeled tasks with gold_tier computed by the policy model (the answer key)."""
    table = policy.load_tiers()
    rows: list[dict[str, Any]] = []
    for task_id, desc, difficulty, caps, privacy in _TASKS:
        required = frozenset(caps)
        gold = policy.decide_tier(table, difficulty, required, privacy)
        rows.append(
            {
                "id": task_id,
                "description": desc,
                "difficulty": difficulty,
                # sorted for byte-stable output
                "required_capabilities": sorted(required),
                "privacy": privacy,
                "gold_tier": gold,
            }
        )
    return rows


def write_corpus(out_dir: Path = FIXTURES) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = build_tasks()
    (out_dir / "tasks.jsonl").write_text(
        "".join(json.dumps(r, sort_keys=True) + "\n" for r in rows)
    )


if __name__ == "__main__":
    write_corpus()
    print(f"wrote corpus to {FIXTURES}")
