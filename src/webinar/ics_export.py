"""Generate an auth-free ICS feed (docs/webinars.ics) from the dataset.

Users can subscribe to this URL in Google Calendar ("Other calendars → From URL")
without any OAuth setup — a lightweight alternative to calendar_sync.
"""
from __future__ import annotations

import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from . import storage
from .config import DOCS_DIR
from .models import Webinar

log = logging.getLogger(__name__)
KST = ZoneInfo("Asia/Seoul")

PRIZE_LABELS = {"survey": "설문", "question": "질문", "consult": "상담", "attendance": "참석/시청"}


def _fmt(dt_iso: str) -> str:
    dt = datetime.fromisoformat(dt_iso).astimezone(ZoneInfo("UTC"))
    return dt.strftime("%Y%m%dT%H%M%SZ")


def _escape(text: str) -> str:
    return (
        text.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\n", "\\n")
    )


def _event_lines(w: Webinar, stamp: str) -> list[str]:
    if not w.start_kst:
        return []
    desc_parts = []
    if w.host:
        desc_parts.append(f"주최: {w.host}")
    if w.register_url or w.url:
        desc_parts.append(f"신청: {w.register_url or w.url}")
    for p in w.prizes:
        label = PRIZE_LABELS.get(p.type, p.type)
        detail = " ".join(filter(None, [p.item, p.condition]))
        desc_parts.append(f"[{label}] {detail}".strip())
    desc = _escape("\n".join(desc_parts))

    lines = [
        "BEGIN:VEVENT",
        f"UID:{w.id}@webinar",
        f"DTSTAMP:{stamp}",
        f"DTSTART:{_fmt(w.start_kst)}",
        f"DTEND:{_fmt(w.end_kst or w.start_kst)}",
        f"SUMMARY:{_escape('[웨비나] ' + w.title)}",
        f"DESCRIPTION:{desc}",
    ]
    if w.url:
        lines.append(f"URL:{_escape(w.url)}")
    lines.append("END:VEVENT")
    return lines


def export(path=None) -> str:
    path = path or (DOCS_DIR / "webinars.ics")
    webinars = [w for w in storage.load_webinars() if storage.is_upcoming(w)]
    stamp = datetime.now(ZoneInfo("UTC")).strftime("%Y%m%dT%H%M%SZ")

    out = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//webinar//KR//",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:웨비나 일정",
        "X-WR-TIMEZONE:Asia/Seoul",
    ]
    for w in webinars:
        out.extend(_event_lines(w, stamp))
    out.append("END:VCALENDAR")

    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    text = "\r\n".join(out) + "\r\n"
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    log.info("wrote ICS feed with %d events -> %s", len(webinars), path)
    return text


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    export()
