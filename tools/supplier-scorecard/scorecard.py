#!/usr/bin/env python3
"""Supplier-scorecard engine for the retail_ops synthetic corpus.

Rolls the per-PO reconciliation corpus (``fixtures/retail_ops/*.jsonl``) up to the
*supplier* level: six retail-buyer KPIs, a weighted composite, a letter grade, a
rank, and per-PO drill atoms, emitted as a byte-stable ``scorecard.json``.

``supplier`` lives on exactly one fixture -- ``purchase_orders.jsonl`` (``po.supplier``);
every other record carries ``po_id`` only, so every roll-up is the join
``record.po_id -> PO.id -> PO.supplier``. Every quantity is normalized to **eaches**
via the SKU pack size before any comparison -- the #1 false-exception guard (PO-8806
is the deliberate CS-vs-EA trap: PO in cases, receipt/ASN in eaches).

Faithful, stdlib-only port of the answer-key roll-ups in
``src/agentic_eval/domains/retail_ops/compute.py`` -- same corpus => same numbers, so
the scorecard can never drift from the eval's per-PO answer key. No third-party deps,
no network, no RNG: the emitted ``scorecard.json`` is byte-reproducible.

Usage:
    python3 scorecard.py                 # write scorecard.json (default)
    python3 scorecard.py --stdout        # print JSON, write nothing
    python3 scorecard.py -o out.json     # custom output path
    python3 scorecard.py --fixtures DIR  # score an alternate (still synthetic) corpus
    python3 scorecard.py --check         # compute twice, assert byte-identical output
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]  # tools/supplier-scorecard -> tools -> repo root
FIXTURES = REPO / "fixtures" / "retail_ops"

SCHEMA = "supplier-scorecard/0.1"
ROUND = 2
_EPS = 1e-6

# Marker substring -> exception type (port of rules.MARKER_TO_TYPE). Every
# exceptions.jsonl row embeds exactly one marker, so the type is known by construction.
MARKER_TO_TYPE: dict[str, str] = {
    "MARKER_SHORT_SHIP": "short_ship",
    "MARKER_OVER_SHIP": "over_ship",
    "MARKER_PRICE_VAR": "price_variance",
    "MARKER_NO_ASN": "blind_receipt",
    "MARKER_DUP_INVOICE": "duplicate_invoice",
    "MARKER_DAMAGE": "damaged_goods",
    "MARKER_DISCONTINUED": "short_ship_discontinued",
    "MARKER_UOM_OK": "no_exception",
}

# Synthetic chase-ladder step names (port of policy.json ``chase_ladder``), indexed by
# prior_chases and clamped to the last step. A "responsive" thread is one the supplier
# actually closed by replying or fulfilling -- not one still climbing the ladder and not
# a "discontinued / won't fulfil" stop.
CHASE_LADDER: tuple[str, ...] = (
    "chase_1_soft",
    "chase_2_firm_cc_manager",
    "chase_3_escalate_buyer",
)
RESPONSIVE_STOPS: frozenset[str] = frozenset({"stop_fulfilled", "stop_confirm_delivery"})

# Composite weights over the four full-coverage KPIs. OTIF is the retail headline KPI
# (weighted highest); "clean" = 100 - exception_rate rewards a low exception load; fill is
# capped at 100 for scoring so an over-ship earns no bonus. Deduction validity and chase
# responsiveness are excluded (sparse: SUP-022 has zero deductions; only three of six chase
# rows map to an in-corpus supplier) -- carried as contextual, coverage-flagged columns.
WEIGHTS: dict[str, float] = {"otif": 0.35, "fill": 0.20, "asn_accuracy": 0.20, "clean": 0.25}

# Letter-grade bands on the 0-100 composite (lower bound inclusive). This is a
# deliberately-stressed teaching corpus, so scores cluster low by design; bands are
# transparent and tunable here in one place.
GRADE_BANDS: list[tuple[str, float]] = [
    ("A", 80.0),
    ("B", 65.0),
    ("C", 50.0),
    ("D", 35.0),
    ("F", 0.0),
]

# Grade -> dashboard LED status token (drives the Collins --fill-* marks on the view).
GRADE_LED: dict[str, str] = {"A": "ok", "B": "ok", "C": "warn", "D": "danger", "F": "danger"}


# --------------------------------------------------------------------------- #
# Row models (frozen; only the fields the scorecard reads)
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class PurchaseOrder:
    id: str
    sku: str
    supplier: str
    qty: float
    uom: str
    unit_price: float
    order_date: str
    promised_date: str
    ship_to: str


@dataclass(frozen=True, slots=True)
class Receipt:
    id: str
    po_id: str
    sku: str
    qty_received: float
    uom: str
    received_date: str
    condition: str
    qty_damaged: float


@dataclass(frozen=True, slots=True)
class Asn:
    id: str
    po_id: str
    sku: str
    qty: float
    uom: str


@dataclass(frozen=True, slots=True)
class Invoice:
    id: str
    po_id: str
    sku: str
    qty_billed: float
    uom: str
    unit_price: float


@dataclass(frozen=True, slots=True)
class Deduction:
    id: str
    po_id: str
    kpi: str
    amount: float


@dataclass(frozen=True, slots=True)
class ChaseState:
    id: str
    po_id: str
    prior_chases: int
    supplier_replied: bool
    fulfilled: bool
    discontinued: bool


@dataclass(frozen=True, slots=True)
class ExceptionRow:
    id: str
    po_id: str
    evidence_text: str
    gold_type: str
    gold_disposition: str


@dataclass(frozen=True, slots=True)
class Corpus:
    """The loaded world the scorecard scores over.

    ``pack_sizes`` maps SKU -> eaches-per-case (policy ``uom`` block);
    ``qty_tolerance_pct`` / ``price_tolerance_per_case`` are carried for the three-way
    drill verdict and for provenance in the output.
    """

    purchase_orders: dict[str, PurchaseOrder]
    receipts: list[Receipt]
    asns: list[Asn]
    invoices: list[Invoice]
    deductions: list[Deduction]
    chase_state: list[ChaseState]
    exceptions: list[ExceptionRow]
    pack_sizes: dict[str, int]
    qty_tolerance_pct: float
    price_tolerance_per_case: float

    def supplier_of(self, po_id: str) -> str | None:
        """The join-key resolver: ``po_id -> supplier`` (None if the PO is not in corpus)."""
        po = self.purchase_orders.get(po_id)
        return po.supplier if po is not None else None

    def suppliers(self) -> list[str]:
        """Sorted distinct supplier ids present on the purchase orders."""
        return sorted({po.supplier for po in self.purchase_orders.values()})


# --------------------------------------------------------------------------- #
# Loaders (stdlib only)
# --------------------------------------------------------------------------- #


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        raise FileNotFoundError(f"missing fixture: {path}")
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def load_corpus(fixtures_dir: Path | str | None = None) -> Corpus:
    """Load the ``retail_ops`` corpus into a :class:`Corpus`.

    ``fixtures_dir`` defaults to ``<repo>/fixtures/retail_ops`` (the shared harness
    fixtures); pass a path to score an alternate (still synthetic) corpus.
    """
    root = Path(fixtures_dir) if fixtures_dir is not None else FIXTURES

    pos = {
        str(r["id"]): PurchaseOrder(
            id=str(r["id"]),
            sku=str(r["sku"]),
            supplier=str(r["supplier"]),
            qty=float(r["qty"]),
            uom=str(r["uom"]),
            unit_price=float(r["unit_price"]),
            order_date=str(r["order_date"]),
            promised_date=str(r["promised_date"]),
            ship_to=str(r["ship_to"]),
        )
        for r in _read_jsonl(root / "purchase_orders.jsonl")
    }

    receipts = [
        Receipt(
            id=str(r["id"]),
            po_id=str(r["po_id"]),
            sku=str(r["sku"]),
            qty_received=float(r["qty_received"]),
            uom=str(r["uom"]),
            received_date=str(r["received_date"]),
            condition=str(r["condition"]),
            qty_damaged=float(r["qty_damaged"]),
        )
        for r in _read_jsonl(root / "receipts.jsonl")
    ]

    asns = [
        Asn(
            id=str(r["id"]),
            po_id=str(r["po_id"]),
            sku=str(r["sku"]),
            qty=float(r["qty"]),
            uom=str(r["uom"]),
        )
        for r in _read_jsonl(root / "asns.jsonl")
    ]

    invoices = [
        Invoice(
            id=str(r["id"]),
            po_id=str(r["po_id"]),
            sku=str(r["sku"]),
            qty_billed=float(r["qty_billed"]),
            uom=str(r["uom"]),
            unit_price=float(r["unit_price"]),
        )
        for r in _read_jsonl(root / "invoices.jsonl")
    ]

    deductions = [
        Deduction(
            id=str(r["id"]),
            po_id=str(r["po_id"]),
            kpi=str(r["kpi"]),
            amount=float(r["amount"]),
        )
        for r in _read_jsonl(root / "deductions.jsonl")
    ]

    chase_state = [
        ChaseState(
            id=str(r["id"]),
            po_id=str(r["po_id"]),
            prior_chases=int(r["prior_chases"]),
            supplier_replied=bool(r["supplier_replied"]),
            fulfilled=bool(r["fulfilled"]),
            discontinued=bool(r["discontinued"]),
        )
        for r in _read_jsonl(root / "chase_state.jsonl")
    ]

    exceptions = [
        ExceptionRow(
            id=str(r["id"]),
            po_id=str(r["po_id"]),
            evidence_text=str(r["evidence_text"]),
            gold_type=str(r["gold_type"]),
            gold_disposition=str(r["gold_disposition"]),
        )
        for r in _read_jsonl(root / "exceptions.jsonl")
    ]

    policy = json.loads((root / "policy.json").read_text(encoding="utf-8"))
    pack_sizes = {str(k): int(v) for k, v in policy["uom"].items()}
    qty_tol = float(policy["qty_tolerance_pct"]["value"])
    price_tol = float(policy["price_tolerance_per_case"]["value"])

    return Corpus(
        purchase_orders=pos,
        receipts=receipts,
        asns=asns,
        invoices=invoices,
        deductions=deductions,
        chase_state=chase_state,
        exceptions=exceptions,
        pack_sizes=pack_sizes,
        qty_tolerance_pct=qty_tol,
        price_tolerance_per_case=price_tol,
    )


# --------------------------------------------------------------------------- #
# UOM normalization -- the #1 false-exception guard
# --------------------------------------------------------------------------- #


def to_ea(corpus: Corpus, qty: float, uom: str, sku: str) -> float:
    """Normalize ``qty`` in ``uom`` to eaches using the SKU pack size.

    Port of ``compute.to_ea``: EA passes through; CS multiplies by the pack size. This is
    the same normalization the reconciliation path uses, so scorecard numbers can't drift
    from the per-PO answer key.
    """
    unit = uom.strip().upper()
    if unit == "EA":
        return float(qty)
    if unit == "CS":
        return float(qty) * corpus.pack_sizes[sku]
    raise ValueError(f"unknown uom: {uom!r}")


# --------------------------------------------------------------------------- #
# Per-PO atoms
# --------------------------------------------------------------------------- #


def _receipts_for(corpus: Corpus, po_id: str) -> list[Receipt]:
    return [r for r in corpus.receipts if r.po_id == po_id]


def _asn_for(corpus: Corpus, po_id: str) -> Asn | None:
    for a in corpus.asns:
        if a.po_id == po_id:
            return a
    return None


def _invoices_for(corpus: Corpus, po_id: str) -> list[Invoice]:
    return [i for i in corpus.invoices if i.po_id == po_id]


def po_fill(corpus: Corpus, po_id: str) -> dict[str, float]:
    """Ordered vs good eaches + fill % for one PO (good excludes damaged units)."""
    po = corpus.purchase_orders[po_id]
    recs = _receipts_for(corpus, po_id)
    ordered_ea = to_ea(corpus, po.qty, po.uom, po.sku)
    received_ea = round(sum(to_ea(corpus, r.qty_received, r.uom, r.sku) for r in recs), ROUND)
    good_ea = round(
        sum(to_ea(corpus, r.qty_received - r.qty_damaged, r.uom, r.sku) for r in recs), ROUND
    )
    fill_pct = round(good_ea / ordered_ea * 100.0, ROUND) if ordered_ea else 0.0
    return {
        "ordered_ea": round(ordered_ea, ROUND),
        "received_ea": received_ea,
        "good_ea": good_ea,
        "fill_pct": fill_pct,
    }


def po_on_time(corpus: Corpus, po_id: str) -> bool:
    """On-time = latest receipt on or before the promised date (early OK, late fails)."""
    recs = _receipts_for(corpus, po_id)
    if not recs:
        return False
    po = corpus.purchase_orders[po_id]
    delivered = max(date.fromisoformat(r.received_date) for r in recs)
    return delivered <= date.fromisoformat(po.promised_date)


def po_otif(corpus: Corpus, po_id: str) -> dict[str, Any]:
    """OTIF pass/fail for one PO: on-time AND in-full (fill >= 100%)."""
    fill = po_fill(corpus, po_id)
    on_time = po_on_time(corpus, po_id)
    in_full = fill["fill_pct"] >= 100.0 - _EPS
    return {
        "otif": "pass" if (on_time and in_full) else "fail",
        "on_time": on_time,
        "in_full": in_full,
        "fill_pct": fill["fill_pct"],
        "ordered_ea": fill["ordered_ea"],
        "good_ea": fill["good_ea"],
        "received_ea": fill["received_ea"],
    }


def po_asn_accuracy(corpus: Corpus, po_id: str) -> dict[str, Any]:
    """ASN accuracy for one PO: the 856 qty (in eaches) equals what arrived.

    Accurate iff an ASN exists AND ``to_ea(asn.qty) == round(sum to_ea(receipt.qty_received))``.
    A missing ASN (blind receipt) is inaccurate by definition.
    """
    recs = _receipts_for(corpus, po_id)
    grn_ea = round(sum(to_ea(corpus, r.qty_received, r.uom, r.sku) for r in recs), ROUND)
    asn = _asn_for(corpus, po_id)
    if asn is None:
        return {"accurate": False, "asn_present": False, "asn_ea": None, "grn_ea": grn_ea}
    asn_ea = round(to_ea(corpus, asn.qty, asn.uom, asn.sku), ROUND)
    return {
        "accurate": abs(asn_ea - grn_ea) <= _EPS,
        "asn_present": True,
        "asn_ea": asn_ea,
        "grn_ea": grn_ea,
    }


def po_three_way(corpus: Corpus, po_id: str) -> str:
    """PO<->receipt<->invoice reconciliation verdict for the drill detail.

    Faithful port of ``compute.three_way_match`` verdict precedence: no_receipt ->
    duplicate_invoice -> short_ship / over_ship (qty outside tolerance) -> price_variance
    -> matched. Quantities compared in eaches; price per case.
    """
    po = corpus.purchase_orders[po_id]
    recs = _receipts_for(corpus, po_id)
    invs = _invoices_for(corpus, po_id)
    qty_po = to_ea(corpus, po.qty, po.uom, po.sku)
    qty_grn = round(sum(to_ea(corpus, r.qty_received, r.uom, r.sku) for r in recs), ROUND)
    tol = qty_po * corpus.qty_tolerance_pct / 100.0

    if not recs:
        return "no_receipt"
    if len(invs) > 1:
        return "duplicate_invoice"
    if qty_grn < qty_po - tol - _EPS:
        return "short_ship"
    if qty_grn > qty_po + tol + _EPS:
        return "over_ship"
    if invs:
        price_gap = abs(round(invs[0].unit_price, ROUND) - round(po.unit_price, ROUND))
        if price_gap > corpus.price_tolerance_per_case + _EPS:
            return "price_variance"
    return "matched"


def classify_exception(row: ExceptionRow) -> str:
    """Exception type from the MARKER token embedded in the evidence text."""
    for marker, kind in MARKER_TO_TYPE.items():
        if marker in row.evidence_text:
            return kind
    raise ValueError(f"no marker matched for exception {row.id!r}")


def chase_step(chase: ChaseState) -> str:
    """Next chase-ladder step, or a stop signal, for one dunning thread."""
    if chase.fulfilled:
        return "stop_fulfilled"
    if chase.discontinued:
        return "stop_no_chase"
    if chase.supplier_replied:
        return "stop_confirm_delivery"
    idx = min(chase.prior_chases, len(CHASE_LADDER) - 1)
    return CHASE_LADDER[idx]


# --------------------------------------------------------------------------- #
# Per-supplier roll-ups (record.po_id -> PO.id -> PO.supplier)
# --------------------------------------------------------------------------- #


def _pos_for(corpus: Corpus, supplier: str) -> list[PurchaseOrder]:
    return sorted(
        (po for po in corpus.purchase_orders.values() if po.supplier == supplier),
        key=lambda p: p.id,
    )


def otif_fill(corpus: Corpus, supplier: str) -> dict[str, Any]:
    """OTIF % (passed POs / n) + aggregate fill % (sum good / sum ordered).

    Fill is uncapped, so an over-ship (>100%) offsets a short-ship in the roll-up --
    matching the harness ``otif_for_supplier``.
    """
    pos = _pos_for(corpus, supplier)
    if not pos:
        raise KeyError(f"no purchase orders for supplier {supplier!r}")
    passed = 0
    good_total = 0.0
    ordered_total = 0.0
    for po in pos:
        atoms = po_otif(corpus, po.id)
        if atoms["otif"] == "pass":
            passed += 1
        good_total += atoms["good_ea"]
        ordered_total += atoms["ordered_ea"]
    n = len(pos)
    return {
        "otif_pct": round(passed / n * 100.0, ROUND),
        "fill_pct": round(good_total / ordered_total * 100.0, ROUND) if ordered_total else 0.0,
        "n_pos": n,
        "passed": passed,
    }


def asn_accuracy(corpus: Corpus, supplier: str) -> dict[str, Any]:
    """ASN accuracy % across the supplier's POs (accurate POs / n)."""
    pos = _pos_for(corpus, supplier)
    accurate = sum(1 for po in pos if po_asn_accuracy(corpus, po.id)["accurate"])
    n = len(pos)
    return {
        "asn_accuracy_pct": round(accurate / n * 100.0, ROUND) if n else 0.0,
        "accurate": accurate,
        "total": n,
    }


