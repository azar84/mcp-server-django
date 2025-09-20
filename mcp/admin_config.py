"""
Custom admin site configuration for better organization
"""

from django.contrib import admin
from django.contrib.admin import AdminSite


class MCPAdminSite(AdminSite):
    """Custom admin site for MCP Server"""
    site_header = "MCP Server Administration"
    site_title = "MCP Server Admin"
    index_title = "Welcome to MCP Server Administration"
    
    def get_app_list(self, request, app_label=None):
        """
        Return a sorted list of all the installed apps that have been
        registered in this site.
        """
        app_dict = self._build_app_dict(request, app_label)
        
        # Convert to list and sort by name
        app_list = sorted(app_dict.values(), key=lambda x: x['name'].lower())
        
        return app_list


# Create custom admin site instance
mcp_admin_site = MCPAdminSite(name='mcp_admin')
