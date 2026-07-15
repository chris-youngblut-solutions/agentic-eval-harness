"""Deterministic generator for the process_mapping fragment world (sources.jsonl).

Everything here is FABRICATED and GENERIC — generic retail/CPG buyer-side process
*shapes* only. Each of the eight processes seeds FOUR messy fragments (an email
thread, a spreadsheet snippet, a portal click-path, a tribal-knowledge note)
that between them mention every real ``STEP-##`` and the evidence a mapper
reasons from, but never the gold labels (no disposition, no system-of-record
verdict, no reason code). Sources individually omit steps (forcing a union),
overlap and disagree, and each carries exactly ONE distractor ``STEP-##`` that is
explicitly flagged as belonging to a different flow — so recovering the true step
set means union + dedup + distractor-drop.

There is no randomness: re-running writes byte-identical ``sources.jsonl`` (a test
guards this). ``processes.jsonl`` (the gold answer key) is hand-authored and is
NOT written here — this generator writes only the world, exactly as
data_semantic's generator writes ``facts.jsonl`` while ``model.json`` is authored.

Run as a module to (re)write the committed fixture:

    uv run python -m agentic_eval.domains.process_mapping.generate
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agentic_eval.domains.process_mapping.process_map import FIXTURES, SOURCES_PATH


def _text(source_id: str, process_id: str, kind: str, content: str) -> dict[str, Any]:
    return {
        "source_id": source_id,
        "process_id": process_id,
        "kind": kind,
        "content": content.strip("\n"),
    }


def _sheet(source_id: str, process_id: str, rows: list[list[str]]) -> dict[str, Any]:
    return {
        "source_id": source_id,
        "process_id": process_id,
        "kind": "spreadsheet",
        "rows": rows,
    }


def build_sources() -> list[dict[str, Any]]:
    """The 32 authored fragments (4 per process), in stable order.

    Layout per process: SRC-x01 email_thread, SRC-x02 spreadsheet,
    SRC-x03 portal_clickpath, SRC-x04 tribal_note (x = process number).
    """
    rows: list[dict[str, Any]] = []

    # --- PROC-01 Vendor Onboarding -----------------------------------------
    rows.append(
        _text(
            "SRC-101",
            "PROC-01",
            "email_thread",
            """
Subject: new vendor - can we get them set up
STEP-10 came in as a plain email, no form behind it, so half the fields are
missing. On STEP-14 the compliance sign-off is still just people replying on
this chain - there's no system field for the risk decision, it only lives here.
STEP-13 banking verification is whatever the AP lead has always eyeballed, not
written down anywhere. (STEP-19 is the payment-run cutover - different flow,
ignore it here.)
""",
        )
    )
    rows.append(
        _sheet(
            "SRC-102",
            "PROC-01",
            [
                ["step_code", "note"],
                ["STEP-11", "W-9 / banking / COI arrive on paper, scanned and keyed in later"],
                ["STEP-15", "EDI trading-partner handshake half-configured; test cycle runs late"],
            ],
        )
    )
    rows.append(
        _text(
            "SRC-103",
            "PROC-01",
            "portal_clickpath",
            """
Portal path:
Screen 1 -> STEP-12 send the structured supplier-portal invite (clean intake form).
Screen 4 -> STEP-16 create the vendor master record once fields validate.
Screen 6 -> STEP-17 flip EDI live after the structured test cycle passes.
""",
        )
    )
    rows.append(
        _text(
            "SRC-104",
            "PROC-01",
            "tribal_note",
            """
order of ops: STEP-10 -> STEP-11 -> STEP-12 -> STEP-13 -> STEP-14 -> STEP-15 ->
STEP-16 -> STEP-17. half of this only makes sense once you've onboarded a few.
""",
        )
    )

    # --- PROC-02 Item / SKU Setup ------------------------------------------
    rows.append(
        _text(
            "SRC-201",
            "PROC-02",
            "email_thread",
            """
Subject: sku setup backlog
STEP-20 the vendor submits item data but it comes in patchy, missing dims and
attributes. STEP-24 the merch attribute enrichment is pure tribal - the analyst
just knows what to put. STEP-25 the cost keeps drifting because the deal sheet
says one thing and the system says another and nobody agrees which is right.
(STEP-29 is the seasonal reset - a different flow, ignore.)
""",
        )
    )
    rows.append(
        _sheet(
            "SRC-202",
            "PROC-02",
            [
                ["step_code", "note"],
                [
                    "STEP-22",
                    "pack hierarchy each/inner/case/pallet keyed by hand; multipliers disagree",
                ],
                ["STEP-23", "catch-weight items - weight varies per unit, conversion never pinned"],
            ],
        )
    )
    rows.append(
        _text(
            "SRC-203",
            "PROC-02",
            "portal_clickpath",
            """
Portal path:
Screen 2 -> STEP-21 portal schema validation runs on submit (structured).
Screen 5 -> STEP-26 create the item master record once validation is green.
""",
        )
    )
    rows.append(
        _text(
            "SRC-204",
            "PROC-02",
            "tribal_note",
            """