def _deduction_is_valid(corpus: Corpus, ded: Deduction) -> bool:
    """A deduction is valid iff the KPI it cites actually failed on that PO."""
    if ded.kpi == "otif":
        return po_otif(corpus, ded.po_id)["otif"] == "fail"
    if ded.kpi == "fill_rate":
        return po_fill(corpus, ded.po_id)["fill_pct"] < 100.0 - _EPS
    if ded.kpi == "asn_accuracy":
        return not po_asn_accuracy(corpus, ded.po_id)["accurate"]
    raise ValueError(f"unknown deduction kpi: {ded.kpi!r}")


def deduction_validity(corpus: Corpus, supplier: str) -> dict[str, Any]:
    """Deduction validity % -- of deductions filed against the supplier, how many were
    genuinely valid (cited KPI actually failed). ``None`` when the supplier has no
    deductions (SUP-022 in the shipped corpus)."""
    valid = invalid = 0
    for ded in corpus.deductions:
        if corpus.supplier_of(ded.po_id) != supplier:
            continue
        if _deduction_is_valid(corpus, ded):
            valid += 1
        else:
            invalid += 1
    total = valid + invalid
    return {
        "deduction_validity_pct": round(valid / total * 100.0, ROUND) if total else None,
        "valid": valid,
        "invalid": invalid,
        "total": total,
    }


