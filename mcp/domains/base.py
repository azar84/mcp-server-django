"""
Base classes for domain providers and tools
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from enum import Enum


class ProviderType(Enum):
    """Types of providers for different domains"""
    GENERAL = "general"
    BOOKING = "booking"
    CRM = "crm"
    PAYMENT = "payment"
    EMAIL = "email"
    COMMUNICATION = "communication"
    VOICE_SMS = "voice_sms"
    RESOURCES = "resources"


class BaseProvider(ABC):
    """Base class for all domain providers"""
    
    def __init__(self, name: str, provider_type: ProviderType, config: Dict[str, Any] = None):
        self.name = name
        self.provider_type = provider_type
        self.config = config or {}
        self.is_enabled = True
    
    @abstractmethod
    def get_tools(self) -> List[Dict[str, Any]]:
        """Return list of tools provided by this provider"""
        pass
    
    @abstractmethod
    async def validate_credentials(self, credentials: Dict[str, str]) -> bool:
        """Validate provider credentials"""
        pass
    
    def get_required_credentials(self) -> List[str]:
        """Return list of required credential keys"""
        return []
    
    def get_required_scopes(self) -> List[str]:
        """Return list of required scopes for this provider"""
        return []


class BaseTool:
    """Base class for domain tools"""
    
    def __init__(self, name: str, provider: BaseProvider, description: str, 
                 input_schema: Dict[str, Any], required_scopes: List[str] = None):
        self.name = name
        self.provider = provider
        self.description = description
        self.input_schema = input_schema
        self.required_scopes = required_scopes or []
        self.full_name = f"{provider.provider_type.value}_{provider.name}_{name}"
    
    async def execute(self, arguments: Dict[str, Any], context: Dict[str, Any]) -> Any:
        """Execute the tool with given arguments and context"""
        # Get provider-specific credentials from context
        credentials = context.get('credentials', {})
        provider_credentials = {}
        
        for key in self.provider.get_required_credentials():
            cred_key = f"{self.provider.name}_{key}"
            if cred_key in credentials:
                provider_credentials[key] = credentials[cred_key]
        
        return await self._execute_with_credentials(arguments, provider_credentials, context)
    
    @abstractmethod
    async def _execute_with_credentials(self, arguments: Dict[str, Any], 
                                      credentials: Dict[str, str], 
                                      context: Dict[str, Any]) -> Any:
        """Execute tool with provider credentials"""
        pass


class DomainManager:
    """Manages providers and tools for a specific domain"""
    
    def __init__(self, domain_name: str):
        self.domain_name = domain_name
        self.providers: Dict[str, BaseProvider] = {}
        self.tools: Dict[str, BaseTool] = {}
    
    def register_provider(self, provider: BaseProvider):
        """Register a provider with this domain"""
        self.providers[provider.name] = provider
        
        # Register all tools from this provider
        for tool_config in provider.get_tools():
            tool = tool_config['tool_class'](
                name=tool_config['name'],
                provider=provider,
                description=tool_config['description'],
                input_schema=tool_config['input_schema'],
                required_scopes=tool_config.get('required_scopes', [])
            )
            self.tools[tool.full_name] = tool
    
    def get_tools_for_tenant(self, tenant_scopes: List[str], 
                           available_credentials: List[str]) -> List[BaseTool]:
        """Get tools available for a tenant based on scopes and credentials"""
        available_tools = []
        
        for tool in self.tools.values():
            # Check if tenant has required scopes
            if not set(tool.required_scopes).issubset(set(tenant_scopes)):
                continue
            
            # Check if tenant has required credentials (if provider requires them)
            required_creds = tool.provider.get_required_credentials()
            if required_creds:
                provider_creds = [f"{tool.provider.name}_{cred}" for cred in required_creds]
                if not set(provider_creds).issubset(set(available_credentials)):
                    continue
            
            available_tools.append(tool)
        
        return available_tools
