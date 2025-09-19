"""
MCP Streamable HTTP Transport Implementation
Compliant with MCP specification for OpenAI Realtime integration
"""

import json
import asyncio
from django.http import StreamingHttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views import View
from django.utils import timezone
from .auth import mcp_auth_middleware
from .protocol import protocol_handler
from .models import MCPSession, MCPToolCall
from channels.db import database_sync_to_async


@method_decorator(csrf_exempt, name='dispatch')
class MCPStreamableHTTPView(View):
    """
    MCP Streamable HTTP transport endpoint
    Implements the MCP specification for OpenAI Realtime integration
    """
    
    def post(self, request):
        """Handle MCP Streamable HTTP requests"""
        try:
            # Authenticate the request
            auth_token, error_message = mcp_auth_middleware.authenticate_http(request)
            if not auth_token:
                return JsonResponse({
                    'jsonrpc': '2.0',
                    'id': None,
                    'error': {
                        'code': -32001,
                        'message': f'Authentication failed: {error_message}'
                    }
                }, status=401)
            
            tenant = auth_token.tenant
            
            # Parse request body
            try:
                if request.content_type == 'application/json':
                    body_str = request.body.decode('utf-8')
                    if not body_str.strip():
                        return JsonResponse({
                            'jsonrpc': '2.0',
                            'id': None,
                            'error': {
                                'code': -32700,
                                'message': 'Parse error: Empty request body'
                            }
                        }, status=400)
                    message_data = json.loads(body_str)
                else:
                    return JsonResponse({
                        'jsonrpc': '2.0',
                        'id': None,
                        'error': {
                            'code': -32700,
                            'message': f'Content-Type must be application/json, got: {request.content_type}'
                        }
                    }, status=400)
            except json.JSONDecodeError as e:
                return JsonResponse({
                    'jsonrpc': '2.0',
                    'id': None,
                    'error': {
                        'code': -32700,
                        'message': f'Parse error: Invalid JSON - {str(e)}'
                    }
                }, status=400)
            
            # Handle different request types
            if isinstance(message_data, list):
                # Batch request - not supported in sync mode for now
                return JsonResponse({
                    'jsonrpc': '2.0',
                    'id': None,
                    'error': {
                        'code': -32601,
                        'message': 'Batch requests not supported in HTTP mode'
                    }
                }, status=400)
            else:
                # Single request
                return self._handle_single_request_sync(message_data, auth_token, tenant, request)
                
        except Exception as e:
            return JsonResponse({
                'jsonrpc': '2.0',
                'id': None,
                'error': {
                    'code': -32603,
                    'message': f'Internal error: {str(e)}'
                }
            }, status=500)
    
    def _handle_single_request_sync(self, message_data, auth_token, tenant, request):
        """Handle a single MCP request synchronously"""
        # For now, handle basic methods synchronously
        method = message_data.get('method')
        message_id = message_data.get('id')
        
        if method == 'tools/list':
            # Get available tools for this tenant
            from .domain_registry import domain_registry
            
            # Get tenant's available credentials
            available_credentials = []
            
            # Check which credential types are available for this tenant
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
            
            # Get tools from legacy protocol handler
            from .protocol import protocol_handler
            tools = []
            
            for tool_name, tool_data in protocol_handler.tools.items():
                # Check if tenant has required scopes
                required_scopes = tool_data.get('required_scopes', [])
                if not set(required_scopes).issubset(set(auth_token.scopes)):
                    continue
                
                tools.append({
                    'name': tool_name,
                    'description': tool_data['description'],
                    'inputSchema': tool_data['inputSchema']
                })
            
            return JsonResponse({
                'jsonrpc': '2.0',
                'id': message_id,
                'result': {
                    'tools': tools
                }
            })
        
        elif method == 'initialize':
            return JsonResponse({
                'jsonrpc': '2.0',
                'id': message_id,
                'result': {
                    'protocolVersion': '2024-11-05',
                    'serverInfo': {
                        'name': 'Django MCP Server',
                        'version': '2.0.0'
                    },
                    'capabilities': {
                        'tools': {},
                        'resources': {}
                    }
                }
            })
        
        else:
            return JsonResponse({
                'jsonrpc': '2.0',
                'id': message_id,
                'error': {
                    'code': -32601,
                    'message': f'Method not implemented in HTTP mode: {method}'
                }
            }, status=400)
    
    async def _handle_batch_request(self, messages, auth_token, tenant, request):
        """Handle batch MCP requests"""
        responses = []
        
        # Generate session ID for this batch
        import uuid
        session_id = str(uuid.uuid4())
        
        # Create temporary session
        await self._create_temp_session(session_id, tenant, auth_token)
        
        try:
            for message_data in messages:
                response = await protocol_handler.handle_message(
                    message_data,
                    session_id,
                    auth_token=auth_token,
                    tenant=tenant
                )
                responses.append(response)
                
                # Log tool calls if applicable
                if message_data.get('method') == 'tools/call':
                    await self._log_tool_call(message_data, response, session_id)
            
            return JsonResponse(responses, safe=False)
            
        finally:
            # Clean up temporary session
            await self._cleanup_temp_session(session_id)
    
    @database_sync_to_async
    def _create_temp_session(self, session_id, tenant, auth_token):
        """Create temporary session for HTTP request"""
        MCPSession.objects.create(
            session_id=session_id,
            tenant=tenant,
            auth_token=auth_token,
            client_info={'transport': 'streamable_http'},
            is_active=True
        )
    
    @database_sync_to_async
    def _cleanup_temp_session(self, session_id):
        """Clean up temporary session"""
        try:
            session = MCPSession.objects.get(session_id=session_id)
            session.is_active = False
            session.save()
        except MCPSession.DoesNotExist:
            pass
    
    @database_sync_to_async
    def _log_tool_call(self, request_data, response_data, session_id):
        """Log tool call for analytics"""
        try:
            session = MCPSession.objects.get(session_id=session_id)
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