order of ops: STEP-20 -> STEP-21 -> STEP-22 -> STEP-23 -> STEP-24 -> STEP-25 ->
STEP-26. the pack-math and cost steps are where everything stalls.
""",
        )
    )

    # --- PROC-03 Replenishment PO ------------------------------------------
    rows.append(
        _text(
            "SRC-301",
            "PROC-03",
            "email_thread",
            """
Subject: this week's buy
STEP-30 the demand forecast is a gut call the planner makes off last year.
STEP-32 the buyer overrides the number and the why-we-changed-it never gets
written down. STEP-33 the PO terms get hammered out right here in email, there's
no system of record for the agreed terms. (STEP-39 is the vendor-scorecard
review, different flow - ignore.)
""",
        )
    )
    rows.append(
        _sheet(
            "SRC-302",
            "PROC-03",
            [
                ["step_code", "note"],
                ["STEP-31", "reorder qty in cases but on-hand in eaches; pack conversion is fuzzy"],
                ["STEP-35", "EDI 850 send fails on incomplete item data; goes out late and dirty"],
            ],
        )
    )
    rows.append(
        _text(
            "SRC-303",
            "PROC-03",
            "portal_clickpath",
            """
Portal path:
Screen 3 -> STEP-34 create the purchase order in the system (deterministic).
""",
        )
    )
    rows.append(
        _text(
            "SRC-304",
            "PROC-03",
            "tribal_note",
            """
order of ops: STEP-30 -> STEP-31 -> STEP-32 -> STEP-33 -> STEP-34 -> STEP-35.
the forecast and the terms are the soft parts.
""",
        )
    )

    # --- PROC-04 PO-to-Receipt 3-Way Match ---------------------------------
    rows.append(
        _text(
            "SRC-401",
            "PROC-04",
            "email_thread",
            """
Subject: match exceptions
On STEP-44 the tolerance % is just whatever AP has always done, not written
anywhere. If it's out of tolerance we kick it to STEP-45 and the reason only
lives in this email chain - there's no system field for it. (STEP-49 slotting is
a merch-promo thing, different flow - ignore it here.)
""",
        )
    )
    rows.append(
        _sheet(
            "SRC-402",
            "PROC-04",
            [
                ["step_code", "note"],
                ["STEP-41", "dock counts still come in on the clipboard, keyed in that night"],
                [
                    "STEP-43",
                    "PO in CASES, ASN in EACHES, invoice by WEIGHT - pack math never reconciled",
                ],
            ],
        )
    )
    rows.append(
        _text(
            "SRC-403",
            "PROC-04",
            "portal_clickpath",
            """
Portal path:
Screen 1 -> EDI inbox: STEP-40 ASN (856) lands structured.
Screen 3 -> match panel: STEP-42 compares receipt/PO/invoice when all three are in.
Screen 7 -> STEP-46 posts the receipt and accrues.
""",
        )
    )
    rows.append(
        _text(
            "SRC-404",
            "PROC-04",
            "tribal_note",
            """
order of ops: STEP-40 -> STEP-41 -> STEP-42 -> STEP-43 -> STEP-44 -> STEP-45 ->
STEP-46. dock count -> match -> fix the UOM -> tolerance -> if it fails, route by
email, then post. half of this only makes sense if you've done it a year.
""",
        )
    )

    # --- PROC-05 Invoice Approval / AP -------------------------------------
    rows.append(
        _text(
            "SRC-501",
            "PROC-05",
            "email_thread",
            """
Subject: approvals stuck
STEP-52 the GL coding is a judgment call the senior clerk makes, no rule for it.
STEP-54 the reconciliation happens off to the side when the numbers disagree.
STEP-55 approval is chased over email and the sign-off reason lives nowhere else.
(STEP-59 is the month-end accrual sweep, different flow - ignore.)
""",
        )
    )
    rows.append(
        _sheet(
            "SRC-502",
            "PROC-05",
            [
                ["step_code", "note"],
                ["STEP-50", "invoices arrive as emailed PDFs; someone keys them in by hand"],
                ["STEP-54", "exceptions reconciled in this sheet because the two systems disagree"],
            ],
        )
    )
    rows.append(
        _text(
            "SRC-503",
            "PROC-05",
            "portal_clickpath",
            """
Portal path:
Screen 1 -> STEP-51 structured invoice capture into the system.
Screen 2 -> STEP-53 auto-match to PO and receipt (deterministic).
Screen 5 -> STEP-56 post the payment.
""",
        )
    )
    rows.append(
        _text(
            "SRC-504",
            "PROC-05",
            "tribal_note",
            """
order of ops: STEP-50 -> STEP-51 -> STEP-52 -> STEP-53 -> STEP-54 -> STEP-55 ->
STEP-56. capture is clean; coding and approval are the soft spots.
""",
        )
    )

    # --- PROC-06 OS&D Receiving Exception ----------------------------------
    rows.append(
        _text(
            "SRC-601",
            "PROC-06",
            "email_thread",
            """
