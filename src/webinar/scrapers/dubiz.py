"""두비즈 (dubiz.co.kr) scraper — public listing at /onoffmix/.

NOTE: dubiz.co.kr is blocked by some corporate web proxies, so this scraper
could not be verified against the live DOM from the dev network; it was written
from the observed structure and runs in CI where the site is reachable. Cards
are anchors to /Event/NNN with a title and a date like "7월 16일(목) 10:30".
`require_date` (default) keeps unmatched selectors from emitting junk.
"""
from __future__ import annotations

import logging

from .base import BaseScraper

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
        cards = self.select_cards(soup, self.CARD_SELECTORS)
        if not cards:
            cards = [li for li in soup.select("li, article") if li.select_one("a[href]")]
        return self.cards_to_webinars(
            cards,
            title_sel="h3, h4, .tit, .title, strong, .subject",
            host_sel=".host, .company, .org",
        )

    def fetch(self, browser):
        # enrich each /Event/NNN detail page for prize-named banner images.
        # (dubiz is blocked on some corporate proxies; this runs in CI.)
        items = super().fetch(browser)
        for w in items:
            try:
                self.enrich_from_detail(browser, w)
            except Exception as e:
                log.warning("[dubiz] enrich failed for %s: %s", w.url, e)
        return items
