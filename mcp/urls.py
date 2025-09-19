"""
URL configuration for MCP app
"""

from django.urls import path
from . import views, admin_views, mcp_transport

urlpatterns = [
    path('', views.index, name='mcp_index'),
    
    # MCP Streamable HTTP Transport (OpenAI Realtime compatible)
    path('api/mcp/', mcp_transport.MCPStreamableHTTPView.as_view(), name='mcp_streamable'),
    path('api/mcp/capabilities/', mcp_transport.MCPCapabilitiesView.as_view(), name='mcp_capabilities'),
    path('api/mcp/tools/', mcp_transport.MCPToolsListView.as_view(), name='mcp_tools_list'),
    
    # Legacy MCP Protocol endpoints (for testing)
    path('api/mcp/info/', views.MCPServerInfoView.as_view(), name='mcp_info'),
    path('api/mcp/rpc/', views.MCPRPCView.as_view(), name='mcp_rpc'),
    path('api/mcp/sessions/', views.MCPSessionsView.as_view(), name='mcp_sessions'),
    path('api/mcp/analytics/', views.MCPAnalyticsView.as_view(), name='mcp_analytics'),
    
    # Tenant management endpoints
    path('api/admin/tenants/', admin_views.TenantManagementView.as_view(), name='admin_tenants'),
    path('api/admin/tokens/', admin_views.TokenManagementView.as_view(), name='admin_tokens'),
    path('api/admin/tokens/<int:token_id>/', admin_views.TokenManagementView.as_view(), name='admin_token_detail'),
    path('api/admin/credentials/', admin_views.CredentialManagementView.as_view(), name='admin_credentials'),
    path('api/admin/credentials/<int:credential_id>/', admin_views.CredentialManagementView.as_view(), name='admin_credential_detail'),
    path('api/admin/scopes/', admin_views.ScopeManagementView.as_view(), name='admin_scopes'),
    path('api/admin/dashboard/<str:tenant_id>/', admin_views.TenantDashboardView.as_view(), name='admin_dashboard'),
]
