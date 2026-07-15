#!/usr/bin/env python3
"""Tests for the supplier-scorecard engine + dashboard.

Covers: engine determinism (byte-stable JSON), the full per-supplier answer key
(every one of the six KPIs for all three suppliers), a hand-computed spot aggregate
(independent of the engine's own roll-up), the composite grade + rank, the per-PO drill
atoms (including the UOM trap + damage/price cases), the committed ``scorecard.json``
regression guard, and the dashboard's self-containment (no external refs; the inlined
data equals ``scorecard.json``; ``build_view`` is idempotent).

Run from the tool dir (uses the harness venv):
    uv run pytest -q
Or standalone: ``python3 tests/test_scorecard.py``. No network, no key, stdlib only.
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path
from typing import Any

import pytest

HERE = Path(__file__).resolve().parent
TOOL = HERE.parent
sys.path.insert(0, str(TOOL))

import scorecard  # noqa: E402  -- sibling engine module, importable once TOOL is on sys.path

Record = dict[str, Any]
Card = dict[str, Any]

SCORECARD_JSON = TOOL / "scorecard.json"
VIEW_HTML = TOOL / "supplier-scorecard.inkspec.html"

# The verified answer key (reproduced from the harness compute functions).
# supplier -> (otif, fill, asn_acc, exception_rate, ded_validity, chase_resp, grade, rank)
ANSWER_KEY: dict[str, tuple[float, float, float, float, float | None, float | None, str, int]] = {
    "SUP-021": (75.0, 98.4, 75.0, 75.0, 50.0, 50.0, "B", 1),
    "SUP-023": (33.33, 93.94, 66.67, 66.67, 50.0, 0.0, "C", 2),
    "SUP-022": (66.67, 99.2, 33.33, 100.0, None, None, "D", 3),
}


@pytest.fixture(scope="module")
def corpus() -> scorecard.Corpus:
    return scorecard.load_corpus()


@pytest.fixture(scope="module")
def card(corpus: scorecard.Corpus) -> Card:
    return scorecard.compute_scorecard(corpus)


@pytest.fixture(scope="module")
def by_supplier(card: Card) -> dict[str, Record]:
    return {r["supplier"]: r for r in card["suppliers"]}


# --------------------------------------------------------------------------- #
# Determinism
# --------------------------------------------------------------------------- #


def test_engine_is_deterministic(corpus: scorecard.Corpus) -> None:
    a = scorecard.compute_scorecard(corpus)
    b = scorecard.compute_scorecard(scorecard.load_corpus())
    assert a == b
    assert scorecard.render_json(a) == scorecard.render_json(b)


def test_render_json_is_byte_stable(card: Card) -> None:
    text = scorecard.render_json(card)
    assert text.endswith("\n")
    # sorted keys => re-serializing the parsed text reproduces it byte-for-byte.
    assert scorecard.render_json(json.loads(text)) == text


# --------------------------------------------------------------------------- #
# Per-supplier answer key (all six KPIs)
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("sid", sorted(ANSWER_KEY))
def test_supplier_kpis_match_answer_key(by_supplier: dict[str, Record], sid: str) -> None:
    otif, fill, asn, exc, ded, chase, grade, rank = ANSWER_KEY[sid]
    m = by_supplier[sid]["metrics"]
    assert m["otif_pct"] == otif
    assert m["fill_pct"] == fill
    assert m["asn_accuracy_pct"] == asn
    assert m["exception_rate_pct"] == exc
    assert m["deduction_validity_pct"] == ded
    assert m["chase_responsiveness_pct"] == chase
    assert by_supplier[sid]["grade"] == grade
    assert by_supplier[sid]["rank"] == rank


def test_spot_aggregate_hand_computed(corpus: scorecard.Corpus) -> None:
    """Independent hand check of one supplier aggregate, not read from the engine roll-up.

    SUP-021 has four POs, all SKUs pack-size 12, all ordered/received in cases:
      PO-8801 100cs->1200ea recv 100cs->good 1200
      PO-8802 100cs->1200ea recv  92cs->good 1104   (short ship)
      PO-8804 200cs->2400ea recv 200cs->good 2400
      PO-8808 100cs->1200ea recv 100cs->good 1200
    good = 1200+1104+2400+1200 = 5904 ; ordered = 1200+1200+2400+1200 = 6000
    fill = 5904/6000*100 = 98.40 ; OTIF passes 3 of 4 (PO-8802 short-fills) = 75.0
    """
    sup21 = ("PO-8801", "PO-8802", "PO-8804", "PO-8808")
    good = sum(scorecard.po_otif(corpus, po)["good_ea"] for po in sup21)
    ordered = sum(scorecard.po_otif(corpus, po)["ordered_ea"] for po in sup21)
    assert good == 5904.0
    assert ordered == 6000.0
    assert round(good / ordered * 100.0, 2) == 98.4

    of = scorecard.otif_fill(corpus, "SUP-021")
    assert of["fill_pct"] == 98.4
    assert of["otif_pct"] == 75.0
    assert (of["passed"], of["n_pos"]) == (3, 4)


def test_ranking_and_grades(card: Card) -> None:
    assert card["overall"]["ranking"] == ["SUP-021", "SUP-023", "SUP-022"]
    assert card["overall"]["best"] == "SUP-021"
    assert card["overall"]["worst"] == "SUP-022"
    assert card["overall"]["grade_distribution"] == {"B": 1, "C": 1, "D": 1}


def test_composite_matches_recomputed_weights(by_supplier: dict[str, Record], card: Card) -> None:
    w = card["weights"]
    for rec in by_supplier.values():
        m = rec["metrics"]
        expected = round(
            w["otif"] * m["otif_pct"]
            + w["fill"] * min(m["fill_pct"], 100.0)
            + w["asn_accuracy"] * m["asn_accuracy_pct"]
            + w["clean"] * (100.0 - m["exception_rate_pct"]),
            2,
        )
        assert rec["composite"] == expected


def test_grade_led_mapping(by_supplier: dict[str, Record]) -> None:
    for rec in by_supplier.values():
        assert rec["led"] == scorecard.GRADE_LED[rec["grade"]]
    assert by_supplier["SUP-021"]["led"] == "ok"
    assert by_supplier["SUP-023"]["led"] == "warn"
    assert by_supplier["SUP-022"]["led"] == "danger"


def test_coverage_counts(by_supplier: dict[str, Record]) -> None:
    # SUP-022 has zero deductions and zero mapped chase threads -> contextual = None.
    cov = by_supplier["SUP-022"]["coverage"]
    assert cov["deductions"] == {"valid": 0, "invalid": 0, "total": 0}
    assert cov["chases"] == {"responsive": 0, "mapped": 0}
    # SUP-021: 1 valid + 1 invalid deduction; 2 mapped chases, 1 responsive.
    cov21 = by_supplier["SUP-021"]["coverage"]
    assert cov21["deductions"] == {"valid": 1, "invalid": 1, "total": 2}
    assert cov21["chases"] == {"responsive": 1, "mapped": 2}


# --------------------------------------------------------------------------- #
# Per-PO drill atoms (the UOM trap + damage + price cases)
# --------------------------------------------------------------------------- #


def test_uom_trap_po_8806_normalizes_to_eaches(corpus: scorecard.Corpus) -> None:
    # PO in CS (100 * 12 = 1200 ea); receipt + ASN already in EA (1200). A naive
    # 100-vs-1200 compare would read catastrophic over-ship; normalized it matches.
    atoms = scorecard.po_asn_accuracy(corpus, "PO-8806")
    assert atoms["asn_ea"] == 1200.0 and atoms["grn_ea"] == 1200.0
    assert atoms["accurate"] is True
    assert scorecard.po_three_way(corpus, "PO-8806") == "matched"


def test_damage_splits_fill_from_three_way(corpus: scorecard.Corpus) -> None:
    # PO-8809: received qty full (3-way matched) but 10 CS damaged -> fill fails.
    assert scorecard.po_three_way(corpus, "PO-8809") == "matched"
    otif = scorecard.po_otif(corpus, "PO-8809")
    assert otif["fill_pct"] == 80.0 and otif["otif"] == "fail"


def test_price_within_tolerance_is_matched(corpus: scorecard.Corpus) -> None:
    # PO-8804: invoice 12.03 vs PO 12.00, tol 0.05 -> within -> matched.
    assert scorecard.po_three_way(corpus, "PO-8804") == "matched"


def test_drill_atoms_present_and_typed(by_supplier: dict[str, Record]) -> None:
    pos = by_supplier["SUP-021"]["pos"]
    assert [p["po_id"] for p in pos] == ["PO-8801", "PO-8802", "PO-8804", "PO-8808"]
    dup = next(p for p in pos if p["po_id"] == "PO-8808")
    assert dup["three_way"] == "duplicate_invoice"
    assert dup["exception_type"] == "duplicate_invoice"


# --------------------------------------------------------------------------- #
# Structure / metadata
# --------------------------------------------------------------------------- #


def test_scorecard_shape(card: Card) -> None:
    assert card["schema"] == scorecard.SCHEMA
    assert card["synthetic"] is True
    assert card["corpus"] == {
        "n_suppliers": 3,
        "n_pos": 10,
        "qty_tolerance_pct": 2.0,
        "pack_uom": "eaches",
    }


# --------------------------------------------------------------------------- #
# Committed artifact regression guard
# --------------------------------------------------------------------------- #


def test_committed_scorecard_json_is_current(card: Card) -> None:
    assert SCORECARD_JSON.is_file(), "run: python3 scorecard.py"
    on_disk = SCORECARD_JSON.read_text(encoding="utf-8")
    assert on_disk == scorecard.render_json(card), "scorecard.json is stale — re-run the engine"


# --------------------------------------------------------------------------- #
# The dashboard is self-contained
# --------------------------------------------------------------------------- #


def _build_view_module() -> Any:
    spec = importlib.util.spec_from_file_location("build_view", TOOL / "build_view.py")
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _inlined_data(html: str) -> Card:
    m = re.search(r'<script[^>]*id="scorecard-data"[^>]*>(.*?)</script>', html, re.DOTALL)
    assert m, "no scorecard-data tag"
    return json.loads(m.group(1))


def test_view_exists_and_is_offline() -> None:
    html = VIEW_HTML.read_text(encoding="utf-8")
    # No external resource references of any kind (fully self-contained / CSP-safe).
    assert "<link" not in html
    assert 'src="http' not in html and 'href="http' not in html
    assert "@import" not in html
    assert "fetch(" not in html and "XMLHttpRequest" not in html
    assert "//cdn" not in html and "WebSocket" not in html


def test_view_data_matches_scorecard(card: Card) -> None:
    html = VIEW_HTML.read_text(encoding="utf-8")
    assert _inlined_data(html) == card, "dashboard is stale — run build_view.py"


def test_view_uses_collins_contract_tokens() -> None:
    html = VIEW_HTML.read_text(encoding="utf-8")
    # Identity materials + the one primary action + focus bridge + fill/ink split present.
    for token in ("--copper", "--oxide", "--sys-accent", "--fill-ok", "--ink", "--paper-3"):
        assert token in html, f"missing Collins token {token}"


def test_build_view_check_is_fresh() -> None:
    mod = _build_view_module()
    assert mod.main(["--check", "--from-json"]) == 0


def test_build_view_inline_is_idempotent() -> None:
    mod = _build_view_module()
    html = VIEW_HTML.read_text(encoding="utf-8")
    json_text = SCORECARD_JSON.read_text(encoding="utf-8")
    once = mod.inline(html, json_text)
    twice = mod.inline(once, json_text)
    assert once == twice == html


# --------------------------------------------------------------------------- #
# Standalone runner (no pytest required)
# --------------------------------------------------------------------------- #


def _main() -> int:
    _corpus = scorecard.load_corpus()
    _card = scorecard.compute_scorecard(_corpus)
    _by: dict[str, Record] = {r["supplier"]: r for r in _card["suppliers"]}
    checks: list[tuple[str, Any]] = [
        ("determinism", lambda: test_engine_is_deterministic(_corpus)),
        ("byte_stable", lambda: test_render_json_is_byte_stable(_card)),
        ("spot_aggregate", lambda: test_spot_aggregate_hand_computed(_corpus)),
        ("ranking", lambda: test_ranking_and_grades(_card)),
        ("composite", lambda: test_composite_matches_recomputed_weights(_by, _card)),
        ("coverage", lambda: test_coverage_counts(_by)),
        ("uom_trap", lambda: test_uom_trap_po_8806_normalizes_to_eaches(_corpus)),
        ("committed_json", lambda: test_committed_scorecard_json_is_current(_card)),
        ("view_offline", test_view_exists_and_is_offline),
        ("view_matches", lambda: test_view_data_matches_scorecard(_card)),
    ]
    failures = 0
    for name, fn in checks:
        try:
            fn()
            print(f"PASS  {name}")
        except AssertionError as e:
            failures += 1
            print(f"FAIL  {name}: {e}")
    print(f"\n{len(checks) - failures}/{len(checks)} spot checks passed")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(_main())
