from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any


class GeneBase:
    """Shared interface for all gene types: to_dict, from_dict, content_hash, anonymize."""

    def to_dict(self) -> dict[str, Any]:
        raise NotImplementedError

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Any:
        raise NotImplementedError

    def content_hash(self) -> str:
        """SHA-256 hash of canonical JSON (sorted keys), for dedup and identification."""
        import json
        payload = json.dumps(self.to_dict(), ensure_ascii=False, sort_keys=True)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]

    def anonymize(self) -> Any:
        """Return a copy with personally-identifiable fields removed."""
        raise NotImplementedError


def _require_mapping(data: Any, name: str) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise ValueError(f"{name} must be a dict")
    return data


def _require_string(data: dict[str, Any], field_name: str) -> str:
    value = data.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value.strip()


def _optional_string(data: dict[str, Any], field_name: str, default: str = "") -> str:
    value = data.get(field_name, default)
    if value is None:
        return default
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string")
    return value.strip() or default


def _optional_number(data: dict[str, Any], field_name: str, default: float = 0.0) -> float:
    value = data.get(field_name, default)
    if value is None:
        return default
    if isinstance(value, bool):
        raise ValueError(f"{field_name} must be a number")
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be a number") from exc


def _optional_list(data: dict[str, Any], field_name: str) -> list[str]:
    value = data.get(field_name, [])
    if not isinstance(value, list):
        raise ValueError(f"{field_name} must be a list")
    return [str(v).strip() for v in value if str(v).strip()]


def _optional_dict(data: dict[str, Any], field_name: str) -> dict[str, Any]:
    value = data.get(field_name, {})
    if not isinstance(value, dict):
        raise ValueError(f"{field_name} must be a dict")
    return value
