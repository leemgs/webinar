"""Configuration + secrets loading."""
from __future__ import annotations

import logging
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

log = logging.getLogger(__name__)

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
MANUAL_WEBINARS_YAML = CONFIG_DIR / "manual_webinars.yaml"
ACCOUNTS_YAML = CONFIG_DIR / "accounts.yaml"  # local, git-ignored (see accounts.example.yaml)
GOOGLE_YAML = CONFIG_DIR / "google.yaml"  # local, git-ignored (see google.example.yaml)
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


_GOOGLE_REQUIRED = ("client_id", "client_secret", "refresh_token")


def _normalize_google_account(name: str, raw: Any) -> dict[str, Any] | None:
    """Validate one {name: {...}} entry; None if it can't be used."""
    if not isinstance(raw, dict):
        return None
    acct: dict[str, Any] = {
        "name": str(name),
        "client_id": raw.get("client_id"),
        "client_secret": raw.get("client_secret"),
        "refresh_token": raw.get("refresh_token"),
        "calendar_id": raw.get("calendar_id") or "primary",
    }
    if "only_registered" in raw:
        acct["only_registered"] = bool(raw["only_registered"])
    if not all(acct[k] for k in _GOOGLE_REQUIRED):
        return None
    return acct


def load_google_accounts() -> list[dict[str, Any]]:
    """Return the Google Calendar target accounts, in declaration order.

    Each account: {name, client_id, client_secret, refresh_token, calendar_id,
    [only_registered]}. Sources, first definition of a name wins:
      1. GOOGLE_ACCOUNTS_YAML env var — inline YAML {name: {...}} (CI Secrets)
      2. config/google.yaml — local, git-ignored (see google.example.yaml)
      3. legacy single-account env vars (GOOGLE_CLIENT_ID/... ) as "default"
    Entries missing client_id/client_secret/refresh_token are skipped.
    """
    sources: list[dict[str, Any]] = []
    inline = os.getenv("GOOGLE_ACCOUNTS_YAML")
    if inline:
        try:
            parsed = yaml.safe_load(inline)
            if isinstance(parsed, dict):
                sources.append(parsed)
            else:
                log.warning("GOOGLE_ACCOUNTS_YAML must be a YAML mapping — ignored")
        except yaml.YAMLError as e:
            log.warning("GOOGLE_ACCOUNTS_YAML is not valid YAML: %s", e)
    if GOOGLE_YAML.exists():
        with open(GOOGLE_YAML, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if isinstance(data, dict):
            sources.append(data)

    accounts: list[dict[str, Any]] = []
    seen: set[str] = set()
    for src in sources:
        for name, raw in src.items():
            if name in seen:
                continue
            acct = _normalize_google_account(name, raw)
            if acct is None:
                log.warning("google account %r incomplete — skipped", name)
                continue
            seen.add(str(name))
            accounts.append(acct)

    if "default" not in seen and has_google_config():
        g = google_config()
        accounts.append(
            {
                "name": "default",
                "client_id": g["client_id"],
                "client_secret": g["client_secret"],
                "refresh_token": g["refresh_token"],
                "calendar_id": g["calendar_id"] or "primary",
            }
        )
    return accounts
