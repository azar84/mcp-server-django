"""
MCP Streamable HTTP Transport Implementation
Compliant with MCP specification for OpenAI Realtime integration
"""

import json
import asyncio
import jwt
import logging
from django.http import StreamingHttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views import View
from django.utils import timezone
from .auth import mcp_auth_middleware
from .protocol import protocol_handler
from .models import MCPSession, MCPToolCall, AuthToken
from channels.db import database_sync_to_async

logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name='dispatch')
class MCPStreamableHTTPView(View):
    """
    MCP Streamable HTTP transport endpoint
    Implements the MCP specification for OpenAI Realtime integration
    """
    
    def post(self, request):
        """Handle MCP Streaming HTTP requests"""
        try:
            # Authenticate the request using the same logic as /api/mcp/
            auth_header = request.headers.get('Authorization', '')
            if not auth_header.startswith('Bearer '):
                return JsonResponse({
                    'jsonrpc': '2.0',
                    'id': None,
                    'error': {
                        'code': -32001,
                        'message': 'Missing or invalid Authorization header. Expected "Bearer <token>"'
                    }
                }, status=401)
            
            # Extract token (remove "Bearer " prefix)
            bearer_token = auth_header[7:]
            
            # Get tenant from token (same logic as OpenAI endpoint)
            auth_token = self._extract_tenant_from_token(bearer_token)
            if not auth_token:
                return JsonResponse({
                    'jsonrpc': '2.0',
                    'id': None,
                    'error': {
                        'code': -32001,
                        'message': 'Invalid or expired token'
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
            
            # Handle different request types with streaming
            if isinstance(message_data, list):
                # Batch request - stream each response
                return self._handle_batch_request_stream(message_data, auth_token, tenant, request)
            else:
                # Single request - stream the response
                return self._handle_single_request_stream(message_data, auth_token, tenant, request)
                
        except Exception as e:
            return JsonResponse({
                'jsonrpc': '2.0',
                'id': None,
                'error': {
                    'code': -32603,
                    'message': f'Internal error: {str(e)}'
                }
            }, status=500)
    
    def _extract_tenant_from_token(self, bearer_token):
        """
        Extract tenant information from Bearer token
        Same logic as OpenAI MCP transport for consistency
        """
        try:
            # Try to decode as JWT first (if using JWT tokens)
            try:
                # For JWT tokens, decode and extract tenant_id and token_secret
                decoded = jwt.decode(bearer_token, options={"verify_signature": False})
                tenant_id = decoded.get('tenant_id')
                token_secret = decoded.get('token_secret')
                
                if tenant_id and token_secret:
                    # Look up by both tenant_id and token_secret for uniqueness
                    return AuthToken.objects.select_related('tenant').get(
                        tenant__tenant_id=tenant_id,
                        token=token_secret,
                        is_active=True
                    )
            except (jwt.InvalidTokenError, jwt.DecodeError):
                pass
            
            # Fallback to direct token lookup (for legacy tokens)
            return AuthToken.objects.select_related('tenant').filter(
                token=bearer_token,
                is_active=True
            ).first()  # Use first() to avoid MultipleObjectsReturned
            
        except AuthToken.DoesNotExist:
            return None
        except AuthToken.MultipleObjectsReturned:
            # If multiple tokens exist, return None for security
            logger.warning(f"Multiple tokens found for bearer token, rejecting for security")
            return None
    
    def _handle_single_request_stream(self, message_data, auth_token, tenant, request):
        """Handle a single MCP request with streaming response"""
        def stream_response():
            try:
                # Process the request and yield the response
                response = self._process_single_request(message_data, auth_token, tenant, request)
                yield json.dumps(response) + '\n'
            except Exception as e:
                error_response = {
                    'jsonrpc': '2.0',
                    'id': message_data.get('id'),
                    'error': {
                        'code': -32603,
                        'message': f'Internal error: {str(e)}'
                    }
                }
                yield json.dumps(error_response) + '\n'
        
        return StreamingHttpResponse(
            stream_response(),
            content_type='application/json'
        )
    
    def _handle_batch_request_stream(self, batch_data, auth_token, tenant, request):
        """Handle batch MCP requests with streaming responses"""
        def stream_batch_responses():
            yield '[\n'  # Start JSON array
            for i, message_data in enumerate(batch_data):
                try:
                    response = self._process_single_request(message_data, auth_token, tenant, request)
                    if i > 0:
                        yield ',\n'  # Add comma between responses
                    yield json.dumps(response)
                except Exception as e:
                    error_response = {
                        'jsonrpc': '2.0',
                        'id': message_data.get('id'),
                        'error': {
                            'code': -32603,
                            'message': f'Internal error: {str(e)}'
                        }
                    }
                    if i > 0:
                        yield ',\n'
                    yield json.dumps(error_response)
            yield '\n]'  # End JSON array
        
        return StreamingHttpResponse(
            stream_batch_responses(),
            content_type='application/json'
        )
    
    def _handle_resources_list(self, message_id, auth_token, tenant):
        """Handle resources/list method and return response data"""
        if not tenant:
            return {
                'jsonrpc': '2.0',
                'id': message_id,
                'error': {
                    'code': -32403,
                    'message': 'Authentication required for resource access'
                }
            }
        
        try:
            import asyncio
            from .resources.onedrive import onedrive_resource
            
            # Get tenant's resources synchronously (direct method call)  
            resources = onedrive_resource.list_resources(tenant)
            
            return {
                'jsonrpc': '2.0',
                'id': message_id,
                'result': {
                    'resources': resources
                }
            }
            
        except Exception as e:
            return {
                'jsonrpc': '2.0',
                'id': message_id,
                'error': {
                    'code': -32603,
                    'message': f'Error listing resources: {str(e)}'
                }
            }
    
    def _handle_resources_read(self, message_id, params, auth_token, tenant):
        """Handle resources/read method and return response data"""
        if not tenant:
            return {
                'jsonrpc': '2.0',
                'id': message_id,
                'error': {
                    'code': -32403,
                    'message': 'Authentication required for resource access'
                }
            }
        
        if not params or 'uri' not in params:
            return {
                'jsonrpc': '2.0',
                'id': message_id,
                'error': {
                    'code': -32602,
                    'message': 'Missing uri parameter'
                }
            }
        
        resource_uri = params['uri']
        
        try:
            import asyncio
            from .resources.onedrive import onedrive_resource
            from .resources.knowledge_base import kb_resource
            
            # Try OneDrive/tenant resources first (now synchronous method)  
            if onedrive_resource.can_handle(resource_uri):
                resource_data = onedrive_resource.resolve_resource(resource_uri, tenant, auth_token)
            else:
                # Fallback to knowledge base resources (global)
                resource_data = kb_resource.resolve_resource(resource_uri)
            
            if resource_data is None:
                return {
                    'jsonrpc': '2.0',
                    'id': message_id,
                    'error': {
                        'code': -32602,
                        'message': f'Resource not found: {resource_uri}'
                    }
                }
            
            # Handle error responses from resource handlers
            if 'error' in resource_data:
                return {
                    'jsonrpc': '2.0',
                    'id': message_id,
                    'error': {
                        'code': -32602,
                        'message': resource_data['error']
                    }
                }
            
            return {
                'jsonrpc': '2.0',
                'id': message_id,
                'result': {
                    'contents': [
                        {
                            'uri': resource_data.get('uri', resource_uri),
                            'mimeType': resource_data.get('mime_type', 'text/plain'),
                            'text': resource_data.get('content', '')
                        }
                    ]
                }
            }
            
        except Exception as e:
            return {
                'jsonrpc': '2.0',
                'id': message_id,
                'error': {
                    'code': -32603,
                    'message': f'Error reading resource: {str(e)}'
                }
            }
    
    def _process_single_request(self, message_data, auth_token, tenant, request):
        """Process a single MCP request and return the response data"""
        method = message_data.get('method')
        message_id = message_data.get('id')
        
        if method == 'tools/list':
            return self._handle_tools_list(message_id, auth_token, tenant)
        elif method == 'initialize':
            return self._handle_initialize(message_id)
        elif method == 'tools/call':
            params = message_data.get('params', {})
            return self._handle_tools_call(message_id, params, auth_token, tenant)
        elif method == 'resources/list':
            return self._handle_resources_list(message_id, auth_token, tenant)
        elif method == 'resources/read':
            params = message_data.get('params', {})
            return self._handle_resources_read(message_id, params, auth_token, tenant)
        else:
            return {
                'jsonrpc': '2.0',
                'id': message_id,
                'error': {
                    'code': -32601,
                    'message': f'Method not found: {method}'
                }
            }
    
    def _handle_tools_list(self, message_id, auth_token, tenant):
        """Handle tools/list method and return response data"""
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
        
        return {
            'jsonrpc': '2.0',
            'id': message_id,
            'result': {
                'tools': tools
            }
        }
    
    def _handle_initialize(self, message_id):
        """Handle initialize method and return response data"""
        return {
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
        }
    
    def _handle_tools_call(self, message_id, params, auth_token, tenant):
        """Handle tools/call method and return response data"""
        tool_name = params.get('name')
        arguments = params.get('arguments', {})
        
        if not tool_name:
            return {
                'jsonrpc': '2.0',
                'id': message_id,
                'error': {
                    'code': -32602,
                    'message': 'Missing tool name in params'
                }
            }
        
        # Check if tool exists and tenant has access
        from .protocol import protocol_handler
        if tool_name not in protocol_handler.tools:
            return {
                'jsonrpc': '2.0',
                'id': message_id,
                'error': {
                    'code': -32601,
                    'message': f'Tool not found: {tool_name}'
                }
            }
        
        tool_data = protocol_handler.tools[tool_name]
        required_scopes = tool_data.get('required_scopes', [])
        
        if not set(required_scopes).issubset(set(auth_token.scopes)):
            return {
                'jsonrpc': '2.0',
                'id': message_id,
                'error': {
                    'code': -32001,
                    'message': f'Insufficient scopes for tool {tool_name}'
                }
            }
        
        # Execute tool
        try:
            # Create context for tool execution
            context = {
                'tenant': tenant,
                'auth_token': auth_token,
                'session_id': f"stream-{message_id}"
            }
            
            # Execute tool synchronously for streaming
            result = asyncio.run(tool_data['handler'](arguments, context))
            
            return {
                'jsonrpc': '2.0',
                'id': message_id,
                'result': {
                    'content': [
                        {
                            'type': 'text',
                            'text': result
                        }
                    ]
                }
            }
            
        except Exception as e:
            return {
                'jsonrpc': '2.0',
                'id': message_id,
                'error': {
                    'code': -32603,
                    'message': f'Tool execution failed: {str(e)}'
                }
            }
    
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
                    available_credentials.extend(['stripe_secret_key', 'stripe_publishable_key', 'stripe_webhook_secret'])
            except:
                pass
            
            try:
                if tenant.calendly_credential and tenant.calendly_credential.is_active:
                    available_credentials.extend(['calendly_api_token'])
            except:
                pass
            
            try:
                if tenant.google_calendar_credential and tenant.google_calendar_credential.is_active:
                    available_credentials.extend(['google_access_token', 'google_refresh_token', 'google_client_id', 'google_client_secret'])
            except:
                pass
            
            try:
                if tenant.twilio_credential and tenant.twilio_credential.is_active:
                    available_credentials.extend(['twilio_account_sid', 'twilio_auth_token', 'twilio_phone_number'])
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
