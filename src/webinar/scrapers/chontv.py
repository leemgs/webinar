"""채널온TV (chontv.com) scraper — JS webinar hub with data-event-no cards.

The live listing renders each webinar as an ``.event-row-col`` card whose link
is a ``data-event-no`` attribute (not an href) opened by JS, e.g.
``<a class="go-event-btn" data-event-no="1266">``. The title sits in
``.event-list-title`` and the schedule in ``.event-day`` rendered as
"2026년 08월 25일(화) 14:00~15:00". We build the detail URL as
``/event/{id}`` (a route the site also serves).

The page mixes real webinars ("웨비나 예고", "지난 추천 웨비나", "잇츠맨
하이라이트") with "촌장의 수요레터" newsletters that are not webinars; the
latter carry a 수요레터 title/tag and are skipped.

A legacy fallback still handles href-based ``/{channel}/{id}`` detail links so
older layouts (and the unit fixture) keep working. ``require_date`` keeps an
unmatched structure emitting nothing rather than junk.
"""
from __future__ import annotations

import logging
import re

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

# a webinar detail link: /{channel-slug}/{numeric-id}, absolute or relative.
_DETAIL = re.compile(
    r"^(?:https?://(?:www\.)?chontv\.com)?/[a-z0-9][a-z0-9_-]*/\d+/?$", re.I
)
# pull the real image URL out of a `background: ...url(...)` inline style
_BG_URL = re.compile(r"url\((['\"]?)(https?://[^)'\"]+)\1\)")


class Scraper(BaseScraper):
    CARD_SELECTORS = [
        "a[href]:has(h3)",
        "a[href]:has(.title)",
        ".webinar-list li",
        ".seminar-list li",
        ".card",
        "article",
    ]

    def parse(self, html):
        soup = self.soup(html)
        webinars = self._parse_event_cards(soup)
        if webinars:
            return webinars
        # legacy: anchors linking to a /{channel}/{id} detail page
        cards = [
            a for a in soup.select("a[href]") if _DETAIL.match((a.get("href") or "").strip())
        ]
        if not cards:
            cards = self.select_cards(soup, self.CARD_SELECTORS)
        if not cards:
            cards = [li for li in soup.select("li, article") if li.select_one("a[href]")]
        return self.cards_to_webinars(
            cards,
            title_sel="h3, h4, .title, .tit, strong, .subject",
            host_sel=".host, .company, .org, .channel",
        )

    def _parse_event_cards(self, soup):
        """Parse the live ``.event-row-col`` cards keyed by ``data-event-no``."""
        out = []
        seen: set[str] = set()
        for card in soup.select(".event-row-col"):
            link = card.select_one("a[data-event-no]")
            event_no = (link.get("data-event-no") if link else "") or ""
            if not event_no.strip():
                continue

            title_el = card.select_one(".event-list-title")
            title = clean(title_el.get_text()) if title_el else ""
            if not title or is_noise_title(title):
                continue
            if "수요레터" in title:  # newsletters, not webinars
                continue

            day_el = card.select_one(".event-day")
            day_text = clean(day_el.get_text()) if day_el else ""
            d = parse_date(day_text)
            if not d:
                continue

            t_start, t_end = parse_time_range(day_text)
            start = to_iso_kst(d, t_start)
            if start and t_end:
                end = to_iso_kst(d, t_end)
                if end and end <= start:
                    end = add_hours_iso(start, 1.0)
            else:
                end = add_hours_iso(start, 1.0) if start else None

            url = f"{self.base_url}/event/{event_no.strip()}"
            thumb = self._bg_image(card.select_one(".event-list-thumb-image"))
            wb = self.new_webinar(
                title=title,
                url=url,
                register_url=url,
                start_kst=start,
                end_kst=end,
                thumbnail=thumb,
            )
            if wb.id in seen:  # same event repeats across page sections
                continue
            seen.add(wb.id)
            out.append(wb)
        return out

    @staticmethod
    def _bg_image(el) -> str:
        if not el:
            return ""
        m = _BG_URL.search(el.get("style") or "")
        return m.group(2) if m else ""
