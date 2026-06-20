from __future__ import annotations

from typing import Any

from evohunter.mcp.client import MCPClient
from evohunter.mcp.models import MCPError, MCPTool, MCPToolCall, MCPToolResult


class MCPToolRegistry:
    """Registry that manages MCP tool lifecycle.

    Tools can be registered statically (built-in adapters) or
    discovered dynamically from MCP servers.

    If no MCP server is configured, the registry falls back to
    local-only tools and returns errors for unregistered tools.
    """

    def __init__(self) -> None:
        self._tools: dict[str, MCPTool] = {}
        self._clients: dict[str, MCPClient] = {}
        self._default_client: MCPClient | None = None

    # ── Registration ───────────────────────────────────────────────────

    def register_tool(self, tool: MCPTool) -> None:
        """Register a static tool definition."""
        self._tools[tool.tool_id] = tool

    def register_client(
        self, name: str, client: MCPClient
    ) -> None:
        """Register an MCP client for dynamic tool discovery."""
        self._clients[name] = client
        if self._default_client is None:
            self._default_client = client

    def unregister_tool(self, tool_id: str) -> None:
        """Remove a tool from the registry."""
        self._tools.pop(tool_id, None)

    # ── Discovery ──────────────────────────────────────────────────────

    def get_tool(self, tool_id: str) -> MCPTool | None:
        return self._tools.get(tool_id)

    def list_tools(self, provider: str | None = None) -> list[MCPTool]:
        """List all registered tools, optionally filtered by provider."""
        tools = list(self._tools.values())
        if provider:
            tools = [t for t in tools if t.provider == provider]
        return tools

    def discover_from_client(self, client_name: str) -> list[MCPTool]:
        """Fetch tools from a registered MCP client and register them."""
        client = self._clients.get(client_name)
        if client is None:
            raise MCPError(f"no MCP client registered as '{client_name}'")
        tools = client.discover_tools()
        for tool in tools:
            self._tools[tool.tool_id] = tool
        return tools

    def discover_all(self) -> list[MCPTool]:
        """Discover tools from all registered clients."""
        all_tools: list[MCPTool] = []
        for client in self._clients.values():
            try:
                all_tools.extend(client.discover_tools())
            except Exception:
                pass
        for tool in all_tools:
            if tool.tool_id not in self._tools:
                self._tools[tool.tool_id] = tool
        return all_tools

    # ── Execution ──────────────────────────────────────────────────────

    def execute_tool(self, call: MCPToolCall) -> MCPToolResult:
        """Execute a tool by tool_id.

        If the tool is registered and has an associated MCP client,
        calls through the client. Otherwise returns an error.
        """
        tool = self._tools.get(call.tool_id)

        # Look for a client that can handle this
        client: MCPClient | None = None
        if tool and tool.provider in self._clients:
            client = self._clients[tool.provider]
        elif self._default_client is not None:
            client = self._default_client

        if client is not None and client.is_online:
            return client.call_tool(call)

        # Offline fallback: try local execution for registered tools
        if tool is not None:
            return MCPToolResult(
                tool_id=call.tool_id,
                success=False,
                error=f"tool '{call.tool_id}' requires an MCP server (provider={tool.provider})",
            )

        return MCPToolResult(
            tool_id=call.tool_id,
            success=False,
            error=f"tool '{call.tool_id}' is not registered",
        )

    def execute_tool_by_name(
        self,
        provider: str,
        action: str,
        params: dict[str, Any] | None = None,
    ) -> MCPToolResult:
        """Convenience: find tool by provider + action, then execute.

        Example:
            execute_tool_by_name("email", "send", {"to": "...", "body": "..."})
        """
        for tool in self._tools.values():
            if tool.provider == provider and action in tool.name.lower():
                return self.execute_tool(
                    MCPToolCall(
                        tool_id=tool.tool_id,
                        parameters=params or {},
                    )
                )
        return MCPToolResult(
            tool_id=f"{provider}_{action}",
            success=False,
            error=f"no tool found for provider='{provider}' action='{action}'",
        )
