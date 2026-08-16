"""e4ds (e4ds.com/webinar.asp) scraper — Next.js listing with D-day cards.

Upcoming webinars render as ``a.wbt-card`` linking to ``/webinar_detail.asp?idx=N``
with the title in ``.wbt-title`` and a relative ``.wbt-dday`` badge ("D-11").
The listing carries no absolute date/time, so the D-day badge is the schedule
signal: a card with a "D-N" badge is upcoming (N days out); cards without one
are past VOD/trend items and are skipped. Dates are therefore day-accurate;
the exact start time isn't published on the listing.

A generic card fallback is kept for other/older layouts. ``require_date`` keeps
unmatched selectors from emitting junk.
"""
from __future__ import annotations

from .base import BaseScraper, clean, is_noise_title, parse_date, to_iso_kst


class Scraper(BaseScraper):
    CARD_SELECTORS = [
        ".webinar_list li",
        ".seminar_list li",
        "table.webinar tr",
        ".list li",
        ".card",
        "article",
    ]

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
