import pytest

from evohunter.mcp import MCPToolRegistry
from evohunter.mcp.client import MCPClient
from evohunter.mcp.models import MCPError, MCPTool, MCPToolCall
from evohunter.mcp.tools import (
    register_calendar_tools,
    register_email_tools,
    register_im_tools,
)


def test_mcp_tool_model():
    tool = MCPTool(
        tool_id="test_tool",
        name="Test Tool",
        description="A test tool",
        provider="email",
        input_schema={
            "type": "object",
            "properties": {"to": {"type": "string"}},
            "required": ["to"],
        },
    )
    assert tool.tool_id == "test_tool"
    assert tool.provider == "email"

    d = tool.to_dict()
    assert d["tool_id"] == "test_tool"
    assert "input_schema" in d

    restored = MCPTool.from_dict(d)
    assert restored.tool_id == tool.tool_id
    assert restored.input_schema == tool.input_schema


def test_mcp_tool_call_model():
    call = MCPToolCall(
        tool_id="email_send",
        parameters={"to": "alice@test.com", "subject": "Test"},
        timeout=60,
    )
    d = call.to_dict()
    restored = MCPToolCall.from_dict(d)
    assert restored.tool_id == "email_send"
    assert restored.parameters["to"] == "alice@test.com"
    assert restored.timeout == 60


def test_mcp_client_offline_mode():
    """Client without a server URL operates in offline mode."""
    client = MCPClient()
    assert not client.is_online

    tools = client.discover_tools()
    assert tools == []

    result = client.call_tool(
        MCPToolCall(tool_id="any", parameters={})
    )
    assert not result.success
    assert "offline" in result.error.lower()


def test_mcp_tool_registry_register_and_list():
    registry = MCPToolRegistry()
    register_email_tools(registry)
    register_im_tools(registry)
    register_calendar_tools(registry)

    all_tools = registry.list_tools()
    assert len(all_tools) == 7

    email_tools = registry.list_tools(provider="email")
    assert len(email_tools) == 2
    assert {t.tool_id for t in email_tools} == {"email_send", "email_receive"}

    calendar_tools = registry.list_tools(provider="calendar")
    assert len(calendar_tools) == 3


def test_mcp_tool_registry_get_tool():
    registry = MCPToolRegistry()
    register_email_tools(registry)

    tool = registry.get_tool("email_send")
    assert tool is not None
    assert tool.name == "Send Email"

    assert registry.get_tool("nonexistent") is None


def test_mcp_tool_registry_unregister():
    registry = MCPToolRegistry()
    register_email_tools(registry)
    assert len(registry.list_tools()) == 2

    registry.unregister_tool("email_send")
    assert len(registry.list_tools()) == 1
    assert registry.get_tool("email_send") is None


def test_mcp_tool_registry_execute_offline():
    """Execute without MCP server returns error."""
    registry = MCPToolRegistry()
    register_email_tools(registry)

    result = registry.execute_tool(
        MCPToolCall(tool_id="email_send", parameters={"to": "test@test.com"})
    )
    assert not result.success
    assert "requires an mcp server" in result.error.lower()


def test_mcp_tool_registry_execute_unknown_tool():
    registry = MCPToolRegistry()
    result = registry.execute_tool(
        MCPToolCall(tool_id="nonexistent", parameters={})
    )
    assert not result.success
    assert "not registered" in result.error.lower()


def test_mcp_tool_registry_execute_by_name():
    registry = MCPToolRegistry()
    register_email_tools(registry)

    result = registry.execute_tool_by_name(
        provider="email", action="send", params={"to": "test@test.com"}
    )
    # Offline, so fails with "requires an MCP server"
    assert not result.success


def test_mcp_tool_input_schema():
    """Verify that all registered tools have valid input schemas."""
    registry = MCPToolRegistry()
    register_email_tools(registry)
    register_im_tools(registry)
    register_calendar_tools(registry)

    for tool in registry.list_tools():
        assert "type" in tool.input_schema
        assert tool.input_schema["type"] == "object"
        assert "properties" in tool.input_schema
