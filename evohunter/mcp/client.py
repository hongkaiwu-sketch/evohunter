from __future__ import annotations

import json
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

from evohunter.mcp.models import MCPError, MCPTool, MCPToolCall, MCPToolResult


class MCPClient:
    """Generic client for MCP (Model Context Protocol).

    Connects to local or remote MCP servers, discovers tools,
    and executes tool calls with standardized envelopes.

    When no server is configured, operates in offline mode
    (returns empty tool lists, errors for tool calls).
    """

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self._config = config or {}
        self._base_url = self._config.get("mcp_url", "")
        self._api_key = self._config.get("mcp_api_key", "")
        self._timeout = int(self._config.get("timeout", 30))
        self._online = bool(self._base_url)

    @property
    def is_online(self) -> bool:
        return self._online

    def discover_tools(self) -> list[MCPTool]:
        """Call MCP server's /tools endpoint to list available tools."""
        if not self._online:
            return []

        try:
            response = self._get("/tools")
            tools_raw = response.get("tools", [])
            if not isinstance(tools_raw, list):
                return []
            return [
                MCPTool.from_dict(t) for t in tools_raw if isinstance(t, dict)
            ]
        except Exception:
            return []

    def call_tool(self, call: MCPToolCall) -> MCPToolResult:
        """Execute a tool via MCP protocol."""
        if not self._online:
            return MCPToolResult(
                tool_id=call.tool_id,
                success=False,
                error="MCP client is offline (no mcp_url configured)",
            )

        import time
        started = time.time()

        try:
            data = self._post(
                "/tools/execute",
                {
                    "tool_id": call.tool_id,
                    "parameters": call.parameters,
                },
                timeout=call.timeout,
            )
            elapsed_ms = int((time.time() - started) * 1000)
            return MCPToolResult(
                tool_id=call.tool_id,
                success=True,
                data=data.get("result", {}),
                execution_time_ms=elapsed_ms,
            )
        except Exception as exc:
            elapsed_ms = int((time.time() - started) * 1000)
            return MCPToolResult(
                tool_id=call.tool_id,
                success=False,
                error=str(exc),
                execution_time_ms=elapsed_ms,
            )

    def health_check(self) -> bool:
        """Check if the MCP server is reachable."""
        if not self._online:
            return False
        try:
            self._get("/health")
            return True
        except Exception:
            return False

    # ── Internal HTTP helpers ──────────────────────────────────────────

    def _get(self, path: str) -> dict[str, Any]:
        url = f"{self._base_url.rstrip('/')}{path}"
        request = Request(url, method="GET")
        return self._do_request(request)

    def _post(
        self, path: str, payload: dict[str, Any], timeout: int | None = None
    ) -> dict[str, Any]:
        url = f"{self._base_url.rstrip('/')}{path}"
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers: dict[str, str] = {
            "Content-Type": "application/json; charset=utf-8",
        }
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        request = Request(url, data=body, headers=headers, method="POST")
        return self._do_request(request, timeout)

    def _do_request(
        self, request: Request, timeout: int | None = None
    ) -> dict[str, Any]:
        try:
            with urlopen(request, timeout=timeout or self._timeout) as response:
                raw = response.read().decode("utf-8")
                data = json.loads(raw)
                if not isinstance(data, dict):
                    raise MCPError("MCP response must be a JSON object")
                return data
        except (URLError, OSError, json.JSONDecodeError) as exc:
            raise MCPError(f"MCP request failed: {exc}") from exc
