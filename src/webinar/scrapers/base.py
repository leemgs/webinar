"""Base scraper + shared parsing helpers (dates, times, urls)."""
from __future__ import annotations

import logging
import re
from datetime import date, datetime, time, timedelta
from typing import Optional
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup

from ..models import Webinar

log = logging.getLogger(__name__)

KST = ZoneInfo("Asia/Seoul")


def now_kst() -> datetime:
    return datetime.now(KST)


# --- date parsing ----------------------------------------------------------

_YMD = re.compile(r"(20\d{2})[.\-/년\s]+(\d{1,2})[.\-/월\s]+(\d{1,2})")
_MD = re.compile(r"(\d{1,2})\s*월\s*(\d{1,2})\s*일")
_MD_SLASH = re.compile(r"\b(\d{1,2})[./](\d{1,2})\b")
_DDAY = re.compile(r"[Dd]\s*[-−]\s*(\d+)")


def parse_date(text: str, ref: Optional[date] = None) -> Optional[date]:
    """Parse a Korean/ISO-ish date fragment into a date.

    Handles: 2026-07-08, 2026.07.08, 2026년 7월 8일, 7월 8일, 7/8, D-2.
    Year-less dates assume the current year, rolling to next year if the date
    already passed by more than a week (so December→January works in January).
    """
    if not text:
        return None
    ref = ref or now_kst().date()
    text = text.strip()

    m = _YMD.search(text)
    if m:
        y, mo, d = (int(x) for x in m.groups())
        try:
            return date(y, mo, d)
        except ValueError:
            return None

    # Prefer an explicit calendar date over a relative D-day badge: cards often
    # show both (e.g. "7월 16일(목) 10:30  D-10") and the calendar date is truth.
    m = _MD.search(text) or _MD_SLASH.search(text)
    if m:
        mo, d = int(m.group(1)), int(m.group(2))
        try:
            candidate = date(ref.year, mo, d)
        except ValueError:
            return None
        # roll to next year if it's clearly in the past
        if candidate < ref - timedelta(days=7):
            try:
                candidate = date(ref.year + 1, mo, d)
            except ValueError:
                return None
        return candidate

    m = _DDAY.search(text)
    if m:
        return ref + timedelta(days=int(m.group(1)))
    return None


_TIME_24 = re.compile(r"\b(\d{1,2}):(\d{2})\b")
_TIME_AMPM = re.compile(r"(오전|오후)?\s*(\d{1,2})\s*시\s*(\d{1,2})?\s*분?")
_TIME_KR_COLON = re.compile(r"(오전|오후)\s*(\d{1,2}):(\d{2})")
_TIME_ENG = re.compile(r"(\d{1,2})(?::(\d{2}))?\s*([APap][Mm])")


def parse_time(text: str) -> Optional[time]:
    """Parse the (first) time in a fragment.

    Handles: 14:00, 오후 2시, 오후 2시 30분, 오후 2:00, 2:00 PM.
    """
    if not text:
        return None

    m = _TIME_KR_COLON.search(text)
    if m:
        ampm, h, mn = m.group(1), int(m.group(2)), int(m.group(3))
        if ampm == "오후" and h < 12:
            h += 12
        if ampm == "오전" and h == 12:
            h = 0
        return time(h % 24, mn)

    m = _TIME_ENG.search(text)
    if m:
        h = int(m.group(1)) % 12
        mn = int(m.group(2) or 0)
        if m.group(3).lower() == "pm":
            h += 12
        return time(h % 24, mn)

    m = _TIME_AMPM.search(text)
    if m:
        ampm, h, mn = m.group(1), int(m.group(2)), int(m.group(3) or 0)
        if ampm == "오후" and h < 12:
            h += 12
        if ampm == "오전" and h == 12:
            h = 0
        return time(h % 24, mn)

    m = _TIME_24.search(text)
    if m:
        return time(int(m.group(1)) % 24, int(m.group(2)))
    return None


def to_iso_kst(d: Optional[date], t: Optional[time]) -> Optional[str]:
    """Combine date+time into an ISO-8601 KST string. Defaults time to 00:00."""
    if not d:
        return None
    t = t or time(0, 0)
    return datetime(d.year, d.month, d.day, t.hour, t.minute, tzinfo=KST).isoformat()


def add_hours_iso(iso: Optional[str], hours: float) -> Optional[str]:
    if not iso:
        return None
    dt = datetime.fromisoformat(iso)
    return (dt + timedelta(hours=hours)).isoformat()


def clean(text: Optional[str]) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).strip()


