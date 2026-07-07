"""DD튜브 (ddtube.co.kr) scraper.

The homepage promotes upcoming webinars via a Slider Revolution slideshow where
title/date/link live in separate absolutely-positioned layers — not a clean
card. The reliable source is the per-webinar detail pages (/dNNNN/), which have
a clean <title> and a date in the body. So we:

  1. collect unique detail slugs from the listing,
  2. visit each detail page to fill title + date.
"""
from __future__ import annotations

import logging
import re

from .. import prizes
from .base import (
    BaseScraper,
    clean,
    parse_date,
    parse_time,
    to_iso_kst,
    add_hours_iso,
)

log = logging.getLogger(__name__)

SLUG_RE = re.compile(r"/d(\d{3,})/?(?:$|[?#])")
MAX_DETAILS = 30


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
        # date/time from the body text
        text = clean(soup.get_text(" "))
        d = parse_date(text)
        t = parse_time(text)
        start = to_iso_kst(d, t)
        if start:
            webinar.start_kst = start
            webinar.end_kst = add_hours_iso(start, 1.0)
        # collect images: prize/event banners (by filename) + a title banner thumbnail
        prize_imgs, banner = [], ""
        for im in soup.select("img"):
            src = im.get("src") or im.get("data-src") or ""
            if not src or src.startswith("data:"):
                continue
            src = self.abs_url(src)
            if src.startswith("http://"):  # avoid mixed-content on https Pages
                src = "https://" + src[len("http://"):]
            if prizes.is_prize_image(src):
                if src not in prize_imgs:
                    prize_imgs.append(src)
            elif not banner and "2560" in src:  # the wide title banner
                banner = src
        webinar.prize_images = prize_imgs
        og = soup.select_one("meta[property='og:image']")
        webinar.thumbnail = (og.get("content") if og and og.get("content") else "") or banner

    def fetch(self, browser):
        html = browser.get_html(self.listing_url, self.cfg.get("wait_selector"))
        if not html:
            return []
        webinars = self.parse(html)[:MAX_DETAILS]
        for w in webinars:
            try:
                self._enrich(browser, w)
            except Exception as e:  # keep going if one detail page fails
                log.warning("[ddtube] enrich failed for %s: %s", w.url, e)
        # drop any that never got a real title
        webinars = [w for w in webinars if not re.fullmatch(r"d\d+", w.title)]
        log.info("[ddtube] scraped %d webinars", len(webinars))
        return webinars
