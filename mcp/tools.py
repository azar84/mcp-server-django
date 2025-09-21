"""
MCP tools registration and MS Bookings tool implementation
"""

import json
from datetime import datetime
from typing import Dict, Any
from .protocol import protocol_handler


async def ms_bookings_book_online_meeting_tool(arguments: Dict[str, Any], context: Dict[str, Any]) -> str:
    """Book an online meeting using Microsoft Bookings"""
    try:
        # Get the MS Bookings provider from domain registry
        from .domain_registry import domain_registry
        from .domains.bookings.ms_bookings import MSBookOnlineMeetingTool
        
        # Get the provider instance
        provider = domain_registry.domains["bookings"].providers["ms_bookings"]
        
        # Create tool instance with required arguments
        booking_tool = MSBookOnlineMeetingTool(
            name="book_online_meeting",
            provider=provider,
            description="Book an online meeting using Microsoft Bookings",
            input_schema={
                "type": "object",
                "properties": {
                    "startLocal": {"type": "string"},
                    "timeZone": {"type": "string"},
                    "customerName": {"type": "string"},
                    "customerEmail": {"type": "string"}
                },
                "required": ["startLocal", "timeZone", "customerName", "customerEmail"]
            }
        )
        
        # Execute the tool
        result = await booking_tool._execute_with_credentials(arguments, {}, context)
        
        # Return the result as a string
        if isinstance(result, dict):
            import json
            return json.dumps(result, indent=2)
        return str(result)
        
    except Exception as e:
        return f'ERROR: {str(e)}'

async def ms_bookings_get_staff_availability_tool(arguments: Dict[str, Any], context: Dict[str, Any]) -> str:
    """Get staff availability from Microsoft Bookings"""
    try:
        # Import the actual MS Bookings tool implementation
        from .domains.bookings.ms_bookings import MSBookingsProvider, MSGetStaffAvailabilityTool
        
        # Create provider and tool instances
        provider = MSBookingsProvider()
        tool = MSGetStaffAvailabilityTool(
            name="get_staff_availability",
            provider=provider,
            description="Get staff availability from Microsoft Bookings",
            input_schema={}
        )
        
        # Execute the tool
        result = await tool._execute_with_credentials(arguments, {}, context)
        
        # Return as string (MCP protocol expects string response)
        if isinstance(result, str):
            return result
        else:
            return json.dumps(result)
            
    except Exception as e:
        return json.dumps({
            'error': True,
            'message': f'MS Bookings tool error: {str(e)}',
            'status': None,
            'details': None
        })


async def connection_test_tool(arguments: Dict[str, Any], context: Dict[str, Any]) -> str:
    """Test MCP server connection and functionality"""
    tenant_name = context.get('tenant').name if context.get('tenant') else 'Unknown'
    return json.dumps({
        "status": "MCP server connection successful",
        "tenant": tenant_name,
        "message": "This tool confirms the MCP server is working correctly",
        "timestamp": datetime.now().isoformat(),
        "test_passed": True
    }, indent=2)


async def current_time_tool(arguments: Dict[str, Any], context: Dict[str, Any]) -> str:
    """Get current server time"""
    from .domains.general.generaltools import GeneralToolsProvider, CurrentTimeTool
    
    provider = GeneralToolsProvider()
    tool = CurrentTimeTool(
        name="current_time",
        provider=provider,
        description="Get current server time",
        input_schema={}
    )
    
    result = await tool._execute_with_credentials(arguments, {}, context)
    return json.dumps(result) if not isinstance(result, str) else result


async def calculator_tool(arguments: Dict[str, Any], context: Dict[str, Any]) -> str:
    """Perform basic mathematical calculations"""
    from .domains.general.generaltools import GeneralToolsProvider, CalculatorTool
    
    provider = GeneralToolsProvider()
    tool = CalculatorTool(
        name="calculator",
        provider=provider,
        description="Perform basic mathematical calculations",
        input_schema={}
    )
    
    result = await tool._execute_with_credentials(arguments, {}, context)
    return json.dumps(result) if not isinstance(result, str) else result


async def timezone_lookup_tool(arguments: Dict[str, Any], context: Dict[str, Any]) -> str:
    """Get Windows and IANA time zones for a geographic location"""
    from .domains.general.generaltools import GeneralToolsProvider, TimezoneLookupTool
    
    provider = GeneralToolsProvider()
    tool = TimezoneLookupTool(
        name="get_timezone_by_location",
        provider=provider,
        description="Get Windows and IANA time zones for a geographic location",
        input_schema={}
    )
    
    result = await tool._execute_with_credentials(arguments, {}, context)
    return json.dumps(result) if not isinstance(result, str) else result


