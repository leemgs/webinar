"""쉐어드IT (sharedit.co.kr) scraper.

The site returns HTTP 402 to plain HTTP clients and its /seminars/NNNN detail
pages sit behind a "please wait" bot challenge, so everything is extracted from
the listing page (fetched with a real browser).

Each webinar is a list item like:
    <li>
      <figure style="background-image: url('...thumb.png')"></figure>
      <header>
        <span class="sponsor">Databricks</span>
        <span class="category">웨비나</span>
        <strong><a title="..." href="/seminars/2312">...</a></strong>
      </header>
      <dl class="info"><dt>일시</dt><dd>2026-07-22(수) 09:00 ~ 17:00</dd> ...</dl>
    </li>

The authoritative date/time is the `일시` value in <dl class="info">. A [MMDD]
code in the title is used as a fallback.
"""
from __future__ import annotations

import logging
import re
from urllib.parse import urlparse

from .base import (
    BaseScraper,
    clean,
    is_noise_title,
    now_kst,
    parse_date,
    parse_time,
    to_iso_kst,
    add_hours_iso,
)
from datetime import date

log = logging.getLogger(__name__)

DETAIL_RE = re.compile(r"^/seminars/\d+$")
WEBINAR_HOST_RE = re.compile(r"(^|\.)webinar\.sharedit\.co\.kr$", re.I)
MMDD_RE = re.compile(r"\[(\d{2})(\d{2})\]")  # [0729] -> 07-29
_BG_URL = re.compile(r"url\(['\"]?([^'\")]+)")
# sharedit renders the whole webinar (title·연사·Event/경품·안내) as image slices on
# its CDN; the 경품 섹션 is one of these. The dedicated posts page is bot-blocked, but
# the /seminars/NNNN page (accessible) embeds the same slices.
_SLICE_SEL = "img[src*='speedgabia.com/Webinar']:not([src*='footer'])"


class Scraper(BaseScraper):
    def fetch(self, browser):
        # enrich each webinar's /seminars/NNNN page for the CDN image slices
        # (the 경품/Event section is embedded among them). The detail page shows an
        # intermittent "잠시만 기다리십시오" bot challenge per request, so we retry
        # with fresh requests until it clears.
        items = super().fetch(browser)
        for w in items:
            try:
                imgs = self._fetch_slices(browser, w.url)
                if imgs:
                    w.prize_images = imgs
            except Exception as e:
                log.warning("[sharedit] enrich failed for %s: %s", w.url, e)
        return items

    def _fetch_slices(self, browser, url, tries: int = 2) -> list[str]:
        for _ in range(tries):
            html = browser.get_html(url, wait_selector="body", wait_ms=3000)
            if html and "잠시만" not in html and "Just a moment" not in html:
                return self.select_prize_images(self.soup(html), _SLICE_SEL)
        log.info("[sharedit] bot challenge persisted for %s", url)
        return []

    def parse(self, html):
        soup = self.soup(html)
        webinars = []
        seen = set()

        # New campaigns are sometimes hosted on webinar.sharedit.co.kr rather
        # than /seminars/NNNN.  Iterate links (instead of only legacy <li>s) so
        # both card layouts are handled.
        for a in soup.select("a[href]"):
            href = clean(a.get("href", ""))
            if not self._is_webinar_href(href):
                continue
            parsed_href = urlparse(href)
            if DETAIL_RE.match(parsed_href.path.rstrip("/")):
                href = parsed_href.path.rstrip("/")
            elif parsed_href.path.endswith("/"):
                href = parsed_href._replace(path=parsed_href.path.rstrip("/")).geturl()
            url = self.abs_url(href)
            if url in seen:
                continue

            card = a.find_parent(["li", "article", "section"]) or a.find_parent("div") or a.parent
            title = self._title(a, card)
            if not title or is_noise_title(title):
                continue

            # authoritative date/time from <dl class="info"> 일시
            info_text = self._info_value(card, "일시")
            if not info_text:
                # The campaign-domain cards do not use dl.info; their visible
                # card text (or image alt) contains the date and time.
                info_text = clean(card.get_text(" ")) if card else ""
                if card:
                    info_text += " " + " ".join(
                        clean(img.get("alt", "")) for img in card.select("img[alt]")
                    )
            d = parse_date(info_text) or self._mmdd_date(title)
            if not d:
                # no reliable date (detail pages are bot-blocked) -> skip
                continue
            t = parse_time(info_text)

            seen.add(url)
            start = to_iso_kst(d, t)
            webinars.append(
                self.new_webinar(
                    title=self._clean_title(title),
                    url=url,
                    register_url=url,
                    start_kst=start,
                    end_kst=add_hours_iso(start, 1.0) if start else None,
                    host=self._text(card, ".sponsor"),
                    thumbnail=self._thumbnail(card),
                )
            )
        return webinars

    # -- helpers --
    def _is_webinar_href(self, href: str) -> bool:
        parsed = urlparse(href)
        if DETAIL_RE.match(parsed.path.rstrip("/")):
            return not parsed.netloc or parsed.hostname in {
                "sharedit.co.kr",
                "www.sharedit.co.kr",
            }
        return parsed.scheme in {"", "http", "https"} and bool(
            WEBINAR_HOST_RE.search(parsed.hostname or "")
        )

    @staticmethod
    def _title(a, card) -> str:
        candidates = [a.get("title")]
        if card:
            heading = card.select_one("h1, h2, h3, h4, strong")
            candidates.append(heading.get_text(" ") if heading else "")
            candidates.extend(img.get("alt") for img in card.select("img[alt]"))
        candidates.append(a.get_text(" "))
        return next((clean(value) for value in candidates if clean(value)), "")

    @staticmethod
    def _info_value(li, label: str) -> str:
        dl = li.select_one("dl.info")
        if not dl:
            return ""
        for dt in dl.find_all("dt"):
            if label in dt.get_text():
                dd = dt.find_next_sibling("dd")
                return clean(dd.get_text()) if dd else ""
        return ""

    @staticmethod
    def _text(li, sel: str) -> str:
        el = li.select_one(sel)
        return clean(el.get_text()) if el else ""

    @staticmethod
    def _figure_bg(li) -> str:
        fig = li.select_one("figure")
        if fig and fig.get("style"):
            m = _BG_URL.search(fig["style"])
            if m:
                return m.group(1)
        return ""

    def _thumbnail(self, card) -> str:
        bg = self._figure_bg(card)
        if bg:
            return self.abs_url(bg)
        img = card.select_one("img[src]") if card else None
        return self.abs_url(img.get("src")) if img else ""

    @staticmethod
    def _mmdd_date(title: str):
        m = MMDD_RE.search(title)
        if not m:
            return None
        ref = now_kst().date()
        mo, day = int(m.group(1)), int(m.group(2))
        try:
            cand = date(ref.year, mo, day)
        except ValueError:
            return None
        if (cand - ref).days < -60:  # roll to next year if clearly past
            cand = date(ref.year + 1, mo, day)
        return cand

    @staticmethod
    def _clean_title(title: str) -> str:
        return clean(MMDD_RE.sub("", title, count=1))
