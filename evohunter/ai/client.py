from __future__ import annotations

import os
from pathlib import Path
from typing import Any

DEFAULT_BASE_URL = "https://api.evomap.ai/v1"
DEFAULT_MODEL = "evomap-gemini-3.1-pro-preview"
EVOMAP_KEY_PREFIX = "sk-evomap-"


class AIConfigurationError(RuntimeError):
    pass


def build_evomap_api_key(api_key: str | None = None) -> str:
    if api_key is None:
        load_local_env()
    raw_api_key = api_key or os.environ.get("EVOMAP_API_KEY") or os.environ.get("API_KEY")
    if not raw_api_key or not raw_api_key.strip():
        raise AIConfigurationError("EVOMAP_API_KEY or API_KEY is required")

    raw_api_key = raw_api_key.strip()
    if raw_api_key.startswith(EVOMAP_KEY_PREFIX):
        return raw_api_key
    return f"{EVOMAP_KEY_PREFIX}{raw_api_key}"


def load_local_env(start_path: str | Path | None = None) -> Path | None:
    env_path = _find_local_env(start_path)
    if env_path is None:
        return None

    for line in env_path.read_text(encoding="utf-8").splitlines():
        key, value = _parse_env_line(line)
        if key and key not in os.environ:
            os.environ[key] = value
    return env_path


def create_evomap_client(
    api_key: str | None = None,
    base_url: str = DEFAULT_BASE_URL,
) -> Any:
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise AIConfigurationError("openai package is required for EvoMap AI calls") from exc
    return OpenAI(base_url=base_url, api_key=build_evomap_api_key(api_key))


def _find_local_env(start_path: str | Path | None) -> Path | None:
    start = Path(start_path or Path.cwd()).resolve()
    if start.is_file():
        start = start.parent
    for current in (start, *start.parents):
        candidate = current / ".env"
        if candidate.is_file():
            return candidate
    return None


def _parse_env_line(line: str) -> tuple[str | None, str]:
    stripped = line.strip()
    if not stripped or stripped.startswith("#") or "=" not in stripped:
        return None, ""
    key, value = stripped.split("=", 1)
    key = key.strip()
    value = value.strip().strip("'\"")
    if not key:
        return None, ""
    return key, value


def complete_chat(
    messages: list[dict[str, str]],
    model: str = DEFAULT_MODEL,
    client: Any | None = None,
) -> str:
    active_client = client or create_evomap_client()
    completion = active_client.chat.completions.create(model=model, messages=messages)
    content = completion.choices[0].message.content
    if not isinstance(content, str) or not content.strip():
        raise AIConfigurationError("AI response content is empty")
    return content.strip()
