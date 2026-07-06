"""쉐어드IT (sharedit.co.kr) scraper.

The site returns HTTP 402 to plain HTTP clients and its /seminars/NNNN detail
pages sit behind a "please wait" bot challenge, so everything is extracted from
the listing page (fetched with a real browser).

Listing items look like:
    <div class="tag">
      <a title="[0729] AI 시대, 운영 가능한 보안은?" href="/seminars/2319">29일 (화)</a>
    </div>

Dates come from a [MMDD] code embedded in the title when present, otherwise from
the day-of-month in the anchor text combined with the current KST month.
"""
from __future__ import annotations

import re
from datetime import date

from .base import (
    BaseScraper,
    clean,
    now_kst,
    parse_time,
    to_iso_kst,
    add_hours_iso,
)

DETAIL_RE = re.compile(r"^/seminars/\d+$")
MMDD_RE = re.compile(r"\[(\d{2})(\d{2})\]")          # [0729] -> 07-29
DAY_RE = re.compile(r"(\d{1,2})\s*일")               # "29일 (화)" -> 29


class Scraper(BaseScraper):
    def parse(self, html):
        soup = self.soup(html)
        ref = now_kst().date()
        webinars = []
        seen = set()

        for a in soup.select("a[href]"):
            href = a.get("href", "").split("?")[0]
            if not DETAIL_RE.match(href):
                continue
            title = clean(a.get("title") or a.get_text())
            if not title or len(title) < 4:
                continue
            url = self.abs_url(href)
            if url in seen:
                continue
            seen.add(url)

            d = self._resolve_date(title, clean(a.get_text()), ref)
            if not d:
                # detail pages are bot-blocked, so we can't enrich; an item
                # with no resolvable date is unusable (and often nav/comment
                # noise) — skip it rather than publish a dateless entry.
                continue
            t = parse_time(title) or parse_time(clean(a.get_text()))
            start = to_iso_kst(d, t)
            webinars.append(
                self.new_webinar(
                    title=self._clean_title(title),
                    url=url,
                    register_url=url,
                    start_kst=start,
                    end_kst=add_hours_iso(start, 1.0) if start else None,
                )
            )
        return webinars

    @staticmethod
    def _resolve_date(title: str, anchor_text: str, ref: date):
        m = MMDD_RE.search(title)
        if m:
            mo, day = int(m.group(1)), int(m.group(2))
            try:
                cand = date(ref.year, mo, day)
            except ValueError:
                return None
            # roll to next year if clearly in the past (e.g. Jan seen in Dec)
            if (cand - ref).days < -60:
                cand = date(ref.year + 1, mo, day)
            return cand
        # day-only in the anchor text -> assume current month, roll forward
        dm = DAY_RE.search(anchor_text)
        if dm:
            day = int(dm.group(1))
            for delta in (0, 1, 2):  # this month, next, month after
                mo = ref.month + delta
                yr = ref.year + (mo - 1) // 12
                mo = (mo - 1) % 12 + 1
                try:
                    cand = date(yr, mo, day)
                except ValueError:
                    continue
                if cand >= ref:
                    return cand
        return None

    @staticmethod
    def _clean_title(title: str) -> str:
        # drop a leading [MMDD] code from the visible title
        return clean(MMDD_RE.sub("", title, count=1))
