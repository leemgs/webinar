"""CLOIT:ON (webinar.cloit.com) scraper — Next.js app backed by Supabase.

The page source carries no sessions: after hydration the app reads them from
Supabase REST, e.g.

    GET https://<project>.supabase.co/rest/v1/webinars
        ?select=*&is_past=eq.false&order=scheduled_at.asc
    -> [{"id": "b1154299-…", "title": "…", "scheduled_at":
         "2026-10-29T05:00:00+00:00", "thumbnail_url": "…", "is_past": false}]

so the primary source is that JSON, captured while the site's own scripts
make the (keyed) call. Each session's page is /intro/<id>.

Fallback: the rendered "다가오는 웨비나" cards — an <a href="/intro/<id>">
holding <h3>title</h3> and a span like "2026년 10월 29일 오후 02:00".
"""
from __future__ import annotations

import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from .base import (
    BaseScraper,
    add_hours_iso,
    clean,
    is_noise_title,
    parse_date,
    parse_time_range,
    to_iso_kst,
)

log = logging.getLogger(__name__)

KST = ZoneInfo("Asia/Seoul")
API_MATCH = "/rest/v1/webinars"
CARD_SEL = "a[href*='/intro/']"


class Scraper(BaseScraper):
    def fetch(self, browser):
        getter = getattr(browser, "get_html_and_json", None)
        kwargs = dict(wait_selector=CARD_SEL, wait_ms=3000, timeout_ms=30000)
        if getter:
            html, payloads = getter(self.listing_url, API_MATCH, **kwargs)
        else:  # plain browsers (tests / older helpers)
            html, payloads = browser.get_html(self.listing_url, **kwargs), []

        by_url = {}
        for _, data in payloads:
            for w in self.parse_api(data):
                by_url.setdefault(w.url, w)
        for w in self.parse(html) if html else []:
            by_url.setdefault(w.url, w)  # API data wins; DOM fills gaps
        items = list(by_url.values())
        for w in items:
            log.info("[cloit] %s | %s | %s", w.start_kst, w.title[:50], w.url)
        log.info("[cloit] scraped %d webinars (api payloads: %d)", len(items), len(payloads))
        return items

    def parse_api(self, data) -> list:
        """Build webinars from Supabase `webinars` rows."""
        out = []
        for row in data if isinstance(data, list) else []:
            if not isinstance(row, dict):
                continue
            wid, title, when = row.get("id"), clean(row.get("title")), row.get("scheduled_at")
            if not (wid and title and when) or is_noise_title(title):
                continue
            try:
                start = datetime.fromisoformat(str(when).replace("Z", "+00:00"))
            except ValueError:
                continue
            start_kst = start.astimezone(KST).replace(microsecond=0).isoformat()
            url = f"{self.base_url}/intro/{wid}"
            out.append(self.new_webinar(
                title=title,
                url=url,
                register_url=url,
                start_kst=start_kst,
                end_kst=add_hours_iso(start_kst, 1.0),
                description=clean(row.get("description")),
                thumbnail=row.get("thumbnail_url") or "",
            ))
        return out

    def parse(self, html):
        """Fallback: rendered session cards (<a href='/intro/<id>'> with <h3>)."""
        soup = self.soup(html)
        out, seen = [], set()
        for a in soup.select(CARD_SEL):
            h3 = a.select_one("h3, h2")
            title = clean(h3.get_text(" ")) if h3 else ""
            if not title or is_noise_title(title):
                continue
            text = clean(a.get_text(" "))
            d = parse_date(text)
            if not d:
                continue
            t_start, t_end = parse_time_range(text)
            start = to_iso_kst(d, t_start)
            end = to_iso_kst(d, t_end) if t_end else add_hours_iso(start, 1.0)
            url = self.abs_url(a.get("href", "")).split("?")[0].rstrip("/")
            if url in seen:
                continue
            seen.add(url)
            img = a.select_one("img")
            out.append(self.new_webinar(
                title=title,
                url=url,
                register_url=url,
                start_kst=start,
                end_kst=end,
                thumbnail=self.abs_url(img.get("src")) if img and img.get("src") else "",
            ))
        return out
