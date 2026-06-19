"""Deterministic loader for the synthetic customer-support action taxonomy
(fixtures/customer_support/policy.json) and the committed JSONL fixtures.

The policy is a FABRICATED, GENERIC taxonomy: each ticket category keys on
abstract MARKER tokens (e.g. ``MARKER_REFUND``), never on real customer data. A
ticket is "matched" to a category by deterministic substring detection of that
category's marker tokens — there is no model and no real classifier. That
marker-match property is what lets the synthetic corpus carry a *computed*
ground truth: every ticket is authored to contain exactly the marker(s) of its
gold category, so the expected disposition is known by construction.

A category's ``disposition`` is one of:

- ``resolve``  — agent-assist auto-resolution (safe self-service action).
- ``deflect``  — answer with self-serve guidance; no human, no account change.
- ``escalate`` — route to a human; the agent must NOT take the account-changing
  auto-action itself.

The leakage-sensitive set is ``UNSAFE_AUTO_ACTIONS``: irreversible / high-risk
account-changing actions (issue_refund, delete_account, freeze_account). A ticket
whose gold disposition is ``escalate`` must never be auto-resolved — taking its
unsafe auto-action automatically is the must-not-happen failure this pack gates.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agentic_eval.domain import ROOT

FIXTURES = ROOT / "fixtures" / "customer_support"
POLICY_PATH = FIXTURES / "policy.json"

Disposition = str  # "resolve" | "escalate" | "deflect"

# dispositions that must be routed to a human, never auto-resolved
ESCALATE_DISPOSITIONS: frozenset[str] = frozenset({"escalate"})

# auto-actions that are irreversible / high-risk: an agent must never take these
# on its own. They are the unsafe auto-actions the hard gate guards against.
UNSAFE_AUTO_ACTIONS: frozenset[str] = frozenset(
    {"issue_refund", "delete_account", "freeze_account"}
)


@dataclass(frozen=True)
class Category:
    id: str
    name: str
    markers: tuple[str, ...]
    disposition: Disposition
    auto_action: str
    unsafe: bool


@dataclass(frozen=True)
class Ticket:
    id: str
    text: str
    gold_category: str
    gold_disposition: Disposition


@dataclass(frozen=True)
class Escalation:
    """A handled ticket appealed/reviewed for routing correctness.

    ``gold_should_escalate`` is True iff the correct routing was to a human.
    """

    id: str
    ticket_id: str
    gold_should_escalate: bool


@dataclass(frozen=True)
class Misroute:
    id: str
    gold_rca_class: str


@dataclass(frozen=True)
class Policy:
    categories: tuple[Category, ...]

    def by_id(self, category_id: str) -> Category:
        for cat in self.categories:
            if cat.id == category_id:
                return cat
        raise KeyError(f"unknown category {category_id!r}")

    @property
    def category_ids(self) -> tuple[str, ...]:
        return tuple(cat.id for cat in self.categories)

    def match(self, text: str) -> Category | None:
        """Return the category whose marker token appears in ``text``.

        Deterministic: scans categories in policy order and returns the first
        whose marker is a substring of the ticket text. Returns ``None`` when no
        marker matches (treated as unclassifiable upstream).
        """
        for cat in self.categories:
            if any(marker in text for marker in cat.markers):
                return cat
        return None


def _category_from_raw(raw: dict[str, Any]) -> Category:
    return Category(
        id=str(raw["id"]),
        name=str(raw["name"]),
        markers=tuple(str(m) for m in raw["markers"]),
        disposition=str(raw["disposition"]),
        auto_action=str(raw["auto_action"]),
        unsafe=bool(raw["unsafe"]),
    )


def load_policy(path: Path = POLICY_PATH) -> Policy:
    """Load the synthetic support action taxonomy."""
    raw: dict[str, Any] = json.loads(path.read_text())
    return Policy(categories=tuple(_category_from_raw(c) for c in raw["categories"]))


def _read_jsonl(name: str) -> list[dict[str, Any]]:
    path = FIXTURES / name
    if not path.is_file():
        raise FileNotFoundError(f"no such fixture: {name!r}")
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def load_tickets(path: Path | None = None) -> dict[str, Ticket]:
    """Load labeled support tickets, keyed by id."""
    rows = (
        [json.loads(line) for line in path.read_text().splitlines() if line]
        if path is not None
        else _read_jsonl("tickets.jsonl")
    )
    tickets = [
        Ticket(
            id=str(r["id"]),
            text=str(r["text"]),
            gold_category=str(r["gold_category"]),
            gold_disposition=str(r["gold_disposition"]),
        )
        for r in rows
    ]
    return {t.id: t for t in tickets}


def load_escalations(path: Path | None = None) -> dict[str, Escalation]:
    """Load labeled routing-review records, keyed by id."""
    rows = (
        [json.loads(line) for line in path.read_text().splitlines() if line]
        if path is not None
        else _read_jsonl("escalations.jsonl")
    )
    escalations = [
        Escalation(
            id=str(r["id"]),
            ticket_id=str(r["ticket_id"]),
            gold_should_escalate=bool(r["gold_should_escalate"]),
        )
        for r in rows
    ]
    return {e.id: e for e in escalations}


def load_misroutes(path: Path | None = None) -> dict[str, Misroute]:
    """Load labeled misroutes (for the RCA metric), keyed by id."""
    rows = (
        [json.loads(line) for line in path.read_text().splitlines() if line]
        if path is not None
        else _read_jsonl("misroutes.jsonl")
    )
    misroutes = [Misroute(id=str(r["id"]), gold_rca_class=str(r["gold_rca_class"])) for r in rows]
    return {m.id: m for m in misroutes}


def load_qc(path: Path = FIXTURES / "qc.json") -> dict[str, dict[str, str]]:
    """Load the two synthetic rater label sets over a shared ticket set.

    Returns ``{set_name: {ticket_id: disposition}}``.
    """
    raw: dict[str, Any] = json.loads(path.read_text())
    out: dict[str, dict[str, str]] = {}
    for set_name, labels in raw["rater_sets"].items():
        out[str(set_name)] = {str(k): str(v) for k, v in labels.items()}
    return out
