"""Open a few listing pages in Playwright Chromium, headed and headless, and
print one OK / CRASH / FAIL line per page — so a run where every site returns 0
can be told apart as a machine-level Chromium problem. Run by runner_diag.sh.
"""
import resource
import sys

from playwright.sync_api import sync_playwright

URLS = ["https://www.e4ds.com/webinar.asp", "https://www.ddtube.co.kr/webinar/"]
ARGS = ["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"]


def probe(pw, headless: bool) -> None:
    mode = "headless" if headless else "headed"
    try:
        browser = pw.chromium.launch(headless=headless, args=ARGS)
    except Exception as e:
        print(f"FAIL  {mode:8} launch: {str(e).splitlines()[0][:120]}")
        return
    for url in URLS:
        page = browser.new_page()
        crashed = []
        page.on("crash", lambda _page: crashed.append(True))
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            print(f"OK    {mode:8} {url} ({len(page.content())} bytes)")
        except Exception as e:
            tag = "CRASH" if crashed else "FAIL "
            print(f"{tag} {mode:8} {url}: {str(e).splitlines()[0][:100]}")
        try:
            page.close()
        except Exception:
            pass
    browser.close()


def main() -> int:
    print("open files limit:", resource.getrlimit(resource.RLIMIT_NOFILE)[0])
    with sync_playwright() as pw:
        for headless in (False, True):
            probe(pw, headless)
    return 0


if __name__ == "__main__":
    sys.exit(main())
