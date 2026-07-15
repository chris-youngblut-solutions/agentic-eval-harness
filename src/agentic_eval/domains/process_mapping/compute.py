"""The single answer key for process_mapping — pure functions over the gold maps.

This is the one source of truth for "what the reconstructed workflow is": the
case-authoring path (which writes ``eval/process_mapping/cases.yaml``'s expected
values) and the tests both call it, so the golden set and the answer key can
never drift. It reads the GOLD (``processes.jsonl``) only — never the fragments —
and it is deterministic: same gold in, same answer out.

The load-bearing judgment is the safety verdict: an FBA (fix-before-automate)
step is NOT safe to automate as-is (``FIX_FIRST``); only an AR (automation-ready)
step is ``READY``. ``ready_violations`` is the audit answer key that the
``ready_to_automate_safety`` hard gate scores — of a proposed "automate now" set,
the ones that are actually broken (the steps you would automate while broken).

Set answers are returned as sorted ``list[str]``; handoff edges are canonicalized
as ``"STEP-A->STEP-B"``. ``dimensions.f1`` is composed (not re-derived) in the
tests to assert an authored expected set equals the gold set at F1 == 1.0.
"""

from __future__ import annotations

from agentic_eval.domains.process_mapping.process_map import ProcessMap, load_gold

CATALOG: dict[str, ProcessMap] = load_gold()  # PROC-## -> gold map


def process_ids() -> list[str]:
    """Every process id in the catalog, sorted (the inventory set)."""
    return sorted(CATALOG)


def step_ids(p: ProcessMap) -> set[str]:
    """All real STEP-## ids in a process (the step_extraction gold set)."""
    return {s.step_id for s in p.steps}


def systems_touched(p: ProcessMap) -> set[str]:
    """The distinct systems of record the process's steps touch."""
    return {s.system for s in p.steps}


def system_for(p: ProcessMap, step_id: str) -> str:
    """The one system of record a named step touches."""
    return p.step(step_id).system


def fix_steps(p: ProcessMap) -> set[str]:
    """The step ids flagged fix-before-automate."""
    return {s.step_id for s in p.steps if s.fix_before_automate}


def fix_count(p: ProcessMap) -> int:
    """How many steps are fix-before-automate."""
    return len(fix_steps(p))


def ar_steps(p: ProcessMap) -> set[str]:
    """The automation-ready step ids (safe to automate now) = all steps - FBA."""
    return step_ids(p) - fix_steps(p)


def reason_for(p: ProcessMap, step_id: str) -> str:
    """The FBA reason code (UOM|SOT|JUDG|DATA) of a step, or "" if it is AR."""
    return p.step(step_id).reason


def disposition_for(p: ProcessMap, step_id: str) -> str:
    """The step's disposition: "FBA" if fix-before-automate, else "AR"."""
    return "FBA" if p.step(step_id).fix_before_automate else "AR"


def safety_verdict(p: ProcessMap, step_id: str) -> str:
    """The hard-gate verdict: "READY" only for an AR step, else "FIX_FIRST"."""
    return "READY" if step_id in ar_steps(p) else "FIX_FIRST"


def _edge_token(frm: str, to: str) -> str:
    return f"{frm}->{to}"


def handoff_edges(p: ProcessMap) -> set[str]:
    """Every ordered edge as "STEP-A->STEP-B" (handoffs and decisions alike)."""
    return {_edge_token(h.frm, h.to) for h in p.handoffs}


def decision_edges(p: ProcessMap) -> set[str]:
    """Only the decision-point edges (a branch is chosen), as "STEP-A->STEP-B"."""
    return {_edge_token(h.frm, h.to) for h in p.handoffs if h.kind == "decision"}


def via_for(p: ProcessMap, frm: str, to: str) -> str:
    """The system that carries a named handoff edge."""
    return p.edge(frm, to).via


def ready_violations(p: ProcessMap, proposed_ready: set[str]) -> set[str]:
    """Of a proposed 'automate now' set, the ones that are actually FBA — i.e. the
    steps you would be automating while broken. The audit hard-gate answer key."""
    return set(proposed_ready) & fix_steps(p)


def is_safe_plan(p: ProcessMap, proposed_ready: set[str]) -> bool:
    """True iff none of the proposed 'automate now' steps are broken (FBA)."""
    return not ready_violations(p, proposed_ready)


def _set_str(items: set[str]) -> str:
    """Canonical comma-separated rendering of a set answer (sorted, stable)."""
    return ",".join(sorted(items))


def build_expectations() -> dict[str, str]:
    """Recompute every case's expected string from the gold — the drift guard.

    Keyed by case id; the value is the canonical expected answer. Set answers are
    rendered sorted (the set checker is order-insensitive, so this only fixes a
    stable serialization). ``test_case_expectations_match_gold`` recomputes this
    and asserts it agrees with the committed ``cases.yaml``.
    """
    c = CATALOG
    return {
        # process_inventory
        "pm_inventory_count": str(len(process_ids())),
        "pm_inventory_set": ",".join(process_ids()),
        # step_extraction
        "pm_steps_proc04": _set_str(step_ids(c["PROC-04"])),
        "pm_steps_proc06": _set_str(step_ids(c["PROC-06"])),
        "pm_steps_proc02": _set_str(step_ids(c["PROC-02"])),
        "pm_steps_proc07": _set_str(step_ids(c["PROC-07"])),
        # system_coverage
        "pm_systems_proc04": _set_str(systems_touched(c["PROC-04"])),
        "pm_systems_proc02": _set_str(systems_touched(c["PROC-02"])),
        "pm_systems_proc07": _set_str(systems_touched(c["PROC-07"])),
        "pm_system_of_step43": system_for(c["PROC-04"], "STEP-43"),
        "pm_system_of_step45": system_for(c["PROC-04"], "STEP-45"),
        # fix_before_automate_flagging
        "pm_fix_set_proc04": _set_str(fix_steps(c["PROC-04"])),
        "pm_fix_count_proc07": str(fix_count(c["PROC-07"])),
        "pm_fix_count_proc06": str(fix_count(c["PROC-06"])),
        "pm_fix_reason_step43": reason_for(c["PROC-04"], "STEP-43"),
        "pm_fix_reason_step44": reason_for(c["PROC-04"], "STEP-44"),
        "pm_disposition_step42": disposition_for(c["PROC-04"], "STEP-42"),
        # handoff_identification
        "pm_edges_proc04": _set_str(handoff_edges(c["PROC-04"])),
        "pm_decision_edges_proc07": _set_str(decision_edges(c["PROC-07"])),
        "pm_via_step44_45": via_for(c["PROC-04"], "STEP-44", "STEP-45"),
        "pm_via_step64_65": via_for(c["PROC-06"], "STEP-64", "STEP-65"),
        # ready_to_automate_safety (hard gate)
        "pm_safety_step44": safety_verdict(c["PROC-04"], "STEP-44"),
        "pm_safety_step71": safety_verdict(c["PROC-07"], "STEP-71"),
        "pm_safety_audit_proc06": _set_str(
            ready_violations(c["PROC-06"], {"STEP-61", "STEP-63", "STEP-65"})
        ),
        "pm_safety_safe_set_proc07": _set_str(ar_steps(c["PROC-07"])),
    }
