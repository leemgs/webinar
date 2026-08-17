"""Orchestrate: scrape all sites -> enrich prizes -> merge -> persist -> publish.

This is the entry point for the daily job:
    python -m webinar.pipeline
"""
from __future__ import annotations

import argparse
import logging
import os
import shutil
import sys
from pathlib import Path

from . import ics_export, prizes, storage
from .browser import Browser
from .config import DOCS_DIR, WEBINARS_JSON, load_sites, site_credentials
from .registrar import login
from .scrapers import get_scraper

log = logging.getLogger(__name__)


def report_fresh_counts(source_counts: dict[str, int]) -> None:
    """Append counts from this exact scrape to the Actions summary, if present."""
    summary_path = os.getenv("GITHUB_STEP_SUMMARY")
    if not summary_path:
        return
    lines = [
        "### 이번 실행의 원본 수집 건수",
        "",
        "| 사이트 | 신규 응답 | 상태 |",
        "| --- | ---: | :---: |",
    ]
    for source, count in source_counts.items():
        lines.append(f"| {source} | {count} | {'✅' if count else '⚠️ 0건'} |")
    with Path(summary_path).open("a", encoding="utf-8") as summary:
        summary.write("\n".join(lines) + "\n\n")


def scrape_site(browser: Browser, key: str, cfg: dict):
    """Scrape one site, logging in first if it requires a session and we have creds."""
    scraper = get_scraper(key, cfg)

    if cfg.get("requires_login"):
        user, password = site_credentials(key)
        if user and password:
            # log in on the shared context so scraping sees a session
            with browser.page() as page:
                if login(page, cfg, user, password):
                    html = browser.get_html(cfg["listing_url"], cfg.get("wait_selector"))
                    return scraper.parse(html) if html else []
        else:
            log.info("[%s] requires login but no credentials — public scrape only", key)

    return scraper.fetch(browser)


def run(site_keys: list[str] | None = None, publish: bool = True) -> list:
    sites = load_sites()
    keys = site_keys or list(sites.keys())

    scraped = []
    source_counts: dict[str, int] = {}
    with Browser(headless=True) as browser:
        for key in keys:
            cfg = sites.get(key)
            if not cfg:
                log.warning("unknown site %s", key)
                continue
            try:
                items = scrape_site(browser, key, cfg)
            except Exception as e:
                log.exception("[%s] scrape crashed: %s", key, e)
                items = []
            log.info("[%s] %d webinars", key, len(items))
            source_counts[key] = len(items)
            scraped.extend(items)

    log.info(
        "scrape summary: %s",
        ", ".join(f"{key}={source_counts.get(key, 0)}" for key in keys),
    )
    report_fresh_counts(source_counts)
    if not scraped and site_keys is None:
        # Do not let a broken browser, proxy outage, or broad DOM change look
        # like a successful daily refresh. Keeping the previous dataset is safer,
        # and failing the job makes the collection outage visible immediately.
        raise RuntimeError("all configured webinar sources returned zero items")

    # enrich prizes
    for w in scraped:
        prizes.apply(w)

    # merge with existing (preserve registered flag + curated prizes), prune old
    existing = storage.load_webinars()
    merged = storage.merge(existing, scraped)
    merged = storage.prune_past(merged)
    storage.save_webinars(merged)
    log.info("saved %d webinars -> %s", len(merged), WEBINARS_JSON)

    if publish:
        publish_docs()
    return merged


def publish_docs() -> None:
    """Copy the dataset into docs/ and (re)generate the ICS feed."""
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    if WEBINARS_JSON.exists():
        shutil.copyfile(WEBINARS_JSON, DOCS_DIR / "webinars.json")
    try:
        ics_export.export()
    except Exception as e:
        log.warning("ics export failed: %s", e)
    log.info("published docs data")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Scrape webinars and publish dataset")
    p.add_argument("--site", action="append", help="limit to site key(s)")
    p.add_argument("--no-publish", action="store_true", help="skip copying to docs/")
    p.add_argument("-v", "--verbose", action="store_true")
    args = p.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )
    run(site_keys=args.site, publish=not args.no_publish)
    return 0


if __name__ == "__main__":
    sys.exit(main())