# common navigation / chrome text that should never be treated as a webinar
_NOISE_TITLES = {
    "로그인", "회원가입", "로그아웃", "마이페이지", "menu", "메뉴", "편성표",
    "홈", "home", "search", "검색", "more", "더보기", "전체보기", "닫기",
    "이전", "다음", "prev", "next", "사전등록", "사전 등록", "신청",
    "사전등록 바로가기", "다시보기", "발표자료", "webinar", "웨비나",
    "테크 전문채널", "지난 웨비나", "고객센터",
}


def is_noise_title(title: str) -> bool:
    t = clean(title).lower().strip(" >›»·")
    if len(t) < 4:
        return True
    return t in _NOISE_TITLES


# --- base scraper ----------------------------------------------------------


class BaseScraper:
    """Subclasses implement `parse(html)`; the framework fetches HTML for them.

    Splitting fetch from parse keeps `parse` unit-testable against saved HTML
    fixtures with no browser required.
    """

    def __init__(self, site_key: str, site_cfg: dict):
        self.key = site_key
        self.cfg = site_cfg
        self.base_url = site_cfg.get("base_url", "")
        self.listing_url = site_cfg.get("listing_url", self.base_url)

    # -- helpers for subclasses --
    def soup(self, html: str) -> BeautifulSoup:
        return BeautifulSoup(html, "html.parser")

    def abs_url(self, href: Optional[str]) -> str:
        if not href:
            return ""
        return urljoin(self.base_url + "/", href)

    def new_webinar(self, **kwargs) -> Webinar:
        kwargs.setdefault("source", self.key)
        return Webinar(**kwargs)

    def card_to_webinar(
        self,
        card,
        *,
        title_sel: Optional[str] = None,
        link_sel: str = "a[href]",
        img_sel: str = "img",
        host_sel: Optional[str] = None,
        default_duration_h: float = 1.0,
        require_date: bool = True,
    ) -> Optional[Webinar]:
        """Best-effort extraction of one webinar from a card element.

        Pulls link, title, thumbnail, and scans the card's text for a
        date + time. Returns None if no usable title is found, the title looks
        like navigation chrome, or (when require_date) no date can be parsed.
        Requiring a date keeps sites with unmatched selectors from emitting
        garbage — better to publish nothing than noise.
        """
        link_el = card.select_one(link_sel)
        if link_el is None and card.name == "a" and card.get("href"):
            link_el = card  # the card itself is the anchor
        href = self.abs_url(link_el.get("href")) if link_el else ""

        title = ""
        if title_sel:
            t = card.select_one(title_sel)
            if t:
                title = clean(t.get_text())
        if not title and link_el:
            title = clean(link_el.get("title") or link_el.get_text())
        if not title:
            title = clean(card.get("aria-label") or "")
        if not title or is_noise_title(title):
            return None

        img = card.select_one(img_sel)
        thumb = ""
        if img:
            thumb = self.abs_url(img.get("src") or img.get("data-src") or "")

        host = ""
        if host_sel:
            h = card.select_one(host_sel)
            if h:
                host = clean(h.get_text())

        text = clean(card.get_text(" "))
        d = parse_date(text)
        if require_date and not d:
            return None
        t = parse_time(text)
        start = to_iso_kst(d, t)
        end = add_hours_iso(start, default_duration_h) if start else None

        return self.new_webinar(
            title=title,
            url=href or self.listing_url,
            register_url=href,
            start_kst=start,
            end_kst=end,
            host=host,
            thumbnail=thumb,
        )

    def select_cards(self, soup, selectors: list[str]):
        """Return the first selector's matches that is non-empty."""
        for sel in selectors:
            cards = soup.select(sel)
            if cards:
                return cards
        return []

    def cards_to_webinars(self, cards, **kwargs) -> list[Webinar]:
        out: list[Webinar] = []
        seen: set[str] = set()
        for card in cards:
            wb = self.card_to_webinar(card, **kwargs)
            if wb and wb.id not in seen:
                seen.add(wb.id)
                out.append(wb)
        return out

    # -- to be implemented by subclasses --
    def parse(self, html: str) -> list[Webinar]:  # pragma: no cover - abstract
        raise NotImplementedError

    # -- default fetch using a shared Browser instance --
    def fetch(self, browser) -> list[Webinar]:
        html = browser.get_html(
            self.listing_url,
            wait_selector=self.cfg.get("wait_selector"),
        )
        if not html:
            log.warning("[%s] empty HTML from %s", self.key, self.listing_url)
            return []
        try:
            items = self.parse(html)
        except Exception as e:  # never let one site break the run
            log.exception("[%s] parse failed: %s", self.key, e)
            return []
        log.info("[%s] scraped %d webinars", self.key, len(items))
        return items
