"""토크아이티 (talkit.tv) scraper — public webinar listing.

Cards are anchors to /main/events/NNN containing an <h3> title and a <time>
element like "7월 9일(목) 오후 2:00~3:00".
"""
import logging

from .base import BaseScraper

log = logging.getLogger(__name__)


class Scraper(BaseScraper):
    CARD_SELECTORS = [
        "a[href*='/main/events/']:has(h3)",  # title anchor (not the image/badge anchor)
        "a[href*='/main/events/']",
        ".event_list li",
        ".webinar_list li",
    ]

    def parse(self, html):
        soup = self.soup(html)
        cards = self.select_cards(soup, self.CARD_SELECTORS)
        if not cards:
            cards = [li for li in soup.select("li, article") if li.select_one("a[href]")]
        return self.cards_to_webinars(
            cards,
            title_sel="h3, h4, .tit, .title, .subject",
            host_sel=".host, .company, .speaker",
        )

    def fetch(self, browser):
        # Enrich each event page for prize-named banner images only. talkit shows
        # its 경품 안내 in a JS tab with generic image filenames, so we do NOT guess
        # a promo banner (it'd repeat a section image across events); we capture an
        # image only when its filename clearly marks it as a prize/event banner.
        items = super().fetch(browser)
        for w in items:
            try:
                self.enrich_from_detail(browser, w)
            except Exception as e:
                log.warning("[talkit] enrich failed for %s: %s", w.url, e)
        return items
