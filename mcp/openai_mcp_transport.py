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
            
            # Extract token (remove "Bearer " prefix)
            bearer_token = auth_header[7:]
            
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
            
            # Check tenant is valid
            tenant = auth_token.tenant
            if not tenant:
                return JsonResponse({
                    'jsonrpc': '2.0',
                    'id': None,
                    'error': {
                        'code': -32001,
                        'message': 'Invalid token: no tenant associated'
                    }
                }, status=401)
            
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
        
        elif method == 'resources/list':
            return self._handle_resources_list(message_id, auth_token, tenant)
        
        elif method == 'resources/read':
            return self._handle_resources_read(message_id, params, auth_token, tenant)
        
        elif method == 'notifications/initialized':
            # Handle notifications/initialized method - this is a standard MCP notification
            return self._handle_notifications_initialized(message_id, auth_token, tenant)
        
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
        """Handle tools/list requests using domain-based tools"""
        try:
            # Get available tools from domain registry
            from .domain_registry import domain_registry
            
            # Get tenant's available credentials
            available_credentials = []
            
            # Check MS Bookings credentials
            try:
                # MS Bookings credentials are now token-specific, not tenant-specific
                # Check if any tokens for this tenant have MS Bookings credentials
                if tenant.authtoken_set.filter(is_active=True, ms_bookings_credential__isnull=False, ms_bookings_credential__is_active=True).exists():
                    available_credentials.extend(['ms_bookings_azure_tenant_id', 'ms_bookings_client_id', 'ms_bookings_client_secret'])
            except:
                pass
            
            # Check Stripe credentials
            try:
                if tenant.stripe_credential and tenant.stripe_credential.is_active:
                    available_credentials.extend(['stripe_secret_key', 'stripe_publishable_key', 'stripe_webhook_secret'])
            except:
                pass
            
            # Check Calendly credentials
            try:
                if tenant.calendly_credential and tenant.calendly_credential.is_active:
                    available_credentials.extend(['calendly_api_token'])
            except:
                pass
            
            # Check Google Calendar credentials
            try:
                if tenant.google_calendar_credential and tenant.google_calendar_credential.is_active:
                    available_credentials.extend(['google_access_token', 'google_refresh_token', 'google_client_id', 'google_client_secret'])
            except:
                pass
            
            # Check Twilio credentials
            try:
                if tenant.twilio_credential and tenant.twilio_credential.is_active:
                    available_credentials.extend(['twilio_account_sid', 'twilio_auth_token', 'twilio_phone_number'])
            except:
                pass
            
            # Get tools available to this tenant from domain registry
            domain_tools = domain_registry.get_available_tools(
                auth_token.scopes,
                available_credentials
            )
            
            # Convert to OpenAI format
            tools = []
            for tool in domain_tools:
                tools.append({
                    'name': tool['name'],
                    'description': tool['description'],
                    'inputSchema': tool['inputSchema']
                })
            
            logger.info(f"Returning {len(tools)} domain-based tools for tenant {tenant.name}")
            
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
        """Handle tools/call requests using domain-based tools"""
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
            
            # Get tool from domain registry
            from .domain_registry import domain_registry
            tool = domain_registry.get_tool_by_name(tool_name)
            
            if not tool:
                return JsonResponse({
                    'jsonrpc': '2.0',
                    'id': message_id,
                    'error': {
                        'code': -32601,
                        'message': f'Tool not found: {tool_name}'
                    }
                }, status=404)
            
            # Check if tenant has required scopes
            if not set(tool.required_scopes).issubset(set(auth_token.scopes)):
                return JsonResponse({
                    'jsonrpc': '2.0',
                    'id': message_id,
                    'error': {
                        'code': -32001,
                        'message': f'Insufficient scopes for tool {tool_name}. Required: {tool.required_scopes}, Available: {auth_token.scopes}'
                    }
                }, status=403)
            
            # Execute domain-based tool
            try:
                # Create context for tool execution
                context = {
                    'tenant': tenant,
                    'auth_token': auth_token,
                    'session_id': f"openai-{message_id}"
                }
                
                # Execute the domain tool
                result = asyncio.run(tool.execute(arguments, context))
                
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
    
    def _handle_resources_list(self, message_id, auth_token, tenant):
        """Handle resources/list method"""
        if not tenant:
            return JsonResponse({
                'jsonrpc': '2.0',
                'id': message_id,
                'error': {
                    'code': -32403,
                    'message': 'Authentication required for resource access'
                }
            })
        
        try:
            from .resources.onedrive import onedrive_resource
            
            # Get tenant's resources using direct method call (now synchronous)
            resources = onedrive_resource.list_resources(tenant)
            
            return JsonResponse({
                'jsonrpc': '2.0',
                'id': message_id,
                'result': {
                    'resources': resources
                }
            })
            
        except Exception as e:
            logger.error(f"Error listing resources for tenant {tenant.name}: {str(e)}")
            return JsonResponse({
                'jsonrpc': '2.0',
                'id': message_id,
                'error': {
                    'code': -32603,
                    'message': f'Error listing resources: {str(e)}'
                }
            })
    
    def _handle_resources_read(self, message_id, params, auth_token, tenant):
        """Handle resources/read method"""
        if not tenant:
            return JsonResponse({
                'jsonrpc': '2.0',
                'id': message_id,
                'error': {
                    'code': -32403,
                    'message': 'Authentication required for resource access'
                }
            })
        
        if not params or 'uri' not in params:
            return JsonResponse({
                'jsonrpc': '2.0',
                'id': message_id,
                'error': {
                    'code': -32602,
                    'message': 'Missing uri parameter'
                }
            })
        
        resource_uri = params['uri']
        
        try:
            from .resources.onedrive import onedrive_resource
            from .resources.knowledge_base import kb_resource
            
            # Try OneDrive/tenant resources first (now synchronous method)
            if onedrive_resource.can_handle(resource_uri):
                resource_data = onedrive_resource.resolve_resource(resource_uri, tenant, auth_token)
            else:
                # Fallback to knowledge base resources (global)
                resource_data = kb_resource.resolve_resource(resource_uri)
            
            if resource_data is None:
                return JsonResponse({
                    'jsonrpc': '2.0',
                    'id': message_id,
                    'error': {
                        'code': -32602,
                        'message': f'Resource not found: {resource_uri}'
                    }
                })
            
            # Handle error responses from resource handlers
            if 'error' in resource_data:
                return JsonResponse({
                    'jsonrpc': '2.0',
                    'id': message_id,
                    'error': {
                        'code': -32602,
                        'message': resource_data['error']
                    }
                })
            
            return JsonResponse({
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
            })
            
        except Exception as e:
            logger.error(f"Error reading resource {resource_uri} for tenant {tenant.name}: {str(e)}")
            return JsonResponse({
                'jsonrpc': '2.0',
                'id': message_id,
                'error': {
                    'code': -32603,
                    'message': f'Error reading resource: {str(e)}'
                }
            })

    def _handle_notifications_initialized(self, message_id, auth_token, tenant):
        """Handle notifications/initialized method - this is a standard MCP notification"""
        logger.info(f"Handling notifications/initialized for tenant: {tenant.name if tenant else 'Unknown'}")
        
        # Notifications are one-way messages, they don't need to return a result
        # Just log that initialization notification was received
        return JsonResponse({
            'jsonrpc': '2.0',
            'id': message_id,
            'result': {
                'notified': True,
                'message': 'Initialization notification received'
            }
        }, status=200)


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
