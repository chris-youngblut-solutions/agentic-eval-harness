#!/usr/bin/env python3
"""newdeploy — stamp a per-customer FDE deployment kit.

Given a customer slug, stamp `deployments/<slug>/` from templates + three real
source artifacts (the exception-spec DSL board, the retail-ops MCP kit config,
and the ROI harness decks), so deployment #2 is faster than deployment #1.

Follows the classic cookiecutter-style scaffolder contract:
  - a canonical, inert template tree lives separate from the output;
  - the basename of the target dir becomes {{SLUG}};
  - `.tmpl` files are substituted-then-suffix-dropped; substitution logic lives
    in exactly ONE place (this file); copied artifacts stay byte-verbatim;
  - refuse a non-empty target unless --force;
  - resolve-the-source ladder; if a source is missing, STOP and report —
    never hand-write the board;
  - report what was stamped as a File | Kind | Purpose table;
  - name the one deliberate manual step the CLI does NOT do.

DETERMINISTIC BY CONSTRUCTION: this module never reads the clock. There is no
`import datetime`/`time`. Date fields are stamped as the fill-in placeholder
`____-__-__`, which the FDE fills at go-live (the no-Date-in-scripts constraint).

Two DISTINCT token layers (never conflated):
  * scaffolding tokens  {{UPPER_SNAKE}}  — substituted here, once, in `.tmpl` files.
  * authoring tokens    <<UPPER_SNAKE>>  — the DSL/ROI business-value placeholders
    the FDE fills at author time. LEFT INTACT. Never touched here.
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

# --- system-selection allowlists (mirror retail-ops-mcp-kit exactly) ---------
SYSTEMS: dict[str, dict[str, object]] = {
    "erp": {
        "server": "retail-erp-mcp",
        "env": "RETAIL_ERP_SYSTEM",
        "allowed": ("sap_s4hana", "netsuite", "dynamics365"),
        "default": "sap_s4hana",
    },
    "supplier": {
        "server": "retail-supplier-mcp",
        "env": "RETAIL_SUPPLIER_SYSTEM",
        "allowed": ("sps_commerce", "coupa", "ariba"),
        "default": "sps_commerce",
    },
    "email": {
        "server": "retail-email-mcp",
        "env": "RETAIL_EMAIL_SYSTEM",
        "allowed": ("msgraph", "gmail"),
        "default": "msgraph",
    },
    "sheets": {
        "server": "retail-sheets-mcp",
        "env": "RETAIL_SHEETS_SYSTEM",
        "allowed": ("google_sheets", "msgraph_excel"),
        "default": "google_sheets",
    },
}

APPROVAL_TOKEN_VAR = "RETAIL_OPS_MCP_APPROVAL_TOKEN"
GENERATOR = "newdeploy"
DATE_FILL_IN = "____-__-__"  # deterministic placeholder; never a real date
SLUG_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")

# The board's per-deployment localStorage key. The ONLY genuinely per-deployment
# string in the 70KB board (the domain name `retail_ops` also appears in the
# provenance/title/sample, so tokenizing it would corrupt the synthetic text).
BOARD_KEY_LITERAL = 'const KEY="exc-spec-dsl-2026-07";'


class StampError(Exception):
    """Fatal, reported to stderr; maps to a nonzero exit code."""

    def __init__(self, message: str, code: int = 1) -> None:
        super().__init__(message)
        self.code = code


# --- source resolution (resolve-the-source ladder; never hand-write) ---------
def _resolve_source(explicit: str | None, sibling_name: str, tools_dir: Path) -> Path:
    """Ladder: --*-src flag  ->  sibling of tools/  ->  STOP and report."""
    if explicit:
        p = Path(explicit).expanduser().resolve()
        if not p.exists():
            raise StampError(f"--*-src path does not exist: {p}", code=3)
        return p
    sibling = (tools_dir / sibling_name).resolve()
    if sibling.exists():
        return sibling
    raise StampError(
        f"could not resolve source artifact {sibling_name!r} "
        f"(looked in {sibling}). Pass --board-src / --roi-src, or run from the "
        f"harness tools/ tree. Refusing to hand-write the artifact.",
        code=3,
    )


def _require(path: Path, what: str) -> Path:
    if not path.is_file():
        raise StampError(f"missing {what}: {path} (refusing to fabricate it)", code=3)
    return path


# --- substitution (exactly one place; `.tmpl` files only) --------------------
def build_tokens(slug: str, customer: str, choices: dict[str, str]) -> dict[str, str]:
    return {
        "{{SLUG}}": slug,
        "{{CUSTOMER}}": customer,
        "{{DATE:fill-in}}": DATE_FILL_IN,
        "{{ERP_SYSTEM}}": choices["erp"],
        "{{SUPPLIER_SYSTEM}}": choices["supplier"],
        "{{EMAIL_SYSTEM}}": choices["email"],
        "{{SHEETS_SYSTEM}}": choices["sheets"],
        "{{APPROVAL_TOKEN_VAR}}": APPROVAL_TOKEN_VAR,
        "{{GENERATOR}}": GENERATOR,
    }


def substitute(text: str, tokens: dict[str, str]) -> str:
    for tok, val in tokens.items():
        text = text.replace(tok, val)
    return text


def assert_no_residual_scaffold_tokens(text: str, name: str) -> None:
    """Catch typo'd/unknown {{TOKEN}} slots.

    Token grammar is uppercase-led (SLUG, ERP_SYSTEM, DATE:fill-in, …), so this
    ignores documentary prose like the literal ``{{...}}`` the templates use to
    *explain* the two token layers, and ignores ``<<...>>`` authoring tokens.
    """
    leftover = re.findall(r"\{\{[A-Z][^}]*\}\}", text)
    if leftover:
        raise StampError(f"unsubstituted scaffolding token(s) in {name}: {sorted(set(leftover))}")


def assert_self_contained(html: str, name: str) -> None:
    """The copied board must stay single-file: no external script/style/asset."""
    problems: list[str] = []
    if re.search(r"<script[^>]*\bsrc\s*=", html, re.I):
        problems.append("external <script src=>")
    if re.search(r'<link[^>]*\brel\s*=\s*["\']?stylesheet', html, re.I):
        problems.append("external <link rel=stylesheet>")
    if re.search(r'\b(?:src|href)\s*=\s*["\']https?://', html, re.I):
        problems.append("http(s):// asset reference")
    if problems:
        raise StampError(f"{name} is not self-contained: {', '.join(problems)}")


# --- the stamp ---------------------------------------------------------------
def stamp(
    slug: str,
    customer: str,
    out_parent: Path,
    choices: dict[str, str],
    templates_dir: Path,
    board_src: Path,
    roi_src: Path,
    isolate_board: bool,
    force: bool,
) -> tuple[Path, list[tuple[str, str, str]]]:
    target = (out_parent / slug).resolve()
    if target.exists() and any(target.iterdir()) and not force:
        raise StampError(
            f"target {target} exists and is not empty. Refusing to clobber; "
            f"re-run with --force to re-seat.",
            code=2,
        )
    tokens = build_tokens(slug, customer, choices)
    report: list[tuple[str, str, str]] = []

    # pre-flight: verify every non-template source artifact exists BEFORE writing
    # anything, so a missing source aborts cleanly (exit 3) rather than leaving a
    # half-stamped kit. (Each `.tmpl` is also checked as it is rendered, below.)
    for path, what in (
        (board_src / "exception-spec.inkspec.html", "exception board HTML"),
        (board_src / "README.md", "board sidecar README.md"),
        (board_src / "PROVENANCE.md", "board sidecar PROVENANCE.md"),
        (board_src / "sample-export.policy.json", "board sidecar sample-export.policy.json"),
        (roi_src / "fixtures" / "cost.json", "ROI cost deck"),
        (roi_src / "fixtures" / "ops_baseline.jsonl", "ROI seed ops_baseline.jsonl"),
        (roi_src / "fixtures" / "ops_automated.jsonl", "ROI seed ops_automated.jsonl"),
        (roi_src / "roi-report.inkspec.html", "ROI report HTML"),
    ):
        _require(path, what)

    # 0. dirs
    (target / "fixtures" / "retail_ops").mkdir(parents=True, exist_ok=True)
    (target / "roi").mkdir(parents=True, exist_ok=True)
    (target / "refs").mkdir(parents=True, exist_ok=True)

    # 1. stamp every `.tmpl` (substitute -> drop `.tmpl`)
    #    mcp.host.json.tmpl -> .mcp.json (special-cased name)
    tmpl_targets = {
        "connector-config.env.example.tmpl": "connector-config.env.example",
        "mcp.host.json.tmpl": ".mcp.json",
        "runbook.md.tmpl": "runbook.md",
        "scoping-checklist.md.tmpl": "scoping-checklist.md",
        "README.md.tmpl": "README.md",
    }
    purposes = {
        "connector-config.env.example": "the four *_SYSTEM dialects + approval-token placeholder",
        ".mcp.json": "host wiring snippet for the four MCP servers",
        "runbook.md": "Phase 0->6 go-live -> expansion runbook with gates",
        "scoping-checklist.md": "tolerances / gated-actions / systems / approval-owners intake",
        "README.md": "deployment index",
    }
    for tmpl_name, out_name in tmpl_targets.items():
        src = _require(templates_dir / tmpl_name, f"template {tmpl_name}")
        rendered = substitute(src.read_text(), tokens)
        assert_no_residual_scaffold_tokens(rendered, out_name)
        (target / out_name).write_text(rendered)
        report.append((out_name, "stamped", purposes[out_name]))

    # 2. copy the exception board IN FULL (verbatim, or one surgical KEY edit)
    board_html = _require(board_src / "exception-spec.inkspec.html", "exception board HTML")
    html = board_html.read_text()
    assert_self_contained(html, "exception board (source)")
    if isolate_board:
        if BOARD_KEY_LITERAL in html:
            html = html.replace(BOARD_KEY_LITERAL, f'const KEY="exc-spec-{slug}";', 1)
            board_note = f"board (localStorage KEY isolated -> exc-spec-{slug})"
        else:
            board_note = "board (copied; --isolate-board KEY literal not found: source drift)"
            print(
                "warning: --isolate-board: KEY literal not found in board; "
                "copied verbatim instead.",
                file=sys.stderr,
            )
    else:
        board_note = "board (copied verbatim) — FDE authors the spec here"
    assert_self_contained(html, "exception board (stamped)")
    (target / "exception-spec.inkspec.html").write_text(html)
    report.append(("exception-spec.inkspec.html", "copied", board_note))

    # board sidecars -> refs/ (read-only reference, verbatim)
    for fname, out in (
        ("README.md", "exception-spec.README.md"),
        ("PROVENANCE.md", "exception-spec.PROVENANCE.md"),
        ("sample-export.policy.json", "sample-export.policy.json"),
    ):
        src = _require(board_src / fname, f"board sidecar {fname}")
        shutil.copyfile(src, target / "refs" / out)
        report.append((f"refs/{out}", "copied", "read-only board reference"))

    # export target keepfile
    (target / "fixtures" / "retail_ops" / ".gitkeep").write_text("")
    report.append(
        ("fixtures/retail_ops/", "created", "export target: board writes policy.json here")
    )

    # 3. ROI decks — seed cost.json as roi-baseline.json + ops jsonl + report
    cost = _require(roi_src / "fixtures" / "cost.json", "ROI cost deck")
    shutil.copyfile(cost, target / "roi-baseline.json")
    report.append(
        ("roi-baseline.json", "seeded", "ROI cost deck — every scalar an <<TOKEN>> to fill")
    )
    for fname in ("ops_baseline.jsonl", "ops_automated.jsonl"):
        src = _require(roi_src / "fixtures" / fname, f"ROI seed {fname}")
        shutil.copyfile(src, target / "roi" / fname)
        kind = "BEFORE weekly ops data" if "baseline" in fname else "AFTER weekly ops data"
        report.append((f"roi/{fname}", "seeded", f"{kind} (replace with real)"))
    report_html = _require(roi_src / "roi-report.inkspec.html", "ROI report HTML")
    rhtml = report_html.read_text()
    assert_self_contained(rhtml, "ROI report")
    shutil.copyfile(report_html, target / "roi" / "roi-report.inkspec.html")
    report.append(("roi/roi-report.inkspec.html", "copied", "Collins ROI report"))

    return target, report


# --- CLI ---------------------------------------------------------------------
def _default_customer(slug: str) -> str:
    return slug.replace("-", " ").title()


def list_systems() -> str:
    lines = [
        f"{'server':<19} {'env var':<24} {'allowed values':<39} default",
        "-" * 100,
    ]
    for meta in SYSTEMS.values():
        allowed = " | ".join(meta["allowed"])  # type: ignore[arg-type]
        lines.append(f"{meta['server']!s:<19} {meta['env']!s:<24} {allowed:<39} {meta['default']}")
    lines.append("")
    lines.append(
        f"approval token var (all four): {APPROVAL_TOKEN_VAR}  "
        "(operator-injected; agent cannot read)"
    )
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="newdeploy",
        description="Stamp a per-customer FDE deployment kit under deployments/<slug>/.",
    )
    p.add_argument("slug", nargs="?", help="customer slug (lowercase kebab-case)")
    p.add_argument("--customer", help="display name (default: title-cased slug)")
    p.add_argument(
        "--out",
        default="deployments",
        help="parent dir the <slug>/ folder is created under (default: ./deployments)",
    )
    for key, meta in SYSTEMS.items():
        p.add_argument(
            f"--{key}",
            choices=list(meta["allowed"]),  # type: ignore[arg-type]
            default=meta["default"],
            help=f"{meta['server']} dialect (default: {meta['default']})",
        )
    p.add_argument(
        "--isolate-board",
        action="store_true",
        help="rewrite the board's localStorage KEY to exc-spec-<slug> "
        "(avoids multi-deployment browser collisions; otherwise copied verbatim)",
    )
    p.add_argument("--board-src", help="override the exception-spec-dsl source dir")
    p.add_argument("--roi-src", help="override the roi source dir")
    p.add_argument("--force", action="store_true", help="overwrite a non-empty target dir")
    p.add_argument(
        "--list-systems",
        action="store_true",
        help="print the four servers, env vars, allowlists and defaults, then exit",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.list_systems:
        print(list_systems())
        return 0

    if not args.slug:
        print("error: a customer slug is required (or use --list-systems)", file=sys.stderr)
        return 2
    slug = args.slug
    if not SLUG_RE.match(slug):
        print(
            f"error: slug {slug!r} must be lowercase kebab-case (^[a-z0-9]+(-[a-z0-9]+)*$)",
            file=sys.stderr,
        )
        return 2

    customer = args.customer or _default_customer(slug)
    choices = {k: getattr(args, k) for k in SYSTEMS}  # already allowlist-validated

    here = Path(__file__).resolve().parent
    tools_dir = here.parent  # .../tools
    templates_dir = here / "templates"
    try:
        board_src = _resolve_source(args.board_src, "exception-spec-dsl", tools_dir)
        roi_src = _resolve_source(args.roi_src, "roi", tools_dir)
        target, report = stamp(
            slug=slug,
            customer=customer,
            out_parent=Path(args.out).expanduser().resolve(),
            choices=choices,
            templates_dir=templates_dir,
            board_src=board_src,
            roi_src=roi_src,
            isolate_board=args.isolate_board,
            force=args.force,
        )
    except StampError as e:
        print(f"error: {e}", file=sys.stderr)
        return e.code

    # report table
    print(f"stamped deployment kit: {target}")
    print(
        f"  customer={customer!r}  systems: "
        f"erp={choices['erp']} supplier={choices['supplier']} "
        f"email={choices['email']} sheets={choices['sheets']}"
    )
    print()
    wf = max(len(f) for f, _, _ in report)
    kf = max(len(k) for _, k, _ in report)
    print(f"{'File'.ljust(wf)}  {'Kind'.ljust(kf)}  Purpose")
    print(f"{'-' * wf}  {'-' * kf}  {'-' * 7}")
    for f, k, purpose in report:
        print(f"{f.ljust(wf)}  {k.ljust(kf)}  {purpose}")
    print()
    print("NOT done by newdeploy (the FDE's supervised per-customer acts):")
    print("  - author the <<TOKEN>> business values in the board / roi-baseline.json")
    print("  - export policy.json  - inject " + APPROVAL_TOKEN_VAR + " (host env only)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
