"""Configuration + secrets loading."""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

try:  # optional: load .env for local runs
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # pragma: no cover - dotenv is optional
    pass

# Repo root = two levels up from this file (src/webinar/config.py -> repo root)
ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = ROOT / "config"
DATA_DIR = ROOT / "data"
DOCS_DIR = ROOT / "docs"

SITES_YAML = CONFIG_DIR / "sites.yaml"
PRIZES_OVERRIDE_YAML = CONFIG_DIR / "prizes_override.yaml"
ACCOUNTS_YAML = CONFIG_DIR / "accounts.yaml"  # local, git-ignored (see accounts.example.yaml)
WEBINARS_JSON = DATA_DIR / "webinars.json"


@lru_cache(maxsize=1)
def load_sites() -> dict[str, dict[str, Any]]:
    """Return the parsed sites.yaml as {site_key: config}."""
    with open(SITES_YAML, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


@lru_cache(maxsize=1)
def load_prize_overrides() -> dict[str, list[dict[str, Any]]]:
    if not PRIZES_OVERRIDE_YAML.exists():
        return {}
    with open(PRIZES_OVERRIDE_YAML, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


@lru_cache(maxsize=1)
def load_accounts() -> dict[str, dict[str, Any]]:
    """Return the parsed, git-ignored config/accounts.yaml, or {} if absent.

    Shape: {site_key: {user: ..., pass: ...}}. Optional convenience file for
    local runs; GitHub Actions should use encrypted Secrets (env vars) instead.
    """
    if not ACCOUNTS_YAML.exists():
        return {}
    with open(ACCOUNTS_YAML, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def site_credentials(site_key: str) -> tuple[str | None, str | None]:
    """Return (user, pass) for a site.

    Precedence: environment variables (SITE_<KEY>_USER/PASS — used by GitHub
    Actions Secrets and .env) first, then the local config/accounts.yaml file.
    Returns (None, None) if unset in both.
    """
    prefix = f"SITE_{site_key.upper()}"
    user = os.getenv(f"{prefix}_USER")
    password = os.getenv(f"{prefix}_PASS")
    if user and password:
        return user, password
    acct = load_accounts().get(site_key) or {}
    # env still wins per-field when present; fall back to file otherwise
    return user or acct.get("user"), password or acct.get("pass")


def google_config() -> dict[str, str | None]:
    return {
        "client_id": os.getenv("GOOGLE_CLIENT_ID"),
        "client_secret": os.getenv("GOOGLE_CLIENT_SECRET"),
        "refresh_token": os.getenv("GOOGLE_REFRESH_TOKEN"),
        "calendar_id": os.getenv("GOOGLE_CALENDAR_ID", "primary"),
    }


def has_google_config() -> bool:
    g = google_config()
    return all(g[k] for k in ("client_id", "client_secret", "refresh_token"))
