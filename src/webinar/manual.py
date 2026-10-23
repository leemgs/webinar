"""Manually registered webinars (config/manual_webinars.yaml).

Some sites bot-check GitHub Actions runners so hard that nothing can be scraped
from CI (e.g. both sharedit hosts). A webinar known to exist can be listed in
config/manual_webinars.yaml so it still reaches the calendar.

Precedence: a webinar actually scraped with the same url always wins (it is
tagged as scraped, the manual one is tagged "manual"). A manual entry replaces
an existing record only when that record was itself manual, so editing the YAML
(e.g. filling in the title or time later) takes effect on the next run.
"""
from __future__ import annotations

import logging
import re
from datetime import date, datetime, time
from pathlib import Path

import yaml

from .config import MANUAL_WEBINARS_YAML
from .models import Webinar

log = logging.getLogger(__name__)

MANUAL_TAG = "manual"


def _iso(d: str, t: str | None) -> str:
    from zoneinfo import ZoneInfo

    day = date.fromisoformat(str(d))
    hh, mm = (int(x) for x in str(t).split(":")) if t else (0, 0)
    return datetime.combine(day, time(hh, mm), ZoneInfo("Asia/Seoul")).isoformat()


def load_manual(path: Path = MANUAL_WEBINARS_YAML) -> list[Webinar]:
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    out = []
    for i, e in enumerate(raw.get("webinars") or []):
        try:
            start = _iso(e["date"], e.get("time"))
            end = _iso(e["date"], e["end"]) if e.get("end") else None
            if not end and e.get("time"):
                end = datetime.fromisoformat(start).replace(
                    hour=(int(e["time"].split(":")[0]) + 1) % 24).isoformat()
            url = e["url"].split("?")[0].rstrip("/")
            out.append(Webinar(
                source=e["source"],
                title=e["title"],
                url=url,
                register_url=url,
                start_kst=start,
                end_kst=end,
                host=e.get("host", ""),
                thumbnail=e.get("thumbnail", ""),
                tags=[MANUAL_TAG],
            ))
        except Exception as ex:  # one bad entry must not break the run
            log.warning("manual_webinars.yaml entry #%d skipped: %s", i, ex)
    return out


def apply_manual(merged: list[Webinar], manual: list[Webinar]) -> list[Webinar]:
    """Add manual entries that no scraped record supersedes."""
    by_id = {w.id: w for w in merged}
    for m in manual:
        cur = by_id.get(m.id)
        if cur is None or MANUAL_TAG in (cur.tags or []):
            if cur is not None:
                m.registered = cur.registered
            by_id[m.id] = m
            log.info("[manual] %s | %s | %s", m.start_kst, m.title[:50], m.url)
    return list(by_id.values())


# --- CLI: add/update an entry, apply entries to the dataset -----------------
_TIME_RE = re.compile(r"^([01]?\d|2[0-3]):[0-5]\d$")


def normalize_url(url: str) -> str:
    return url.strip().split("?")[0].split("#")[0].rstrip("/")


def add_entry(path: Path, source: str, url: str, title: str, day: str,
              start: str | None = None, end: str | None = None) -> str:
    """Add (or update, matched by source + url) one entry in the YAML file.

    Validates input; keeps the file's header comments (everything up to the
    `webinars:` line). Returns "added" or "updated".
    """
    from .config import load_sites

    source, title = source.strip(), " ".join(title.split())
    if source not in load_sites():
        raise ValueError(f"unknown source {source!r}")
    if not re.match(r"^https?://", url.strip()):
        raise ValueError("url must start with http:// or https://")
    if not title:
        raise ValueError("title is required")
    date.fromisoformat(day.strip())  # raises on a bad date
    for t in (start, end):
        if t and not _TIME_RE.match(t.strip()):
            raise ValueError(f"time must be HH:MM, got {t!r}")

    text = path.read_text(encoding="utf-8") if path.exists() else ""
    head, sep, _ = text.partition("\nwebinars:")
    header = head if sep else text.rstrip("\n")
    entries = (yaml.safe_load(text) or {}).get("webinars") or [] if text.strip() else []

    entry = {"source": source, "url": normalize_url(url), "title": title,
             "date": day.strip()}
    if start:
        entry["time"] = start.strip()
    if end:
        entry["end"] = end.strip()

    action = "added"
    for i, e in enumerate(entries):
        if e.get("source") == source and normalize_url(str(e.get("url", ""))) == entry["url"]:
            entries[i], action = entry, "updated"
            break
    else:
        entries.append(entry)

    body = yaml.safe_dump({"webinars": entries}, allow_unicode=True, sort_keys=False,
                          default_flow_style=False)
    path.write_text((header.rstrip("\n") + "\n\n" if header.strip() else "") + body,
                    encoding="utf-8")
    return action


def apply_to_dataset() -> int:
    """Merge manual entries into data/webinars.json and republish docs (no scraping)."""
    from . import storage
    from .pipeline import publish_docs

    merged = storage.prune_past(apply_manual(storage.load_webinars(), load_manual()))
    storage.save_webinars(merged)
    publish_docs()
    return len(merged)


def main(argv: list[str] | None = None) -> int:
    import argparse
    import os

    p = argparse.ArgumentParser(description="Manually registered webinars")
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("add", help="add or update one entry")
    # values may also come from env (workflow inputs are passed that way so
    # they are never interpolated into a shell command)
    a.add_argument("--source", default=os.getenv("MANUAL_SOURCE"))
    a.add_argument("--url", default=os.getenv("MANUAL_URL"))
    a.add_argument("--title", default=os.getenv("MANUAL_TITLE"))
    a.add_argument("--date", default=os.getenv("MANUAL_DATE"))
    a.add_argument("--time", default=os.getenv("MANUAL_TIME") or None)
    a.add_argument("--end", default=os.getenv("MANUAL_END") or None)
    sub.add_parser("apply", help="merge entries into the dataset and docs")
    args = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    if args.cmd == "add":
        missing = [k for k in ("source", "url", "title", "date") if not getattr(args, k)]
        if missing:
            p.error("missing: " + ", ".join(missing))
        action = add_entry(MANUAL_WEBINARS_YAML, args.source, args.url, args.title,
                           args.date, args.time, args.end)
        print(f"{action}: [{args.source}] {args.date} {args.time or '(시간 미정)'} {args.title}")
    else:
        print(f"applied manual entries; dataset now has {apply_to_dataset()} webinars")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
