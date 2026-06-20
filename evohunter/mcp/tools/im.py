from evohunter.mcp.client import MCPClient
from evohunter.mcp.models import MCPTool
from evohunter.mcp.tool_registry import MCPToolRegistry


def register_im_tools(
    registry: MCPToolRegistry, client: MCPClient | None = None
) -> None:
    """Register IM tool definitions in the registry.

    Tools:
    - im_send: Send an instant message
    - im_receive: Poll for incoming messages
    """

    registry.register_tool(
        MCPTool(
            tool_id="im_send",
            name="Send IM Message",
            description="Send an instant message via configured IM platform (WeChat Work, Feishu, Slack, etc.)",
            provider="im",
            input_schema={
                "type": "object",
                "properties": {
                    "platform": {
                        "type": "string",
                        "description": "IM platform: wechat_work | feishu | slack",
                    },
                    "to": {
                        "type": "string",
                        "description": "Recipient ID or channel",
                    },
                    "body": {
                        "type": "string",
                        "description": "Message text",
                    },
                    "message_type": {
                        "type": "string",
                        "description": "text | markdown | rich_text",
                    },
                },
                "required": ["platform", "to", "body"],
            },
        )
    )

    registry.register_tool(
        MCPTool(
            tool_id="im_receive",
            name="Check IM Messages",
            description="Poll for incoming IM messages",
            provider="im",
            input_schema={
                "type": "object",
                "properties": {
                    "platform": {
                        "type": "string",
                        "description": "IM platform",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max messages to fetch",
                    },
                    "since": {
                        "type": "string",
                        "description": "ISO timestamp, messages after this time",
                    },
                },
                "required": ["platform"],
            },
        )
    )

    if client is not None:
        registry.register_client("im", client)
