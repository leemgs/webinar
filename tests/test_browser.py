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
