"""Sync registered webinars to Google Calendar via an OAuth refresh token.

Idempotent: each event uses a deterministic id derived from the webinar id, so
re-runs update rather than duplicate. Only webinars marked `registered` (or all
upcoming, via --all) are synced.
"""
from __future__ import annotations

import argparse
import logging
import re
import sys
from datetime import datetime

from . import storage
from .config import google_config, has_google_config
from .models import Webinar

log = logging.getLogger(__name__)

TOKEN_URI = "https://oauth2.googleapis.com/token"
SCOPES = ["https://www.googleapis.com/auth/calendar.events"]

PRIZE_LABELS = {
    "survey": "설문",
    "question": "질문",
    "consult": "상담",
    "attendance": "참석/시청",
}


def _service():
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    g = google_config()
    creds = Credentials(
        token=None,
        refresh_token=g["refresh_token"],
        client_id=g["client_id"],
        client_secret=g["client_secret"],
        token_uri=TOKEN_URI,
        scopes=SCOPES,
    )
    return build("calendar", "v3", credentials=creds, cache_discovery=False)


def _event_id(webinar: Webinar) -> str:
    # Google event ids: lowercase a-v0-9, 5-1024 chars. Hash the webinar id.
    base = re.sub(r"[^a-v0-9]", "", webinar.id.lower())
    return ("wb" + base)[:100] or "wb0000"


def _describe(webinar: Webinar) -> str:
    lines = []
    if webinar.host:
        lines.append(f"주최: {webinar.host}")
    if webinar.register_url or webinar.url:
        lines.append(f"신청/링크: {webinar.register_url or webinar.url}")
    if webinar.prizes:
        lines.append("")
        lines.append("🎁 경품:")
        for p in webinar.prizes:
            label = PRIZE_LABELS.get(p.type, p.type)
            detail = " — ".join(filter(None, [p.item, p.condition]))
            lines.append(f"  • [{label}] {detail}".rstrip())
    lines.append("")
    lines.append(f"출처: {webinar.source}")
    return "\n".join(lines)


def _to_event(webinar: Webinar) -> dict:
    ev = {
        "id": _event_id(webinar),
        "summary": f"[웨비나] {webinar.title}",
        "description": _describe(webinar),
        "source": {"title": webinar.source, "url": webinar.url or "https://"},
    }
    if webinar.start_kst:
        ev["start"] = {"dateTime": webinar.start_kst, "timeZone": "Asia/Seoul"}
        end = webinar.end_kst or webinar.start_kst
        ev["end"] = {"dateTime": end, "timeZone": "Asia/Seoul"}
    else:
        # all-day fallback: today
        today = datetime.now().date().isoformat()
        ev["start"] = {"date": today}
        ev["end"] = {"date": today}
    return ev


def sync(only_registered: bool = True) -> int:
    if not has_google_config():
        log.warning("Google config incomplete — skipping calendar sync")
        return 0
    webinars = [w for w in storage.load_webinars() if storage.is_upcoming(w)]
    if only_registered:
        webinars = [w for w in webinars if w.registered]
    if not webinars:
        log.info("no webinars to sync")
        return 0

    svc = _service()
    cal_id = google_config()["calendar_id"]
    synced = 0
    for wb in webinars:
        body = _to_event(wb)
        eid = body["id"]
        try:
            svc.events().update(calendarId=cal_id, eventId=eid, body=body).execute()
            synced += 1
        except Exception:
            # not found -> insert
            try:
                svc.events().insert(calendarId=cal_id, body=body).execute()
                synced += 1
            except Exception as e:
                log.warning("calendar upsert failed for %s: %s", wb.title, e)
    log.info("calendar synced %d events", synced)
    return synced


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Sync webinars to Google Calendar")
    p.add_argument("--all", action="store_true", help="sync all upcoming, not just registered")
    p.add_argument("-v", "--verbose", action="store_true")
    args = p.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )
    sync(only_registered=not args.all)
    return 0


if __name__ == "__main__":
    sys.exit(main())
