from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class MCPError(RuntimeError):
    pass


@dataclass(frozen=True)
class MCPTool:
    tool_id: str
    name: str
    description: str
    provider: str  # "email" | "im" | "calendar" | "custom"
    input_schema: dict[str, Any]
    output_schema: dict[str, Any] | None = None
    endpoint: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MCPTool":
        if not isinstance(data, dict):
            raise MCPError("MCPTool data must be a dict")
        return cls(
            tool_id=_require_string(data, "tool_id"),
            name=_require_string(data, "name"),
            description=data.get("description", ""),
            provider=_require_string(data, "provider"),
            input_schema=data.get("input_schema", {}),
            output_schema=data.get("output_schema"),
            endpoint=data.get("endpoint"),
        )

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "tool_id": self.tool_id,
            "name": self.name,
            "description": self.description,
            "provider": self.provider,
            "input_schema": dict(self.input_schema),
        }
        if self.output_schema is not None:
            result["output_schema"] = dict(self.output_schema)
        if self.endpoint is not None:
            result["endpoint"] = self.endpoint
        return result


@dataclass(frozen=True)
class MCPToolCall:
    tool_id: str
    parameters: dict[str, Any] = field(default_factory=dict)
    timeout: int = 30

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MCPToolCall":
        if not isinstance(data, dict):
            raise MCPError("MCPToolCall data must be a dict")
        return cls(
            tool_id=_require_string(data, "tool_id"),
            parameters=data.get("parameters", {}),
            timeout=int(data.get("timeout", 30)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool_id": self.tool_id,
            "parameters": dict(self.parameters),
            "timeout": self.timeout,
        }


@dataclass(frozen=True)
class MCPToolResult:
    tool_id: str
    success: bool
    data: dict[str, Any] | None = None
    error: str | None = None
    execution_time_ms: int = 0

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "tool_id": self.tool_id,
            "success": self.success,
            "execution_time_ms": self.execution_time_ms,
        }
        if self.data is not None:
            result["data"] = self.data
        if self.error is not None:
            result["error"] = self.error
        return result


def _require_string(data: dict[str, Any], field_name: str) -> str:
    value = data.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise MCPError(f"{field_name} must be a non-empty string")
    return value.strip()
