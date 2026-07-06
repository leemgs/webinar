"""e4ds (e4ds.com/webinar.asp) scraper.

Full details require login; when a session is available the pipeline scrapes
within the logged-in browser context. Parsing is generic card-based and works
on whatever portion of the listing is visible.
"""
from __future__ import annotations

from .base import BaseScraper


class Scraper(BaseScraper):
    CARD_SELECTORS = [
        ".webinar_list li",
        ".seminar_list li",
        "table.webinar tr",
        ".list li",
        ".card",
        "article",
    ]

    def parse(self, html):
        soup = self.soup(html)
        cards = self.select_cards(soup, self.CARD_SELECTORS)
        if not cards:
            cards = [li for li in soup.select("li, article, tr") if li.select_one("a[href]")]
        return self.cards_to_webinars(
            cards,
            title_sel="h3, .tit, .title, strong, .subject, td.title",
            host_sel=".host, .company, .org",
        )