def exception_rate(corpus: Corpus, supplier: str) -> dict[str, Any]:
    """Exception rate % -- supplier's POs that threw a real exception / n.

    ``no_exception`` rows (the clean-UOM control, EX-10) are excluded.
    """
    pos = _pos_for(corpus, supplier)
    po_ids = {po.id for po in pos}
    flagged = {
        row.po_id
        for row in corpus.exceptions
        if row.po_id in po_ids and classify_exception(row) != "no_exception"
    }
    n = len(pos)
    return {
        "exception_rate_pct": round(len(flagged) / n * 100.0, ROUND) if n else 0.0,
        "n_exceptions": len(flagged),
        "n_pos": n,
    }


def chase_responsiveness(corpus: Corpus, supplier: str) -> dict[str, Any]:
    """Chase responsiveness % over the supplier's *mapped* dunning threads.

    THIN/ILLUSTRATIVE by construction: only chase rows whose ``po_id`` resolves to a
    supplier count (three of six rows in the shipped corpus reference POs that don't
    exist). Responsive = a thread the supplier closed (``stop_fulfilled`` /
    ``stop_confirm_delivery``); still-climbing or ``stop_no_chase`` (discontinued) is
    non-responsive. ``None`` when the supplier has no mapped threads.
    """
    responsive = mapped = 0
    for ch in corpus.chase_state:
        if corpus.supplier_of(ch.po_id) != supplier:
            continue
        mapped += 1
        if chase_step(ch) in RESPONSIVE_STOPS:
            responsive += 1
    return {
        "chase_responsiveness_pct": round(responsive / mapped * 100.0, ROUND) if mapped else None,
        "responsive": responsive,
        "mapped": mapped,
    }


