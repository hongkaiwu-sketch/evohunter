"""MCP tool adapters.

Each module provides a ``register_*_tools(registry, client)`` function
that registers tool definitions and optionally a client with the registry.
"""

from evohunter.mcp.tools.calendar import register_calendar_tools
from evohunter.mcp.tools.email import register_email_tools
from evohunter.mcp.tools.im import register_im_tools

__all__ = [
    "register_calendar_tools",
    "register_email_tools",
    "register_im_tools",
]