Subject: OS&D at the dock
STEP-61 the damage/overage note is handwritten and it's a judgment whether it's
short or damaged. STEP-62 the shortage log is a spreadsheet standing in for a
system nobody built. STEP-64 the exception gets routed to a person by email, and
the disposition reason is only in the thread. STEP-66 the carrier claim is filed
from a pile of unstructured notes. (STEP-68 is the returns-to-vendor flow,
different flow - ignore.)
""",
        )
    )
    rows.append(
        _sheet(
            "SRC-602",
            "PROC-06",
            [
                ["step_code", "note"],
                ["STEP-60", "receipt scan/count still half paper at the dock; totals keyed later"],
                ["STEP-63", "exception qty in eaches but PO in cases - pack math never lines up"],
            ],
        )
    )
    rows.append(
        _text(
            "SRC-603",
            "PROC-06",
            "portal_clickpath",
            """
Portal path:
Screen 4 -> STEP-65 post the exception adjustment into the system (structured).
""",
        )
    )
    rows.append(
        _text(
            "SRC-604",
            "PROC-06",
            "tribal_note",
            """
order of ops: STEP-60 -> STEP-61 -> STEP-62 -> STEP-63 -> STEP-64 -> STEP-65 ->
STEP-66. the handoff from STEP-64 to STEP-65 is literally an email to the desk
that keys the adjustment. then you file the claim.
""",
        )
    )

    # --- PROC-07 Deduction / Chargeback ------------------------------------
    rows.append(
        _text(
            "SRC-701",
            "PROC-07",
            "email_thread",
            """
Subject: deduction disputes
STEP-71 someone has to decode the retailer's reason code by hand - the mapping is
in nobody's system, it's tribal. STEP-72 the validity triage is a judgment and
the two systems disagree on what's owed. STEP-75 the dispute package is drafted
here in email and the argument only lives in the thread. STEP-76 whether we
dispute or eat it is a person's call. (STEP-79 is the co-op accrual, different
flow - ignore.)
""",
        )
    )
    rows.append(
        _sheet(
            "SRC-702",
            "PROC-07",
            [
                ["step_code", "note"],
                ["STEP-73", "backup docs (POD, signed BOLs) show up late or not at all"],
                [
                    "STEP-74",
                    "claim by weight, our records by case - recomputing pack math is manual",
                ],
            ],
        )
    )
    rows.append(
        _text(
            "SRC-703",
            "PROC-07",
            "portal_clickpath",
            """
Portal path:
Screen 1 -> EDI inbox: STEP-70 the deduction (812) lands structured.
Screen 8 -> STEP-77 post the recovery/accrual once the dispute resolves.
""",
        )
    )
    rows.append(
        _text(
            "SRC-704",
            "PROC-07",
            "tribal_note",
            """
order of ops: STEP-70 -> STEP-71 -> STEP-72 -> STEP-73 -> STEP-74 -> STEP-75 ->
STEP-76 -> STEP-77. at STEP-72 if it's a valid deduction you branch to gather
backup; at STEP-76 if we win the dispute you branch to post recovery.
""",
        )
    )

    # --- PROC-08 Trade-Promo Settlement ------------------------------------
    rows.append(
        _text(
            "SRC-801",
            "PROC-08",
            "email_thread",
            """
Subject: promo settlement
STEP-80 the promo terms arrive on a deal sheet over email and that sheet is the
only record of what was agreed. STEP-83 the incremental-lift number is an
analyst's judgment. STEP-85 the settlement never reconciles cleanly because the
deal sheet and the ledger disagree on what's owed. (STEP-89 is the new-item
launch fund, different flow - ignore.)
""",
        )
    )
    rows.append(
        _sheet(
            "SRC-802",
            "PROC-08",
            [
                ["step_code", "note"],
                [
                    "STEP-81",
                    "accrual rate is per-case but claims come per-each; rate math keyed by hand",
                ],
                [
                    "STEP-84",
                    "matching promo claims to deals fails when the deal reference is missing",
                ],
            ],
        )
    )
    rows.append(
        _text(
            "SRC-803",
            "PROC-08",
            "portal_clickpath",
            """
Portal path:
Screen 1 -> EDI inbox: STEP-82 the POS sales (852) load structured.
Screen 6 -> STEP-86 post the settlement.
""",
        )
    )
    rows.append(
        _text(
            "SRC-804",
            "PROC-08",
            "tribal_note",
            """
order of ops: STEP-80 -> STEP-81 -> STEP-82 -> STEP-83 -> STEP-84 -> STEP-85 ->
STEP-86. the deal sheet drives the whole thing and it's just a spreadsheet in
someone's inbox.
""",
        )
    )

    return rows


def write_sources(out_path: Path = SOURCES_PATH) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    rows = build_sources()
    out_path.write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in rows))


if __name__ == "__main__":
    write_sources()
    print(f"wrote sources to {FIXTURES / 'sources.jsonl'} ({len(build_sources())} fragments)")
