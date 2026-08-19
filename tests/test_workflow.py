"""Checks for invariants in the daily collection/publishing workflow."""
from pathlib import Path

import pytest

from webinar import pipeline


ROOT = Path(__file__).resolve().parents[1]


def test_daily_workflow_scrapes_once_and_syncs_all_collected_webinars():
    workflow = (ROOT / ".github/workflows/daily.yml").read_text(encoding="utf-8")

    # A second scrape after calendar sync could publish events that were never
    # sent to Google Calendar. All collected events must be synced because site
    # registration is currently disabled and therefore every flag is false.
    assert workflow.count("python -m webinar.pipeline") == 1
    assert "python -m webinar.calendar_sync --all --strict -v" in workflow
    calendar_step = workflow.split("- name: Sync Google Calendar", 1)[1].split(
        "- name:", 1
    )[0]
    assert "continue-on-error" not in calendar_step
    assert workflow.count("if: always()") >= 3  # republish, coverage, commit


def test_pipeline_fails_without_overwriting_when_every_source_is_empty(monkeypatch):
    class FakeBrowser:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    monkeypatch.setattr(pipeline, "Browser", FakeBrowser)
    monkeypatch.setattr(pipeline, "load_sites", lambda: {"source": {}})
    monkeypatch.setattr(pipeline, "scrape_site", lambda browser, key, cfg: [])
    save_called = False

    def unexpected_save(_items):
        nonlocal save_called
        save_called = True

    monkeypatch.setattr(pipeline.storage, "save_webinars", unexpected_save)

    with pytest.raises(RuntimeError, match="all configured webinar sources"):
        pipeline.run(publish=False)
    assert save_called is False


def test_fresh_scrape_counts_are_written_to_actions_summary(monkeypatch, tmp_path):
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))

    pipeline.report_fresh_counts({"talkit": 3, "sharedit": 0})

    report = summary.read_text(encoding="utf-8")
    assert "| talkit | 3 | ✅ |" in report
    assert "| sharedit | 0 | ⚠️ 0건 |" in report


def test_pipeline_rejects_an_unexpected_empty_source(monkeypatch):
    class FakeBrowser:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    sites = {
        "healthy": {"scraper": "fake"},
        "broken": {"scraper": "fake"},
        "idle": {"scraper": "fake", "allow_empty": True},
    }
    monkeypatch.setattr(pipeline, "Browser", FakeBrowser)
    monkeypatch.setattr(pipeline, "load_sites", lambda: sites)
    monkeypatch.setattr(
        pipeline,
        "scrape_site",
        lambda browser, key, cfg: [object()] if key == "healthy" else [],
    )

    with pytest.raises(RuntimeError, match="broken"):
        pipeline.run(publish=False)
