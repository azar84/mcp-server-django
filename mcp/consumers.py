"""
WebSocket consumers for MCP protocol communication
"""

import json
import uuid
import asyncio
from channels.generic.websocket import AsyncWebsocketConsumer
from django.utils import timezone
from .protocol import protocol_handler
from .models import MCPSession, MCPToolCall, Tenant, AuthToken
from .auth import mcp_auth_middleware
from channels.db import database_sync_to_async


class MCPConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for MCP protocol messages"""
    
    async def connect(self):
        """Handle WebSocket connection with authentication"""
        # Authenticate the connection
        auth_token, error_message = mcp_auth_middleware.authenticate_websocket(
            self.scope, self.receive, self.send
        )
        
        if not auth_token:
            await self.close(code=4001, reason=error_message)
            return
        
        self.session_id = str(uuid.uuid4())
        self.auth_token = auth_token
        self.tenant = auth_token.tenant
        
        await self.accept()
        
        # Create authenticated session record
        await self.create_session()
        
        print(f"MCP client connected: {self.tenant.name} (Session: {self.session_id})")
    
    async def disconnect(self, close_code):
        """Handle WebSocket disconnection"""
        await self.deactivate_session()
        print(f"MCP client disconnected: {self.session_id}")
    
    async def receive(self, text_data):
        """Handle incoming WebSocket messages with tenant context"""
        try:
            message_data = json.loads(text_data)
            
            # Process MCP message with authentication context
            response = await protocol_handler.handle_message(
                message_data, 
                self.session_id,
                auth_token=self.auth_token,
                tenant=self.tenant
            )
            
            # Log tool calls if applicable
            if message_data.get('method') == 'tools/call':
                await self.log_tool_call(message_data, response)
            
            # Send response
            await self.send(text_data=json.dumps(response))
            
        except json.JSONDecodeError:
            error_response = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {
                    "code": -32700,
                    "message": "Parse error"
                }
            }
            await self.send(text_data=json.dumps(error_response))
        
        except Exception as e:
            error_response = {
                "jsonrpc": "2.0",
                "id": message_data.get('id') if 'message_data' in locals() else None,
                "error": {
                    "code": -32603,
                    "message": f"Internal error: {str(e)}"
                }
            }
            await self.send(text_data=json.dumps(error_response))
    
    @database_sync_to_async
    def create_session(self):
        """Create a new MCP session record with tenant context"""
        MCPSession.objects.create(
            session_id=self.session_id,
            tenant=self.tenant,
            auth_token=self.auth_token,
            client_info={},
            is_active=True
        )
    
    @database_sync_to_async
    def deactivate_session(self):
        """Deactivate the MCP session"""
        try:
            session = MCPSession.objects.get(session_id=self.session_id)
            session.is_active = False
            session.save()
        except MCPSession.DoesNotExist:
            pass
    
    @database_sync_to_async
    def log_tool_call(self, request_data, response_data):
        """Log tool call for analytics"""
        try:
            session = MCPSession.objects.get(session_id=self.session_id)
            tool_name = request_data.get('params', {}).get('name', 'unknown')
            arguments = request_data.get('params', {}).get('arguments', {})
            
            # Extract result or error
            result = None
            error = None
            
            if 'result' in response_data:
                result = response_data['result']
            elif 'error' in response_data:
                error = response_data['error']['message']
            
            MCPToolCall.objects.create(
                session=session,
                tool_name=tool_name,
                arguments=arguments,
                result=result,
                error=error
            )
        except Exception as e:
            print(f"Failed to log tool call: {e}")


class MCPStdioConsumer:
    """STDIO-based consumer for MCP protocol (for non-WebSocket clients)"""
    
    def __init__(self):
        self.session_id = str(uuid.uuid4())
    
    async def handle_message(self, message_data: dict) -> dict:
        """Handle a single MCP message via STDIO"""
        return await protocol_handler.handle_message(message_data, self.session_id)
