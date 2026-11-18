"""ZDNet Korea IT'Sight (itsight.zdnet.co.kr) scraper.

The home page lists every recent event as a ``.blogs`` card: a type tag
(``.blog-tag``: "실시간 웨비나", "온디맨드 웨비나" or "conference"), the title in
``h4 a`` linking to ``webinar/{slug}`` or ``conference/{slug}``, and a meta row
with the date ("2026-11-19 (목)") and the time ("14:00~15:00").

On-demand videos ("온디맨드 웨비나") carry a running time ("1시간4분") instead of a
schedule and are skipped. Upcoming webinars are enriched from their detail
page: its EVENT section (``section#pricing``) holds the giveaway text — kept
as the description, which prizes.apply() classifies — and the prize images.
"""
from __future__ import annotations

import logging

from .base import BaseScraper, clean, is_noise_title, now_kst, parse_date, parse_time_range, to_iso_kst

log = logging.getLogger(__name__)

_PRIZE_SECTION = "section#pricing"


class Scraper(BaseScraper):
    def fetch(self, browser):
        html = browser.get_html(self.listing_url, wait_selector=self.cfg.get("wait_selector"))
        if not html:
            log.warning("[zdnet] empty HTML from %s", self.listing_url)
            return []
        try:
            items = self.parse(html)
        except Exception as e:  # never let one site break the run
            log.exception("[zdnet] parse failed: %s", e)
            return []
        today = now_kst().date().isoformat()
        for webinar in items:
            if webinar.start_kst[:10] < today:
                continue  # past events: the listing already has all we show
            detail = browser.get_html(webinar.url, wait_selector=_PRIZE_SECTION, wait_ms=800, timeout_ms=20000)
            if detail:
                self.apply_detail(webinar, detail)
        log.info("[zdnet] scraped %d webinars", len(items))
        return items

    def parse(self, html):
        out, seen = [], set()
        for card in self.soup(html).select(".blogs"):
            tag = clean(card.select_one(".blog-tag").get_text()) if card.select_one(".blog-tag") else ""
            if "온디맨드" in tag:
                continue  # a recording, not a scheduled session
            link = card.select_one("h4 a[href]")
            if not link:
                continue
            title = " ".join(clean(link.get_text(" ")).split())
            if not title or is_noise_title(title):
                continue
            date_text = time_text = ""
            for p in card.select(".blogs__content--meta p"):
                if p.select_one(".fa-calendar-alt"):
                    date_text = clean(p.get_text(" "))
                elif p.select_one(".fa-alarm-clock"):
                    time_text = clean(p.get_text(" "))
            d = parse_date(date_text)
            if not d:
                continue
            start, end = parse_time_range(time_text)
            url = self.abs_url(link.get("href"))
            img = card.select_one(".blogs__thumb img[src]")
            webinar = self.new_webinar(
                title=title,
                url=url,
                register_url=url,
                start_kst=to_iso_kst(d, start),
                end_kst=to_iso_kst(d, end) if start and end else None,
                thumbnail=self.https(self.abs_url(img.get("src"))) if img else "",
                tags=["conference"] if tag.lower() == "conference" else [],
            )
            if webinar.id in seen:
                continue
            seen.add(webinar.id)
            out.append(webinar)
        return out

    def apply_detail(self, webinar, html) -> None:
        """Giveaway text (→ description, classified by prizes.apply) and images."""
        soup = self.soup(html)
        section = soup.select_one(_PRIZE_SECTION)
        if section:
            # one clause per giveaway (.plan: "좋은 질문" + condition + item),
            # " · "-joined so prizes.extract_prizes() classifies each one
            # (질문 / 설문 / 참여) on its own
            plans = section.select(".plan") or [section]
            parts = [" ".join(clean(plan.get_text(" ")).split()) for plan in plans]
            text = " · ".join(t.removeprefix("EVENT").strip() for t in parts if t)
            if text:
                webinar.description = text[:600]
            images = self.select_prize_images(soup, f"{_PRIZE_SECTION} img")
            if images:
                webinar.prize_images = images
        og = soup.select_one("meta[property='og:image']")
        if not webinar.thumbnail and og and og.get("content"):
            webinar.thumbnail = self.https(og["content"])
