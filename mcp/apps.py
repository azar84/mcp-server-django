from django.apps import AppConfig


class McpConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'mcp'
    verbose_name = 'MCP Server'
    
    def ready(self):
        """Initialize MCP domains when the app is ready"""
        # Tools are now automatically registered through the domain-based system
        # See mcp/domain_registry.py for domain and provider registration
        pass