#!/usr/bin/env python3
"""Refresh the single-file Collins report view from report.json.

The view (`roi-report.inkspec.html`) is self-contained: the report data lives inline
in a `<script id="roi-data" type="application/json">` block so the file opens offline
with no fetch. This script re-inlines that block from `report.json` after a recompute,
keeping the shipped HTML a byte-for-byte function of the data.

Pipeline:
    python3 roi.py --out report.json          # recompute the numbers
    python3 build_view.py                      # re-inline them into the HTML

Idempotent: running it twice with the same report.json produces the same HTML.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPORT = HERE / "report.json"
VIEW = HERE / "roi-report.inkspec.html"

BLOCK = re.compile(
    r'(<script id="roi-data" type="application/json">)(.*?)(</script>)',
    re.DOTALL,
)


def main() -> int:
    data = json.loads(REPORT.read_text())  # validate it parses
    payload = json.dumps(data, indent=2)
    html = VIEW.read_text()
    if not BLOCK.search(html):
        print('ERROR: no <script id="roi-data"> block found in the view', flush=True)
        return 1
    html = BLOCK.sub(lambda m: m.group(1) + "\n" + payload + "\n" + m.group(3), html)
    VIEW.write_text(html)
    print(f"inlined report.json ({len(payload)} bytes) into {VIEW.name}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
