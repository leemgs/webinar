"""The GitHub Pages site: one generated page per menu, each with its own URL."""
from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _build_pages():
    spec = importlib.util.spec_from_file_location("build_pages", ROOT / "scripts/build_pages.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_committed_pages_match_the_generator():
    assert _build_pages().main(["--check"]) == 0, "run: python scripts/build_pages.py"


def test_each_menu_page_holds_only_its_own_view():
    bp = _build_pages()
    sections = {"dashboard": 'id="dashboard-view"', "calendar": 'id="calendar-view"', "list": 'id="list-view"'}
    for key, *_ in bp.VIEWS:
        html = (ROOT / "docs" / key / "index.html").read_text(encoding="utf-8")
        assert f'data-view="{key}"' in html
        assert f'<a href="../{key}/" class="active" aria-current="page">' in html
        for other, marker in sections.items():
            assert (marker in html) == (other == key), (key, other)
        # the dashboard is an overview without source/prize filters
        assert ('id="source-filters"' in html) == (key != "dashboard")
        assert 'src="../assets/app.js' in html and 'href="../webinars.ics"' in html


def test_site_root_forwards_to_the_default_view():
    html = (ROOT / "docs/index.html").read_text(encoding="utf-8")
    assert 'url=calendar/' in html and 'location.replace("calendar/"' in html
