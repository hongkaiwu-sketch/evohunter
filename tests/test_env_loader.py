from evohunter.ai import build_evomap_api_key


def test_build_evomap_api_key_loads_parent_dotenv(tmp_path, monkeypatch):
    project_dir = tmp_path / "repo" / "evohunter"
    project_dir.mkdir(parents=True)
    (tmp_path / "repo" / ".env").write_text("API_KEY=local_key\n", encoding="utf-8")
    monkeypatch.chdir(project_dir)
    monkeypatch.delenv("EVOMAP_API_KEY", raising=False)
    monkeypatch.delenv("API_KEY", raising=False)

    assert build_evomap_api_key() == "sk-evomap-local_key"
