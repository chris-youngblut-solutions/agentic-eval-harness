"""Deterministic loader for the synthetic compliance-rule taxonomy
(fixtures/fintech_compliance/rules.json) and the committed JSONL fixtures.

The rule set is a FABRICATED, GENERIC taxonomy: each rule keys on abstract
MARKER tokens (e.g. ``MARKER_SANCTIONS_HIT``), never on real customer, account,
or transaction data. A case record is "matched" to a rule by deterministic
substring detection of that rule's marker tokens — there is no model and no real
screening engine. That marker-match property is what lets the synthetic corpus
carry a *computed* ground truth: every record is authored to contain exactly the
marker(s) of its gold rule, so the expected disposition is known by construction.

`escalate` is the high-severity, leakage-sensitive disposition (route to a human
compliance officer): records whose gold disposition is ``reject`` or ``escalate``
must never be ``approve``d. Approving such a record is a compliance violation —
the leakage-sensitive failure this pack guards.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agentic_eval.domain import ROOT

FIXTURES = ROOT / "fixtures" / "fintech_compliance"
RULES_PATH = FIXTURES / "rules.json"

Disposition = str  # "approve" | "reject" | "escalate"

# dispositions that must never be downgraded to approve — the leakage-sensitive set.
# Approving a reject/escalate record is the compliance violation this pack guards.
ENFORCED_DISPOSITIONS: frozenset[str] = frozenset({"reject", "escalate"})


@dataclass(frozen=True)
class Rule:
    id: str
    name: str
    markers: tuple[str, ...]
    disposition: Disposition
    severity: str


@dataclass(frozen=True)
class CaseRecord:
    id: str
    text: str
    gold_rule: str
    gold_disposition: Disposition


@dataclass(frozen=True)
class AccessRequest:
    id: str
    role: str
    resource: str
    gold_grant: bool


@dataclass(frozen=True)
class AuditEvent:
    id: str
    gold_complete: bool


@dataclass(frozen=True)
class RuleSet:
    rules: tuple[Rule, ...]

    def by_id(self, rule_id: str) -> Rule:
        for rule in self.rules:
            if rule.id == rule_id:
                return rule
        raise KeyError(f"unknown rule {rule_id!r}")

    @property
    def rule_ids(self) -> tuple[str, ...]:
        return tuple(rule.id for rule in self.rules)

    def match(self, text: str) -> Rule | None:
        """Return the rule whose marker token appears in ``text``.

        Deterministic: scans rules in declared order and returns the first whose
        marker is a substring of the record text. Returns ``None`` when no marker
        matches (treated as clear / approvable-by-default upstream).
        """
        for rule in self.rules:
            if any(marker in text for marker in rule.markers):
                return rule
        return None


def _rule_from_raw(raw: dict[str, Any]) -> Rule:
    return Rule(
        id=str(raw["id"]),
        name=str(raw["name"]),
        markers=tuple(str(m) for m in raw["markers"]),
        disposition=str(raw["disposition"]),
        severity=str(raw["severity"]),
    )


def load_rules(path: Path = RULES_PATH) -> RuleSet:
    """Load the synthetic compliance-rule taxonomy."""
    raw: dict[str, Any] = json.loads(path.read_text())
    return RuleSet(rules=tuple(_rule_from_raw(r) for r in raw["rules"]))


def _read_jsonl(name: str) -> list[dict[str, Any]]:
    path = FIXTURES / name
    if not path.is_file():
        raise FileNotFoundError(f"no such fixture: {name!r}")
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def load_records(path: Path | None = None) -> dict[str, CaseRecord]:
    """Load labeled KYC/AML case records, keyed by id."""
    rows = (
        [json.loads(line) for line in path.read_text().splitlines() if line]
        if path is not None
        else _read_jsonl("records.jsonl")
    )
    items = [
        CaseRecord(
            id=str(r["id"]),
            text=str(r["text"]),
            gold_rule=str(r["gold_rule"]),
            gold_disposition=str(r["gold_disposition"]),
        )
        for r in rows
    ]
    return {item.id: item for item in items}


def load_access(path: Path | None = None) -> dict[str, AccessRequest]:
    """Load labeled access-control requests, keyed by id."""
    rows = (
        [json.loads(line) for line in path.read_text().splitlines() if line]
        if path is not None
        else _read_jsonl("access.jsonl")
    )
    reqs = [
        AccessRequest(
            id=str(r["id"]),
            role=str(r["role"]),
            resource=str(r["resource"]),
            gold_grant=bool(r["gold_grant"]),
        )
        for r in rows
    ]
    return {a.id: a for a in reqs}


def load_audit(path: Path | None = None) -> dict[str, AuditEvent]:
    """Load labeled audit-trail events (for the audit-completeness metric), keyed by id."""
    rows = (
        [json.loads(line) for line in path.read_text().splitlines() if line]
        if path is not None
        else _read_jsonl("audit.jsonl")
    )
    events = [AuditEvent(id=str(r["id"]), gold_complete=bool(r["gold_complete"])) for r in rows]
    return {e.id: e for e in events}


def load_acl(path: Path = FIXTURES / "acl.json") -> dict[str, list[str]]:
    """Load the synthetic role -> allowed-resources access-control matrix.

    Returns ``{role: [resource, ...]}``. The authorization rule is least-privilege:
    a request is granted iff its resource is in its role's allowed set.
    """
    raw: dict[str, Any] = json.loads(path.read_text())
    out: dict[str, list[str]] = {}
    for role, resources in raw["roles"].items():
        out[str(role)] = [str(res) for res in resources]
    return out
