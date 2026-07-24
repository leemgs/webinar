"""Shared pytest fixtures.

Freeze "now" for the whole suite so scraper tests that parse *year-less* Korean
dates (e.g. dubiz's "7월 16일", talkit's "7월 9일") are deterministic.

Without this, ``parse_date`` infers the year from the wall clock and rolls a
date that already passed by more than a week into next year. A test asserting a
specific year would then start failing the moment real time moved past that
date — which is exactly how the daily CI run broke on 2026-07-24 (dubiz's
"7월 16일" rolled to 2027 and no longer matched the hard-coded 2026 assertion).

Freezing the clock keeps the production rollover heuristic intact while making
every year-less-date test independent of when CI happens to run.
"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

KST = ZoneInfo("Asia/Seoul")

# Matches REF in test_parsers.py. Chosen so the fixtures' year-less dates fall in
# the near future (no year rollover) and stay consistent with their D-day badges
# (e.g. dubiz "7월 16일 … D-10" == 2026-07-06 + 10 days).
FROZEN_NOW = datetime(2026, 7, 6, 9, 0, tzinfo=KST)


@pytest.fixture(autouse=True)
def _freeze_scraper_clock(monkeypatch):
    """Pin the scrapers' notion of 'now' so date inference is reproducible."""
    monkeypatch.setattr("webinar.scrapers.base.now_kst", lambda: FROZEN_NOW)
