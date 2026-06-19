"""Deterministic routing-policy model for the routing domain.

This is the domain's *answer key*: a pure, offline reimplementation of a
documented two-lane (``local`` | ``frontier``) dispatch contract, extended to
three tiers (``edge`` | ``local`` | ``frontier``) by adding an on-device
``edge`` tier below ``local``.

Everything is FABRICATED and GENERIC: the tier roster, capability sets,
difficulty band, and cost weights (``fixtures/routing/tiers.json``) are
illustrative constructs authored to exercise the eval metrics. No real routing
table, model roster, cost sheet, or capability matrix is reproduced.

Rule order (mirrors the dispatch contract's decide order, first match wins):

1. **privacy** → the cheapest *capable* tier whose ``net == "none"``; the
   frontier (net) arm is *never* selected for a privacy-flagged task. This is
   the hard, must-not-misroute guarantee.
2. **capability-miss** → the cheapest tier whose capability set is a superset of
   the required capabilities (escalating upward; ``frontier`` is the ceiling).
3. **difficulty** → the cheapest *capable* tier whose ``max_difficulty`` admits
   the task's difficulty.
4. **cost tiebreak** → among the still-eligible capable tiers, the cheapest.

Privacy is evaluated **before** capability and difficulty on purpose: a
privacy-flagged task stays off the net even when it is hard or needs a
capability only the frontier tier has — exactly as the reference contract pins a
privacy request local even on a capability-miss.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agentic_eval.domain import ROOT

FIXTURES = ROOT / "fixtures" / "routing"
TIERS_PATH = FIXTURES / "tiers.json"

# Tiers whose traffic leaves the box. A privacy-flagged task must never route to
# one of these — the leakage-sensitive (must-not-misroute) set.
NET_TIERS: frozenset[str] = frozenset({"frontier"})


@dataclass(frozen=True)
class Tier:
    id: str
    name: str
    capabilities: frozenset[str]
    max_difficulty: float
    cost: float
    net: str  # "none" | "frontier"

    @property
    def is_net(self) -> bool:
        return self.net != "none"

    def satisfies(self, required: frozenset[str]) -> bool:
        return required <= self.capabilities

    def admits_difficulty(self, difficulty: float) -> bool:
        return difficulty <= self.max_difficulty + 1e-9


@dataclass(frozen=True)
class TierTable:
    """The ordered tier roster, cheapest first (edge, local, frontier)."""

    tiers: tuple[Tier, ...]

    def by_id(self, tier_id: str) -> Tier:
        for tier in self.tiers:
            if tier.id == tier_id:
                return tier
        raise KeyError(f"unknown tier {tier_id!r}")

    @property
    def tier_ids(self) -> tuple[str, ...]:
        return tuple(t.id for t in self.tiers)

    def capable(self, required: frozenset[str]) -> tuple[Tier, ...]:
        """Tiers that satisfy the required capabilities, cheapest first."""
        return tuple(t for t in self.tiers if t.satisfies(required))


@dataclass(frozen=True)
class RoutingTask:
    """A unit of routable work + the gold expected tier (computed by the model)."""

    id: str
    description: str
    difficulty: float
    required_capabilities: frozenset[str]
    privacy: bool
    gold_tier: str


def _tier_from_raw(raw: dict[str, Any]) -> Tier:
    return Tier(
        id=str(raw["id"]),
        name=str(raw["name"]),
        capabilities=frozenset(str(c) for c in raw["capabilities"]),
        max_difficulty=float(raw["max_difficulty"]),
        cost=float(raw["cost"]),
        net=str(raw["net"]),
    )


def load_tiers(path: Path = TIERS_PATH) -> TierTable:
    """Load the synthetic tier table (cheapest first)."""
    raw: dict[str, Any] = json.loads(path.read_text())
    return TierTable(tiers=tuple(_tier_from_raw(t) for t in raw["tiers"]))


def load_tasks(path: Path | None = None) -> dict[str, RoutingTask]:
    """Load labeled routing tasks, keyed by id."""
    tasks_path = path if path is not None else FIXTURES / "tasks.jsonl"
    if not tasks_path.is_file():
        raise FileNotFoundError(f"no such fixture: {tasks_path}")
    tasks: dict[str, RoutingTask] = {}
    for line in tasks_path.read_text().splitlines():
        if not line:
            continue
        r = json.loads(line)
        task = RoutingTask(
            id=str(r["id"]),
            description=str(r["description"]),
            difficulty=float(r["difficulty"]),
            required_capabilities=frozenset(str(c) for c in r["required_capabilities"]),
            privacy=bool(r["privacy"]),
            gold_tier=str(r["gold_tier"]),
        )
        tasks[task.id] = task
    return tasks


def decide_tier(
    table: TierTable,
    difficulty: float,
    required_capabilities: frozenset[str],
    privacy: bool,
) -> str:
    """Compute the gold tier for a task, mirroring the dispatch contract's rule order.

    Pure and deterministic — the answer key for every routing case. Raises
    :class:`ValueError` for an out-of-range difficulty (the contract requires
    difficulty in [0, 1]) or a capability no tier can satisfy.
    """
    if not 0.0 <= difficulty <= 1.0:
        raise ValueError(f"difficulty must be in [0, 1]; got {difficulty}")

    required = frozenset(required_capabilities)
    capable = table.capable(required)
    if not capable:
        # No tier (not even frontier) satisfies — a malformed task, surfaced
        # rather than silently mis-routed.
        raise ValueError(f"no tier satisfies required capabilities {sorted(required)}")

    # Rule 1 — privacy pins to the cheapest capable NON-net tier; the net
    # (frontier) arm is never an option for a privacy-flagged task.
    if privacy:
        for tier in capable:
            if not tier.is_net:
                return tier.id
        # Every capable tier is a net tier: the only honest answer is that the
        # task cannot be served privately. Surface it (never silently leak).
        raise ValueError(
            "privacy-flagged task needs a capability only a net tier provides; "
            "cannot route privately without leaking"
        )

    # Rules 2+3+4 — among capable tiers (cheapest first), pick the cheapest that
    # also admits the difficulty; if none admits it, escalate to the most-capable
    # (frontier) tier, whose max_difficulty is the ceiling.
    for tier in capable:
        if tier.admits_difficulty(difficulty):
            return tier.id
    # Difficulty exceeds every cheaper capable tier's band → the priciest capable
    # tier (the cost-tiebreak/ escalation ceiling).
    return capable[-1].id
