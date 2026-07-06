"""CLOIT:ON (webinar.cloit.com) scraper — JS-rendered SPA.

The listing hydrates client-side, so the framework waits for `wait_selector`
before handing us HTML. We parse whatever session cards are present.
"""
from __future__ import annotations

from .base import BaseScraper


class Scraper(BaseScraper):
    CARD_SELECTORS = [
        ".webinar-card",
        ".session-card",
        ".card",
        "[class*='session'] li",
        "article",
        "li",
    ]

    def parse(self, html):
        soup = self.soup(html)
        cards = self.select_cards(soup, self.CARD_SELECTORS)
        # SPA may render 0 sessions ("총 0개의 세션 대기 중") — that's valid.
        cards = [c for c in cards if c.select_one("a[href]") or c.select_one("img")]
        return self.cards_to_webinars(
            cards,
            title_sel="h3, h4, .tit, .title, strong",
            host_sel=".host, .company",
        )
