"""Sync registered webinars to Google Calendar via OAuth refresh tokens.

Targets one or more user-specified Google accounts (config/google.yaml,
GOOGLE_ACCOUNTS_YAML secret, or the legacy GOOGLE_* env vars — see
config.load_google_accounts). Idempotent: each event uses a deterministic id
derived from the webinar id, so re-runs update rather than duplicate. Only
webinars marked `registered` (or all upcoming, via --all or a per-account
`only_registered: false`) are synced.
"""
from __future__ import annotations

import argparse
import logging
import os
import re
import sys
import time
from datetime import datetime, timedelta

from . import storage
from .config import load_google_accounts
from .models import Webinar

log = logging.getLogger(__name__)

TOKEN_URI = "https://oauth2.googleapis.com/token"
SCOPES = ["https://www.googleapis.com/auth/calendar.events"]
WRITE_INTERVAL_SECONDS = float(os.getenv("CALENDAR_WRITE_INTERVAL_SECONDS", "1.0"))
MAX_RATE_LIMIT_ATTEMPTS = 7

PRIZE_LABELS = {
    "survey": "설문",
    "question": "질문",
    "consult": "상담",
    "attendance": "참석/시청",
}


def _service(account: dict):
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    creds = Credentials(
        token=None,
        refresh_token=account["refresh_token"],
        client_id=account["client_id"],
        client_secret=account["client_secret"],
        token_uri=TOKEN_URI,
        scopes=SCOPES,
    )
    return build("calendar", "v3", credentials=creds, cache_discovery=False)


def _event_id(webinar: Webinar) -> str:
    # Google event ids: base32hex only (a-v, 0-9), 5-1024 chars — 'w' is NOT
    # allowed, so the prefix must stay within a-v. Hash the webinar id.
    base = re.sub(r"[^a-v0-9]", "", webinar.id.lower())
    return ("vb" + base)[:100].ljust(5, "0")


def _describe(webinar: Webinar) -> str:
    lines = []
    if webinar.host:
        lines.append(f"주최: {webinar.host}")
    if webinar.register_url or webinar.url:
        lines.append(f"신청/링크: {webinar.register_url or webinar.url}")
    if webinar.prizes:
        lines.append("")
        lines.append("🎁 경품:")
        for p in webinar.prizes:
            label = PRIZE_LABELS.get(p.type, p.type)
            detail = " — ".join(filter(None, [p.item, p.condition]))
            lines.append(f"  • [{label}] {detail}".rstrip())
    lines.append("")
    lines.append(f"출처: {webinar.source}")
    return "\n".join(lines)


def _to_event(webinar: Webinar) -> dict:
    ev = {
        "id": _event_id(webinar),
        "summary": f"[웨비나] {webinar.title}",
        "description": _describe(webinar),
        "source": {"title": webinar.source, "url": webinar.url or "https://"},
    }
    if webinar.start_kst:
        ev["start"] = {"dateTime": webinar.start_kst, "timeZone": "Asia/Seoul"}
        end = webinar.end_kst or (
            datetime.fromisoformat(webinar.start_kst) + timedelta(hours=1)
        ).isoformat()
        ev["end"] = {"dateTime": end, "timeZone": "Asia/Seoul"}
    else:
        # all-day fallback: today
        today_dt = datetime.now().date()
        today = today_dt.isoformat()
        ev["start"] = {"date": today}
        ev["end"] = {"date": (today_dt + timedelta(days=1)).isoformat()}
    return ev


def _is_rate_limit_error(error: Exception) -> bool:
    """Return whether a Google API error is safe to retry with backoff."""
    status = getattr(getattr(error, "resp", None), "status", None)
    if status == 429:
        return True
    if status != 403:
        return False
    content = getattr(error, "content", b"")
    if isinstance(content, bytes):
        content = content.decode("utf-8", errors="replace")
    detail = f"{content} {error}".lower()
    return "ratelimitexceeded" in detail or "userratelimitexceeded" in detail


def _execute_with_backoff(
    request,
    *,
    account_name: str,
    webinar_title: str,
    max_attempts: int = MAX_RATE_LIMIT_ATTEMPTS,
    sleeper=None,
):
    """Execute a Calendar request, retrying quota throttles exponentially."""
    sleeper = sleeper or time.sleep
    for attempt in range(max_attempts):
        try:
            return request.execute()
        except Exception as error:
            if not _is_rate_limit_error(error) or attempt == max_attempts - 1:
                raise
            delay = 2**attempt
            retry_after = getattr(getattr(error, "resp", None), "get", lambda *_: None)(
                "retry-after"
            )
            try:
                delay = max(delay, float(retry_after)) if retry_after else delay
            except (TypeError, ValueError):
                pass
            log.warning(
                "[%s] Calendar rate limit for %s; retrying in %.1fs (%d/%d)",
                account_name,
                webinar_title,
                delay,
                attempt + 1,
                max_attempts - 1,
            )
            sleeper(delay)


