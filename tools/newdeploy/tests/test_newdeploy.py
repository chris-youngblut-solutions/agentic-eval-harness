"""Tests for the newdeploy scaffolder.

Stamp a sample deployment into a tmp dir and assert:
  - all expected files present in the right layout;
  - every {{scaffolding}} token was replaced; no residuals leak;
  - <<authoring>> tokens are LEFT INTACT (the FDE's editable surface);
  - the copied board is byte-identical to source (verbatim mode) and still
    self-contained (no external script/style/http asset);
  - --isolate-board rewrites exactly the localStorage KEY and nothing else;
  - the seeded ROI cost deck round-trips as JSON and keeps its <<TOKENS>>;
  - the seeded/committed policy shape keeps the frozen 11 gated_actions and
    excludes write_off / close_exception (the drift-guard newdeploy must not break);
  - system-dialect validation: invalid values fail; --list-systems works;
  - refuse-on-nonempty unless --force; slug validation; determinism (no clock).
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
NEWDEPLOY = HERE.parent / "newdeploy.py"
TOOLS = HERE.parent.parent
BOARD_SRC = TOOLS / "exception-spec-dsl"
ROI_SRC = TOOLS / "roi"

sys.path.insert(0, str(HERE.parent))
import newdeploy as nd  # noqa: E402

FROZEN_GATED = {
    "pay_invoice",
    "issue_debit_note",
    "issue_credit_note",
    "post_deduction",
    "accept_chargeback",
    "po_amendment",
    "po_cancellation",
    "accept_over_ship",
    "authorize_return",
    "commit_supplier_payment",
    "override_scorecard",
}
EXPECTED_FILES = [
    "README.md",
    "runbook.md",
    "scoping-checklist.md",
    "connector-config.env.example",
    ".mcp.json",
    "roi-baseline.json",
    "exception-spec.inkspec.html",
    "fixtures/retail_ops/.gitkeep",
    "roi/ops_baseline.jsonl",
    "roi/ops_automated.jsonl",
    "roi/roi-report.inkspec.html",
    "refs/exception-spec.README.md",
    "refs/exception-spec.PROVENANCE.md",
    "refs/sample-export.policy.json",
]


def run_cli(args, cwd):
    return subprocess.run(
        [sys.executable, str(NEWDEPLOY), *args],
        cwd=cwd,
        capture_output=True,
        text=True,
    )


@pytest.fixture()
def stamped(tmp_path):
    r = run_cli(
        [
            "acme-foods",
            "--customer",
            "ACME Foods Inc",
            "--erp",
            "netsuite",
            "--supplier",
            "coupa",
            "--out",
            str(tmp_path),
        ],
        cwd=tmp_path,
    )
    assert r.returncode == 0, r.stderr
    return tmp_path / "acme-foods"


def test_all_files_present(stamped):
    for rel in EXPECTED_FILES:
        assert (stamped / rel).exists(), f"missing {rel}"


def test_scaffolding_tokens_replaced_none_leak(stamped):
    # No scaffolding token survives: neither a token-SHAPED residual ({{UPPER...}})
    # nor ANY literal "{{" sequence. The templates teach the two token layers in
    # words, so a naive grep for "{{" over the stamped kit is clean. (The <<...>>
    # authoring tokens are intentionally kept for the FDE; asserted elsewhere.)
    token_shaped = re.compile(r"\{\{[A-Z][^}]*\}\}")
    for rel in (
        "README.md",
        "runbook.md",
        "scoping-checklist.md",
        "connector-config.env.example",
        ".mcp.json",
    ):
        text = (stamped / rel).read_text()
        assert not token_shaped.search(text), f"residual token in {rel}"
        assert "{{" not in text, f"stray '{{{{' in {rel}"
    # {{SLUG}} lands in the doc files (the .mcp.json snippet is slug-agnostic)
    for rel in ("README.md", "runbook.md", "scoping-checklist.md", "connector-config.env.example"):
        assert "acme-foods" in (stamped / rel).read_text(), f"slug missing in {rel}"
    assert "ACME Foods Inc" in (stamped / "README.md").read_text()  # {{CUSTOMER}}


def test_chosen_systems_stamped(stamped):
    env = (stamped / "connector-config.env.example").read_text()
    assert "RETAIL_ERP_SYSTEM=netsuite" in env
    assert "RETAIL_SUPPLIER_SYSTEM=coupa" in env
    assert "RETAIL_EMAIL_SYSTEM=msgraph" in env  # default
    assert "RETAIL_SHEETS_SYSTEM=google_sheets" in env  # default
    mcp = json.loads((stamped / ".mcp.json").read_text())
    assert mcp["mcpServers"]["retail-erp"]["env"]["RETAIL_ERP_SYSTEM"] == "netsuite"
    assert mcp["mcpServers"]["retail-supplier"]["env"]["RETAIL_SUPPLIER_SYSTEM"] == "coupa"
    # approval token stays an operator placeholder on every server, never a real value
    for srv in mcp["mcpServers"].values():
        assert "operator-injected" in srv["env"][nd.APPROVAL_TOKEN_VAR]


def test_date_is_fillin_not_clock(stamped):
    # deterministic: a literal fill-in blank, never a real YYYY-MM-DD
    assert "____-__-__" in (stamped / "runbook.md").read_text()
    # the module never imports a clock (real import statements, not prose)
    src_lines = [ln.strip() for ln in NEWDEPLOY.read_text().splitlines()]
    clock = re.compile(r"^(import|from)\s+(datetime|time|calendar)\b")
    assert not any(clock.match(ln) for ln in src_lines)


def test_board_copied_verbatim_and_self_contained(stamped):
    stamped_html = (stamped / "exception-spec.inkspec.html").read_text()
    src_html = (BOARD_SRC / "exception-spec.inkspec.html").read_text()
    assert stamped_html == src_html, "verbatim board must be byte-identical"
    # self-containment: no external assets
    nd.assert_self_contained(stamped_html, "board")
    assert 'const KEY="exc-spec-dsl-2026-07";' in stamped_html


def test_authoring_tokens_left_intact(stamped):
    # <<TOKEN>> business placeholders survive in board + cost deck
    assert "<<QTY_TOL_PCT>>" in (stamped / "exception-spec.inkspec.html").read_text()
    cost = (stamped / "roi-baseline.json").read_text()
    for tok in ("<<T_MANUAL_MIN>>", "<<W_FTE>>", "<<INTEGRATION>>", "<<ALPHA>>"):
        assert tok in cost


def test_roi_baseline_valid_json_and_read_shape(stamped):
    cost = json.loads((stamped / "roi-baseline.json").read_text())
    assert cost["schema"] == "roi-cost/0.1"
    assert set(cost["params"]) >= {"t_manual_min", "w_fte_usd_per_hr", "integration_onetime"}
    # only .value is read by roi.py; each param carries one
    assert cost["params"]["t_manual_min"]["value"] == 12


def test_gated_actions_drift_guard_preserved(stamped):
    pol = json.loads((stamped / "refs" / "sample-export.policy.json").read_text())
    assert set(pol["gated_actions"]) == FROZEN_GATED
    assert "write_off" not in pol["gated_actions"]
    assert "close_exception" not in pol["gated_actions"]


def test_isolate_board_rewrites_only_the_key(tmp_path):
    r = run_cli(["beta-mart", "--isolate-board", "--out", str(tmp_path)], cwd=tmp_path)
    assert r.returncode == 0, r.stderr
    html = (tmp_path / "beta-mart" / "exception-spec.inkspec.html").read_text()
    assert 'const KEY="exc-spec-beta-mart";' in html
    assert 'const KEY="exc-spec-dsl-2026-07";' not in html
    # exactly one line changed vs source
    src = (BOARD_SRC / "exception-spec.inkspec.html").read_text().splitlines()
    got = html.splitlines()
    diffs = [i for i, (a, b) in enumerate(zip(src, got, strict=True)) if a != b]
    assert len(diffs) == 1 and len(src) == len(got)
    nd.assert_self_contained(html, "isolated board")


def test_invalid_system_rejected(tmp_path):
    r = run_cli(["x", "--erp", "oracle_ebs", "--out", str(tmp_path)], cwd=tmp_path)
    assert r.returncode != 0
    assert "invalid choice" in r.stderr.lower() or "oracle_ebs" in r.stderr


def test_bad_slug_rejected(tmp_path):
    r = run_cli(["Acme_Foods", "--out", str(tmp_path)], cwd=tmp_path)
    assert r.returncode == 2
    assert "kebab" in r.stderr.lower()


def test_refuse_nonempty_then_force(tmp_path):
    a = run_cli(["dup", "--out", str(tmp_path)], cwd=tmp_path)
    assert a.returncode == 0
    b = run_cli(["dup", "--out", str(tmp_path)], cwd=tmp_path)
    assert b.returncode == 2 and "clobber" in b.stderr.lower()
    c = run_cli(["dup", "--force", "--out", str(tmp_path)], cwd=tmp_path)
    assert c.returncode == 0


def test_list_systems(tmp_path):
    r = run_cli(["--list-systems"], cwd=tmp_path)
    assert r.returncode == 0
    for token in (
        "RETAIL_ERP_SYSTEM",
        "sap_s4hana",
        "dynamics365",
        "sps_commerce",
        "msgraph",
        "google_sheets",
        nd.APPROVAL_TOKEN_VAR,
    ):
        assert token in r.stdout


def test_missing_source_stops(tmp_path):
    r = run_cli(
        ["y", "--board-src", str(tmp_path / "nope"), "--out", str(tmp_path)],
        cwd=tmp_path,
    )
    assert r.returncode == 3
