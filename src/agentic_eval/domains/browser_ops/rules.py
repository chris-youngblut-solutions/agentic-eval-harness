"""Deterministic loaders for the synthetic browser-ops policy
(fixtures/browser_ops/policy.json) and the committed JSONL corpora.

The policy is a FABRICATED, GENERIC configuration: the leakage-sensitive
side-effecting-action set, the safe confirm-dialog default, and the first-retry
response. Scalar entries are ``{token, value, unit}`` objects (the tools and
``compute`` read only the ``.value`` field); ``side_effecting_actions`` is a
string[]. The corpora are benign fabricated rows whose ids are structural MARKER
tokens by construction (``PAGE-##``, ``PORTAL-#``, ``ACT-##``), and the "URLs" are
opaque ``MARKER_URL_##`` tokens — no real portal HTML or URL appears.

``SIDE_EFFECTING_ACTIONS`` is the leakage-sensitive frozenset: action kinds that
are money-moving or irreversible, so re-executing an already-``done`` one is a
double-execute. That double-execute is the failure this pack guards with the
``idempotency_safety`` hard gate. The policy file lists the same set;
``test_policy_side_effecting_actions_match_constant`` asserts the two never drift.
See fixtures/browser_ops/PROVENANCE.md — no real portal, URL, DOM, session, or
customer data appears anywhere.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agentic_eval.domain import ROOT

FIXTURES = ROOT / "fixtures" / "browser_ops"
POLICY_PATH = FIXTURES / "policy.json"

# The leakage-sensitive money-moving / irreversible action-kind set. Re-executing
# an already-done one of these is a double-execute — the failure the idempotency
# gate guards. Kept in sync with policy.json's "side_effecting_actions" (guarded by
# test_policy_side_effecting_actions_match_constant).
SIDE_EFFECTING_ACTIONS: frozenset[str] = frozenset(
    {
        "send_chase",
        "confirm_receipt",
        "post_grn",
        "approve_invoice",
        "close_exception",
        "submit_order",
        "delete_draft",
        "cancel_order",
        "dispatch_batch",
        "issue_credit",
    }
)

# The two action states a queued action can be in. "done" means the side effect
# already fired (re-executing would repeat it); "pending" means it has not.
ACTION_STATES: frozenset[str] = frozenset({"done", "pending"})


@dataclass(frozen=True)
class Page:
    """A portal page: static structure only (selectors + the safe confirm default),
    never action state. State is read separately via the read_action_state oracle."""

    id: str
    portal_id: str
    title: str
    url_token: str
    primary_control: str
    confirm_default: str


@dataclass(frozen=True)
class Action:
    """A queued action instance on a page, with its idempotency state.

    ``kind`` is the action's semantic class (side-effecting iff it is in
    ``SIDE_EFFECTING_ACTIONS``); ``state`` is ``done`` or ``pending``.
    """

    id: str
    page_id: str
    kind: str
    state: str


@dataclass(frozen=True)
class Policy:
    side_effecting_actions: frozenset[str]
    confirm_safe_default: str
    retry_first_response: str
    raw: dict[str, Any]

    def is_side_effecting(self, kind: str) -> bool:
        return kind in self.side_effecting_actions

    def lookup(self, key: str) -> dict[str, Any]:
        """Return the configured value for a policy key as a flat dict.

        Scalar ``{token, value, unit}`` entries flatten to
        ``{key, token, value, unit, …}``; the ``side_effecting_actions`` list
        returns ``{key, value: [...]}``. Private (``_``-prefixed) and unknown keys
        raise ``KeyError``.
        """
        if key not in self.raw or key.startswith("_"):
            raise KeyError(f"unknown policy key: {key!r}")
        entry = self.raw[key]
        if isinstance(entry, dict):
            return {"key": key, **entry}
        return {"key": key, "value": entry}


def load_policy(path: Path = POLICY_PATH) -> Policy:
    """Load the synthetic browser-ops policy (side-effecting set, confirm default,
    first-retry response)."""
    raw: dict[str, Any] = json.loads(path.read_text())
    return Policy(
        side_effecting_actions=frozenset(str(a) for a in raw["side_effecting_actions"]),
        confirm_safe_default=str(raw["confirm_safe_default"]["value"]),
        retry_first_response=str(raw["retry_first_response"]["value"]),
        raw=raw,
    )


def _read_jsonl(name: str, path: Path | None) -> list[dict[str, Any]]:
    target = path if path is not None else FIXTURES / name
    if not target.is_file():
        raise FileNotFoundError(f"no such fixture: {name!r}")
    return [json.loads(line) for line in target.read_text().splitlines() if line]


def load_pages(path: Path | None = None) -> dict[str, Page]:
    """Load the portal pages, keyed by id (insertion-ordered)."""
    rows = _read_jsonl("portals.jsonl", path)
    items = [
        Page(
            id=str(r["id"]),
            portal_id=str(r["portal_id"]),
            title=str(r["title"]),
            url_token=str(r["url_token"]),
            primary_control=str(r["primary_control"]),
            confirm_default=str(r["confirm_default"]),
        )
        for r in rows
    ]
    return {item.id: item for item in items}


def load_actions(path: Path | None = None) -> dict[str, Action]:
    """Load the queued action instances (the per-action done|pending state world),
    keyed by id."""
    rows = _read_jsonl("scenarios.jsonl", path)
    items = [
        Action(
            id=str(r["id"]),
            page_id=str(r["page_id"]),
            kind=str(r["kind"]),
            state=str(r["state"]),
        )
        for r in rows
    ]
    return {item.id: item for item in items}
