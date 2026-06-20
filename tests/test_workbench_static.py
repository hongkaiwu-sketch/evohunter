import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "evohunter" / "web" / "static" / "index.html"
JS = ROOT / "evohunter" / "web" / "static" / "app.js"
LOCALES = ROOT / "evohunter" / "web" / "static" / "locales"


def test_workbench_has_search_bar():
    html = HTML.read_text(encoding="utf-8")
    assert 'id="search-skills"' in html
    assert 'id="search-location"' in html
    assert 'id="search-level"' in html
    assert 'id="search-btn"' in html


def test_workbench_has_dual_panel():
    html = HTML.read_text(encoding="utf-8")
    assert 'id="jd-list"' in html
    assert 'id="candidate-list"' in html


def test_workbench_has_seed_button():
    html = HTML.read_text(encoding="utf-8")
    assert 'id="seed-btn"' in html


def test_workbench_has_match_bar():
    html = HTML.read_text(encoding="utf-8")
    assert 'id="match-btn"' in html
    assert 'id="match-info"' in html


def test_workbench_has_results():
    html = HTML.read_text(encoding="utf-8")
    assert 'id="results-list"' in html
    assert 'id="detail-wrap"' in html


def test_workbench_script_has_search_and_match():
    script = JS.read_text(encoding="utf-8")
    assert "function search()" in script
    assert "function matchSelected()" in script
    assert "function seedDemo()" in script
    assert "function importJD()" in script
    assert "function importResume()" in script
    assert "function selectMatch(" in script
    assert "function draftOutreach(" in script
    assert "function generateReport(" in script
    assert "/api/pool/search" in script
    assert "/api/pool/seed" in script


def test_no_external_deps():
    combined = (HTML.read_text() + JS.read_text()).lower()
    assert "bootstrap" not in combined
    assert "chart.js" not in combined
    assert "flask" not in combined


def test_workbench_has_status_bar():
    html = HTML.read_text(encoding="utf-8")
    for eid in ("sb-generation", "sb-jds", "sb-candidates", "api-dot"):
        assert f'id="{eid}"' in html


def test_workbench_has_evolution_nav():
    assert 'href="/evolution"' in HTML.read_text()


def test_locale_files():
    en = json.loads((LOCALES / "en.json").read_text(encoding="utf-8"))
    zh = json.loads((LOCALES / "zh.json").read_text(encoding="utf-8"))
    for p in (en, zh):
        assert p["app"]["title"]
        assert p["buttons"]["score"]
    assert en["buttons"]["score"] == "Score"
    assert zh["buttons"]["score"] == "评分"
