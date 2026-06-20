import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INDEX_HTML = ROOT / "evohunter" / "web" / "static" / "index.html"
APP_JS = ROOT / "evohunter" / "web" / "static" / "app.js"
LOCALES_DIR = ROOT / "evohunter" / "web" / "static" / "locales"


def test_workbench_has_dual_panel():
    html = INDEX_HTML.read_text(encoding="utf-8")

    assert 'class="dual-panel"' in html
    assert 'Companies hiring' in html
    assert 'Candidates looking' in html


def test_workbench_has_add_forms():
    html = INDEX_HTML.read_text(encoding="utf-8")

    assert 'id="add-jd-btn"' in html
    assert 'id="add-resume-btn"' in html
    assert 'id="jd-input"' in html
    assert 'id="resume-input"' in html


def test_workbench_has_match_bar():
    html = INDEX_HTML.read_text(encoding="utf-8")

    assert 'id="match-all-btn"' in html
    assert 'id="match-jd-count"' in html
    assert 'id="match-candidate-count"' in html
    assert 'id="match-total"' in html


def test_workbench_has_results_area():
    html = INDEX_HTML.read_text(encoding="utf-8")

    assert 'id="results-list"' in html
    assert 'id="detail-panel"' in html
    assert 'id="result-count"' in html


def test_workbench_script_has_match_flow():
    script = APP_JS.read_text(encoding="utf-8")

    assert "function parseJD()" in script
    assert "function parseResume()" in script
    assert "function matchAll()" in script
    assert "function renderResults()" in script
    assert "function selectMatch(" in script
    assert "function draftOutreach(" in script
    assert "function generateReport(" in script


def test_dashboard_prototype_files_are_not_runtime_entrypoints():
    assert not (ROOT / "Untitled-1.py").exists()
    assert not (ROOT / "Untitled-1.html").exists()
    assert not (ROOT / "src" / "import random.py").exists()


def test_workbench_static_has_no_external_dashboard_dependency():
    html = INDEX_HTML.read_text(encoding="utf-8")
    script = APP_JS.read_text(encoding="utf-8")
    combined = f"{html}\n{script}".lower()
    assert "bootstrap" not in combined
    assert "chart.js" not in combined
    assert "flask" not in combined


def test_workbench_has_status_bar():
    html = INDEX_HTML.read_text(encoding="utf-8")

    for eid in ("sb-generation", "sb-jds", "sb-candidates", "sb-strategy", "api-dot", "api-status"):
        assert f'id="{eid}"' in html


def test_workbench_has_evolution_nav():
    html = INDEX_HTML.read_text(encoding="utf-8")
    assert 'href="/evolution"' in html


def test_workbench_script_api_helpers():
    script = APP_JS.read_text(encoding="utf-8")

    assert "function checkApiKey()" in script
    assert "function updateStatusBar()" in script
    assert "function init()" in script
    assert "/api/config" in script
    assert "/api/recruiter/assess" in script
    assert "/api/evaluation/generate" in script
    assert "/api/evolution/data" in script
    assert "/api/draft-outreach" in script
