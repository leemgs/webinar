"""e4ds (e4ds.com/webinar.asp) scraper — Next.js listing with D-day cards.

Upcoming webinars render as ``a.wbt-card`` linking to ``/webinar_detail.asp?idx=N``
with the title in ``.wbt-title`` and a relative ``.wbt-dday`` badge ("D-11").
The listing carries no absolute date/time, so the D-day badge is the schedule
signal: a card with a "D-N" badge is upcoming (N days out); cards without one
are past VOD/trend items and are skipped. The exact schedule is on the public
detail page (``.wd-meta``: "2026.11.12 10:30~12:00", "연사 / 회사"), which each
upcoming card is enriched from; without it the event stays day-accurate. The
banner carousel (``#carouselWebinarBanner``) promotes upcoming webinars the grid
omits; those are built from their detail page and kept only if still upcoming.

A generic card fallback is kept for other/older layouts. ``require_date`` keeps
unmatched selectors from emitting junk.
"""
from __future__ import annotations

import logging

from .base import (
    BaseScraper, clean, is_noise_title, now_kst, parse_date, parse_time_range, to_iso_kst,
)

log = logging.getLogger(__name__)


class Scraper(BaseScraper):
    CARD_SELECTORS = [
        ".webinar_list li",
        ".seminar_list li",
        "table.webinar tr",
        ".list li",
        ".card",
        "article",
    ]

    def fetch(self, browser):
        html = browser.get_html(
            self.listing_url, wait_selector=self.cfg.get("wait_selector"), exhaust_listing=True,
        )
        if not html:
            log.warning("[e4ds] empty HTML from %s", self.listing_url)
            return []
        try:
            items = self.parse(html)
            banner = self.banner_links(html)
        except Exception as e:  # never let one site break the run
            log.exception("[e4ds] parse failed: %s", e)
            return []
        for webinar in items:
            detail = self._detail(browser, webinar.url)
            if detail:
                self.apply_detail(webinar, detail)
        # the banner carousel also promotes upcoming webinars the D-day grid
        # leaves out; their detail page supplies the title and schedule
        known = {w.url for w in items}
        today = now_kst().date().isoformat()
        for url, thumb in banner:
            if url in known:
                continue
            known.add(url)
            detail = self._detail(browser, url)
            webinar = self.from_detail(url, detail, thumb) if detail else None
            if webinar and webinar.start_kst[:10] >= today:
                items.append(webinar)
        log.info("[e4ds] scraped %d webinars", len(items))
        return items

    @staticmethod
    def _detail(browser, url: str) -> str:
        return browser.get_html(url, wait_selector=".wd-meta", wait_ms=800, timeout_ms=20000)

    def banner_links(self, html) -> list[tuple[str, str]]:
        """(detail url, banner image) for each slide of the webinar banner carousel."""
        out = []
        for a in self.soup(html).select("#carouselWebinarBanner a[href*='webinar_detail.asp']"):
            img = a.select_one("img")
            thumb = self.https(self.abs_url(img.get("src"))) if img and img.get("src") else ""
            out.append((self.abs_url(a.get("href")), thumb))
        return out

    def from_detail(self, url: str, html: str, thumbnail: str = ""):
        """A webinar built from its detail page alone (None without title + date)."""
        title_el = self.soup(html).select_one("h1.wd-title")
        title = clean(title_el.get_text()) if title_el else ""
        if not title or is_noise_title(title):
            return None
        webinar = self.new_webinar(title=title, url=url, register_url=url, thumbnail=thumbnail)
        self.apply_detail(webinar, html)
        return webinar if webinar.start_kst else None

    def apply_detail(self, webinar, html) -> None:
        """Take the exact schedule (and host company) from a detail page."""
        meta = self.soup(html).select_one(".wd-meta")
        if not meta:
            return
        for item in meta.select(".wd-meta__item"):
            text = clean(item.get_text(" "))
            if item.select_one(".fa-calendar"):
                d = parse_date(text)
                start, end = parse_time_range(text)
                if d and start:
                    webinar.start_kst = to_iso_kst(d, start)
                    webinar.end_kst = to_iso_kst(d, end) if end else None
            elif item.select_one(".fa-user") and "/" in text and not webinar.host:
                webinar.host = clean(text.rsplit("/", 1)[1])

    def parse(self, html):
        soup = self.soup(html)
        cards = soup.select("a.wbt-card[href]")
        if cards:
            return self._parse_cards(cards)
        # legacy/unknown layout fallback
        cards = self.select_cards(soup, self.CARD_SELECTORS)
        if not cards:
            cards = [li for li in soup.select("li, article, tr") if li.select_one("a[href]")]
        return self.cards_to_webinars(
            cards,
            title_sel="h3, .tit, .title, strong, .subject, td.title",
            host_sel=".host, .company, .org",
        )

    def _parse_cards(self, cards):
        out = []
        seen: set[str] = set()
        for a in cards:
            href = self.abs_url(a.get("href"))
            if "webinar_detail.asp" not in href:
                continue

            dday_el = a.select_one(".wbt-dday")
            # only the D-day badge dates the event; no badge => past VOD, skip
            d = parse_date(clean(dday_el.get_text())) if dday_el else None
            if not d:
                continue

            title_el = a.select_one(".wbt-title")
            title = clean(title_el.get_text()) if title_el else ""
            if not title or is_noise_title(title):
                continue

            img = a.select_one("img")
            thumb = self.https(self.abs_url(img.get("src"))) if img and img.get("src") else ""

            wb = self.new_webinar(
                title=title,
                url=href,
                register_url=href,
                start_kst=to_iso_kst(d, None),
                thumbnail=thumb,
            )
            if wb.id in seen:
                continue
            seen.add(wb.id)
            out.append(wb)
        return out
