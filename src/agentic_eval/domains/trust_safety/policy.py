"""Deterministic loader for the synthetic content-policy taxonomy
(fixtures/trust_safety/policy.json) and the committed JSONL fixtures.

The policy is a FABRICATED, GENERIC taxonomy: each category keys on abstract
MARKER tokens (e.g. ``MARKER_BULK_PROMO``), never on real harmful content. A
content item is "matched" to a category by deterministic substring detection of
that category's marker tokens — there is no model and no real classifier. That
marker-match property is what lets the synthetic corpus carry a *computed*
ground truth: every item is authored to contain exactly the marker(s) of its
gold category, so the expected classification is known by construction.

`escalate` is the high-severity, leakage-sensitive action (route-to-support):
items whose gold action is ``remove`` or ``escalate`` must never be ALLOWed.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agentic_eval.domain import ROOT

FIXTURES = ROOT / "fixtures" / "trust_safety"
POLICY_PATH = FIXTURES / "policy.json"

Action = str  # "allow" | "remove" | "escalate"

# actions that must never be downgraded to allow — the leakage-sensitive set
ENFORCED_ACTIONS: frozenset[str] = frozenset({"remove", "escalate"})


@dataclass(frozen=True)
class Category:
    id: str
    name: str
    markers: tuple[str, ...]
    action: Action
    severity: str


@dataclass(frozen=True)
class ContentItem:
    id: str
    text: str
    gold_category: str
    gold_action: Action


@dataclass(frozen=True)
class Appeal:
    id: str
    content_id: str
    gold_overturn: bool


@dataclass(frozen=True)
class Misfire:
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
        whose marker is a substring of the item text. Returns ``None`` when no
        marker matches (treated as unclassifiable / benign-by-default upstream).
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
        action=str(raw["action"]),
        severity=str(raw["severity"]),
    )


def load_policy(path: Path = POLICY_PATH) -> Policy:
    """Load the synthetic policy taxonomy."""
    raw: dict[str, Any] = json.loads(path.read_text())
    return Policy(categories=tuple(_category_from_raw(c) for c in raw["categories"]))


def _read_jsonl(name: str) -> list[dict[str, Any]]:
    path = FIXTURES / name
    if not path.is_file():
        raise FileNotFoundError(f"no such fixture: {name!r}")
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def load_content(path: Path | None = None) -> dict[str, ContentItem]:
    """Load labeled content items, keyed by id."""
    rows = (
        [json.loads(line) for line in path.read_text().splitlines() if line]
        if path is not None
        else _read_jsonl("content.jsonl")
    )
    items = [
        ContentItem(
            id=str(r["id"]),
            text=str(r["text"]),
            gold_category=str(r["gold_category"]),
            gold_action=str(r["gold_action"]),
        )
        for r in rows
    ]
    return {item.id: item for item in items}


def load_appeals(path: Path | None = None) -> dict[str, Appeal]:
    """Load labeled appeals, keyed by id."""
    rows = (
        [json.loads(line) for line in path.read_text().splitlines() if line]
        if path is not None
        else _read_jsonl("appeals.jsonl")
    )
    appeals = [
        Appeal(
            id=str(r["id"]),
            content_id=str(r["content_id"]),
            gold_overturn=bool(r["gold_overturn"]),
        )
        for r in rows
    ]
    return {a.id: a for a in appeals}


def load_misfires(path: Path | None = None) -> dict[str, Misfire]:
    """Load labeled misfires (for the RCA metric), keyed by id."""
    rows = (
        [json.loads(line) for line in path.read_text().splitlines() if line]
        if path is not None
        else _read_jsonl("misfires.jsonl")
    )
    misfires = [Misfire(id=str(r["id"]), gold_rca_class=str(r["gold_rca_class"])) for r in rows]
    return {m.id: m for m in misfires}


def load_qc(path: Path = FIXTURES / "qc.json") -> dict[str, dict[str, str]]:
    """Load the two synthetic rater label sets over a shared item set.

    Returns ``{set_name: {item_id: label}}``.
    """
    raw: dict[str, Any] = json.loads(path.read_text())
    out: dict[str, dict[str, str]] = {}
    for set_name, labels in raw["rater_sets"].items():
        out[str(set_name)] = {str(k): str(v) for k, v in labels.items()}
    return out
