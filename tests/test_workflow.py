"""Checks for invariants in the daily collection/publishing workflow."""
from pathlib import Path

import pytest

from webinar import pipeline
from webinar.models import Webinar


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


def test_pipeline_preserves_previous_data_when_some_sources_are_empty(monkeypatch):
    class FakeBrowser:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    sites = {"healthy": {"scraper": "fake"}, "blocked": {"scraper": "fake"}}
    monkeypatch.setattr(pipeline, "Browser", FakeBrowser)
    monkeypatch.setattr(pipeline, "load_sites", lambda: sites)
    monkeypatch.setattr(
        pipeline,
        "scrape_site",
        lambda browser, key, cfg: [
            Webinar(source="healthy", title="new", url="https://example.com/new")
        ] if key == "healthy" else [],
    )

    existing = [
        Webinar(source="blocked", title="previous", url="https://example.com/previous")
    ]
    monkeypatch.setattr(pipeline.storage, "load_webinars", lambda: existing)
    monkeypatch.setattr(pipeline.prizes, "apply", lambda webinar: None)
    saved = []
    monkeypatch.setattr(pipeline.storage, "save_webinars", lambda items: saved.extend(items))
    monkeypatch.setattr(pipeline.storage, "prune_past", lambda items: items)

    result = pipeline.run(publish=False)

    assert result == saved
    assert len(result) == len(existing) + 1
    assert {webinar.source for webinar in result} == {"healthy", "blocked"}
