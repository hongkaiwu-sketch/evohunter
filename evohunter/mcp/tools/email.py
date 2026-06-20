from evohunter.mcp.client import MCPClient
from evohunter.mcp.models import MCPTool
from evohunter.mcp.tool_registry import MCPToolRegistry


def register_email_tools(
    registry: MCPToolRegistry, client: MCPClient | None = None
) -> None:
    """Register email tool definitions in the registry.

    Tools:
    - email_send: Send an email
    - email_receive: Check incoming emails
    """

    registry.register_tool(
        MCPTool(
            tool_id="email_send",
            name="Send Email",
            description="Send an email via configured SMTP/email MCP server",
            provider="email",
            input_schema={
                "type": "object",
                "properties": {
                    "to": {
                        "type": "string",
                        "description": "Recipient email address",
                    },
                    "subject": {
                        "type": "string",
                        "description": "Email subject line",
                    },
                    "body": {
                        "type": "string",
                        "description": "Email body (plain text or HTML)",
                    },
                    "cc": {
                        "type": "string",
                        "description": "CC recipients (comma-separated)",
                    },
                },
                "required": ["to", "subject", "body"],
            },
        )
    )

    registry.register_tool(
        MCPTool(
            tool_id="email_receive",
            name="Check Emails",
            description="Check incoming emails from a mailbox",
            provider="email",
            input_schema={
                "type": "object",
                "properties": {
                    "folder": {
                        "type": "string",
                        "description": "Mail folder name (default: INBOX)",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max emails to fetch",
                    },
                    "unread_only": {
                        "type": "boolean",
                        "description": "Only fetch unread emails",
                    },
                },
            },
        )
    )

    if client is not None:
        registry.register_client("email", client)
