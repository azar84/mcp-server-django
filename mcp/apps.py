from django.apps import AppConfig


class McpConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'mcp'
    verbose_name = 'MCP Server'
    
    def ready(self):
        """Initialize MCP tools when the app is ready"""
        from .tools import register_default_tools
        register_default_tools()