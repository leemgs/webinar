"""Offline tests for Browser.get_html navigation resilience — no real browser."""
from __future__ import annotations

import contextlib

from webinar.browser import Browser


class FakePage:
    """Minimal stand-in for a Playwright page used by Browser.get_html."""

    def __init__(self, fail_strategies=(), content_html="<html>ok</html>"):
        self.fail_strategies = set(fail_strategies)
        self._content = content_html
        self.goto_calls = []

    def goto(self, url, wait_until="load", timeout=0):
        self.goto_calls.append(wait_until)
        if wait_until in self.fail_strategies:
            raise TimeoutError(f"Page.goto: Timeout {timeout}ms exceeded")

    def wait_for_selector(self, selector, timeout=0):
        return None

    def click(self, selector, timeout=0):
        return None

    def wait_for_timeout(self, ms):
        return None

    def evaluate(self, js):
        return 0

    def content(self):
        return self._content


def _browser_with_page(page):
    b = Browser()

    @contextlib.contextmanager
    def fake_page():
        yield page

    b.page = fake_page  # type: ignore[assignment]
    return b


def test_navigation_success_first_try():
    page = FakePage(content_html="<html>fast</html>")
    html = _browser_with_page(page).get_html("https://x", wait_ms=0)
    assert html == "<html>fast</html>"
    assert page.goto_calls == ["domcontentloaded"]


def test_navigation_falls_back_to_commit_on_timeout():
    # mirrors allshowtv: 'domcontentloaded' never fires in budget, 'commit' does
    page = FakePage(fail_strategies={"domcontentloaded"}, content_html="<html>allshow</html>")
    html = _browser_with_page(page).get_html("https://x", wait_ms=0)
    assert html == "<html>allshow</html>"
    assert page.goto_calls == ["domcontentloaded", "commit"]


def test_navigation_salvages_dom_when_all_strategies_fail():
    page = FakePage(
        fail_strategies={"domcontentloaded", "commit"}, content_html="<html>partial</html>"
    )
    html = _browser_with_page(page).get_html("https://x", wait_ms=0)
    assert html == "<html>partial</html>"
    assert page.goto_calls == ["domcontentloaded", "commit"]


class FakeContext:
    def __init__(self, pages=(), factory=None):
        self.pages, self.factory = list(pages), factory

    def new_page(self):
        return self.pages.pop(0) if self.pages else self.factory()

    def storage_state(self):
        return {"cookies": [{"name": "cf_clearance"}]}

    def close(self):
        pass


class CrashingPage(FakePage):
    """Renderer dies on goto: fires the 'crash' event, then raises like Playwright."""

    def __init__(self):
        super().__init__(content_html="")
        self.handlers = {}

    def on(self, event, handler):
        self.handlers[event] = handler

    def goto(self, url, wait_until="load", timeout=0):
        self.goto_calls.append(wait_until)
        self.handlers["crash"](self)
        raise RuntimeError("Page.goto: Page crashed")

    def close(self):
        pass


class HealthyPage(FakePage):
    def on(self, event, handler):
        pass

    def close(self):
        pass


def _browser_with_contexts(*contexts):
    b = Browser()
    b._context = contexts[0]
    launched = []

    def fake_launch(state):
        launched.append(state)
        b._context = contexts[len(launched)]

    b._launch = fake_launch  # type: ignore[assignment]
    b._close_browser = lambda: None  # type: ignore[assignment]
    return b, launched


def test_renderer_crash_relaunches_chromium_and_retries_with_cookies():
    b, launched = _browser_with_contexts(
        FakeContext([CrashingPage()]),
        FakeContext([HealthyPage(content_html="<html>after restart</html>")]),
    )
    assert b.get_html("https://x", wait_ms=0) == "<html>after restart</html>"
    assert b.restarts == 1
    assert launched == [{"cookies": [{"name": "cf_clearance"}]}]


def test_renderer_crash_restarts_are_bounded():
    b, launched = _browser_with_contexts(
        *[FakeContext(factory=CrashingPage) for _ in range(Browser.MAX_RESTARTS + 1)]
    )
    for _ in range(Browser.MAX_RESTARTS + 2):
        assert b.get_html("https://x", wait_ms=0) == ""
    assert b.restarts == Browser.MAX_RESTARTS == len(launched)
    assert b.broken


def test_broken_browser_skips_pages_instead_of_touching_chromium():
    b = Browser()
    b.broken = True
    b._context = None  # any Chromium call would raise
    assert b.get_html("https://x") == ""
    assert b.get_html_and_json("https://x", "api") == ("", [])


def test_chromium_launch_args_survive_small_shm_and_no_gpu():
    assert "--disable-dev-shm-usage" in Browser.LAUNCH_ARGS
    assert "--disable-gpu" in Browser.LAUNCH_ARGS
