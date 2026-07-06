"""Orchestrate: scrape all sites -> enrich prizes -> merge -> persist -> publish.

This is the entry point for the daily job:
    python -m webinar.pipeline
"""
from __future__ import annotations

import argparse
import logging
import shutil
import sys

from . import ics_export, prizes, storage
from .browser import Browser
from .config import DOCS_DIR, WEBINARS_JSON, load_sites, site_credentials
from .registrar import login
from .scrapers import get_scraper

log = logging.getLogger(__name__)


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
            scraped.extend(items)

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
