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

www.sharedit.co.kr is frequently behind a bot challenge from CI runners, while
new webinars are also published on the dedicated host webinar.sharedit.co.kr
(e.g. /posts/36031). Both hosts' listings are scraped, a blocked detail page is
retried on the other host, and the same post id is de-duplicated across hosts.
"""
from __future__ import annotations

import logging
import re
from urllib.parse import urljoin, urlparse

from .base import (
    BaseScraper,
    clean,
    is_noise_title,
    now_kst,
    parse_date,
    parse_time,
    parse_time_range,
    to_iso_kst,
    add_hours_iso,
)
from datetime import date

log = logging.getLogger(__name__)

DETAIL_RE = re.compile(r"^/(?:posts|seminars)/\d+$")
WEBINAR_HOST_RE = re.compile(r"(^|\.)webinar\.sharedit\.co\.kr$", re.I)
MAIN_HOSTS = {"sharedit.co.kr", "www.sharedit.co.kr"}
WEBINAR_HOST = "webinar.sharedit.co.kr"
# "일시 : 2026-10-27(화) 14:00 ~ 15:00" — the authoritative schedule on a page
_CHALLENGE_MARKERS = (
    "잠시만 기다리십시오", "잠시만 기다려", "just a moment",
    "cf-chl-", "challenge-platform",
)
_CHALLENGE_WAIT_MS = 25000
_SCHEDULE_RE = re.compile(r"일\s*시\s*[:：]?\s*(.{4,60})")
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
        # Scrape every configured listing (www + the webinar.* host) so one
        # blocked host can't hide webinars published on the other.
        listing_urls = [self.listing_url] + list(self.cfg.get("extra_listing_urls", []))
        # canonical URL per post: a configured detail URL wins, so the stored id
        # stays stable whichever host the listing happens to surface it on
        canonical = {self._post_key(u): u.rstrip("/") for u in self.cfg.get("detail_urls", [])}
        by_key: dict[str, object] = {}
        for listing in listing_urls:
            html = self._fetch_listing(browser, listing)
            for w in self.parse(html, page_url=listing) if html else []:
                key = self._post_key(w.url)
                if key in by_key:
                    continue
                if key in canonical and canonical[key] != w.url:
                    w.url = w.register_url = canonical[key]
                    w.id = w.make_id(w.source, w.url)
                by_key[key] = w
        for url in self.cfg.get("detail_urls", []):
            by_key.setdefault(self._post_key(url), url.rstrip("/"))

        enriched = []
        for key, item in by_key.items():
            url = item if isinstance(item, str) else item.url
            html = self._fetch_detail_any_host(browser, url)
            webinar = None if isinstance(item, str) else item
            if html:
                if webinar is None:
                    webinar = self.parse_detail(html, url)
                else:
                    self._enrich_from_detail_html(webinar, html)
            if webinar:
                enriched.append(webinar)
                log.info("[sharedit] %s | %s | %s", webinar.start_kst, webinar.title[:50], webinar.url)
        log.info("[sharedit] scraped %d webinars", len(enriched))
        return enriched

    @staticmethod
    def _post_key(url: str) -> str:
        """Host-independent identity: '/posts/36031' for detail URLs, else the URL."""
        path = urlparse(url).path.rstrip("/")
        return path if DETAIL_RE.match(path) else url.rstrip("/")

    def _fetch_detail_any_host(self, browser, url: str) -> str:
        """Fetch a detail page; if its host is challenged, try the other host."""
        html = self._fetch_clear_html(browser, url)
        if html:
            return html
        parsed = urlparse(url)
        if DETAIL_RE.match(parsed.path.rstrip("/")):
            other = WEBINAR_HOST if parsed.hostname in MAIN_HOSTS else "www.sharedit.co.kr"
            alt = parsed._replace(netloc=other, query="").geturl()
            log.info("[sharedit] retrying blocked detail on %s", alt)
            return self._fetch_clear_html(browser, alt)
        return ""

    def _fetch_listing(self, browser, url: str = None, tries: int = 2) -> str:
        url = url or self.listing_url
        for _ in range(tries):
            html = browser.get_html(
                url,
                wait_selector=self.cfg.get("wait_selector"),
                wait_ms=3000,
                timeout_ms=30000,
                exhaust_listing=True,
                challenge_markers=_CHALLENGE_MARKERS,
                challenge_wait_ms=_CHALLENGE_WAIT_MS,
            )
            if html and not self._is_challenge(html) and re.search(
                r'href=["\'][^"\']*/(?:posts|seminars)/\d+', html
            ):
                return html
        log.warning("[sharedit] listing %s remained blocked or contained no webinar links", url)
        return ""

    def _fetch_clear_html(self, browser, url: str, tries: int = 2) -> str:
        for _ in range(tries):
            html = browser.get_html(
                url, wait_selector="body", wait_ms=3000,
                challenge_markers=_CHALLENGE_MARKERS,
                challenge_wait_ms=_CHALLENGE_WAIT_MS,
            )
            if html and not self._is_challenge(html):
                return html
        log.info("[sharedit] bot challenge persisted for %s", url)
        return ""

    @staticmethod
    def _is_challenge(html: str) -> bool:
        lowered = html.lower()
        return any(marker in lowered for marker in _CHALLENGE_MARKERS)

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

        d, start, end = self._detail_schedule(soup, title)
        if not d:
            return None
        og_img = soup.select_one("meta[property='og:image']")
        thumbnail = clean(og_img.get("content")) if og_img else ""
        webinar = self.new_webinar(
            title=self._clean_title(title),
            url=url.rstrip("/"),
            register_url=url.rstrip("/"),
            start_kst=start,
            end_kst=end,
            thumbnail=urljoin(url, thumbnail) if thumbnail else "",
        )
        self._enrich_from_detail_html(webinar, html)
        return webinar

    def _enrich_from_detail_html(self, webinar, html: str) -> None:
        """Replace listing-only midnight times with authoritative detail data."""
        soup = self.soup(html)
        detail_date, start, end = self._detail_schedule(soup, webinar.title)
        if detail_date and start:
            # keep the listing's clock time if the detail page only gave a date
            if start.endswith("T00:00:00+09:00") and webinar.start_kst and \
                    webinar.start_kst[:10] == start[:10]:
                start, end = webinar.start_kst, webinar.end_kst
            webinar.start_kst, webinar.end_kst = start, end
        imgs = self.select_prize_images(soup, _SLICE_SEL)
        if imgs:
            webinar.prize_images = imgs
        if not webinar.thumbnail:
            og_img = soup.select_one("meta[property='og:image']")
            if og_img and og_img.get("content"):
                webinar.thumbnail = self.abs_url(og_img.get("content"))

    def _detail_schedule(self, soup, title: str):
        """(date, start_iso, end_iso) for a detail page.

        Prefers the labelled "일시" value, then the [MMDD] code in the title,
        then the first date in the body — the body alone can carry unrelated
        dates (posting date, other events), so it is only a last resort.
        """
        content = soup.select_one("article, .post-content, .view-content, main") or soup.body
        text = clean(content.get_text(" ")) if content else ""
        m = _SCHEDULE_RE.search(text)
        snippet = m.group(1) if m else ""
        d = (parse_date(snippet) if snippet else None) or self._mmdd_date(title) \
            or parse_date(text)
        if not d:
            return None, None, None
        t_start, t_end = parse_time_range(snippet) if snippet else (None, None)
        if not t_start:
            t_start, t_end = parse_time_range(text)
        start = to_iso_kst(d, t_start)
        end = to_iso_kst(d, t_end) if t_end else None
        if not end or end <= start:
            end = add_hours_iso(start, 1.0)
        return d, start, end

    def parse(self, html, page_url: str = None):
        soup = self.soup(html)
        webinars = []
        seen = set()

        # The current board links to /posts/NNNN; legacy cards use
        # /seminars/NNNN and some campaigns use webinar.sharedit.co.kr.
        for a in soup.select("a[href]"):
            href = clean(a.get("href", ""))
            if not self._is_webinar_href(href):
                continue
            url = urljoin(page_url or (self.base_url + "/"), href)
            parsed_url = urlparse(url)
            # drop tracking queries (?referer=...) and trailing slashes
            url = parsed_url._replace(path=parsed_url.path.rstrip("/"), query="",
                                      fragment="").geturl()
            if parsed_url.hostname == "sharedit.co.kr":
                url = url.replace("://sharedit.co.kr", "://www.sharedit.co.kr", 1)
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
            return not parsed.netloc or parsed.hostname in MAIN_HOSTS or bool(
                WEBINAR_HOST_RE.search(parsed.hostname or "")
            )
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
