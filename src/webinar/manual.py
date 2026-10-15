"""Manually registered webinars (config/manual_webinars.yaml).

Some sites bot-check GitHub Actions runners so hard that nothing can be scraped
from CI (e.g. both sharedit hosts). A webinar known to exist can be listed in
config/manual_webinars.yaml so it still reaches the calendar.

Precedence: a webinar actually scraped with the same url always wins (it is
tagged as scraped, the manual one is tagged "manual"). A manual entry replaces
an existing record only when that record was itself manual, so editing the YAML
(e.g. filling in the title or time later) takes effect on the next run.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, time
from pathlib import Path

import yaml

from .config import MANUAL_WEBINARS_YAML
from .models import Webinar

log = logging.getLogger(__name__)

MANUAL_TAG = "manual"


def _iso(d: str, t: str | None) -> str:
    from zoneinfo import ZoneInfo

    day = date.fromisoformat(str(d))
    hh, mm = (int(x) for x in str(t).split(":")) if t else (0, 0)
    return datetime.combine(day, time(hh, mm), ZoneInfo("Asia/Seoul")).isoformat()


def load_manual(path: Path = MANUAL_WEBINARS_YAML) -> list[Webinar]:
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    out = []
    for i, e in enumerate(raw.get("webinars") or []):
        try:
            start = _iso(e["date"], e.get("time"))
            end = _iso(e["date"], e["end"]) if e.get("end") else None
            if not end and e.get("time"):
                end = datetime.fromisoformat(start).replace(
                    hour=(int(e["time"].split(":")[0]) + 1) % 24).isoformat()
            url = e["url"].split("?")[0].rstrip("/")
            out.append(Webinar(
                source=e["source"],
                title=e["title"],
                url=url,
                register_url=url,
                start_kst=start,
                end_kst=end,
                host=e.get("host", ""),
                thumbnail=e.get("thumbnail", ""),
                tags=[MANUAL_TAG],
            ))
        except Exception as ex:  # one bad entry must not break the run
            log.warning("manual_webinars.yaml entry #%d skipped: %s", i, ex)
    return out


def apply_manual(merged: list[Webinar], manual: list[Webinar]) -> list[Webinar]:
    """Add manual entries that no scraped record supersedes."""
    by_id = {w.id: w for w in merged}
    for m in manual:
        cur = by_id.get(m.id)
        if cur is None or MANUAL_TAG in (cur.tags or []):
            if cur is not None:
                m.registered = cur.registered
            by_id[m.id] = m
            log.info("[manual] %s | %s | %s", m.start_kst, m.title[:50], m.url)
    return list(by_id.values())
