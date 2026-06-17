"""Deterministic synthetic-corpus generator for the trust_safety domain.

Everything here is FABRICATED and GENERIC. Content items are benign fabricated
sentences carrying abstract MARKER tokens (e.g. ``MARKER_BULK_PROMO``); no real
harmful content, no real platform policy, no real moderation case is reproduced.
Each item is authored to contain exactly the marker(s) of its gold category, so
the expected classification + action is known by construction (the policy is the
answer key). There is no randomness: re-running reproduces byte-identical
fixtures (a test guards this). Run as a module to (re)write the committed
fixtures:

    uv run python -m agentic_eval.domains.trust_safety.generate

Fixtures written under fixtures/trust_safety/:
- content.jsonl   labeled items {id, text, gold_category, gold_action}. The text
                  is a benign filler sentence that embeds the gold category's
                  marker token(s). Includes BENIGN (allow) items.
- appeals.jsonl   {id, content_id, gold_overturn}: some correct removals (uphold)
                  and some wrong removals (overturn).
- misfires.jsonl  {id, gold_rca_class} across three fabricated root-cause classes
                  (policy_gap, classifier_threshold, label_ambiguity).
- qc.json         two synthetic rater label sets over a shared item set, for the
                  inter-rater agreement metric.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agentic_eval.domains.trust_safety import policy

FIXTURES = policy.FIXTURES

# Benign filler so the item text reads like a sentence; the MARKER token is what
# the deterministic classifier keys on. No real harmful content appears.
_FILLER = "Fabricated sample item for eval; benign filler text. Token:"


def _item(item_id: str, marker: str, category: str, action: str) -> dict[str, Any]:
    return {
        "id": item_id,
        "text": f"{_FILLER} {marker} end.",
        "gold_category": category,
        "gold_action": action,
    }


def build_content() -> list[dict[str, Any]]:
    """Labeled content items. Marker → (category, action) by the policy."""
    return [
        # benign / allow
        _item("c-01", "MARKER_BENIGN", "BENIGN", "allow"),
        _item("c-02", "MARKER_BENIGN", "BENIGN", "allow"),
        _item("c-03", "MARKER_BENIGN", "BENIGN", "allow"),
        # spam / remove
        _item("c-04", "MARKER_BULK_PROMO", "SPAM", "remove"),
        _item("c-05", "MARKER_LINK_FARM", "SPAM", "remove"),
        # harassment / remove
        _item("c-06", "MARKER_TARGETED_INSULT", "HARASSMENT", "remove"),
        _item("c-07", "MARKER_PILE_ON", "HARASSMENT", "remove"),
        # graphic violence / remove (high severity)
        _item("c-08", "MARKER_GORE", "GRAPHIC_VIOLENCE", "remove"),
        _item("c-09", "MARKER_VIOLENT_THREAT", "GRAPHIC_VIOLENCE", "remove"),
        # misinformation / remove
        _item("c-10", "MARKER_FALSE_CLAIM", "MISINFO", "remove"),
        _item("c-11", "MARKER_COORDINATED", "MISINFO", "remove"),
        # self-harm / escalate (high severity, leakage-sensitive)
        _item("c-12", "MARKER_CRISIS", "SELF_HARM", "escalate"),
        _item("c-13", "MARKER_SELF_HARM", "SELF_HARM", "escalate"),
    ]


def build_appeals() -> list[dict[str, Any]]:
    """Appeals over prior removals. gold_overturn=True means the removal was wrong."""
    return [
        # correct removals -> uphold (overturn=false)
        {"id": "a-01", "content_id": "c-04", "gold_overturn": False},
        {"id": "a-02", "content_id": "c-08", "gold_overturn": False},
        {"id": "a-03", "content_id": "c-10", "gold_overturn": False},
        # wrong removals -> overturn (overturn=true)
        {"id": "a-04", "content_id": "c-01", "gold_overturn": True},
        {"id": "a-05", "content_id": "c-02", "gold_overturn": True},
    ]


def build_misfires() -> list[dict[str, Any]]:
    """Labeled misfires across three fabricated root-cause classes."""
    return [
        {"id": "m-01", "gold_rca_class": "policy_gap"},
        {"id": "m-02", "gold_rca_class": "policy_gap"},
        {"id": "m-03", "gold_rca_class": "classifier_threshold"},
        {"id": "m-04", "gold_rca_class": "classifier_threshold"},
        {"id": "m-05", "gold_rca_class": "label_ambiguity"},
        {"id": "m-06", "gold_rca_class": "label_ambiguity"},
    ]


def build_qc() -> dict[str, Any]:
    """Two synthetic rater label sets over a shared 10-item set.

    Raters agree on 8 of 10 items -> 80% raw inter-rater agreement.
    """
    items = [f"q-{i:02d}" for i in range(1, 11)]
    labels = ["BENIGN", "SPAM", "HARASSMENT", "MISINFO", "BENIGN", "SPAM", "BENIGN", "MISINFO"]
    rater_a = dict(zip(items, [*labels, "BENIGN", "SPAM"], strict=True))
    # rater_b disagrees on the last two items only
    rater_b = dict(zip(items, [*labels, "SPAM", "HARASSMENT"], strict=True))
    return {"items": items, "rater_sets": {"set_a": rater_a, "set_b": rater_b}}


def write_corpus(out_dir: Path = FIXTURES) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    jsonl = {
        "content.jsonl": build_content(),
        "appeals.jsonl": build_appeals(),
        "misfires.jsonl": build_misfires(),
    }
    for name, rows in jsonl.items():
        (out_dir / name).write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in rows))
    (out_dir / "qc.json").write_text(json.dumps(build_qc(), indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    write_corpus()
    print(f"wrote corpus to {FIXTURES}")
