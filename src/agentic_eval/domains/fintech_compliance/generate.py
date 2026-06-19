"""Deterministic synthetic-corpus generator for the fintech_compliance domain.

Everything here is FABRICATED and GENERIC. Case records are benign fabricated
sentences carrying abstract MARKER tokens (e.g. ``MARKER_SANCTIONS_HIT``); no real
customer, account, transaction, or PII data, no real sanctions list, and no real
financial system is reproduced. Each record is authored to contain exactly the
marker(s) of its gold rule, so the expected disposition is known by construction
(the rule set is the answer key). There is no randomness: re-running reproduces
byte-identical fixtures (a test guards this). Run as a module to (re)write the
committed fixtures:

    uv run python -m agentic_eval.domains.fintech_compliance.generate

Fixtures written under fixtures/fintech_compliance/:
- records.jsonl   labeled KYC/AML records {id, text, gold_rule, gold_disposition}.
                  The text is a benign filler sentence embedding the gold rule's
                  marker token(s). Includes CLEAR (approve) records.
- access.jsonl    {id, role, resource, gold_grant}: least-privilege access requests,
                  some authorized and some not.
- audit.jsonl     {id, gold_complete}: audit-trail events, some complete and some
                  with a missing required field.
- acl.json        the synthetic role -> allowed-resources access-control matrix.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agentic_eval.domains.fintech_compliance import rules

FIXTURES = rules.FIXTURES

# Benign filler so the record text reads like a sentence; the MARKER token is what
# the deterministic screener keys on. No real customer or transaction data appears.
_FILLER = "Fabricated sample case record for eval; benign filler text. Token:"


def _record(record_id: str, marker: str, rule: str, disposition: str) -> dict[str, Any]:
    return {
        "id": record_id,
        "text": f"{_FILLER} {marker} end.",
        "gold_rule": rule,
        "gold_disposition": disposition,
    }


def build_records() -> list[dict[str, Any]]:
    """Labeled KYC/AML case records. Marker -> (rule, disposition) by the rule set."""
    return [
        # clear / approve
        _record("r-01", "MARKER_CLEAR", "CLEAR", "approve"),
        _record("r-02", "MARKER_CLEAR", "CLEAR", "approve"),
        _record("r-03", "MARKER_CLEAR", "CLEAR", "approve"),
        # KYC unverified / reject
        _record("r-04", "MARKER_UNVERIFIED_ID", "KYC_UNVERIFIED", "reject"),
        _record("r-05", "MARKER_STALE_KYC", "KYC_UNVERIFIED", "reject"),
        # AML structuring / reject
        _record("r-06", "MARKER_STRUCTURING", "AML_PATTERN", "reject"),
        _record("r-07", "MARKER_RAPID_MOVEMENT", "AML_PATTERN", "reject"),
        # PEP exposure / escalate (high severity, leakage-sensitive)
        _record("r-08", "MARKER_PEP_EXPOSURE", "PEP", "escalate"),
        _record("r-09", "MARKER_PEP_FAMILY", "PEP", "escalate"),
        # sanctions hit / escalate (high severity, leakage-sensitive)
        _record("r-10", "MARKER_SANCTIONS_HIT", "SANCTIONS", "escalate"),
        _record("r-11", "MARKER_WATCHLIST", "SANCTIONS", "escalate"),
        # high-risk jurisdiction / reject
        _record("r-12", "MARKER_HIGH_RISK_GEO", "HIGH_RISK_GEO", "reject"),
        _record("r-13", "MARKER_HIGH_RISK_GEO", "HIGH_RISK_GEO", "reject"),
    ]


def build_access() -> list[dict[str, Any]]:
    """Access-control requests under least-privilege. gold_grant=True means authorized."""
    return [
        # authorized -> grant (resource in role's allowed set)
        {"id": "ac-01", "role": "analyst", "resource": "case_records", "gold_grant": True},
        {"id": "ac-02", "role": "officer", "resource": "sar_filings", "gold_grant": True},
        {"id": "ac-03", "role": "auditor", "resource": "audit_log", "gold_grant": True},
        # unauthorized -> deny (resource not in role's allowed set)
        {"id": "ac-04", "role": "analyst", "resource": "sar_filings", "gold_grant": False},
        {"id": "ac-05", "role": "auditor", "resource": "case_records", "gold_grant": False},
    ]


def build_audit() -> list[dict[str, Any]]:
    """Audit-trail events; gold_complete=False means a required field is missing."""
    return [
        {"id": "au-01", "gold_complete": True},
        {"id": "au-02", "gold_complete": True},
        {"id": "au-03", "gold_complete": True},
        {"id": "au-04", "gold_complete": False},
        {"id": "au-05", "gold_complete": False},
    ]


def build_acl() -> dict[str, Any]:
    """Synthetic role -> allowed-resources access-control matrix (least-privilege)."""
    return {
        "roles": {
            "analyst": ["case_records", "screening_tool"],
            "officer": ["case_records", "sar_filings", "screening_tool"],
            "auditor": ["audit_log"],
        }
    }


def write_corpus(out_dir: Path = FIXTURES) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    jsonl = {
        "records.jsonl": build_records(),
        "access.jsonl": build_access(),
        "audit.jsonl": build_audit(),
    }
    for name, rows in jsonl.items():
        (out_dir / name).write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in rows))
    (out_dir / "acl.json").write_text(json.dumps(build_acl(), indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    write_corpus()
    print(f"wrote corpus to {FIXTURES}")
