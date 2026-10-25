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
    # exactly one scrape; a race-retry may re-merge the SAVED scrape (--merge-from)
    scrapes = [line for line in workflow.splitlines()
               if "python -m webinar.pipeline" in line and "--merge-from" not in line]
    assert len(scrapes) == 1
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
    # isolate from the repo's real config/manual_webinars.yaml
    monkeypatch.setattr(pipeline.manual, "load_manual", lambda: [])

    result = pipeline.run(publish=False)

    assert result == saved
    assert len(result) == len(existing) + 1
    assert {webinar.source for webinar in result} == {"healthy", "blocked"}


# --- manual-entry + self-hosted daily workflows -----------------------------
def _yaml(name):
    import yaml
    return yaml.safe_load((ROOT / ".github/workflows" / name).read_text(encoding="utf-8"))


def test_add_webinar_workflow_never_interpolates_inputs_into_shell():
    wf = _yaml("add-webinar.yml")
    trig = wf.get("on") or wf.get(True)  # PyYAML parses bare `on:` as True
    assert set(trig) == {"workflow_dispatch"}
    for step in wf["jobs"]["add"]["steps"]:
        assert "${{ inputs." not in step.get("run", ""), step.get("name")
    env = wf["jobs"]["add"]["env"]
    assert env["MANUAL_URL"] == "${{ inputs.url }}"


def test_runner_setup_provides_fonts_for_chromium():
    # no fonts on the runner => every Chromium page aborts (remote_font_face_source.cc)
    action = (ROOT / ".github/actions/setup-runner/action.yml").read_text(encoding="utf-8")
    assert 'FONTCONFIG_FILE=$(scripts/ensure_fonts.sh)' in action


def test_daily_sync_scrapes_sharedit_on_the_self_hosted_runner():
    wf = _yaml("daily.yml")
    assert wf["jobs"]["sync"]["runs-on"] == "self-hosted"
    daily = (ROOT / ".github/workflows/daily.yml").read_text(encoding="utf-8")
    assert "WEBINAR_SKIP_SITES" not in daily
    assert not (ROOT / ".github/workflows/sharedit.yml").exists()


def test_commit_script_survives_a_concurrent_push(tmp_path):
    """Another writer pushes first: the script resets, rebuilds and pushes."""
    import shutil
    import subprocess

    def git(cwd, *args):
        return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout

    origin = tmp_path / "origin.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(origin)], check=True)
    seed = tmp_path / "seed"
    git(tmp_path, "clone", "-q", str(origin), str(seed))
    for c in (seed,):
        git(c, "config", "user.email", "t@t"); git(c, "config", "user.name", "t")
    (seed / "data").mkdir(); (seed / "docs").mkdir(); (seed / "config").mkdir()
    for f in ("data/webinars.json", "docs/webinars.json", "docs/webinars.ics", "config/manual_webinars.yaml"):
        (seed / f).write_text("v0\n")
    git(seed, "add", "-A"); git(seed, "commit", "-qm", "seed"); git(seed, "push", "-q", "origin", "main")

    me = tmp_path / "me"
    git(tmp_path, "clone", "-q", str(origin), str(me))
    (me / "scripts").mkdir()
    shutil.copy(ROOT / "scripts/commit_data.sh", me / "scripts/commit_data.sh")
    (me / "data/webinars.json").write_text("mine\n")

    # someone else pushes data first
    (seed / "data/webinars.json").write_text("theirs\n")
    git(seed, "commit", "-qam", "theirs"); git(seed, "push", "-q", "origin", "main")

    rebuild = "printf 'theirs+mine\\n' > data/webinars.json"
    subprocess.run(["bash", "scripts/commit_data.sh", "chore: test", "bash", "-c", rebuild],
                   cwd=me, check=True, capture_output=True, text=True)
    check = tmp_path / "check"
    git(tmp_path, "clone", "-q", str(origin), str(check))
    assert (check / "data/webinars.json").read_text() == "theirs+mine\n"
    assert "theirs" in git(check, "log", "--format=%s")


def test_every_workflow_runs_on_self_hosted_without_root():
    # GitHub-hosted runners are Cloudflare-challenged by sharedit; all jobs run
    # on the self-hosted runner, which has no passwordless sudo/apt.
    for path in sorted((ROOT / ".github/workflows").glob("*.yml")):
        wf = _yaml(path.name)
        text = path.read_text(encoding="utf-8")
        for name, job in wf["jobs"].items():
            assert job["runs-on"] == "self-hosted", (path.name, name)
        assert "ubuntu-latest" not in text and "sudo " not in text, path.name
        assert "actions/setup-python" not in text, path.name  # venv via setup-runner
        assert "./.github/actions/setup-runner" in text, path.name
