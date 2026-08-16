"""Per-source coverage report for the current dataset.

Prints a Markdown table of total vs. upcoming webinars per configured site so a
silently-broken scraper (0 results) stands out in the CI job summary instead of
disappearing behind the merge (which keeps stale entries when a scrape fails).

    python -m webinar.coverage        # -> Markdown table on stdout
"""
from __future__ import annotations

import sys

from . import storage
from .config import load_sites


def build_report() -> str:
    sites = list(load_sites().keys())
    webinars = storage.load_webinars()
    total: dict[str, int] = {s: 0 for s in sites}
    upcoming: dict[str, int] = {s: 0 for s in sites}
    for w in webinars:
        total[w.source] = total.get(w.source, 0) + 1
        if storage.is_upcoming(w):
            upcoming[w.source] = upcoming.get(w.source, 0) + 1

    lines = [
        "### 웨비나 수집 현황",
        "",
        "| 사이트 | 전체 | 예정 | 상태 |",
        "| --- | ---: | ---: | :---: |",
    ]
    for s in sites:
        # a configured site with nothing at all is the signal worth flagging
        flag = "⚠️" if total.get(s, 0) == 0 else "✅"
        lines.append(f"| {s} | {total.get(s, 0)} | {upcoming.get(s, 0)} | {flag} |")
    lines.append(f"| **합계** | **{sum(total.values())}** | **{sum(upcoming.values())}** | |")
    return "\n".join(lines) + "\n"


def main() -> int:
    sys.stdout.write(build_report())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