@method_decorator(csrf_exempt, name='dispatch')
class MCPCapabilitiesView(View):
    """
    MCP server capabilities endpoint
    Returns server information and capabilities for OpenAI integration
    """
    
    def get(self, request):
        """Return MCP server capabilities"""
        return JsonResponse({
            'jsonrpc': '2.0',
            'result': {
                'protocolVersion': '2024-11-05',
                'serverInfo': {
                    'name': 'Django MCP Server',
                    'version': '2.0.0'
                },
                'capabilities': {
                    'tools': {},
                    'resources': {
                        'subscribe': False,
                        'listChanged': False
                    }
                }
            }
        })


@method_decorator(csrf_exempt, name='dispatch') 
class MCPToolsListView(View):
    """
    MCP tools list endpoint for OpenAI integration
    Returns available tools filtered by tenant scopes
    """
    
    def get(self, request):
        """Return available tools for authenticated tenant"""
        try:
            # Authenticate the request
            auth_token, error_message = mcp_auth_middleware.authenticate_http(request)
            if not auth_token:
                return JsonResponse({
                    'jsonrpc': '2.0',
                    'id': None,
                    'error': {
                        'code': -32001,
                        'message': f'Authentication failed: {error_message}'
                    }
                }, status=401)
            
            # Get available tools for this tenant
            from .domain_registry import domain_registry
            
            # Get tenant's available credentials
            available_credentials = []
            tenant = auth_token.tenant
            
            # Check which credential types are available for this tenant
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
            
            # Get tools available to this tenant
            available_tools = domain_registry.get_available_tools(
                auth_token.scopes,
                available_credentials
            )
            
            return JsonResponse({
                'jsonrpc': '2.0',
                'id': request.GET.get('id', '1'),
                'result': {
                    'tools': available_tools
                }
            })
            
        except Exception as e:
            return JsonResponse({
                'jsonrpc': '2.0',
                'id': request.GET.get('id'),
                'error': {
                    'code': -32603,
                    'message': f'Internal error: {str(e)}'
                }
            }, status=500)
