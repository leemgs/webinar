"""이벤터스 (event-us.kr) scraper — IT/프로그래밍 카테고리.

국내 최대 규모의 행사 플랫폼으로 IT 웨비나·세미나·컨퍼런스가 활발하며 참여 경품
이벤트가 많습니다. 검색 페이지는 Vue로 렌더링되며 각 카드는 /{host}/event/{id}
로 링크됩니다. 제목은 카드 이미지 alt, 날짜는 카드 텍스트("07월09일(목)")에 있습니다.

이벤터스는 월·일만 노출하므로 연도를 추론합니다: 올해 기준으로 이미 지난 날짜는
연말→연초 래핑(약 120일 이내)만 내년으로 보고, 그 외 과거는 지난 행사로 간주해
버립니다(홈페이지는 다가오는 일정 중심).
"""
from __future__ import annotations

import re
from datetime import date, timedelta

from .base import (
    BaseScraper,
    clean,
    is_noise_title,
    now_kst,
    parse_time,
    to_iso_kst,
    add_hours_iso,
)

EVENT_RE = re.compile(r"/event/(\d+)$")
_MD = re.compile(r"(\d{1,2})\s*월\s*(\d{1,2})\s*일")
_DEFAULT_IMG = "event-default-img"
# 웨비나/세미나가 아닌 모집·채용성 게시물 제외
_SKIP = ("강사 모집", "교육생 모집", "수강생 모집", "채용", "구인")


class Scraper(BaseScraper):
    def parse(self, html):
        soup = self.soup(html)
        ref = now_kst().date()
        out, seen = [], set()

        for a in soup.select("a[href*='/event/']"):
            href = a.get("href", "").split("?")[0]
            m = EVENT_RE.search(href)
            if not m:
                continue
            eid = m.group(1)
            if eid in seen:
                continue

            # climb to the nearest ancestor whose text carries a date
            node = a
            for _ in range(7):
                if node.parent is None:
                    break
                node = node.parent
                if _MD.search(node.get_text(" ", strip=True)):
                    break
            text = node.get_text(" ", strip=True)
            d = self._resolve_date(text, ref)
            if not d:
                continue

            title = self._title(node)
            if not title or is_noise_title(title) or any(s in title for s in _SKIP):
                continue

            seen.add(eid)
            start = to_iso_kst(d, parse_time(text))
            out.append(
                self.new_webinar(
                    title=title,
                    url=href,
                    register_url=href,
                    start_kst=start,
                    end_kst=add_hours_iso(start, 1.0) if start else None,
                    thumbnail=self._thumb(node),
                )
            )
        return out

    @staticmethod
    def _resolve_date(text: str, ref: date):
        m = _MD.search(text)
        if not m:
            return None
        mo, day = int(m.group(1)), int(m.group(2))
        try:
            cand = date(ref.year, mo, day)
        except ValueError:
            return None
        if cand < ref:  # already passed this year
            nxt = date(ref.year + 1, mo, day)
            # accept only a near year-end wrap; otherwise it's a past event -> drop
            return nxt if (nxt - ref).days <= 120 else None
        return cand

    @staticmethod
    def _title(node) -> str:
        for im in node.select("img[alt]"):
            alt = clean(im.get("alt"))
            if alt and _DEFAULT_IMG not in (im.get("src") or ""):
                return alt
        h = node.select_one("h3, h4, strong, .title, p")
        return clean(h.get_text()) if h else ""

    @staticmethod
    def _thumb(node) -> str:
        for im in node.select("img"):
            src = im.get("src") or im.get("data-src") or ""
            if src and not src.startswith("data:") and _DEFAULT_IMG not in src:
                return src
        return ""