# --------------------------------------------------------------------------- #
# Composite / grade / assembly
# --------------------------------------------------------------------------- #


def composite_score(otif: float, fill: float, asn: float, exception_rate_pct: float) -> float:
    """Weighted blend of the four full-coverage KPIs. Fill capped at 100 (no over-ship
    bonus); ``clean`` = 100 - exception_rate."""
    clean = 100.0 - exception_rate_pct
    fill_capped = min(fill, 100.0)
    score = (
        WEIGHTS["otif"] * otif
        + WEIGHTS["fill"] * fill_capped
        + WEIGHTS["asn_accuracy"] * asn
        + WEIGHTS["clean"] * clean
    )
    return round(score, 2)


def grade_for(composite: float) -> str:
    """Letter grade for a 0-100 composite (first band whose lower bound it clears)."""
    for letter, lo in GRADE_BANDS:
        if composite >= lo:
            return letter
    return "F"


def _supplier_record(corpus: Corpus, supplier: str) -> dict[str, Any]:
    of = otif_fill(corpus, supplier)
    asn = asn_accuracy(corpus, supplier)
    exc = exception_rate(corpus, supplier)
    ded = deduction_validity(corpus, supplier)
    chase = chase_responsiveness(corpus, supplier)

    composite = composite_score(
        of["otif_pct"], of["fill_pct"], asn["asn_accuracy_pct"], exc["exception_rate_pct"]
    )
    grade = grade_for(composite)

    pos: list[dict[str, Any]] = []
    for po in _pos_for(corpus, supplier):
        atoms = po_otif(corpus, po.id)
        asn_a = po_asn_accuracy(corpus, po.id)
        exc_type = next(
            (classify_exception(row) for row in corpus.exceptions if row.po_id == po.id),
            None,
        )
        pos.append(
            {
                "po_id": po.id,
                "sku": po.sku,
                "ordered_ea": atoms["ordered_ea"],
                "received_ea": atoms["received_ea"],
                "good_ea": atoms["good_ea"],
                "on_time": atoms["on_time"],
                "fill_pct": atoms["fill_pct"],
                "otif": atoms["otif"],
                "asn_accurate": asn_a["accurate"],
                "asn_ea": asn_a["asn_ea"],
                "grn_ea": asn_a["grn_ea"],
                "three_way": po_three_way(corpus, po.id),
                "exception_type": exc_type,
            }
        )

    return {
        "supplier": supplier,
        "grade": grade,
        "led": GRADE_LED[grade],
        "composite": composite,
        "n_pos": of["n_pos"],
        "po_ids": [p["po_id"] for p in pos],
        "metrics": {
            "otif_pct": of["otif_pct"],
            "fill_pct": of["fill_pct"],
            "asn_accuracy_pct": asn["asn_accuracy_pct"],
            "exception_rate_pct": exc["exception_rate_pct"],
            "clean_pct": round(100.0 - exc["exception_rate_pct"], 2),
            "deduction_validity_pct": ded["deduction_validity_pct"],
            "chase_responsiveness_pct": chase["chase_responsiveness_pct"],
        },
        "coverage": {
            "otif": {"passed": of["passed"], "total": of["n_pos"]},
            "asn_accuracy": {"accurate": asn["accurate"], "total": asn["total"]},
            "exceptions": {"flagged": exc["n_exceptions"], "total": exc["n_pos"]},
            "deductions": {"valid": ded["valid"], "invalid": ded["invalid"], "total": ded["total"]},
            "chases": {"responsive": chase["responsive"], "mapped": chase["mapped"]},
        },
        "pos": pos,
    }


