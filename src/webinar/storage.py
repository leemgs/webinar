"""Read/write the aggregated webinar dataset (data/webinars.json)."""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from .config import DATA_DIR, WEBINARS_JSON
from .models import Webinar

KST = ZoneInfo("Asia/Seoul")


def load_webinars() -> list[Webinar]:
    if not WEBINARS_JSON.exists():
        return []
    with open(WEBINARS_JSON, encoding="utf-8") as f:
        raw = json.load(f)
    items = raw.get("webinars", raw) if isinstance(raw, dict) else raw
    return [Webinar.from_dict(d) for d in items]


def save_webinars(webinars: list[Webinar]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.now(KST).isoformat(),
        "count": len(webinars),
        "webinars": [w.to_dict() for w in _sorted(webinars)],
    }
    with open(WEBINARS_JSON, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def _sorted(webinars: list[Webinar]) -> list[Webinar]:
    return sorted(webinars, key=lambda w: (w.start_kst or "9999", w.source))


def is_upcoming(w: Webinar, grace_hours: int = 2) -> bool:
    """True if the webinar hasn't started (minus a small grace) or has no date."""
    if not w.start_kst:
        return True
    try:
        start = datetime.fromisoformat(w.start_kst)
    except ValueError:
        return True
    return start >= datetime.now(KST) - timedelta(hours=grace_hours)


def merge(existing: list[Webinar], scraped: list[Webinar]) -> list[Webinar]:
    """Merge freshly scraped webinars into the existing set.

    Preserves the `registered` flag and any manually-enriched prizes from the
    existing record; refreshes scrapeable fields from the new scrape.
    """
    by_id = {w.id: w for w in existing}
    for w in scraped:
        old = by_id.get(w.id)
        if old:
            w.registered = old.registered or w.registered
            if old.prizes and not w.prizes:
                w.prizes = old.prizes
        by_id[w.id] = w
    return list(by_id.values())


def prune_past(webinars: list[Webinar], keep_days: int = 60) -> list[Webinar]:
    """Drop webinars that ended more than keep_days ago (keeps recent history)."""
    cutoff = datetime.now(KST) - timedelta(days=keep_days)
    out = []
    for w in webinars:
        if not w.start_kst:
            out.append(w)
            continue
        try:
            start = datetime.fromisoformat(w.start_kst)
        except ValueError:
            out.append(w)
            continue
        if start >= cutoff:
            out.append(w)
    return out
