#!/usr/bin/env python3
"""Refresh step: re-inline ``scorecard.json`` into the single-file dashboard.

The Collins dashboard (``supplier-scorecard.inkspec.html``) is self-contained — the
scorecard data rides *inside* it, in a ``<script type="application/json"
id="scorecard-data">`` tag, so the file opens offline with no fetch. This script
recomputes the scorecard (or reads the committed ``scorecard.json``) and swaps the JSON
inside that one tag, leaving all markup / CSS / JS untouched.

Pipeline:
    python3 scorecard.py                # recompute the numbers -> scorecard.json
    python3 build_view.py               # recompute + re-inline them into the HTML

Run:
    python3 build_view.py               # recompute + re-inline (default)
    python3 build_view.py --from-json   # re-inline the committed scorecard.json (no recompute)
    python3 build_view.py --check       # nonzero exit if the dashboard is stale (no write)

Idempotent: byte-stable JSON in => byte-stable HTML out.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
VIEW = HERE / "supplier-scorecard.inkspec.html"
SCORECARD_JSON = HERE / "scorecard.json"

# The one tag whose inner text is the data payload. Non-greedy body capture.
DATA_TAG = re.compile(
    r'(<script\b[^>]*\bid="scorecard-data"[^>]*>)(.*?)(</script>)',
    re.DOTALL,
)


def _load_json_text(*, from_json: bool) -> str:
    """Return canonical scorecard JSON text (recompute unless ``from_json``)."""
    if from_json:
        if not SCORECARD_JSON.is_file():
            raise FileNotFoundError(
                f"no scorecard.json at {SCORECARD_JSON}; run scorecard.py first"
            )
        return SCORECARD_JSON.read_text(encoding="utf-8")

    # Recompute from the corpus (the engine is the source of truth) and keep the
    # committed artifact in sync. Imported lazily so re-inlining a committed
    # scorecard.json (--from-json) needs neither the engine nor sys.path juggling.
    sys.path.insert(0, str(HERE))
    import scorecard

    text = scorecard.render_json(scorecard.compute_scorecard(scorecard.load_corpus()))
    SCORECARD_JSON.write_text(text, encoding="utf-8")
    return text


def inline(html: str, json_text: str) -> str:
    """Return ``html`` with the scorecard-data tag body replaced by ``json_text``."""
    if not DATA_TAG.search(html):
        raise ValueError('no <script id="scorecard-data"> tag found in the dashboard')
    payload = "\n" + json_text.strip() + "\n"
    return DATA_TAG.sub(lambda m: m.group(1) + payload + m.group(3), html, count=1)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Re-inline scorecard.json into the dashboard.")
    parser.add_argument(
        "--from-json", action="store_true", help="re-inline committed scorecard.json (no recompute)"
    )
    parser.add_argument(
        "--check", action="store_true", help="exit nonzero if the dashboard is stale (no write)"
    )
    args = parser.parse_args(argv)

    if not VIEW.is_file():
        sys.stderr.write(f"error: missing dashboard at {VIEW}\n")
        return 2

    html = VIEW.read_text(encoding="utf-8")
    json_text = _load_json_text(from_json=args.from_json)
    updated = inline(html, json_text)

    if args.check:
        if updated != html:
            sys.stderr.write("STALE: dashboard does not match the scorecard — run build_view\n")
            return 1
        sys.stderr.write("fresh: supplier-scorecard.inkspec.html is up to date\n")
        return 0

    if updated != html:
        VIEW.write_text(updated, encoding="utf-8")
        sys.stderr.write(f"re-inlined scorecard.json ({len(json_text)} bytes) -> {VIEW.name}\n")
    else:
        sys.stderr.write("no change: dashboard already current\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
