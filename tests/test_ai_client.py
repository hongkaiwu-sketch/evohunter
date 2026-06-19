import pytest

from evohunter.ai import AIConfigurationError, build_evomap_api_key


def test_build_evomap_api_key_uses_evomap_env_first(monkeypatch):
    monkeypatch.setenv("EVOMAP_API_KEY", "abc123")
    monkeypatch.setenv("API_KEY", "fallback")

    assert build_evomap_api_key() == "sk-evomap-abc123"


def test_build_evomap_api_key_preserves_full_key(monkeypatch):
    monkeypatch.delenv("EVOMAP_API_KEY", raising=False)
    monkeypatch.setenv("API_KEY", "sk-evomap-existing")

    assert build_evomap_api_key() == "sk-evomap-existing"


def test_build_evomap_api_key_raises_when_missing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("EVOMAP_API_KEY", raising=False)
    monkeypatch.delenv("API_KEY", raising=False)

    with pytest.raises(AIConfigurationError, match="EVOMAP_API_KEY"):
        build_evomap_api_key()
