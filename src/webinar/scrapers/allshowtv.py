"""올쇼TV (allshowtv.com) scraper — public card layout with D-day badges.

Layout as of 2026-10 (index.html renders the "지난 세미나 리스트" page):
  * the UPCOMING webinar is only in the hero banner:
      <a href="detail.html?idx=1762"><div class="vi" style="background:url(...)">
        … <div class="vi_text"><h2>제목</h2><p class="date">2026년 10월 27일(화)
        14:00 ~ 15:00</p></div></div></a>
  * past webinars are list items whose first link wraps only the thumbnail:
      <li><dl><dd class="thumb"><a href="detail.html?idx=1755"><img></a></dd>
          <dt><a href="detail.html?idx=1755">[주최] 제목</a></dt>
          <dd class="date"><a …><p>2026년 10월 21일(수) 15:00 ~ 16:00</p></a></dd>
      </dl></li>
    Taking the title from that first (image-only) link yielded "" and dropped
    every card, so titles come from <dt> and dates from .date.
The older "whole card inside one <a>" layout is still handled below.

Cards don't use a dedicated title element, so the raw card text bundles the
title with the date/time/D-day tail (e.g. "[주최] 제목 2026년 07월 08일(수)
15:00 ~ 16:00 D-2"). We trim that tail and lift the host out of the leading
[brackets].
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

# cut the title at the date tail ("... 2026년 07월 ..." or "... D-2")
_TITLE_TAIL = re.compile(r"\s*(20\d\d\s*년|\bD\s*[-−]\s*\d+).*$")
_HOST_BRACKET = re.compile(r"^\[([^\]]+)\]\s*")
_BG_URL = re.compile(r"url\(['\"]?([^'\")]+)")


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
        structured = self._parse_hero(soup) + self._parse_list_items(soup)
        if structured:
            out, seen = [], set()
            for w in structured:
                if w.id not in seen:
                    seen.add(w.id)
                    self._tidy(w)
                    out.append(w)
            return out
        return self._parse_legacy(soup)

    # -- current layout --
    def _webinar(self, title, date_text, href, thumb=""):
        title = clean(title)
        if not title or is_noise_title(title):
            return None
        d = parse_date(date_text)
        if not d:
            return None
        t_start, t_end = parse_time_range(date_text)
        start = to_iso_kst(d, t_start)
        end = to_iso_kst(d, t_end) if t_end else None
        if not end or end <= start:
            end = add_hours_iso(start, 1.0)
        url = self.abs_url(href) if href else self.listing_url
        return self.new_webinar(
            title=title, url=url, register_url=url, start_kst=start, end_kst=end,
            thumbnail=self.https(self.abs_url(thumb)) if thumb else "",
        )

    def _parse_hero(self, soup):
        out = []
        for vi in soup.select("div.vi"):
            a = vi if vi.name == "a" else vi.find_parent("a")
            title_el = vi.select_one(".vi_text h2, .vi_text .tit, h2")
            date_el = vi.select_one(".vi_text .date, .date")
            m = _BG_URL.search(vi.get("style") or "")
            w = self._webinar(
                title_el.get_text(" ") if title_el else "",
                date_el.get_text(" ") if date_el else "",
                a.get("href") if a else "",
                m.group(1) if m else "",
            )
            if w:
                out.append(w)
        return out

    def _parse_list_items(self, soup):
        out = []
        for li in soup.select("li"):
            dt, date_el = li.select_one("dt"), li.select_one(".date")
            if not dt or not date_el:
                continue  # needs both; image-only/old cards go to the fallback
            link = dt.select_one("a[href]") or li.select_one("a[href*='detail']")
            img = li.select_one("img")
            w = self._webinar(
                dt.get_text(" "),
                date_el.get_text(" "),
                link.get("href") if link else "",
                (img.get("src") or img.get("data-src") or "") if img else "",
            )
            if w:
                out.append(w)
        return out

    # -- older layouts (whole card inside one link) --
    def _parse_legacy(self, soup):
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

    def fetch(self, browser):
        # enrich each webinar's detail page: the "경품 안내" section is <div class="gift">
        items = super().fetch(browser)
        for w in items:
            try:
                self.enrich_from_detail(browser, w, prize_selector=".gift img")
            except Exception as e:
                log.warning("[allshowtv] enrich failed for %s: %s", w.url, e)
        return items

    @staticmethod
    def _tidy(w) -> None:
        title = _TITLE_TAIL.sub("", w.title).strip()
        m = _HOST_BRACKET.match(title)
        if m and not w.host:
            w.host = m.group(1).strip()
            title = _HOST_BRACKET.sub("", title).strip()
        if title:
            w.title = clean(title)
