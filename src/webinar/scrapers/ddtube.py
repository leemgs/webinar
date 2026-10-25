"""DD튜브 (ddtube.co.kr) scraper.

The homepage promotes upcoming webinars via a Slider Revolution slideshow where
title/date/link live in separate absolutely-positioned layers — not a clean
card. The reliable source is the per-webinar detail pages (/dNNNN/), which have
a clean <title> and the schedule ("2026-10-21 10:00~ 15:45") under the title.
So we:

  1. collect unique detail slugs from the homepage AND the /webinar/ and
     /conference/ archive pages (``extra_listing_urls``) — the slider only
     shows a few promoted events, the archives list the rest,
  2. visit the newest ``max_details`` detail pages to fill title + schedule.
"""
from __future__ import annotations

import logging
import re

from .. import prizes
from .base import (
    _YMD,
    BaseScraper,
    clean,
    parse_date,
    parse_time_range,
    to_iso_kst,
    add_hours_iso,
)

log = logging.getLogger(__name__)

SLUG_RE = re.compile(r"/d(\d{3,})/?(?:$|[?#])")
# slugs are sequential, so the newest N cover every upcoming event; older ones
# are long past (and pruned) — no need to load each multi-MB page twice a day
DEFAULT_MAX_DETAILS = 24


def parse_schedule(text: str):
    """Return ``(start_iso, end_iso)`` from a detail page's text.

    The time range is read right after the event date ("2026-10-21 10:00~
    15:45"), so the published end time is kept instead of assuming one hour,
    and a stray time elsewhere on the page can't be picked up.
    """
    m = _YMD.search(text or "")
    if not m:
        return None, None
    d = parse_date(m.group(0))
    t, end_t = parse_time_range(text[m.end(): m.end() + 40])
    start = to_iso_kst(d, t)
    if not start:
        return None, None
    if t and end_t and end_t > t:
        return start, to_iso_kst(d, end_t)
    return start, (add_hours_iso(start, 1.0) if t else None)


class Scraper(BaseScraper):
    def parse(self, html):
        """Extract unique detail URLs from a listing (no enrichment)."""
        soup = self.soup(html)
        slugs: dict[str, str] = {}  # number -> canonical url
        for a in soup.select("a[href]"):
            m = SLUG_RE.search(a.get("href", ""))
            if not m:
                continue
            num = m.group(1)
            slugs.setdefault(num, self.abs_url(f"/d{num}/"))
        out = []
        for num, url in slugs.items():
            out.append(self.new_webinar(title=f"d{num}", url=url, register_url=url))
        return out

    def _enrich(self, browser, webinar) -> None:
        html = browser.get_html(webinar.url, wait_selector="body")
        if not html:
            return
        soup = self.soup(html)
        # title from <title>, stripping the site suffix
        if soup.title:
            title = clean(soup.title.get_text())
            title = re.split(r"\s*[–\-|]\s*DD?튜브", title)[0].strip()
            if title:
                webinar.title = title
        # date + time range from the body text (scripts/styles hold no schedule)
        for tag in soup(["script", "style"]):
            tag.decompose()
        start, end = parse_schedule(clean(soup.get_text(" ")))
        if start:
            webinar.start_kst = start
            webinar.end_kst = end
        # collect images: prize/event banners (by filename) + a title banner thumbnail
        imgs = self.detail_images(soup)
        webinar.prize_images = [u for u in imgs if prizes.is_prize_image(u)]
        og = soup.select_one("meta[property='og:image']")
        banner = next((u for u in imgs if "2560" in u), "")  # wide title banner
        webinar.thumbnail = (og.get("content") if og and og.get("content") else "") or banner

    def collect(self, browser) -> list:
        """Unique detail stubs from every listing page, newest slug first."""
        found: dict[str, object] = {}
        listing_urls = [self.listing_url] + list(self.cfg.get("extra_listing_urls", []))
        for i, url in enumerate(listing_urls):
            html = browser.get_html(
                url,
                self.cfg.get("wait_selector"),
                exhaust_listing=(i == 0),  # the slider homepage
            )
            if not html:
                log.warning("[ddtube] listing %s returned nothing", url)
                continue
            for w in self.parse(html):
                found.setdefault(w.url, w)
        stubs = sorted(found.values(), key=lambda w: -int(SLUG_RE.search(w.url).group(1)))
        limit = int(self.cfg.get("max_details", DEFAULT_MAX_DETAILS))
        return stubs[:limit]

    def fetch(self, browser):
        webinars = self.collect(browser)
        for w in webinars:
            try:
                self._enrich(browser, w)
            except Exception as e:  # keep going if one detail page fails
                log.warning("[ddtube] enrich failed for %s: %s", w.url, e)
        # drop any that never got a real title
        webinars = [w for w in webinars if not re.fullmatch(r"d\d+", w.title)]
        log.info("[ddtube] scraped %d webinars", len(webinars))
        return webinars
