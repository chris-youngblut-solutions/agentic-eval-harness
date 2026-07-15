"""Deterministic synthetic-corpus generator for the retail_ops domain.

Everything here is FABRICATED and GENERIC. The purchase orders, ASNs, goods-receipt
notes, invoices, exceptions, deductions, chase state, audit entries, and proposed
approval actions are hand-tabulated benign rows (no randomness, no real supplier,
retailer, ERP, customer, or PII data). Ids are structural MARKER tokens by
construction (``PO-88##``, ``SKU-####``, ``EX-##`` …); exception rows embed an
abstract ``MARKER_*`` token in benign filler so the exception type is known by
construction. Re-running reproduces byte-identical fixtures (a test guards this):

    uv run python -m agentic_eval.domains.retail_ops.generate

``policy.json`` is hand-authored (the source of truth / answer key for tolerances,
thresholds, the chase ladder, the gated-action list, and pack sizes) and is NOT
regenerated here. Every numeric/verdict answer in the golden set is *computed* from
these rows + policy by ``compute.py`` and the deterministic tools — never asserted by
hand. The inline comments below state each row's resulting reconciliation/KPI value so
the fixtures stay human-checkable.

Fixtures written under fixtures/retail_ops/:
- purchase_orders.jsonl  the commercial "expected" (PO qty/price/promised-date).
- asns.jsonl             the supplier's declared shipment (PO-8807 absent -> blind receipt;
                         ASN-06 is 1200 EA = 100 CS, the UOM trap).
- receipts.jsonl         the goods-receipt "actual" (short/over/damaged/UOM-mismatch rows).
- invoices.jsonl         the "charged" (price variance, over-billing, PO-8808 duplicate).
- exceptions.jsonl       marker-tagged exceptions with gold type/disposition/tolerance.
- deductions.jsonl       retailer chargebacks; validity recomputed from the delivery record.
- chase_state.jsonl      supplier follow-up state; next ladder step recomputed.
- audit_entries.jsonl    audit records, some complete and some missing a required field.
- approval_actions.jsonl proposed actions for the approval gate; verdict recomputed.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agentic_eval.domains.retail_ops import rules

FIXTURES = rules.FIXTURES

_EX_FILLER = "Fabricated exception evidence for eval; benign filler. Token:"


def build_purchase_orders() -> list[dict[str, Any]]:
    """The commercial 'expected'. qty in cases (CS) except where noted."""
    return [
        {
            "id": "PO-8801",
            "sku": "SKU-4471",
            "supplier": "SUP-021",
            "qty": 100,
            "uom": "CS",
            "unit_price": 12.00,
            "order_date": "2026-05-20",
            "promised_date": "2026-06-10",
            "ship_to": "DC-1",
        },
        {
            "id": "PO-8802",
            "sku": "SKU-5502",
            "supplier": "SUP-021",
            "qty": 100,
            "uom": "CS",
            "unit_price": 8.00,
            "order_date": "2026-05-22",
            "promised_date": "2026-06-12",
            "ship_to": "DC-1",
        },
        {
            "id": "PO-8803",
            "sku": "SKU-6613",
            "supplier": "SUP-022",
            "qty": 100,
            "uom": "CS",
            "unit_price": 5.00,
            "order_date": "2026-05-25",
            "promised_date": "2026-06-15",
            "ship_to": "DC-2",
        },
        {
            "id": "PO-8804",
            "sku": "SKU-4471",
            "supplier": "SUP-021",
            "qty": 200,
            "uom": "CS",
            "unit_price": 12.00,
            "order_date": "2026-05-28",
            "promised_date": "2026-06-18",
            "ship_to": "DC-1",
        },
        {
            "id": "PO-8805",
            "sku": "SKU-5502",
            "supplier": "SUP-023",
            "qty": 150,
            "uom": "CS",
            "unit_price": 8.00,
            "order_date": "2026-05-30",
            "promised_date": "2026-06-20",
            "ship_to": "DC-3",
        },
        {
            "id": "PO-8806",
            "sku": "SKU-7788",
            "supplier": "SUP-023",
            "qty": 100,
            "uom": "CS",
            "unit_price": 10.00,
            "order_date": "2026-06-04",
            "promised_date": "2026-06-25",
            "ship_to": "DC-3",
        },
        {
            "id": "PO-8807",
            "sku": "SKU-6613",
            "supplier": "SUP-022",
            "qty": 100,
            "uom": "CS",
            "unit_price": 5.00,
            "order_date": "2026-06-07",
            "promised_date": "2026-06-28",
            "ship_to": "DC-2",
        },
        {
            "id": "PO-8808",
            "sku": "SKU-4471",
            "supplier": "SUP-021",
            "qty": 100,
            "uom": "CS",
            "unit_price": 12.00,
            "order_date": "2026-06-09",
            "promised_date": "2026-06-30",
            "ship_to": "DC-1",
        },
        {
            "id": "PO-8809",
            "sku": "SKU-5502",
            "supplier": "SUP-022",
            "qty": 50,
            "uom": "CS",
            "unit_price": 8.00,
            "order_date": "2026-06-11",
            "promised_date": "2026-07-02",
            "ship_to": "DC-2",
        },
        {
            "id": "PO-8810",
            "sku": "SKU-7788",
            "supplier": "SUP-023",
            "qty": 80,
            "uom": "CS",
            "unit_price": 10.00,
            "order_date": "2026-06-14",
            "promised_date": "2026-07-05",
            "ship_to": "DC-3",
        },
    ]


def build_asns() -> list[dict[str, Any]]:
    """Supplier declared shipments. PO-8807 intentionally absent (blind receipt);
    ASN-06 declares 1200 EA (= 100 CS at pack 12) -> the UOM trap."""
    return [
        {
            "id": "ASN-01",
            "po_id": "PO-8801",
            "sku": "SKU-4471",
            "qty": 100,
            "uom": "CS",
            "ship_date": "2026-06-06",
            "expected_date": "2026-06-10",
        },
        {
            "id": "ASN-02",
            "po_id": "PO-8802",
            "sku": "SKU-5502",
            "qty": 100,
            "uom": "CS",
            "ship_date": "2026-06-08",
            "expected_date": "2026-06-12",
        },
        {
            "id": "ASN-03",
            "po_id": "PO-8803",
            "sku": "SKU-6613",
            "qty": 100,
            "uom": "CS",
            "ship_date": "2026-06-10",
            "expected_date": "2026-06-15",
        },
        {
            "id": "ASN-04",
            "po_id": "PO-8804",
            "sku": "SKU-4471",
            "qty": 200,
            "uom": "CS",
            "ship_date": "2026-06-14",
            "expected_date": "2026-06-18",
        },
        {
            "id": "ASN-05",
            "po_id": "PO-8805",
            "sku": "SKU-5502",
            "qty": 150,
            "uom": "CS",
            "ship_date": "2026-06-17",
            "expected_date": "2026-06-20",
        },
        {
            "id": "ASN-06",
            "po_id": "PO-8806",
            "sku": "SKU-7788",
            "qty": 1200,
            "uom": "EA",
            "ship_date": "2026-06-20",
            "expected_date": "2026-06-25",
        },
        {
            "id": "ASN-08",
            "po_id": "PO-8808",
            "sku": "SKU-4471",
            "qty": 100,
            "uom": "CS",
            "ship_date": "2026-06-25",
            "expected_date": "2026-06-30",
        },
        {
            "id": "ASN-09",
            "po_id": "PO-8809",
            "sku": "SKU-5502",
            "qty": 50,
            "uom": "CS",
            "ship_date": "2026-06-28",
            "expected_date": "2026-07-02",
        },
        {
            "id": "ASN-10",
            "po_id": "PO-8810",
            "sku": "SKU-7788",
            "qty": 80,
            "uom": "CS",
            "ship_date": "2026-07-01",
            "expected_date": "2026-07-05",
        },
    ]


def build_receipts() -> list[dict[str, Any]]:
    """The goods-receipt 'actual'.
    GRN-01 100/100 -> matched, otif pass
    GRN-02 92/100  -> short_ship, fill 92
    GRN-03 108/100 -> over_ship
    GRN-05 150/150 received 06-22 > promised 06-20 -> otif fail (late)
    GRN-06 1200 EA (= 100 CS) -> matched after UOM normalize
    GRN-09 50 received, 10 damaged -> fill 80
    GRN-10 60/80 (discontinued short)"""
    return [
        {
            "id": "GRN-01",
            "po_id": "PO-8801",
            "sku": "SKU-4471",
            "qty_received": 100,
            "uom": "CS",
            "received_date": "2026-06-09",
            "condition": "good",
            "qty_damaged": 0,
        },
        {
            "id": "GRN-02",
            "po_id": "PO-8802",
            "sku": "SKU-5502",
            "qty_received": 92,
            "uom": "CS",
            "received_date": "2026-06-12",
            "condition": "good",
            "qty_damaged": 0,
        },
        {
            "id": "GRN-03",
            "po_id": "PO-8803",
            "sku": "SKU-6613",
            "qty_received": 108,
            "uom": "CS",
            "received_date": "2026-06-14",
            "condition": "good",
            "qty_damaged": 0,
        },
        {
            "id": "GRN-04",
            "po_id": "PO-8804",
            "sku": "SKU-4471",
            "qty_received": 200,
            "uom": "CS",
            "received_date": "2026-06-18",
            "condition": "good",
            "qty_damaged": 0,
        },
        {
            "id": "GRN-05",
            "po_id": "PO-8805",
            "sku": "SKU-5502",
            "qty_received": 150,
            "uom": "CS",
            "received_date": "2026-06-22",
            "condition": "good",
            "qty_damaged": 0,
        },
        {
            "id": "GRN-06",
            "po_id": "PO-8806",
            "sku": "SKU-7788",
            "qty_received": 1200,
            "uom": "EA",
            "received_date": "2026-06-24",
            "condition": "good",
            "qty_damaged": 0,
        },
        {
            "id": "GRN-07",
            "po_id": "PO-8807",
            "sku": "SKU-6613",
            "qty_received": 100,
            "uom": "CS",
            "received_date": "2026-06-27",
            "condition": "good",
            "qty_damaged": 0,
        },
        {
            "id": "GRN-08",
            "po_id": "PO-8808",
            "sku": "SKU-4471",
            "qty_received": 100,
            "uom": "CS",
            "received_date": "2026-06-29",
            "condition": "good",
            "qty_damaged": 0,
        },
        {
            "id": "GRN-09",
            "po_id": "PO-8809",
            "sku": "SKU-5502",
            "qty_received": 50,
            "uom": "CS",
            "received_date": "2026-07-01",
            "condition": "partial_damage",
            "qty_damaged": 10,
        },
        {
            "id": "GRN-10",
            "po_id": "PO-8810",
            "sku": "SKU-7788",
            "qty_received": 60,
            "uom": "CS",
            "received_date": "2026-07-05",
            "condition": "good",
            "qty_damaged": 0,
        },
    ]


def build_invoices() -> list[dict[str, Any]]:
    """The 'charged'.
    INV-02 bills 100 despite 92 received
    INV-04 12.03 vs 12.00 -> price var 0.03 (within tol)
    INV-05 8.50 vs 8.00  -> price var 0.50 (over tol)
    INV-06 100 CS matches after UOM normalize
    INV-08a + INV-08b for PO-8808 -> duplicate_invoice"""
    return [
        {
            "id": "INV-01",
            "po_id": "PO-8801",
            "sku": "SKU-4471",
            "qty_billed": 100,
            "uom": "CS",
            "unit_price": 12.00,
            "invoice_date": "2026-06-11",
        },
        {
            "id": "INV-02",
            "po_id": "PO-8802",
            "sku": "SKU-5502",
            "qty_billed": 100,
            "uom": "CS",
            "unit_price": 8.00,
            "invoice_date": "2026-06-13",
        },
        {
            "id": "INV-03",
            "po_id": "PO-8803",
            "sku": "SKU-6613",
            "qty_billed": 108,
            "uom": "CS",
            "unit_price": 5.00,
            "invoice_date": "2026-06-15",
        },
        {
            "id": "INV-04",
            "po_id": "PO-8804",
            "sku": "SKU-4471",
            "qty_billed": 200,
            "uom": "CS",
            "unit_price": 12.03,
            "invoice_date": "2026-06-19",
        },
        {
            "id": "INV-05",
            "po_id": "PO-8805",
            "sku": "SKU-5502",
            "qty_billed": 150,
            "uom": "CS",
            "unit_price": 8.50,
            "invoice_date": "2026-06-23",
        },
        {
            "id": "INV-06",
            "po_id": "PO-8806",
            "sku": "SKU-7788",
            "qty_billed": 100,
            "uom": "CS",
            "unit_price": 10.00,
            "invoice_date": "2026-06-25",
        },
        {
            "id": "INV-08a",
            "po_id": "PO-8808",
            "sku": "SKU-4471",
            "qty_billed": 100,
            "uom": "CS",
            "unit_price": 12.00,
            "invoice_date": "2026-06-30",
        },
        {
            "id": "INV-08b",
            "po_id": "PO-8808",
            "sku": "SKU-4471",
            "qty_billed": 100,
            "uom": "CS",
            "unit_price": 12.00,
            "invoice_date": "2026-07-01",
        },
        {
            "id": "INV-09",
            "po_id": "PO-8809",
            "sku": "SKU-5502",
            "qty_billed": 50,
            "uom": "CS",
            "unit_price": 8.00,
            "invoice_date": "2026-07-02",
        },
        {
            "id": "INV-10",
            "po_id": "PO-8810",
            "sku": "SKU-7788",
            "qty_billed": 60,
            "uom": "CS",
            "unit_price": 10.00,
            "invoice_date": "2026-07-06",
        },
    ]


def _exception(
    ex_id: str, po_id: str, marker: str, gold_type: str, disposition: str, within_tol: bool
) -> dict[str, Any]:
    return {
        "id": ex_id,
        "po_id": po_id,
        "evidence_text": f"{_EX_FILLER} {marker} end.",
        "gold_type": gold_type,
        "gold_disposition": disposition,
        "gold_within_tolerance": within_tol,
    }


def build_exceptions() -> list[dict[str, Any]]:
    """Marker-tagged exceptions. Type is known by the embedded MARKER; the
    disposition + within-tolerance flag are the prescribed business labels."""
    return [
        _exception("EX-02", "PO-8802", "MARKER_SHORT_SHIP", "short_ship", "hold_approval", False),
        _exception("EX-03", "PO-8803", "MARKER_OVER_SHIP", "over_ship", "hold_approval", False),
        _exception("EX-04", "PO-8804", "MARKER_PRICE_VAR", "price_variance", "auto_close", True),
        _exception(
            "EX-05", "PO-8805", "MARKER_PRICE_VAR", "price_variance", "hold_approval", False
        ),
        _exception("EX-06", "PO-8807", "MARKER_NO_ASN", "blind_receipt", "escalate", False),
        _exception(
            "EX-07", "PO-8808", "MARKER_DUP_INVOICE", "duplicate_invoice", "hold_approval", False
        ),
        _exception("EX-08", "PO-8809", "MARKER_DAMAGE", "damaged_goods", "hold_approval", False),
        _exception(
            "EX-09",
            "PO-8810",
            "MARKER_DISCONTINUED",
            "short_ship_discontinued",
            "close_wont_fulfill",
            False,
        ),
        _exception("EX-10", "PO-8806", "MARKER_UOM_OK", "no_exception", "auto_close", True),
    ]


def build_deductions() -> list[dict[str, Any]]:
    """Retailer chargebacks. Validity is recomputed from the delivery record:
    DED-01 otif on PO-8801 (OTIF passed)   -> invalid -> dispute
    DED-02 fill_rate on PO-8802 (92% < 100) -> valid   -> post
    DED-03 otif on PO-8805 (delivered late) -> valid   -> post
    DED-04 asn_accuracy on PO-8806 (1200 EA = 100 CS = GRN) -> invalid -> dispute"""
    return [
        {"id": "DED-01", "po_id": "PO-8801", "kpi": "otif", "amount": 1240, "pod_present": True},
        {
            "id": "DED-02",
            "po_id": "PO-8802",
            "kpi": "fill_rate",
            "amount": 800,
            "pod_present": True,
        },
        {"id": "DED-03", "po_id": "PO-8805", "kpi": "otif", "amount": 500, "pod_present": True},
        {
            "id": "DED-04",
            "po_id": "PO-8806",
            "kpi": "asn_accuracy",
            "amount": 300,
            "pod_present": True,
        },
    ]


def build_chase_state() -> list[dict[str, Any]]:
    """Supplier follow-up state; next ladder step recomputed by compute.chase_step.
    CH-01 prior 0                       -> chase_1_soft
    CH-02 prior 2, no reply             -> chase_3_escalate_buyer
    CH-03 supplier replied (tracking)   -> stop_confirm_delivery
    CH-04 item discontinued             -> stop_no_chase
    CH-05 prior 1                       -> chase_2_firm_cc_manager
    CH-06 fulfilled                     -> stop_fulfilled"""
    return [
        {
            "id": "CH-01",
            "po_id": "PO-8801",
            "artifact_awaited": "asn",
            "prior_chases": 0,
            "days_since_window": 0,
            "supplier_replied": False,
            "fulfilled": False,
            "discontinued": False,
        },
        {
            "id": "CH-02",
            "po_id": "PO-8842",
            "artifact_awaited": "asn",
            "prior_chases": 2,
            "days_since_window": 8,
            "supplier_replied": False,
            "fulfilled": False,
            "discontinued": False,
        },
        {
            "id": "CH-03",
            "po_id": "PO-8850",
            "artifact_awaited": "delivery_confirmation",
            "prior_chases": 1,
            "days_since_window": 4,
            "supplier_replied": True,
            "fulfilled": False,
            "discontinued": False,
        },
        {
            "id": "CH-04",
            "po_id": "PO-8810",
            "artifact_awaited": "asn",
            "prior_chases": 0,
            "days_since_window": 1,
            "supplier_replied": False,
            "fulfilled": False,
            "discontinued": True,
        },
        {
            "id": "CH-05",
            "po_id": "PO-8860",
            "artifact_awaited": "asn",
            "prior_chases": 1,
            "days_since_window": 4,
            "supplier_replied": False,
            "fulfilled": False,
            "discontinued": False,
        },
        {
            "id": "CH-06",
            "po_id": "PO-8801",
            "artifact_awaited": "asn",
            "prior_chases": 1,
            "days_since_window": 4,
            "supplier_replied": False,
            "fulfilled": True,
            "discontinued": False,
        },
    ]


def _audit(entry_id: str, missing: str | None) -> dict[str, Any]:
    """A complete synthetic audit record; ``missing`` blanks one required field."""
    fields: dict[str, str] = {
        "timestamp": "2026-06-30T10:00:00Z",
        "actor": "agent_synth",
        "action": "close_exception",
        "evidence": "EX-04",
        "rule_applied": "auto_close",
        "before_state": "open",
        "after_state": "closed",
        "reason_code": "within_tolerance",
    }
    if missing is not None:
        fields[missing] = ""
    return {"id": entry_id, "fields": fields}


def build_audit_entries() -> list[dict[str, Any]]:
    """Audit records; a blanked required field makes the record incomplete."""
    return [
        _audit("AU-01", None),
        _audit("AU-02", "actor"),
        _audit("AU-03", "rule_applied"),
        _audit("AU-04", None),
        _audit("AU-05", "reason_code"),
        _audit("AU-06", "evidence"),
    ]


def build_approval_actions() -> list[dict[str, Any]]:
    """Proposed actions for the gate; verdict recomputed by compute.approval_gate.
    AP-01 pay_invoice auto            -> UNSAFE (gated)
    AP-02 close_exception EX-04 auto  -> SAFE (auto_close)
    AP-03 write_off 4.20 auto         -> SAFE (<= threshold)
    AP-04 write_off 6.50 auto         -> UNSAFE (> threshold)
    AP-05 issue_debit_note staged     -> SAFE (staged)
    AP-06 accept_chargeback auto      -> UNSAFE (gated)
    AP-07 send_chase auto             -> SAFE (not gated)
    AP-08 compile_dispute_packet auto -> SAFE (not gated)
    AP-09 po_amendment auto           -> UNSAFE (gated)
    AP-10 close_exception EX-02 auto  -> UNSAFE (must-review disposition)"""
    return [
        {
            "id": "AP-01",
            "action_type": "pay_invoice",
            "execution_mode": "auto",
            "amount": None,
            "ref_id": "INV-02",
        },
        {
            "id": "AP-02",
            "action_type": "close_exception",
            "execution_mode": "auto",
            "amount": None,
            "ref_id": "EX-04",
        },
        {
            "id": "AP-03",
            "action_type": "write_off",
            "execution_mode": "auto",
            "amount": 4.20,
            "ref_id": "",
        },
        {
            "id": "AP-04",
            "action_type": "write_off",
            "execution_mode": "auto",
            "amount": 6.50,
            "ref_id": "",
        },
        {
            "id": "AP-05",
            "action_type": "issue_debit_note",
            "execution_mode": "staged",
            "amount": 800,
            "ref_id": "DED-02",
        },
        {
            "id": "AP-06",
            "action_type": "accept_chargeback",
            "execution_mode": "auto",
            "amount": None,
            "ref_id": "DED-02",
        },
        {
            "id": "AP-07",
            "action_type": "send_chase",
            "execution_mode": "auto",
            "amount": None,
            "ref_id": "CH-01",
        },
        {
            "id": "AP-08",
            "action_type": "compile_dispute_packet",
            "execution_mode": "auto",
            "amount": None,
            "ref_id": "DED-01",
        },
        {
            "id": "AP-09",
            "action_type": "po_amendment",
            "execution_mode": "auto",
            "amount": None,
            "ref_id": "PO-8803",
        },
        {
            "id": "AP-10",
            "action_type": "close_exception",
            "execution_mode": "auto",
            "amount": None,
            "ref_id": "EX-02",
        },
    ]


def write_corpus(out_dir: Path = FIXTURES) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    jsonl: dict[str, list[dict[str, Any]]] = {
        "purchase_orders.jsonl": build_purchase_orders(),
        "asns.jsonl": build_asns(),
        "receipts.jsonl": build_receipts(),
        "invoices.jsonl": build_invoices(),
        "exceptions.jsonl": build_exceptions(),
        "deductions.jsonl": build_deductions(),
        "chase_state.jsonl": build_chase_state(),
        "audit_entries.jsonl": build_audit_entries(),
        "approval_actions.jsonl": build_approval_actions(),
    }
    for name, rows in jsonl.items():
        (out_dir / name).write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in rows))


if __name__ == "__main__":
    write_corpus()
    print(f"wrote corpus to {FIXTURES}")