def _grade_distribution(records: list[dict[str, Any]]) -> dict[str, int]:
    dist: dict[str, int] = {}
    for r in records:
        dist[r["grade"]] = dist.get(r["grade"], 0) + 1
    return dist


def compute_scorecard(corpus: Corpus) -> dict[str, Any]:
    """Compute the full supplier scorecard (per-supplier records + overall).

    Ranking is by composite descending, ties broken by supplier id ascending (fully
    deterministic). Returns a JSON-serializable dict.
    """
    records = [_supplier_record(corpus, s) for s in corpus.suppliers()]
    records.sort(key=lambda r: (-r["composite"], r["supplier"]))
    for i, rec in enumerate(records, start=1):
        rec["rank"] = i

    ranking = [r["supplier"] for r in records]
    return {
        "schema": SCHEMA,
        "synthetic": True,
        "generated_from": "fixtures/retail_ops (synthetic corpus)",
        "weights": WEIGHTS,
        "grade_bands": dict(GRADE_BANDS),
        "kpis": {
            "composite": ["otif_pct", "fill_pct", "asn_accuracy_pct", "exception_rate_pct"],
            "contextual": ["deduction_validity_pct", "chase_responsiveness_pct"],
        },
        "corpus": {
            "n_suppliers": len(records),
            "n_pos": len(corpus.purchase_orders),
            "qty_tolerance_pct": corpus.qty_tolerance_pct,
            "pack_uom": "eaches",
        },
        "suppliers": records,
        "overall": {
            "ranking": ranking,
            "best": ranking[0] if ranking else None,
            "worst": ranking[-1] if ranking else None,
            "grade_distribution": _grade_distribution(records),
        },
    }


