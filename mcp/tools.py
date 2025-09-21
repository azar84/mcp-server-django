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
    """
    Legacy tool registration - now deprecated
    Tools are now managed through the domain-based system in mcp/domains/
    This function is kept for backward compatibility but should be empty
    """
    # All tools are now registered through the domain-based system
    # See mcp/domains/ for tool implementations
    # See mcp/domain_registry.py for domain registration
    pass
