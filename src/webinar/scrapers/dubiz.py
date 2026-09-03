"""두비즈 (dubiz.co.kr) scraper — public listing at /onoffmix/.

Each webinar is a ``.onoffmix_thum_item`` card: an anchor to ``/Event/NNN``
holding the thumbnail, a ``.onoffmix_card_title`` and a ``.onoffmix_card_date``
rendered as "26.10.02 (금) 13:30" (YY.MM.DD) — sometimes a range like
"26.07.21 (화) ~ 26.07,22 (수) 10:00". Reading the title and date from their
own elements (rather than scanning the whole card) keeps a product name such as
"Pickit 4.1" from being mistaken for a 4/1 event date.

A generic card fallback is kept for any other/older layout. ``require_date``
keeps unmatched selectors from emitting junk.
"""
from __future__ import annotations

import logging

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


class Scraper(BaseScraper):
    CARD_SELECTORS = [
        "a[href*='/Event/']:has(h3)",
        "a[href*='/Event/']",
        ".webinar_list li",
        ".seminar-list li",
        ".list-item",
        ".card",
        "article",
    ]

    def parse(self, html):
        soup = self.soup(html)
        cards = soup.select(".onoffmix_thum_item")
        if cards:
            return self._parse_cards(cards)
        # legacy/unknown layout fallback
        cards = self.select_cards(soup, self.CARD_SELECTORS)
        if not cards:
            cards = [li for li in soup.select("li, article") if li.select_one("a[href]")]
        return self.cards_to_webinars(
            cards,
            title_sel="h3, h4, .tit, .title, strong, .subject",
            host_sel=".host, .company, .org",
        )

    def _parse_cards(self, cards):
        out = []
        seen: set[str] = set()
        for card in cards:
            link = card.select_one("a[href*='/Event/']")
            href = self.abs_url(link.get("href")) if link else ""

            title_el = card.select_one(".onoffmix_card_title")
            title = clean(title_el.get_text()) if title_el else ""
            if not title or is_noise_title(title):
                continue

            date_el = card.select_one(".onoffmix_card_date")
            date_text = clean(date_el.get_text()) if date_el else ""
            d = parse_date(date_text)
            if not d:
                continue

            t_start, t_end = parse_time_range(date_text)
            start = to_iso_kst(d, t_start)
            if start and t_end:
                end = to_iso_kst(d, t_end)
                if end and end <= start:
                    end = add_hours_iso(start, 1.0)
            else:
                end = add_hours_iso(start, 1.0) if start else None

            img = card.select_one("img")
            thumb = ""
            if img:
                thumb = self.abs_url(img.get("src") or img.get("data-src") or "")

            wb = self.new_webinar(
                title=title,
                url=href or self.listing_url,
                register_url=href,
                start_kst=start,
                end_kst=end,
                thumbnail=thumb,
            )
            if wb.id in seen:
                continue
            seen.add(wb.id)
            out.append(wb)
        return out

    def fetch(self, browser):
        # The /onoffmix/ listing is paginated ("?CurrentPage=N", ~17 pages) and
        # sorted newest-date-first, so a single page misses events. Walk pages
        # until one is entirely older than the prune window (only older pages
        # remain), adds nothing new, or is empty — de-duplicating by id.
        from datetime import timedelta

        from .base import now_kst

        keep_after = (now_kst().date() - timedelta(days=70)).isoformat()
        max_pages = int(self.cfg.get("max_pages", 6))
        base = self.listing_url
        sep = "&" if "?" in base else "?"

        by_id: dict[str, object] = {}
        for n in range(1, max_pages + 1):
            url = base if n == 1 else f"{base}{sep}CurrentPage={n}"
            html = browser.get_html(url, wait_selector=self.cfg.get("wait_selector"))
            if not html:
                break
            page_items = self.parse(html)
            if not page_items:
                break
            added = 0
            for w in page_items:
                if w.id not in by_id:
                    by_id[w.id] = w
                    added += 1
            dates = [w.start_kst[:10] for w in page_items if w.start_kst]
            log.info("[dubiz] page %d: %d cards, %d new", n, len(page_items), added)
            # nothing new (pagination looped) or every card older than the window
            if added == 0:
                break
            if dates and max(dates) < keep_after:
                break

        items = list(by_id.values())
        # enrich only events that will survive pruning (skip old history to bound
        # the number of detail-page visits). 경품 안내 is <h2>경품 안내</h2><img ...>.
        for w in items:
            if w.start_kst and w.start_kst[:10] < keep_after:
                continue
            try:
                self.enrich_from_detail(browser, w, prize_heading="경품")
            except Exception as e:
                log.warning("[dubiz] enrich failed for %s: %s", w.url, e)
        return items
