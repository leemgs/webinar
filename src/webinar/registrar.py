"""Config-driven auto login + webinar registration.

Registration is gated by `register.enabled` in config/sites.yaml AND the
presence of SITE_<KEY>_USER / SITE_<KEY>_PASS env vars. Use --dry-run to walk
the flow (navigate + locate buttons) without submitting anything.
"""
from __future__ import annotations

import argparse
import logging
import sys

from . import storage
from .browser import Browser
from .config import load_sites, site_credentials
from .models import Webinar

log = logging.getLogger(__name__)


def login(page, site_cfg: dict, user: str, password: str, timeout: int = 20000) -> bool:
    """Perform a login using selectors from sites.yaml. Returns success."""
    lc = site_cfg.get("login") or {}
    url = lc.get("url")
    if not url:
        log.warning("no login.url configured")
        return False
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=timeout)
        page.fill(lc["user_selector"], user, timeout=timeout)
        page.fill(lc["pass_selector"], password, timeout=timeout)
        page.click(lc["submit_selector"], timeout=timeout)
        page.wait_for_load_state("networkidle", timeout=timeout)
        log.info("login submitted for %s", url)
        return True
    except Exception as e:
        log.warning("login failed (%s): %s", url, e)
        return False


def register_one(page, site_cfg: dict, webinar: Webinar, dry_run: bool, timeout: int = 20000) -> bool:
    """Navigate to a webinar and click through its registration flow."""
    rc = site_cfg.get("register") or {}
    target = webinar.register_url or webinar.url
    if not target:
        return False
    try:
        page.goto(target, wait_until="domcontentloaded", timeout=timeout)
        btn = page.query_selector(rc.get("button_selector", ""))
        if not btn:
            log.info("[%s] no register button on %s", webinar.source, target)
            return False
        if dry_run:
            log.info("[dry-run] would click register on %s", target)
            return False
        btn.click()
        confirm_sel = rc.get("confirm_selector")
        if confirm_sel:
            try:
                page.click(confirm_sel, timeout=8000)
            except Exception:
                pass
        page.wait_for_load_state("networkidle", timeout=timeout)
        log.info("[%s] registered: %s", webinar.source, webinar.title)
        return True
    except Exception as e:
        log.warning("[%s] register failed for %s: %s", webinar.source, target, e)
        return False


def run(site_keys: list[str] | None = None, dry_run: bool = False) -> int:
    """Register for upcoming, not-yet-registered webinars on enabled sites."""
    sites = load_sites()
    webinars = storage.load_webinars()
    by_id = {w.id: w for w in webinars}
    upcoming = [w for w in webinars if storage.is_upcoming(w)]

    keys = site_keys or list(sites.keys())
    changed = 0

    with Browser(headless=True) as browser:
        for key in keys:
            cfg = sites.get(key)
            if not cfg:
                continue
            rc = cfg.get("register") or {}
            if not rc.get("enabled"):
                log.info("[%s] registration disabled — skipping", key)
                continue
            user, password = site_credentials(key)
            if not (user and password):
                log.info("[%s] no credentials — skipping", key)
                continue

            targets = [w for w in upcoming if w.source == key and not w.registered]
            if not targets:
                log.info("[%s] nothing to register", key)
                continue

            with browser.page() as page:
                if not login(page, cfg, user, password):
                    continue
                for wb in targets:
                    if register_one(page, cfg, wb, dry_run=dry_run):
                        by_id[wb.id].registered = True
                        changed += 1

    if changed and not dry_run:
        storage.save_webinars(list(by_id.values()))
        log.info("updated %d webinars as registered", changed)
    return changed


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Auto-register for webinars")
    p.add_argument("--site", action="append", help="limit to site key(s)")
    p.add_argument("--dry-run", action="store_true", help="walk flow without submitting")
    p.add_argument("-v", "--verbose", action="store_true")
    args = p.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )
    run(site_keys=args.site, dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
