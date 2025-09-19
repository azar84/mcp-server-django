"""
OpenAI Realtime Compatible MCP Transport
Handles the specific requirements and limitations of OpenAI's MCP implementation
"""

import json
import asyncio
import logging
import jwt
from django.http import JsonResponse
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from .models import AuthToken, Tenant
from .protocol import protocol_handler

logger = logging.getLogger(__name__)


def extract_tenant_from_token(bearer_token):
    """
    Extract tenant information from Bearer token
    Since OpenAI doesn't forward X-Tenant-ID, we need to encode it in the JWT
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


@method_decorator(csrf_exempt, name='dispatch')
class OpenAIMCPTransport(View):
    """
    OpenAI Realtime compatible MCP transport
    
    Handles the specific requirements:
    - Accept: application/json, text/event-stream
    - Only Authorization header is forwarded
    - MCP-Protocol-Version: 2024-11-05
    - Optional params: {} in requests
    """
    
    def post(self, request):
        """Handle OpenAI MCP requests"""
        try:
            # Log request for debugging
            logger.info(f"OpenAI MCP Request - Method: {request.method}")
            logger.info(f"Headers: {dict(request.headers)}")
            
            # Validate and extract authorization
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
            
            # Extract token (remove "Bearer " prefix, handle double "Bearer Bearer" case)
            bearer_token = auth_header[7:]  # Remove "Bearer "
            
            # Handle case where OpenAI sends "Bearer Bearer <token>"
            if bearer_token.startswith('Bearer '):
                bearer_token = bearer_token[7:]  # Remove second "Bearer "
            
            logger.info(f"Extracted bearer token: {bearer_token[:50]}...")
            
            # Get tenant from token (since X-Tenant-ID won't be forwarded)
            auth_token = extract_tenant_from_token(bearer_token)
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
            
            # Parse request body - be permissive with content type
            try:
                body_str = request.body.decode('utf-8')
                if not body_str.strip():
                    return JsonResponse({
                        'jsonrpc': '2.0',
                        'id': None,
                        'error': {
                            'code': -32700,
                            'message': 'Empty request body'
                        }
                    }, status=400)
                
                message_data = json.loads(body_str)
            except json.JSONDecodeError as e:
                return JsonResponse({
                    'jsonrpc': '2.0',
                    'id': None,
                    'error': {
                        'code': -32700,
                        'message': f'Invalid JSON: {str(e)}'
                    }
                }, status=400)
            
            # Validate JSON-RPC 2.0
            if message_data.get('jsonrpc') != '2.0':
                return JsonResponse({
                    'jsonrpc': '2.0',
                    'id': message_data.get('id'),
                    'error': {
                        'code': -32600,
                        'message': 'Invalid JSON-RPC 2.0 request'
                    }
                }, status=400)
            
            # Handle the request
            return self._handle_mcp_request(message_data, auth_token, tenant)
            
        except Exception as e:
            logger.error(f"OpenAI MCP Transport error: {str(e)}", exc_info=True)
            return JsonResponse({
                'jsonrpc': '2.0',
                'id': None,
                'error': {
                    'code': -32603,
                    'message': f'Internal error: {str(e)}'
                }
            }, status=500)
    
    def _handle_mcp_request(self, message_data, auth_token, tenant):
        """Handle specific MCP methods"""
        method = message_data.get('method')
        message_id = message_data.get('id')
        params = message_data.get('params', {})  # OpenAI sends params: {} even if empty
        
        logger.info(f"Handling method: {method} for tenant: {tenant.name}")
        
        if method == 'tools/list':
            return self._handle_tools_list(message_id, auth_token, tenant)
        
        elif method == 'initialize':
            return self._handle_initialize(message_id)
        
        elif method == 'tools/call':
            # Handle tool calls asynchronously
            return self._handle_tools_call(message_id, params, auth_token, tenant)
        
        else:
            return JsonResponse({
                'jsonrpc': '2.0',
                'id': message_id,
                'error': {
                    'code': -32601,
                    'message': f'Method not found: {method}'
                }
            }, status=404)
    
    def _handle_tools_list(self, message_id, auth_token, tenant):
        """Handle tools/list requests"""
        try:
            # Get available tools from protocol handler
            tools = []
            
            for tool_name, tool_data in protocol_handler.tools.items():
                # Check if tenant has required scopes
                required_scopes = tool_data.get('required_scopes', [])
                if not set(required_scopes).issubset(set(auth_token.scopes)):
                    logger.debug(f"Skipping tool {tool_name} - missing scopes. Required: {required_scopes}, Available: {auth_token.scopes}")
                    continue
                
                # Check if tool requires credentials and tenant has them
                requires_credentials = tool_data.get('requires_credentials', False)
                if requires_credentials:
                    # For MS Bookings, check if credentials exist
                    if 'ms_bookings' in required_scopes:
                        try:
                            if not (hasattr(tenant, 'ms_bookings_credential') and 
                                   tenant.ms_bookings_credential and 
                                   tenant.ms_bookings_credential.is_active):
                                logger.debug(f"Skipping tool {tool_name} - missing MS Bookings credentials")
                                continue
                        except:
                            logger.debug(f"Skipping tool {tool_name} - error checking MS Bookings credentials")
                            continue
                
                tools.append({
                    'name': tool_name,
                    'description': tool_data['description'],
                    'inputSchema': tool_data['inputSchema']
                })
            
            logger.info(f"Returning {len(tools)} tools for tenant {tenant.name}")
            
            return JsonResponse({
                'jsonrpc': '2.0',
                'id': message_id,
                'result': {
                    'tools': tools
                }
            })
            
        except Exception as e:
            logger.error(f"Error in tools/list: {str(e)}", exc_info=True)
            return JsonResponse({
                'jsonrpc': '2.0',
                'id': message_id,
                'error': {
                    'code': -32603,
                    'message': f'Error listing tools: {str(e)}'
                }
            }, status=500)
    
    def _handle_initialize(self, message_id):
        """Handle initialize requests"""
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
    
    def _handle_tools_call(self, message_id, params, auth_token, tenant):
        """Handle tools/call requests"""
        try:
            tool_name = params.get('name')
            arguments = params.get('arguments', {})
            
            if not tool_name:
                return JsonResponse({
                    'jsonrpc': '2.0',
                    'id': message_id,
                    'error': {
                        'code': -32602,
                        'message': 'Missing tool name in params'
                    }
                }, status=400)
            
            # Check if tool exists and tenant has access
            if tool_name not in protocol_handler.tools:
                return JsonResponse({
                    'jsonrpc': '2.0',
                    'id': message_id,
                    'error': {
                        'code': -32601,
                        'message': f'Tool not found: {tool_name}'
                    }
                }, status=404)
            
            tool_data = protocol_handler.tools[tool_name]
            required_scopes = tool_data.get('required_scopes', [])
            
            if not set(required_scopes).issubset(set(auth_token.scopes)):
                return JsonResponse({
                    'jsonrpc': '2.0',
                    'id': message_id,
                    'error': {
                        'code': -32001,
                        'message': f'Insufficient scopes for tool {tool_name}'
                    }
                }, status=403)
            
            # Execute tool synchronously for now (OpenAI expects immediate response)
            try:
                # Create context for tool execution
                context = {
                    'tenant': tenant,
                    'auth_token': auth_token,
                    'session_id': f"openai-{message_id}"
                }
                
                # Execute tool
                result = asyncio.run(tool_data['handler'](arguments, context))
                
                return JsonResponse({
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
                })
                
            except Exception as e:
                logger.error(f"Tool execution error for {tool_name}: {str(e)}", exc_info=True)
                return JsonResponse({
                    'jsonrpc': '2.0',
                    'id': message_id,
                    'error': {
                        'code': -32603,
                        'message': f'Tool execution failed: {str(e)}'
                    }
                }, status=500)
            
        except Exception as e:
            logger.error(f"Error in tools/call: {str(e)}", exc_info=True)
            return JsonResponse({
                'jsonrpc': '2.0',
                'id': message_id,
                'error': {
                    'code': -32603,
                    'message': f'Error calling tool: {str(e)}'
                }
            }, status=500)


@method_decorator(csrf_exempt, name='dispatch')
class OpenAIMCPHealthCheck(View):
    """Health check endpoint for OpenAI MCP integration"""
    
    def get(self, request):
        """Simple health check"""
        return JsonResponse({
            'status': 'healthy',
            'server': 'Django MCP Server',
            'version': '2.0.0',
            'protocol': '2024-11-05',
            'transport': 'openai-compatible'
        })
