import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "evohunter" / "web" / "static" / "index.html"
JS = ROOT / "evohunter" / "web" / "static" / "app.js"
LOCALES = ROOT / "evohunter" / "web" / "static" / "locales"


def test_has_mode_tabs():
    html = HTML.read_text(encoding="utf-8")
    assert 'I\'m Hiring' in html
    assert 'I\'m Looking' in html
    assert 'class="mode-tab"' in html


def test_has_search_and_import():
    html = HTML.read_text(encoding="utf-8")
    assert 'id="h-search-skills"' in html
    assert 'id="l-search-skills"' in html
    assert 'id="h-import-text"' in html
    assert 'id="l-import-text"' in html


def test_has_seed_and_detail():
    html = HTML.read_text(encoding="utf-8")
    assert 'id="seed-btn"' in html
    assert 'id="h-detail"' in html
    assert 'id="l-detail"' in html


def test_script_one_sided_match():
    script = JS.read_text(encoding="utf-8")
    assert "function selectJD(" in script
    assert "function selectCandidate(" in script
    assert "function importJD()" in script
    assert "function importResume()" in script
    assert "function seed()" in script
    assert "function switchMode(" in script
    assert "/api/pool/search" in script
    assert "/api/recruiter/assess" in script


def test_no_external_deps():
    c = (HTML.read_text() + JS.read_text()).lower()
    for w in ("bootstrap", "chart.js", "flask", "react", "vue"):
        assert w not in c


def test_status_bar_and_nav():
    html = HTML.read_text(encoding="utf-8")
    for eid in ("sb-generation", "sb-jds", "sb-candidates", "api-dot"):
        assert f'id="{eid}"' in html
    assert 'href="/evolution"' in html


def test_locales():
    en = json.loads((LOCALES / "en.json").read_text(encoding="utf-8"))
    zh = json.loads((LOCALES / "zh.json").read_text(encoding="utf-8"))
    for p in (en, zh):
        assert p["app"]["title"]
    assert en["buttons"]["score"] == "Score"
    assert zh["buttons"]["score"] == "评分"
