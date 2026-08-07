"""Playwright browser helper (sync API).

Provides a single reusable browser/context for all scrapers so that a daily run
launches Chromium once. Handles JS-rendered pages and bot-blocked sites by
using a real browser with a normal user-agent and Korean locale / KST timezone.
"""
from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Iterator, Optional

log = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)


class Browser:
    """Thin wrapper over a Playwright Chromium context.

    Usage:
        with Browser() as b:
            html = b.get_html("https://example.com", wait_selector=".card")
    """

    def __init__(self, headless: bool = True, storage_state: Optional[str] = None):
        self.headless = headless
        self.storage_state = storage_state
        self._pw = None
        self._browser = None
        self._context = None

    def __enter__(self) -> "Browser":
        from playwright.sync_api import sync_playwright

        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(
            headless=self.headless,
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
        )
        self._context = self._browser.new_context(
            user_agent=USER_AGENT,
            locale="ko-KR",
            timezone_id="Asia/Seoul",
            viewport={"width": 1366, "height": 900},
            storage_state=self.storage_state,
        )
        # Light stealth: hide webdriver flag
        self._context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
        )
        return self

    def __exit__(self, *exc) -> None:
        for closer in (self._context, self._browser):
            try:
                if closer:
                    closer.close()
            except Exception:  # pragma: no cover
                pass
        try:
            if self._pw:
                self._pw.stop()
        except Exception:  # pragma: no cover
            pass

    @property
    def context(self):
        return self._context

    @contextmanager
    def page(self) -> Iterator["object"]:
        page = self._context.new_page()
        try:
            yield page
        finally:
            page.close()

    def get_html(
        self,
        url: str,
        wait_selector: Optional[str] = None,
        wait_ms: int = 2500,
        timeout_ms: int = 30000,
        click_selector: Optional[str] = None,
        exhaust_listing: bool = False,
    ) -> str:
        """Navigate to `url`, let JS render, and return the page HTML.

        Returns "" on failure (so one bad site never breaks the whole run).
        """
        with self.page() as page:
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
                if wait_selector:
                    try:
                        page.wait_for_selector(wait_selector, timeout=timeout_ms)
                    except Exception:
                        log.warning("wait_selector %r not found on %s", wait_selector, url)
                # optionally reveal content behind a tab/accordion (e.g. 경품 안내)
                if click_selector:
                    try:
                        page.click(click_selector, timeout=5000)
                        page.wait_for_timeout(800)
                    except Exception:
                        log.debug("click_selector %r not clickable on %s", click_selector, url)
                if exhaust_listing:
                    self._exhaust_listing(page)
                # allow SPA XHR/hydration to settle
                page.wait_for_timeout(wait_ms)
                return page.content()
            except Exception as e:
                log.warning("failed to load %s: %s", url, e)
                return ""

    @staticmethod
    def _exhaust_listing(page, max_rounds: int = 12) -> None:
        """Reveal lazy-loaded/paginated cards before snapshotting a listing.

        Several webinar sites only hydrate cards after scrolling, while others
        use a conventional "더보기" button.  Stop as soon as two rounds produce
        the same document height and no enabled load-more control is present.
        The bounded loop prevents an infinite-news-feed style page from making
        the daily job hang.
        """
        stable_rounds = 0
        previous_height = 0
        more_selector = (
            "button:visible:not([disabled]):has-text('더보기'), "
            "a:visible:has-text('더보기'), "
            "button:visible:not([disabled]):has-text('Load more')"
        )
        for _ in range(max_rounds):
            clicked = False
            try:
                more = page.locator(more_selector).last
                if more.count():
                    more.click(timeout=1500)
                    clicked = True
            except Exception:
                pass
            try:
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                page.wait_for_timeout(700)
                height = page.evaluate("document.body.scrollHeight")
            except Exception:
                return
            stable_rounds = stable_rounds + 1 if height == previous_height and not clicked else 0
            previous_height = height
            if stable_rounds >= 2:
                break
        try:
            page.evaluate("window.scrollTo(0, 0)")
        except Exception:
            pass

    def save_storage_state(self, path: str) -> None:
        self._context.storage_state(path=path)
