"""
REST API views for MCP server management
"""

from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.http import JsonResponse
from .models import MCPSession, MCPTool, MCPToolCall
from .protocol import protocol_handler
from .consumers import MCPStdioConsumer
import json


class MCPServerInfoView(APIView):
    """Get MCP server information"""
    
    def get(self, request):
        """Return server info and capabilities"""
        tools = []
        for name, tool_data in protocol_handler.tools.items():
            tools.append({
                'name': name,
                'description': tool_data['description'],
                'inputSchema': tool_data['inputSchema']
            })
        
        return Response({
            'server_info': {
                'name': 'Django MCP Server',
                'version': '1.0.0',
                'protocol_version': '2024-11-05'
            },
            'capabilities': {
                'tools': {}
            },
            'available_tools': tools,
            'endpoints': {
                'websocket': '/ws/mcp/',
                'http_rpc': '/api/mcp/rpc/',
                'server_info': '/api/mcp/info/',
                'sessions': '/api/mcp/sessions/',
                'tools': '/api/mcp/tools/'
            }
        })


class MCPRPCView(APIView):
    """Handle MCP RPC calls via HTTP (Legacy endpoint - use /api/mcp/ for OpenAI)"""
    
    def post(self, request):
        """Handle MCP RPC request (synchronous)"""
        try:
            # Redirect to the new streamable HTTP endpoint
            from django.http import JsonResponse
            return JsonResponse({
                'jsonrpc': '2.0',
                'id': request.data.get('id'),
                'error': {
                    'code': -32001,
                    'message': 'This endpoint is deprecated. Use /api/mcp/ for MCP Streamable HTTP transport compatible with OpenAI Realtime.'
                }
            }, status=400)
            
        except Exception as e:
            return Response({
                'jsonrpc': '2.0',
                'id': request.data.get('id') if hasattr(request, 'data') else None,
                'error': {
                    'code': -32603,
                    'message': f'Internal error: {str(e)}'
                }
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class MCPSessionsView(APIView):
    """Manage MCP sessions"""
    
    def get(self, request):
        """List active sessions"""
        sessions = MCPSession.objects.filter(is_active=True)
        data = []
        
        for session in sessions:
            data.append({
                'session_id': session.session_id,
                'client_info': session.client_info,
                'created_at': session.created_at.isoformat(),
                'last_activity': session.last_activity.isoformat(),
                'tool_calls_count': session.mcptoolcall_set.count()
            })
        
        return Response({
            'active_sessions': len(data),
            'sessions': data
        })


class MCPToolsView(APIView):
    """Manage MCP tools"""
    
    def get(self, request):
        """List available tools"""
        tools = []
        for name, tool_data in protocol_handler.tools.items():
            tools.append({
                'name': name,
                'description': tool_data['description'],
                'inputSchema': tool_data['inputSchema']
            })
        
        return Response({
            'tools_count': len(tools),
            'tools': tools
        })
    
    def post(self, request):
        """Register a new tool (for dynamic tool registration)"""
        try:
            name = request.data.get('name')
            description = request.data.get('description')
            input_schema = request.data.get('input_schema')
            
            if not all([name, description, input_schema]):
                return Response({
                    'error': 'Missing required fields: name, description, input_schema'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # For now, we'll just store the tool definition
            # In a real implementation, you'd need to provide the handler
            MCPTool.objects.create(
                name=name,
                description=description,
                input_schema=input_schema
            )
            
            return Response({
                'message': f'Tool {name} registered successfully',
                'tool': {
                    'name': name,
                    'description': description,
                    'input_schema': input_schema
                }
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            return Response({
                'error': f'Failed to register tool: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class MCPAnalyticsView(APIView):
    """Analytics and monitoring for MCP server"""
    
    def get(self, request):
        """Get server analytics"""
        total_sessions = MCPSession.objects.count()
        active_sessions = MCPSession.objects.filter(is_active=True).count()
        total_tool_calls = MCPToolCall.objects.count()
        
        # Tool usage statistics
        tool_stats = {}
        for call in MCPToolCall.objects.all():
            tool_name = call.tool_name
            if tool_name not in tool_stats:
                tool_stats[tool_name] = {'calls': 0, 'errors': 0}
            tool_stats[tool_name]['calls'] += 1
            if call.error:
                tool_stats[tool_name]['errors'] += 1
        
        return Response({
            'sessions': {
                'total': total_sessions,
                'active': active_sessions,
                'inactive': total_sessions - active_sessions
            },
            'tool_calls': {
                'total': total_tool_calls,
                'by_tool': tool_stats
            },
            'server_status': 'running',
            'registered_tools': len(protocol_handler.tools)
        })


def index(request):
    """Simple index page for the MCP server"""
    # Build the server URL dynamically
    server_url = request.build_absolute_uri('/api/mcp/')
    
    context = {
        'server_name': 'Django MCP Server',
        'version': '1.0.0',
        'tools_count': len(protocol_handler.tools),
        'websocket_url': '/ws/mcp/',
        'server_url': server_url
    }
    return render(request, 'mcp/index.html', context)