"""Offline tests for Google account config loading + calendar sync — no network."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from webinar import calendar_sync, config, storage
from webinar.models import Webinar

KST = timezone(timedelta(hours=9))

GOOGLE_ENV_VARS = (
    "GOOGLE_CLIENT_ID",
    "GOOGLE_CLIENT_SECRET",
    "GOOGLE_REFRESH_TOKEN",
    "GOOGLE_CALENDAR_ID",
    "GOOGLE_ACCOUNTS_YAML",
)


@pytest.fixture(autouse=True)
def _clean_google_env(monkeypatch, tmp_path):
    for var in GOOGLE_ENV_VARS:
        monkeypatch.delenv(var, raising=False)
    # point the local google.yaml at an (absent) temp file by default
    monkeypatch.setattr(config, "GOOGLE_YAML", tmp_path / "google.yaml")
    monkeypatch.setattr(calendar_sync, "WRITE_INTERVAL_SECONDS", 0)


def _account(name="acct", **extra):
    return {
        "client_id": f"{name}-id",
        "client_secret": f"{name}-secret",
        "refresh_token": f"{name}-token",
        **extra,
    }


# --- account loading --------------------------------------------------------
def test_no_config_means_no_accounts():
    assert config.load_google_accounts() == []


def test_legacy_env_vars_become_default_account(monkeypatch):
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "cid")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "sec")
    monkeypatch.setenv("GOOGLE_REFRESH_TOKEN", "tok")
    (acct,) = config.load_google_accounts()
    assert acct["name"] == "default"
    assert acct["calendar_id"] == "primary"
    monkeypatch.setenv("GOOGLE_CALENDAR_ID", "team@group.calendar.google.com")
    (acct,) = config.load_google_accounts()
    assert acct["calendar_id"] == "team@group.calendar.google.com"


def test_yaml_file_accounts(monkeypatch, tmp_path):
    yml = tmp_path / "google.yaml"
    yml.write_text(
        """
personal:
  client_id: cid1
  client_secret: sec1
  refresh_token: tok1
work:
  client_id: cid2
  client_secret: sec2
  refresh_token: tok2
  calendar_id: work@group.calendar.google.com
  only_registered: false
broken:
  client_id: cid3