def _upsert(
    svc,
    calendar_id: str,
    name: str,
    webinars: list[Webinar],
    strict: bool = False,
    write_interval: float = 0.0,
    sleeper=None,
) -> int:
    synced = 0
    failures = []
    sleeper = sleeper or time.sleep
    for index, wb in enumerate(webinars):
        body = _to_event(wb)
        eid = body["id"]
        try:
            request = svc.events().update(calendarId=calendar_id, eventId=eid, body=body)
            _execute_with_backoff(
                request, account_name=name, webinar_title=wb.title, sleeper=sleeper
            )
            synced += 1
        except Exception as update_error:
            # Insert only when Google explicitly reports that the deterministic
            # event id does not exist. Auth, quota, and network failures must not
            # be misreported as a missing event and retried as an insert.
            status = getattr(getattr(update_error, "resp", None), "status", None)
            if status != 404:
                log.warning("[%s] calendar update failed for %s: %s", name, wb.title, update_error)
                failures.append(wb.title)
                continue
            try:
                request = svc.events().insert(calendarId=calendar_id, body=body)
                _execute_with_backoff(
                    request, account_name=name, webinar_title=wb.title, sleeper=sleeper
                )
                synced += 1
            except Exception as e:
                log.warning("[%s] calendar upsert failed for %s: %s", name, wb.title, e)
                failures.append(wb.title)
        if write_interval > 0 and index < len(webinars) - 1:
            sleeper(write_interval)
    if strict and failures:
        raise RuntimeError(
            f"[{name}] failed to sync {len(failures)} webinar(s): "
            + ", ".join(failures[:3])
        )
    return synced


def sync(
    only_registered: bool = True,
    account_names: list[str] | None = None,
    strict: bool = False,
) -> int:
    """Upsert upcoming webinars into every configured Google account's calendar.

    `account_names` limits the run to those accounts; a per-account
    `only_registered` setting overrides the global flag. Returns the total
    number of events written across all accounts.
    """
    accounts = load_google_accounts()
    if account_names:
        known = {a["name"] for a in accounts}
        for missing in [n for n in account_names if n not in known]:
            log.warning("unknown google account %r (configured: %s)", missing, sorted(known))
        accounts = [a for a in accounts if a["name"] in set(account_names)]
    if not accounts:
        log.warning(
            "no Google account configured — skipping calendar sync "
            "(see config/google.example.yaml or GOOGLE_* env vars)"
        )
        if strict:
            raise RuntimeError("no Google account configured for calendar sync")
        return 0

    upcoming = [w for w in storage.load_webinars() if storage.is_upcoming(w)]
    total = 0
    for acct in accounts:
        webinars = upcoming
        if acct.get("only_registered", only_registered):
            webinars = [w for w in webinars if w.registered]
        if not webinars:
            log.info("[%s] no webinars to sync", acct["name"])
            continue
        try:
            svc = _service(acct)
        except Exception as e:
            log.warning("[%s] google auth failed: %s", acct["name"], e)
            if strict:
                raise RuntimeError(f"[{acct['name']}] Google Calendar authentication failed") from e
            continue
        synced = _upsert(
            svc,
            acct["calendar_id"],
            acct["name"],
            webinars,
            strict=strict,
            write_interval=WRITE_INTERVAL_SECONDS,
        )
        log.info("[%s] calendar synced %d events -> %s", acct["name"], synced, acct["calendar_id"])
        total += synced
    log.info("calendar synced %d events across %d account(s)", total, len(accounts))
    return total


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Sync webinars to Google Calendar")
    p.add_argument("--all", action="store_true", help="sync all upcoming, not just registered")
    p.add_argument(
        "--strict",
        action="store_true",
        help="exit with an error when credentials or any calendar write fails",
    )
    p.add_argument(
        "--account",
        action="append",
        metavar="NAME",
        help="sync only this configured account (repeatable; default: all accounts)",
    )
    p.add_argument("-v", "--verbose", action="store_true")
    args = p.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )
    sync(only_registered=not args.all, account_names=args.account, strict=args.strict)
    return 0


if __name__ == "__main__":
    sys.exit(main())
