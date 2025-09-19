"""
MCP tools registration and MS Bookings tool implementation
"""

import json
from datetime import datetime
from typing import Dict, Any
from .protocol import protocol_handler


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
    
    # MS Bookings tool - domain-based tool
    protocol_handler.register_tool(
        name="bookings.get_staff_availability",
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
