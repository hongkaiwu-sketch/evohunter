import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INDEX_HTML = ROOT / "evohunter" / "web" / "static" / "index.html"
APP_JS = ROOT / "evohunter" / "web" / "static" / "app.js"
LOCALES_DIR = ROOT / "evohunter" / "web" / "static" / "locales"


def test_workbench_has_stateful_workflow_steps():
    html = INDEX_HTML.read_text(encoding="utf-8")

    for step_name in ("job", "source", "candidates", "score", "evolve"):
        assert f'data-step="{step_name}"' in html


def test_workbench_disables_downstream_actions_before_inputs_are_ready():
    html = INDEX_HTML.read_text(encoding="utf-8")

    assert 'id="score-button" type="button" disabled' in html
    assert 'id="evolve-button" type="button" disabled' in html


def test_workbench_script_syncs_button_and_step_state():
    script = APP_JS.read_text(encoding="utf-8")

    assert "function syncControlState()" in script
    assert "function setStepState(" in script
    assert "score_detail" in script


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
    assert "/api/dashboard" not in combined


def test_workbench_has_overview_and_outreach_controls():
    html = INDEX_HTML.read_text(encoding="utf-8")
    script = APP_JS.read_text(encoding="utf-8")

    for element_id in (
        "overview-candidate-count",
        "overview-highest-score",
        "overview-generation",
        "overview-last-step",
        "draft-outreach-button",
        "outreach-output",
    ):
        assert f'id="{element_id}"' in html
    assert "function refreshOverview()" in script
    assert "function draftOutreach()" in script


def test_workbench_has_history_analysis_controls():
    html = INDEX_HTML.read_text(encoding="utf-8")
    script = APP_JS.read_text(encoding="utf-8")

    for element_id in (
        "evolution-summary",
        "history-trend",
        "history-candidates",
        "history-generations",
    ):
        assert f'id="{element_id}"' in html
    assert "function refreshHistory()" in script
    assert "function renderHistory(" in script
    assert "/api/history" in script
    assert "evolution_summary" in script


def test_workbench_has_language_selector_and_i18n_markers():
    html = INDEX_HTML.read_text(encoding="utf-8")

    assert 'id="language-select"' in html
    assert 'data-i18n="app.language_label"' in html
    assert 'data-i18n="panels.jd_title"' in html
    assert 'data-i18n="buttons.score"' in html


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


def test_workbench_script_loads_and_applies_locales():
    script = APP_JS.read_text(encoding="utf-8")

    assert "async function loadLocale(" in script
    assert "function applyLocale()" in script
    assert "localStorage.setItem(\"evohunter_locale\"" in script
    assert "/static/locales/" in script
