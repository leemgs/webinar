"""Per-site scrapers. Each module exposes a `Scraper` subclass of BaseScraper."""
from __future__ import annotations

import importlib
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .base import BaseScraper

# site key -> module name (all live in this package)
SCRAPER_MODULES = {
    "allshowtv": "allshowtv",
    "sharedit": "sharedit",
    "ddtube": "ddtube",
    "e4ds": "e4ds",
    "talkit": "talkit",
    "dubiz": "dubiz",
    "cloit": "cloit",
    "eventus": "eventus",
}


def get_scraper(site_key: str, site_cfg: dict) -> "BaseScraper":
    """Instantiate the Scraper for a given site key."""
    mod_name = SCRAPER_MODULES.get(site_key, site_key)
    module = importlib.import_module(f".{mod_name}", __package__)
    return module.Scraper(site_key, site_cfg)
