"""
Domain registry for organizing and managing MCP tools by business domain
"""

from typing import Dict, List
from .domains.base import DomainManager
from .domains.general import GeneralToolsProvider
from .domains.bookings import CalendlyProvider, GoogleCalendarProvider, MSBookingsProvider
from .domains.crm import SalesforceProvider, HubSpotProvider, PipedriveProvider  
from .domains.payments import StripeProvider, PayPalProvider
from .domains.email import SendGridProvider, MailgunProvider


class MCPDomainRegistry:
    """Registry for managing domain-based tools"""
    
    def __init__(self):
        self.domains: Dict[str, DomainManager] = {}
        self._initialize_domains()
    
    def _initialize_domains(self):
        """Initialize all domains with their providers"""
        
        # General tools domain
        general_domain = DomainManager("general")
        general_domain.register_provider(GeneralToolsProvider())
        self.domains["general"] = general_domain
        
        # Other domains are structure only for now
        # They will be activated when tools are fully implemented
    
    def get_available_tools(self, tenant_scopes: List[str], 
                          available_credentials: List[str]) -> List[Dict]:
        """Get all available tools across domains for a tenant"""
        all_tools = []
        
        # Add domain-based tools
        for domain_name, domain_manager in self.domains.items():
            domain_tools = domain_manager.get_tools_for_tenant(
                tenant_scopes, available_credentials
            )
            
            for tool in domain_tools:
                all_tools.append({
                    'name': tool.full_name,
                    'description': tool.description,
                    'inputSchema': tool.input_schema,
                    'domain': domain_name,
                    'provider': tool.provider.name,
                    'required_scopes': tool.required_scopes
                })
        
        # Add legacy tools from protocol handler for backward compatibility
        from .protocol import protocol_handler
        for tool_name, tool_data in protocol_handler.tools.items():
            # Check if tenant has required scopes
            required_scopes = tool_data.get('required_scopes', [])
            if not set(required_scopes).issubset(set(tenant_scopes)):
                continue
            
            # Skip if this tool is already included from domains
            if any(t['name'] == tool_name for t in all_tools):
                continue
            
            all_tools.append({
                'name': tool_name,
                'description': tool_data['description'],
                'inputSchema': tool_data['inputSchema'],
                'domain': 'legacy',
                'provider': 'built-in',
                'required_scopes': required_scopes
            })
        
        return all_tools
    
    def get_tool_by_name(self, tool_name: str):
        """Get a specific tool by its full name (domain_tool_name)"""
        for domain_manager in self.domains.values():
            if tool_name in domain_manager.tools:
                return domain_manager.tools[tool_name]
        return None
    
    def get_domain_structure(self) -> Dict:
        """Get the complete domain structure for documentation"""
        structure = {
            'domains': {},
            'total_providers': 0,
            'total_tools': 0
        }
        
        for domain_name, domain_manager in self.domains.items():
            providers = {}
            tool_count = 0
            
            for provider_name, provider in domain_manager.providers.items():
                provider_tools = []
                for tool_name, tool in domain_manager.tools.items():
                    if tool.provider.name == provider_name:
                        provider_tools.append({
                            'name': tool_name,
                            'description': tool.description,
                            'required_scopes': tool.required_scopes
                        })
                        tool_count += 1
                
                providers[provider_name] = {
                    'type': provider.provider_type.value,
                    'tools': provider_tools,
                    'required_credentials': provider.get_required_credentials()
                }
            
            structure['domains'][domain_name] = {
                'providers': providers,
                'tool_count': tool_count
            }
            structure['total_providers'] += len(providers)
            structure['total_tools'] += tool_count
        
        return structure


# Global domain registry instance
domain_registry = MCPDomainRegistry()
