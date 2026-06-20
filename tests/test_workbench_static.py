import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INDEX_HTML = ROOT / "evohunter" / "web" / "static" / "index.html"
APP_JS = ROOT / "evohunter" / "web" / "static" / "app.js"
LOCALES_DIR = ROOT / "evohunter" / "web" / "static" / "locales"


def test_workbench_has_pipeline_bar():
    html = INDEX_HTML.read_text(encoding="utf-8")

    for node in ("jd", "parse", "outreach", "report"):
        assert f'data-node="{node}"' in html

    assert 'class="pipeline-bar"' in html
    assert 'class="pl-node"' in html


def test_workbench_has_input_and_run():
    html = INDEX_HTML.read_text(encoding="utf-8")

    assert 'id="jd-input"' in html
    assert 'id="resume-input"' in html
    assert 'id="run-btn"' in html


def test_workbench_script_has_pipeline_flow():
    script = APP_JS.read_text(encoding="utf-8")

    assert "function runPipeline()" in script
    assert "function setPipelineNode(" in script
    assert "function renderCards()" in script
    assert "function renderDetail(" in script


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


def test_workbench_has_cards_and_detail_panel():
    html = INDEX_HTML.read_text(encoding="utf-8")
    script = APP_JS.read_text(encoding="utf-8")

    assert 'id="cards-list"' in html
    assert 'id="detail-panel"' in html
    assert 'class="candidate-card' in script
    assert "function selectCard(" in script


def test_workbench_has_status_bar():
    html = INDEX_HTML.read_text(encoding="utf-8")

    for element_id in (
        "sb-generation",
        "sb-candidates",
        "sb-avg",
        "sb-strategy",
        "api-dot",
        "api-status",
    ):
        assert f'id="{element_id}"' in html


def test_workbench_has_evolution_nav():
    html = INDEX_HTML.read_text(encoding="utf-8")

    assert 'href="/evolution"' in html


def test_workbench_locale_files_cover_english_and_chinese():
    en = json.loads((LOCALES_DIR / "en.json").read_text(encoding="utf-8"))
    zh = json.loads((LOCALES_DIR / "zh.json").read_text(encoding="utf-8"))

    for payload in (en, zh):
        assert payload["app"]["title"]
        assert payload["buttons"]["score"]
        assert payload["messages"]["api_key_loaded"]
        assert payload["table"]["candidate"]

    assert en["buttons"]["score"] == "Score"
    assert zh["buttons"]["score"] == "评分"


def test_workbench_script_api_helpers():
    script = APP_JS.read_text(encoding="utf-8")

    assert "function checkApiKey()" in script
    assert "function updateStatusBar()" in script
    assert "function draftOutreach(" in script
    assert "function generateReport(" in script
    assert "function init()" in script
    assert "/api/config" in script
    assert "/api/recruiter/assess" in script
    assert "/api/evaluation/generate" in script
    assert "/api/evolution/data" in script
