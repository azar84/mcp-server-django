"""
MCP Protocol Implementation
Handles the Model Context Protocol messages and responses
"""

import json
import uuid
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from datetime import datetime


class MCPMessage(BaseModel):
    """Base MCP message structure"""
    jsonrpc: str = "2.0"
    id: Optional[str] = None
    method: Optional[str] = None
    params: Optional[Dict[str, Any]] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[Dict[str, Any]] = None


class MCPError(BaseModel):
    """MCP error structure"""
    code: int
    message: str
    data: Optional[Dict[str, Any]] = None


class MCPTool(BaseModel):
    """MCP tool definition"""
    name: str
    description: str
    inputSchema: Dict[str, Any]


class MCPClientInfo(BaseModel):
    """Client information for MCP initialization"""
    name: str
    version: str


class MCPServerInfo(BaseModel):
    """Server information for MCP initialization"""
    name: str = "Django MCP Server"
    version: str = "1.0.0"


class MCPProtocolHandler:
    """Handles MCP protocol messages and routing"""
    
    def __init__(self):
        self.tools = {}
        self.sessions = {}
        
    def register_tool(self, name: str, description: str, input_schema: Dict[str, Any], 
                     handler, required_scopes: List[str] = None, requires_credentials: bool = False):
        """Register a tool with the MCP server"""
        self.tools[name] = {
            'description': description,
            'inputSchema': input_schema,
            'handler': handler,
            'required_scopes': required_scopes or [],
            'requires_credentials': requires_credentials
        }
    
    async def handle_message(self, message_data: Dict[str, Any], session_id: str, 
                           auth_token=None, tenant=None) -> Dict[str, Any]:
        """Handle incoming MCP message with authentication"""
        try:
            message = MCPMessage(**message_data)
            
            if message.method == "initialize":
                return await self._handle_initialize(message, session_id, auth_token, tenant)
            elif message.method == "tools/list":
                return await self._handle_list_tools(message, auth_token)
            elif message.method == "tools/call":
                return await self._handle_call_tool(message, session_id, auth_token, tenant)
            else:
                return self._create_error_response(
                    message.id, -32601, f"Method not found: {message.method}"
                )
                
        except Exception as e:
            return self._create_error_response(
                message_data.get('id'), -32603, f"Internal error: {str(e)}"
            )
    
    async def _handle_initialize(self, message: MCPMessage, session_id: str, 
                               auth_token=None, tenant=None) -> Dict[str, Any]:
        """Handle MCP initialize request"""
        client_info = message.params.get('clientInfo', {}) if message.params else {}
        
        # Store session info with tenant context
        self.sessions[session_id] = {
            'client_info': client_info,
            'initialized_at': datetime.now().isoformat(),
            'tenant': tenant.tenant_id if tenant else None,
            'scopes': auth_token.scopes if auth_token else []
        }
        
        server_info = MCPServerInfo()
        
        return {
            "jsonrpc": "2.0",
            "id": message.id,
            "result": {
                "protocolVersion": "2024-11-05",
                "serverInfo": server_info.dict(),
                "capabilities": {
                    "tools": {}
                }
            }
        }
    
    async def _handle_list_tools(self, message: MCPMessage, auth_token=None, tenant=None) -> Dict[str, Any]:
        """Handle tools/list request with scope filtering"""
        from .auth import mcp_authenticator
        from .domain_registry import domain_registry
        
        tools = []
        
        # Get tenant scopes
        tenant_scopes = auth_token.scopes if auth_token else []
        
        # Get available credentials for domain-based tools
        available_credentials = []
        if tenant:
            try:
                if tenant.ms_bookings_credential and tenant.ms_bookings_credential.is_active:
                    available_credentials.extend(['ms_bookings_azure_tenant_id', 'ms_bookings_client_id', 'ms_bookings_client_secret'])
            except:
                pass
            
            try:
                if tenant.stripe_credential and tenant.stripe_credential.is_active:
                    available_credentials.extend(['stripe_secret_key', 'stripe_publishable_key'])
            except:
                pass
        
        # Get tools from domain registry (includes the new timezone tool)
        domain_tools = domain_registry.get_available_tools(tenant_scopes, available_credentials)
        for tool_data in domain_tools:
            tools.append({
                "name": tool_data['name'],
                "description": tool_data['description'],
                "inputSchema": tool_data['inputSchema']
            })
        
        # Add legacy tools from protocol handler for backward compatibility
        for name, tool_data in self.tools.items():
            # Skip if this tool is already included from domains
            if any(t['name'] == name for t in tools):
                continue
                
            # Check if user has required scopes for this tool
            if auth_token:
                required_scopes = tool_data.get('required_scopes', [])
                if not mcp_authenticator.check_scope_permission(auth_token, required_scopes):
                    continue  # Skip tools user doesn't have access to
            
            tools.append({
                "name": name,
                "description": tool_data['description'],
                "inputSchema": tool_data['inputSchema']
            })
        
        return {
            "jsonrpc": "2.0",
            "id": message.id,
            "result": {
                "tools": tools
            }
        }
    
    async def _handle_call_tool(self, message: MCPMessage, session_id: str, 
                              auth_token=None, tenant=None) -> Dict[str, Any]:
        """Handle tools/call request with authentication and tenant context"""
        if not message.params:
            return self._create_error_response(
                message.id, -32602, "Invalid params"
            )
        
        tool_name = message.params.get('name')
        arguments = message.params.get('arguments', {})
        
        if tool_name not in self.tools:
            return self._create_error_response(
                message.id, -32602, f"Tool not found: {tool_name}"
            )
        
        # Check scope permissions
        if auth_token:
            from .auth import mcp_authenticator
            required_scopes = self.tools[tool_name].get('required_scopes', [])
            if not mcp_authenticator.check_scope_permission(auth_token, required_scopes):
                return self._create_error_response(
                    message.id, -32403, f"Insufficient permissions for tool: {tool_name}"
                )
        
        try:
            tool_handler = self.tools[tool_name]['handler']
            
            # Pass tenant context and credentials to tool handler
            tool_context = {
                'session_id': session_id,
                'tenant': tenant,
                'auth_token': auth_token
            }
            
            # Get tenant-specific credentials if tool requires them
            if self.tools[tool_name].get('requires_credentials') and tenant:
                from .auth import mcp_authenticator
                credentials = mcp_authenticator.get_tenant_credentials(tenant, tool_name)
                tool_context['credentials'] = credentials
            
            result = await tool_handler(arguments, tool_context)
            
            return {
                "jsonrpc": "2.0",
                "id": message.id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": str(result)
                        }
                    ]
                }
            }
            
        except Exception as e:
            return self._create_error_response(
                message.id, -32603, f"Tool execution error: {str(e)}"
            )
    
    def _create_error_response(self, message_id: Optional[str], code: int, message: str) -> Dict[str, Any]:
        """Create an error response"""
        return {
            "jsonrpc": "2.0",
            "id": message_id,
            "error": {
                "code": code,
                "message": message
            }
        }


# Global protocol handler instance
protocol_handler = MCPProtocolHandler()
