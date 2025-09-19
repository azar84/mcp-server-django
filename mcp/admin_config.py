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
        registered in this site with custom grouping.
        """
        app_dict = self._build_app_dict(request, app_label)
        
        # Custom ordering and grouping
        app_list = []
        
        # Core MCP Management
        if 'mcp' in app_dict:
            mcp_app = app_dict['mcp']
            
            # Separate models into categories
            core_models = []
            credential_models = []
            monitoring_models = []
            
            for model in mcp_app['models']:
                model_name = model['object_name']
                
                if model_name in ['Tenant', 'AuthToken']:
                    core_models.append(model)
                elif 'Credential' in model_name:
                    credential_models.append(model)
                elif model_name in ['MCPSession', 'MCPToolCall', 'MCPTool']:
                    monitoring_models.append(model)
                else:
                    core_models.append(model)
            
            # Core Management section
            if core_models:
                app_list.append({
                    'name': 'Core Management',
                    'app_label': 'core_management',
                    'app_url': '/admin/mcp/',
                    'has_module_perms': True,
                    'models': sorted(core_models, key=lambda x: x['name'])
                })
            
            # Tool Credentials section
            if credential_models:
                app_list.append({
                    'name': 'Tool Credentials',
                    'app_label': 'tool_credentials',
                    'app_url': '/admin/mcp/',
                    'has_module_perms': True,
                    'models': sorted(credential_models, key=lambda x: x['name'])
                })
            
            # Monitoring & Analytics section
            if monitoring_models:
                app_list.append({
                    'name': 'Monitoring & Analytics',
                    'app_label': 'monitoring',
                    'app_url': '/admin/mcp/',
                    'has_module_perms': True,
                    'models': sorted(monitoring_models, key=lambda x: x['name'])
                })
        
        # Add other apps (Auth, etc.)
        for app_name, app_data in app_dict.items():
            if app_name != 'mcp':
                app_list.append(app_data)
        
        return app_list


# Create custom admin site instance
mcp_admin_site = MCPAdminSite(name='mcp_admin')
