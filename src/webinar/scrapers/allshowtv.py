"""올쇼TV (allshowtv.com) scraper — public card layout with D-day badges.

Cards don't use a dedicated title element, so the raw card text bundles the
title with the date/time/D-day tail (e.g. "[주최] 제목 2026년 07월 08일(수)
15:00 ~ 16:00 D-2"). We trim that tail and lift the host out of the leading
[brackets].
"""
from __future__ import annotations

import re

from .base import BaseScraper, clean

# cut the title at the date tail ("... 2026년 07월 ..." or "... D-2")
_TITLE_TAIL = re.compile(r"\s*(20\d\d\s*년|\bD\s*[-−]\s*\d+).*$")
_HOST_BRACKET = re.compile(r"^\[([^\]]+)\]\s*")


class Scraper(BaseScraper):
    CARD_SELECTORS = [
        ".seminar_list li",
        ".webinar_list li",
        "ul.list li.item",
        ".card-webinar",
        "article.seminar",
        ".main_seminar li",
    ]

    def parse(self, html):
        soup = self.soup(html)
        cards = self.select_cards(soup, self.CARD_SELECTORS)
        if not cards:
            cards = [
                li
                for li in soup.select("li, article")
                if li.select_one("a[href]") and li.select_one("img")
            ]
        webinars = self.cards_to_webinars(
            cards,
            title_sel="h3, .tit, .title, strong",
            host_sel=".host, .company, .org",
        )
        for w in webinars:
            self._tidy(w)
        return webinars

    @staticmethod
    def _tidy(w) -> None:
        title = _TITLE_TAIL.sub("", w.title).strip()
        m = _HOST_BRACKET.match(title)
        if m and not w.host:
            w.host = m.group(1).strip()
            title = _HOST_BRACKET.sub("", title).strip()
        if title:
            w.title = clean(title)
