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

from . import ics_export, manual, prizes, storage
from .browser import Browser
from .config import DOCS_DIR, WEBINARS_JSON, load_sites, site_credentials
from .registrar import login
from .models import Webinar
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


def merge_and_save(scraped: list, publish: bool = True) -> list:
    """Merge scraped records + manual entries into the dataset, prune, save."""
    existing = storage.load_webinars()
    merged = storage.merge(existing, scraped)
    # webinars registered by hand for sites that block CI (scraped data wins)
    merged = manual.apply_manual(merged, manual.load_manual())
    merged = storage.prune_past(merged)
    storage.save_webinars(merged)
    log.info("saved %d webinars -> %s", len(merged), WEBINARS_JSON)
    if publish:
        publish_docs()
    return merged


def merge_from_file(path: str, publish: bool = True) -> list:
    """Re-apply a saved scrape (see --scraped-out) onto the current dataset.

    Lets a workflow whose push lost a race reset to the latest main and merge
    its results again, instead of discarding the scrape or re-scraping.
    """
    import json

    with open(path, encoding="utf-8") as f:
        items = [Webinar.from_dict(d) for d in json.load(f)]
    log.info("merging %d saved webinars from %s", len(items), path)
    return merge_and_save(items, publish=publish)


def run(site_keys: list[str] | None = None, publish: bool = True,
        scraped_out: str | None = None) -> list:
    sites = load_sites()
    keys = site_keys or list(sites.keys())
    # WEBINAR_SKIP_SITES="a,b": leave these sources out of this run (e.g. one
    # scraped by a separate job). Their existing records are kept as-is.
    skip = {k.strip() for k in os.getenv("WEBINAR_SKIP_SITES", "").split(",") if k.strip()}
    if skip and site_keys is None:
        keys = [k for k in keys if k not in skip]
        log.info("skipping sources handled elsewhere: %s", ", ".join(sorted(skip)))

    scraped = []
    source_counts: dict[str, int] = {}
    # WEBINAR_HEADED=1 runs a real (headed) Chromium — used in CI under Xvfb,
    # since several sites' bot checks reject headless Chromium outright.
    headed = os.getenv("WEBINAR_HEADED", "").strip() in {"1", "true", "yes"}
    with Browser(headless=not headed) as browser:
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
    empty_sources = [key for key in keys if source_counts.get(key, 0) == 0]
    if empty_sources:
        # A source can legitimately have no upcoming sessions, and several sites
        # intermittently block GitHub runner IPs. Keep the last known records for
        # those sources via merge(), while making the degraded scrape conspicuous
        # in logs and the Actions summary. Only a total outage is fatal above.
        log.warning(
            "sources returned zero items; preserving their previous data: %s",
            ", ".join(empty_sources),
        )

    # enrich prizes
    for w in scraped:
        prizes.apply(w)

    if scraped_out:
        import json

        with open(scraped_out, "w", encoding="utf-8") as f:
            json.dump([w.to_dict() for w in scraped], f, ensure_ascii=False)

    # merge with existing (preserve registered flag + curated prizes), prune old
    return merge_and_save(scraped, publish=publish)


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
    p.add_argument("--scraped-out", help="also write this run's scraped records (JSON)")
    p.add_argument("--merge-from", help="no scraping: merge records saved by --scraped-out")
    p.add_argument("-v", "--verbose", action="store_true")
    args = p.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )
    if args.merge_from:
        merge_from_file(args.merge_from, publish=not args.no_publish)
    else:
        run(site_keys=args.site, publish=not args.no_publish, scraped_out=args.scraped_out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
