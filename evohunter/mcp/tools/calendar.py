from evohunter.mcp.client import MCPClient
from evohunter.mcp.models import MCPTool
from evohunter.mcp.tool_registry import MCPToolRegistry


def register_calendar_tools(
    registry: MCPToolRegistry, client: MCPClient | None = None
) -> None:
    """Register calendar tool definitions in the registry.

    Tools:
    - calendar_create_event: Create a calendar event (for interview scheduling)
    - calendar_check_availability: Check free/busy slots
    - calendar_list_events: List upcoming events
    """

    registry.register_tool(
        MCPTool(
            tool_id="calendar_create_event",
            name="Create Calendar Event",
            description="Schedule an interview or meeting in the calendar",
            provider="calendar",
            input_schema={
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Event title (e.g., 'Interview: AI Engineer - Alice')",
                    },
                    "start_time": {
                        "type": "string",
                        "description": "Start time in ISO 8601 format",
                    },
                    "end_time": {
                        "type": "string",
                        "description": "End time in ISO 8601 format",
                    },
                    "attendees": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of attendee email addresses",
                    },
                    "location": {
                        "type": "string",
                        "description": "Meeting location or video call link",
                    },
                    "description": {
                        "type": "string",
                        "description": "Event description/agenda",
                    },
                    "send_invites": {
                        "type": "boolean",
                        "description": "Whether to send calendar invites to attendees",
                    },
                },
                "required": ["title", "start_time", "end_time"],
            },
        )
    )

    registry.register_tool(
        MCPTool(
            tool_id="calendar_check_availability",
            name="Check Calendar Availability",
            description="Check free/busy time slots for scheduling interviews",
            provider="calendar",
            input_schema={
                "type": "object",
                "properties": {
                    "start_date": {
                        "type": "string",
                        "description": "Start of date range (ISO date)",
                    },
                    "end_date": {
                        "type": "string",
                        "description": "End of date range (ISO date)",
                    },
                    "duration_minutes": {
                        "type": "integer",
                        "description": "Required meeting duration in minutes",
                    },
                    "working_hours_only": {
                        "type": "boolean",
                        "description": "Only show working hours (9-18)",
                    },
                    "attendees": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Check availability for these attendees",
                    },
                },
                "required": ["start_date", "end_date"],
            },
        )
    )

    registry.register_tool(
        MCPTool(
            tool_id="calendar_list_events",
            name="List Calendar Events",
            description="List upcoming calendar events",
            provider="calendar",
            input_schema={
                "type": "object",
                "properties": {
                    "start_date": {
                        "type": "string",
                        "description": "Start of date range",
                    },
                    "end_date": {
                        "type": "string",
                        "description": "End of date range",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max events to return",
                    },
                },
            },
        )
    )

    if client is not None:
        registry.register_client("calendar", client)
