"""채널온TV (chontv.com) scraper — webinar hub with /{channel}/{id} detail pages.

Detail links look like ``/paloaltonetworks/548`` or ``/event/858`` (a channel
slug + numeric id), with a date rendered as "2026년 04월 22일(수) 14:00~15:00".

NOTE: chontv.com is blocked by this project's dev-network egress proxy, so the
scraper could not be verified against the live DOM; it was written from the
observed URL/date structure and runs in CI where the site is reachable.
``require_date`` (default) makes unmatched selectors emit nothing rather than
junk, so a structure change publishes an empty result instead of garbage.
"""
from __future__ import annotations

import logging
import re

from .base import BaseScraper

log = logging.getLogger(__name__)

# a webinar detail link: /{channel-slug}/{numeric-id}, absolute or relative.
_DETAIL = re.compile(
    r"^(?:https?://(?:www\.)?chontv\.com)?/[a-z0-9][a-z0-9_-]*/\d+/?$", re.I
)


class Scraper(BaseScraper):
    CARD_SELECTORS = [
        "a[href]:has(h3)",
        "a[href]:has(.title)",
        ".webinar-list li",
        ".seminar-list li",
        ".card",
        "article",
    ]

    def parse(self, html):
        soup = self.soup(html)
        # prefer anchors that link to a /{channel}/{id} detail page
        cards = [
            a for a in soup.select("a[href]") if _DETAIL.match((a.get("href") or "").strip())
        ]
        if not cards:
            cards = self.select_cards(soup, self.CARD_SELECTORS)
        if not cards:
            cards = [li for li in soup.select("li, article") if li.select_one("a[href]")]
        return self.cards_to_webinars(
            cards,
            title_sel="h3, h4, .title, .tit, strong, .subject",
            host_sel=".host, .company, .org, .channel",
        )