""",
        encoding="utf-8",
    )
    monkeypatch.setattr(config, "GOOGLE_YAML", yml)
    accounts = config.load_google_accounts()
    assert [a["name"] for a in accounts] == ["personal", "work"]  # broken skipped
    assert accounts[0]["calendar_id"] == "primary"
    assert "only_registered" not in accounts[0]
    assert accounts[1]["only_registered"] is False


def test_env_yaml_wins_over_file_and_merges_legacy(monkeypatch, tmp_path):
    yml = tmp_path / "google.yaml"
    yml.write_text(
        "work:\n  client_id: file-cid\n  client_secret: s\n  refresh_token: t\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(config, "GOOGLE_YAML", yml)
    monkeypatch.setenv(
        "GOOGLE_ACCOUNTS_YAML",
        "work:\n  client_id: env-cid\n  client_secret: s\n  refresh_token: t\n",
    )
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "cid")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "sec")
    monkeypatch.setenv("GOOGLE_REFRESH_TOKEN", "tok")
    accounts = config.load_google_accounts()
    assert [a["name"] for a in accounts] == ["work", "default"]
    assert accounts[0]["client_id"] == "env-cid"


def test_invalid_env_yaml_is_ignored(monkeypatch):
    monkeypatch.setenv("GOOGLE_ACCOUNTS_YAML", "just a string")
    assert config.load_google_accounts() == []


# --- event mapping -----------------------------------------------------------
def test_event_id_is_deterministic_and_valid():
    w = Webinar(source="ddtube", title="T", url="https://x/d1")
    eid = calendar_sync._event_id(w)
    assert eid == calendar_sync._event_id(w)
    assert eid.startswith("vb")
    assert len(eid) >= 5
    assert all(c in "abcdefghijklmnopqrstuv0123456789" for c in eid)


def test_to_event_uses_kst_timezone():
    w = Webinar(
        source="ddtube",
        title="NVMe 웨비나",
        url="https://x/d1",
        start_kst="2026-08-01T14:00:00+09:00",
    )
    ev = calendar_sync._to_event(w)
    assert ev["summary"] == "[웨비나] NVMe 웨비나"
    assert ev["start"] == {"dateTime": "2026-08-01T14:00:00+09:00", "timeZone": "Asia/Seoul"}
    assert ev["end"]["dateTime"] == "2026-08-01T15:00:00+09:00"  # valid 1h fallback


# --- sync orchestration (fake service, no network) ---------------------------
class FakeEvents:
    def __init__(self, calls):
        self.calls = calls

    def update(self, calendarId, eventId, body):
        self.calls.append(("update", calendarId, body["id"]))
        return self

    def insert(self, calendarId, body):
        self.calls.append(("insert", calendarId, body["id"]))
        return self

    def execute(self):
        return {}


class FakeService:
    def __init__(self):
        self.calls = []

    def events(self):
        return FakeEvents(self.calls)


class ResponseError(Exception):
    def __init__(self, status):
        self.resp = type("Response", (), {"status": status})()


class RateLimitError(Exception):
    def __init__(self, status=403, reason="rateLimitExceeded"):
        self.resp = type(
            "Response",
            (),
            {"status": status, "get": lambda self, key, default=None: default},
        )()
        self.content = f'{{"error":{{"errors":[{{"reason":"{reason}"}}]}}}}'.encode()


class SequencedRequest:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = 0

    def execute(self):
        outcome = self.outcomes[self.calls]
        self.calls += 1
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class FailingEvents(FakeEvents):
    def __init__(self, calls, update_status):
        super().__init__(calls)
        self.update_status = update_status
        self.operation = None

    def update(self, calendarId, eventId, body):
        self.calls.append(("update", calendarId, body["id"]))
        self.operation = "update"
        return self

    def insert(self, calendarId, body):
        self.calls.append(("insert", calendarId, body["id"]))
        self.operation = "insert"
        return self

    def execute(self):
        if self.operation == "update":
            raise ResponseError(self.update_status)
        return {}


class FailingService:
    def __init__(self, update_status):
        self.calls = []
        self.update_status = update_status

    def events(self):
        return FailingEvents(self.calls, self.update_status)


def _future_webinar(title, registered):
    start = (datetime.now(KST) + timedelta(days=3)).isoformat()
    return Webinar(
        source="ddtube", title=title, url=f"https://x/{title}", start_kst=start, registered=registered
    )


def test_sync_respects_per_account_only_registered(monkeypatch):
    webinars = [_future_webinar("a", registered=True), _future_webinar("b", registered=False)]
    monkeypatch.setattr(storage, "load_webinars", lambda: webinars)
    accounts = [
        {**_account("p"), "name": "personal", "calendar_id": "primary"},
        {
            **_account("w"),
            "name": "work",
            "calendar_id": "work@cal",
            "only_registered": False,
        },
    ]
    monkeypatch.setattr(calendar_sync, "load_google_accounts", lambda: accounts)
    services = {}
    monkeypatch.setattr(
        calendar_sync, "_service", lambda acct: services.setdefault(acct["name"], FakeService())
    )

    total = calendar_sync.sync(only_registered=True)
    assert total == 3  # 1 registered on personal + 2 (all) on work
    assert [c[1] for c in services["personal"].calls] == ["primary"]
    assert len(services["work"].calls) == 2


def test_sync_account_filter(monkeypatch):
    monkeypatch.setattr(storage, "load_webinars", lambda: [_future_webinar("a", registered=True)])
    accounts = [
        {**_account("p"), "name": "personal", "calendar_id": "primary"},
        {**_account("w"), "name": "work", "calendar_id": "work@cal"},
    ]
    monkeypatch.setattr(calendar_sync, "load_google_accounts", lambda: accounts)
    services = {}
    monkeypatch.setattr(
        calendar_sync, "_service", lambda acct: services.setdefault(acct["name"], FakeService())
    )

    total = calendar_sync.sync(only_registered=True, account_names=["work"])
    assert total == 1
    assert "personal" not in services
    assert services["work"].calls == [("update", "work@cal", calendar_sync._event_id(_future_webinar("a", True)))]


def test_sync_without_accounts_is_noop(monkeypatch):
    monkeypatch.setattr(calendar_sync, "load_google_accounts", lambda: [])
    assert calendar_sync.sync() == 0


def test_upsert_inserts_only_after_not_found():
    webinar = _future_webinar("missing", registered=True)
    missing = FailingService(404)
    assert calendar_sync._upsert(missing, "primary", "acct", [webinar]) == 1
    assert [call[0] for call in missing.calls] == ["update", "insert"]

    unauthorized = FailingService(401)
    assert calendar_sync._upsert(unauthorized, "primary", "acct", [webinar]) == 0
    assert [call[0] for call in unauthorized.calls] == ["update"]


def test_strict_upsert_surfaces_calendar_write_failures():
    webinar = _future_webinar("unauthorized", registered=True)
    with pytest.raises(RuntimeError, match="failed to sync 1 webinar"):
        calendar_sync._upsert(
            FailingService(401), "primary", "acct", [webinar], strict=True
        )


def test_strict_sync_requires_google_configuration(monkeypatch):
    monkeypatch.setattr(calendar_sync, "load_google_accounts", lambda: [])
    with pytest.raises(RuntimeError, match="no Google account configured"):
        calendar_sync.sync(strict=True)


def test_calendar_rate_limit_is_retried_with_exponential_backoff():
    request = SequencedRequest(
        [RateLimitError(), RateLimitError(status=429), {"id": "event"}]
    )
    delays = []

    result = calendar_sync._execute_with_backoff(
        request,
        account_name="personal",
        webinar_title="AI webinar",
        sleeper=delays.append,
    )

    assert result == {"id": "event"}
    assert request.calls == 3
    assert delays == [1, 2]


def test_calendar_non_quota_403_is_not_retried():
    request = SequencedRequest([RateLimitError(reason="forbidden")])
    delays = []

    with pytest.raises(RateLimitError):
        calendar_sync._execute_with_backoff(
            request,
            account_name="personal",
            webinar_title="AI webinar",
            sleeper=delays.append,
        )

    assert request.calls == 1
    assert delays == []


def test_upsert_paces_calendar_writes():
    webinars = [
        _future_webinar("first", registered=True),
        _future_webinar("second", registered=True),
    ]
    delays = []

    synced = calendar_sync._upsert(
        FakeService(),
        "primary",
        "personal",
        webinars,
        write_interval=1.0,
        sleeper=delays.append,
    )

    assert synced == 2
    assert delays == [1.0]