def render_json(scorecard: dict[str, Any]) -> str:
    """Canonical byte-stable JSON (sorted keys, 2-space indent, trailing newline)."""
    return json.dumps(scorecard, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def main(argv: list[str] | None = None) -> int:
    """CLI: load the corpus, compute the scorecard, write scorecard.json (or stdout)."""
    parser = argparse.ArgumentParser(description="Compute the retail_ops supplier scorecard.")
    parser.add_argument(
        "-o", "--output", type=Path, default=None, help="output path (default: ./scorecard.json)"
    )
    parser.add_argument(
        "--fixtures",
        type=Path,
        default=None,
        help="corpus dir (default: <repo>/fixtures/retail_ops)",
    )
    parser.add_argument(
        "--stdout", action="store_true", help="print JSON instead of writing a file"
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="compute twice and assert byte-identical output (determinism gate)",
    )
    args = parser.parse_args(argv)

    def build() -> str:
        return render_json(compute_scorecard(load_corpus(args.fixtures)))

    text = build()

    if args.check:
        if text != build():
            sys.stderr.write("NON-DETERMINISTIC: two runs differ\n")
            return 1
        sys.stderr.write("deterministic: two runs byte-identical\n")
        return 0

    if args.stdout:
        sys.stdout.write(text)
        return 0

    out = args.output if args.output is not None else HERE / "scorecard.json"
    out.write_text(text, encoding="utf-8")
    scorecard = json.loads(text)
    ranking = " > ".join(
        f"{r['supplier']}({r['grade']} {r['composite']})" for r in scorecard["suppliers"]
    )
    sys.stderr.write(f"wrote {out}  |  {ranking}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
