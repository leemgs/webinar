"""쉐어드IT (sharedit.co.kr) scraper.

The authoritative webinar board is /posts?post_type_id=4. New entries link to
/posts/NNNN, while older entries can still use /seminars/NNNN. The site returns
HTTP 402 to plain HTTP clients, so the listing is fetched with a real browser.

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

DETAIL_RE = re.compile(r"^/(?:posts|seminars)/\d+$")
WEBINAR_HOST_RE = re.compile(r"(^|\.)webinar\.sharedit\.co\.kr$", re.I)
MMDD_RE = re.compile(r"\[(\d{2})(\d{2})\]")  # [0729] -> 07-29
_BG_URL = re.compile(r"url\(['\"]?([^'\")]+)")
# sharedit renders the whole webinar (title·연사·Event/경품·안내) as image slices on
# its CDN; the 경품 섹션 is one of these. The dedicated posts page is bot-blocked, but
# the /seminars/NNNN page (accessible) embeds the same slices.
_SLICE_SEL = "img[src*='speedgabia.com/Webinar']:not([src*='footer'])"


class Scraper(BaseScraper):
    def fetch(self, browser):
        # A bot-challenge document is returned with HTTP 200 intermittently.
        # Validate the DOM and retry rather than accepting it as an empty board.
        listing_html = self._fetch_listing(browser)
        items = self.parse(listing_html) if listing_html else []
        by_url = {w.url.rstrip("/"): w for w in items}
        for url in self.cfg.get("detail_urls", []):
            by_url.setdefault(url.rstrip("/"), None)

        enriched = []
        for url, webinar in by_url.items():
            html = self._fetch_clear_html(browser, url)
            if html:
                if webinar is None:
                    webinar = self.parse_detail(html, url)
                else:
                    self._enrich_from_detail_html(webinar, html)
            if webinar:
                enriched.append(webinar)
        log.info("[sharedit] scraped %d webinars", len(enriched))
        return enriched

    def _fetch_listing(self, browser, tries: int = 3) -> str:
        for _ in range(tries):
            html = browser.get_html(
                self.listing_url,
                wait_selector=self.cfg.get("wait_selector"),
                wait_ms=3000,
                exhaust_listing=True,
            )
            if html and not self._is_challenge(html) and re.search(
                r'href=["\'][^"\']*/(?:posts|seminars)/\d+', html
            ):
                return html
        log.warning("[sharedit] listing remained blocked or contained no webinar links")
        return ""

    def _fetch_clear_html(self, browser, url: str, tries: int = 3) -> str:
        for _ in range(tries):
            html = browser.get_html(url, wait_selector="body", wait_ms=3000)
            if html and not self._is_challenge(html):
                return html
        log.info("[sharedit] bot challenge persisted for %s", url)
        return ""

    @staticmethod
    def _is_challenge(html: str) -> bool:
        lowered = html.lower()
        return any(marker in lowered for marker in (
            "잠시만 기다리십시오", "잠시만 기다려", "just a moment",
            "cf-chl-", "challenge-platform",
        ))

    def _fetch_slices(self, browser, url, tries: int = 2) -> list[str]:
        html = self._fetch_clear_html(browser, url, tries)
        if html:
            return self.select_prize_images(self.soup(html), _SLICE_SEL)
        return []

    def parse_detail(self, html: str, url: str):
        """Build one webinar from a /posts/NNNN detail page."""
        soup = self.soup(html)
        og_title = soup.select_one("meta[property='og:title']")
        title = clean(og_title.get("content")) if og_title else ""
        if not title:
            heading = soup.select_one("h1, .post-title, .view-title")
            title = clean(heading.get_text(" ")) if heading else ""
        if not title or is_noise_title(title):
            return None

        content = soup.select_one("article, .post-content, .view-content, main") or soup.body
        text = clean(content.get_text(" ")) if content else ""
        d = parse_date(text) or self._mmdd_date(title)
        if not d:
            return None
        start = to_iso_kst(d, parse_time(text))
        og_img = soup.select_one("meta[property='og:image']")
        thumbnail = clean(og_img.get("content")) if og_img else ""
        webinar = self.new_webinar(
            title=self._clean_title(title),
            url=url.rstrip("/"),
            register_url=url.rstrip("/"),
            start_kst=start,
            end_kst=add_hours_iso(start, 1.0),
            thumbnail=self.abs_url(thumbnail),
        )
        self._enrich_from_detail_html(webinar, html)
        return webinar

    def _enrich_from_detail_html(self, webinar, html: str) -> None:
        """Replace listing-only midnight times with authoritative detail data."""
        soup = self.soup(html)
        content = soup.select_one("article, .post-content, .view-content, main") or soup.body
        text = clean(content.get_text(" ")) if content else ""
        detail_date = parse_date(text)
        detail_time = parse_time(text)
        if detail_date or detail_time:
            current = webinar.start_kst
            current_date = date.fromisoformat(current[:10]) if current else None
            start = to_iso_kst(detail_date or current_date, detail_time)
            if start:
                webinar.start_kst = start
                webinar.end_kst = add_hours_iso(start, 1.0)
        imgs = self.select_prize_images(soup, _SLICE_SEL)
        if imgs:
            webinar.prize_images = imgs
        if not webinar.thumbnail:
            og_img = soup.select_one("meta[property='og:image']")
            if og_img and og_img.get("content"):
                webinar.thumbnail = self.abs_url(og_img.get("content"))

    def parse(self, html):
        soup = self.soup(html)
        webinars = []
        seen = set()

        # The current board links to /posts/NNNN; legacy cards use
        # /seminars/NNNN and some campaigns use webinar.sharedit.co.kr.
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
        img = card.select_one("img") if card else None
        if not img:
            return ""
        return self.abs_url(
            img.get("src") or img.get("data-src") or img.get("data-original") or ""
        )

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
