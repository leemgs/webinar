"""Playwright browser helper (sync API).

Provides a single reusable browser/context for all scrapers so that a daily run
launches Chromium once. Handles JS-rendered pages and bot-blocked sites by
using a real browser with a normal user-agent and Korean locale / KST timezone.
"""
from __future__ import annotations

import logging
import os
import re
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional

log = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)


class _DebugDump:
    """Save rendered HTML + JSON API responses for chosen hosts (CI diagnostics).

    Enabled by WEBINAR_DEBUG_DIR (output dir) and WEBINAR_DEBUG_HOSTS
    (comma-separated host substrings, e.g. "allshowtv.com,cloit.com"). The
    workflow uploads the directory as an artifact so a scraper returning 0 can
    be fixed against exactly what the CI browser saw — including data that a
    JS app fetches from its API and never puts in the page source.
    """

    MAX_JSON = 2_000_000
    MAX_FILES = 40

    def __init__(self, root: Path, slug: str):
        self.root, self.slug, self.n = root, slug, 0

    @classmethod
    def for_url(cls, url: str):
        out = os.getenv("WEBINAR_DEBUG_DIR")
        hosts = [h.strip() for h in os.getenv("WEBINAR_DEBUG_HOSTS", "").split(",") if h.strip()]
        if not out or not any(h in url for h in hosts):
            return None
        root = Path(out)
        root.mkdir(parents=True, exist_ok=True)
        slug = re.sub(r"[^A-Za-z0-9]+", "_", url.split("://", 1)[-1]).strip("_")[:90]
        return cls(root, slug)

    def on_response(self, response) -> None:
        try:
            ctype = response.headers.get("content-type", "")
            if "json" not in ctype or self.n >= self.MAX_FILES:
                return
            body = response.text()
            if len(body) > self.MAX_JSON:
                return
            self.n += 1
            (self.root / f"{self.slug}.api{self.n:02d}.json").write_text(
                f"// {response.status} {response.url}\n{body}", encoding="utf-8")
        except Exception:
            pass

    def save_html(self, html: str) -> None:
        (self.root / f"{self.slug}.html").write_text(html, encoding="utf-8")


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
        timeout_ms: int = 45000,
        click_selector: Optional[str] = None,
        exhaust_listing: bool = False,
        challenge_markers: Optional[tuple] = None,
        challenge_wait_ms: int = 0,
    ) -> str:
        """Navigate to `url`, let JS render, and return the page HTML.

        Returns "" on failure (so one bad site never breaks the whole run).

        Navigation is resilient: if the strict "domcontentloaded" wait times out
        (some sites — e.g. allshowtv — stall on a slow blocking sub-resource so
        the event never fires within the budget), we retry with the lenient
        "commit" strategy (resolves on the first response byte) and then let the
        selector/settle waits below render the content. As a last resort we still
        return whatever HTML is in the DOM instead of discarding the whole page.

        `challenge_markers` + `challenge_wait_ms`: if the page is a bot-check
        interstitial ("Just a moment", "잠시만 기다리십시오"), keep waiting on the
        SAME page for it to clear instead of reloading — reloading restarts the
        check, while staying lets it finish and set its clearance cookie on the
        shared context for every later request.
        """
        with self.page() as page:
            dump = _DebugDump.for_url(url)
            if dump:
                page.on("response", dump.on_response)
            try:
                html = self._load(page, url, wait_selector, wait_ms, timeout_ms,
                                  click_selector, exhaust_listing,
                                  challenge_markers, challenge_wait_ms)
            finally:
                if dump:
                    try:
                        dump.save_html(page.content())
                    except Exception:
                        pass
            return html

    def get_html_and_json(self, url: str, json_match: str, **kwargs) -> tuple[str, list]:
        """Like get_html, but also return JSON responses the page fetched.

        For JS apps whose content arrives from an API (e.g. CLOIT:ON reads its
        sessions from Supabase REST): the site's own scripts make the call
        with whatever keys they need, and we read the response. Returns
        (html, [(response_url, parsed_json), ...]) for responses whose URL
        contains `json_match`.
        """
        import json as _json

        captured: list = []

        def on_response(response):
            try:
                if json_match in response.url and "json" in response.headers.get(
                    "content-type", ""
                ):
                    captured.append((response.url, _json.loads(response.text())))
            except Exception:
                pass

        with self.page() as page:
            page.on("response", on_response)
            dump = _DebugDump.for_url(url)
            if dump:
                page.on("response", dump.on_response)
            try:
                html = self._load(
                    page, url, kwargs.get("wait_selector"), kwargs.get("wait_ms", 2500),
                    kwargs.get("timeout_ms", 45000), kwargs.get("click_selector"),
                    kwargs.get("exhaust_listing", False), kwargs.get("challenge_markers"),
                    kwargs.get("challenge_wait_ms", 0),
                )
            finally:
                if dump:
                    try:
                        dump.save_html(page.content())
                    except Exception:
                        pass
        return html, captured

    def _load(self, page, url, wait_selector, wait_ms, timeout_ms, click_selector,
              exhaust_listing, challenge_markers, challenge_wait_ms) -> str:
        try:
            if not self._navigate(page, url, timeout_ms):
                # navigation never committed — salvage anything that rendered
                try:
                    return page.content()
                except Exception:
                    return ""
            if challenge_markers and challenge_wait_ms:
                self._wait_challenge_clear(page, challenge_markers, challenge_wait_ms)
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
    def _wait_challenge_clear(page, markers: tuple, max_ms: int) -> bool:
        """Poll the current page until no challenge marker remains (or timeout)."""
        waited = 0
        while waited <= max_ms:
            try:
                html = page.content().lower()
            except Exception:
                html = ""
            if html and not any(m in html for m in markers):
                return True
            page.wait_for_timeout(1000)
            waited += 1000
        log.info("bot challenge did not clear within %d ms on %s", max_ms, page.url)
        return False

    @staticmethod
    def _navigate(page, url: str, timeout_ms: int) -> bool:
        """Navigate to `url`, trying a strict then a lenient wait strategy.

        Returns True once the navigation commits, False if every strategy fails.
        """
        for strategy in ("domcontentloaded", "commit"):
            try:
                page.goto(url, wait_until=strategy, timeout=timeout_ms)
                return True
            except Exception as e:
                log.warning("goto(%s) failed for %s: %s", strategy, url, e)
        return False

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
