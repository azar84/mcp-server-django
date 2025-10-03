"""
URL configuration for MCP app
"""

from django.urls import path
from . import views, admin_views, mcp_transport, openai_mcp_transport

urlpatterns = [
    path('', views.index, name='mcp_index'),

    # OpenAI Realtime Compatible MCP Transport (RECOMMENDED)
    path('api/mcp/', openai_mcp_transport.OpenAIMCPTransport.as_view(), name='openai_mcp'),
    path('api/mcp/health/', openai_mcp_transport.OpenAIMCPHealthCheck.as_view(), name='openai_mcp_health'),
    
    # MCP Streaming RPC Transport
    path('api/mcp/rpc/stream/', mcp_transport.MCPStreamableHTTPView.as_view(), name='mcp_streamable'),
    path('api/mcp/capabilities/', mcp_transport.MCPCapabilitiesView.as_view(), name='mcp_capabilities'),
    path('api/mcp/tools/', mcp_transport.MCPToolsListView.as_view(), name='mcp_tools_list'),
    
    # Legacy MCP Protocol endpoints (for testing)
    path('api/mcp/info/', views.MCPServerInfoView.as_view(), name='mcp_info'),
    path('api/mcp/rpc/', views.MCPRPCView.as_view(), name='mcp_rpc'),
    path('api/mcp/sessions/', views.MCPSessionsView.as_view(), name='mcp_sessions'),
    path('api/mcp/analytics/', views.MCPAnalyticsView.as_view(), name='mcp_analytics'),
    
    # Tenant management endpoints
    path('api/admin/tenants/', admin_views.TenantManagementView.as_view(), name='admin_tenants'),
    path('api/admin/tenants/<str:tenant_id>/', admin_views.TenantManagementView.as_view(), name='admin_tenant_detail'),
    path('api/admin/tokens/', admin_views.TokenManagementView.as_view(), name='admin_tokens'),
    path('api/admin/tokens/<int:token_id>/', admin_views.TokenManagementView.as_view(), name='admin_token_detail'),
    path('api/admin/scopes/', admin_views.ScopeManagementView.as_view(), name='admin_scopes'),
    path('api/admin/dashboard/<str:tenant_id>/', admin_views.TenantDashboardView.as_view(), name='admin_dashboard'),
    
    # Admin token management endpoints
    path('api/admin/admin-tokens/', admin_views.AdminTokenManagementView.as_view(), name='admin_admin_tokens'),
    path('api/admin/admin-tokens/<int:token_id>/', admin_views.AdminTokenManagementView.as_view(), name='admin_admin_token_detail'),
    
    # MS Bookings credentials management endpoints
    path('api/admin/ms-bookings-credentials/', admin_views.MSBookingsCredentialsView.as_view(), name='admin_ms_bookings_credentials'),
    path('api/admin/ms-bookings-credentials/<int:token_id>/', admin_views.MSBookingsCredentialsView.as_view(), name='admin_ms_bookings_credential_detail'),
    
    # OpenAI-compatible token generation
    path('api/admin/openai-tokens/', admin_views.OpenAITokenView.as_view(), name='openai_tokens'),
]
