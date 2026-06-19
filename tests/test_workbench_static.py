from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INDEX_HTML = ROOT / "evohunter" / "web" / "static" / "index.html"
APP_JS = ROOT / "evohunter" / "web" / "static" / "app.js"


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