def register_default_tools():
    """Register tools with the protocol handler"""
    
    # Server status tool - no scopes required
    protocol_handler.register_tool(
        name="general_get_server_status",
        description="Check if the MCP server is working and get basic server information. Use this when user asks 'is the server working', 'test connection', or 'server status'.",
        input_schema={
            "type": "object",
            "properties": {},
            "additionalProperties": False
        },
        handler=connection_test_tool,
        required_scopes=[],
        requires_credentials=False
    )
    
    # MS Bookings tools - domain-based tools
    protocol_handler.register_tool(
        name="bookings_get_staff_availability",
        description="Get staff availability from Microsoft Bookings for a 7-day window",
        input_schema={
            "type": "object",
            "properties": {
                "startLocal": {
                    "type": "string",
                    "description": "Start date/time in local format (YYYY-MM-DDTHH:mm:ss or YYYY-MM-DD)",
                    "examples": ["2025-09-15T09:00:00", "2025-09-15T9:00", "2025-09-15"]
                },
                "timeZone": {
                    "type": "string",
                    "description": "Windows time zone name",
                    "examples": ["Eastern Standard Time", "Pacific Standard Time", "Central Standard Time"]
                },
                "business_id": {
                    "type": "string",
                    "description": "Microsoft Bookings business ID or email (optional, uses tenant default if not provided)"
                },
                "staff_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of staff member GUIDs (optional, uses tenant default if not provided)"
                }
            },
            "required": ["startLocal", "timeZone"]
        },
        handler=ms_bookings_get_staff_availability_tool,
        required_scopes=["booking", "ms_bookings"],
        requires_credentials=True
    )
    
    protocol_handler.register_tool(
        name="bookings_book_online_meeting",
        description="After confirming with the client, use this tool to book the meeting online. Gather the following information and ensure you've found staff availability and never book a meeting outside it. When you call the tool try to collect missing information and once you get it send it to this tool.",
        input_schema={
            "type": "object",
            "properties": {
                "startLocal": {
                    "type": "string",
                    "description": "YYYY-MM-DDTHH:mm[:ss] (local wall time)",
                    "examples": ["2025-09-15T14:30:00", "2025-09-15T14:30", "2025-09-15"]
                },
                "timeZone": {
                    "type": "string",
                    "description": "Windows time zone, e.g. 'Canada Central Standard Time'",
                    "examples": ["Eastern Standard Time", "Pacific Standard Time", "Canada Central Standard Time"]
                },
                "customerName": {
                    "type": "string",
                    "description": "Customer full name"
                },
                "customerEmail": {
                    "type": "string",
                    "description": "Customer email address"
                },
                "customerPhone": {
                    "type": "string",
                    "description": "Customer phone number (optional, will be formatted to E.164)"
                },
                "notes": {
                    "type": "string",
                    "description": "Additional notes for the appointment (optional)"
                },
                "serviceId": {
                    "type": "string",
                    "description": "Service ID (optional, uses tenant default if not provided)"
                },
                "durationMinutes": {
                    "type": "number",
                    "description": "Meeting duration in minutes (optional, uses service default)"
                }
            },
            "required": ["startLocal", "timeZone", "customerName", "customerEmail"]
        },
        handler=ms_bookings_book_online_meeting_tool,
        required_scopes=["booking", "ms_bookings", "write"],
        requires_credentials=True
    )
    
    # Current time tool
    protocol_handler.register_tool(
        name="general_current_time",
        description="Get the current server time",
        input_schema={
            "type": "object",
            "properties": {
                "format": {
                    "type": "string",
                    "enum": ["iso", "timestamp", "human"],
                    "description": "Time format to return"
                }
            }
        },
        handler=current_time_tool,
        required_scopes=["basic"],
        requires_credentials=False
    )
    
    # Calculator tool
    protocol_handler.register_tool(
        name="general_calculator",
        description="Perform basic mathematical calculations",
        input_schema={
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "Mathematical expression to evaluate"
                }
            },
            "required": ["expression"]
        },
        handler=calculator_tool,
        required_scopes=["basic"],
        requires_credentials=False
    )
    
    # Timezone lookup tool
    protocol_handler.register_tool(
        name="general_get_timezone_by_location",
        description="Get Windows and IANA time zones for a geographic location (city, country, etc.)",
        input_schema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Location to lookup (city name, \"City, Country\", etc.)",
                    "examples": ["Saskatoon", "New York", "London, UK", "Tokyo, Japan"]
                }
            },
            "required": ["query"],
            "additionalProperties": False
        },
        handler=timezone_lookup_tool,
        required_scopes=["basic"],
        requires_credentials=False
    )
