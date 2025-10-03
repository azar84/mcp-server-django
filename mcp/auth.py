"""
Authentication and authorization utilities for MCP server
"""

from django.utils import timezone
from django.core.exceptions import ValidationError
from cryptography.fernet import Fernet
from django.conf import settings
import base64
import os
from datetime import timedelta
from typing import Optional, Dict, Any, List
from .models import AuthToken, Tenant, AdminToken


class MCPAuthenticator:
    """Handle MCP authentication and authorization"""
    
    def __init__(self):
        # Initialize encryption for credentials
        self._init_encryption()
    
    def _init_encryption(self):
        """Initialize encryption key for credentials"""
        # In production, this should be stored securely (e.g., environment variable)
        encryption_key = getattr(settings, 'MCP_ENCRYPTION_KEY', None)
        if not encryption_key:
            # Generate a key for development (store this securely in production)
            encryption_key = Fernet.generate_key()
            print(f"Generated encryption key: {encryption_key.decode()}")
            print("Store this key securely in production as MCP_ENCRYPTION_KEY")
        
        if isinstance(encryption_key, str):
            encryption_key = encryption_key.encode()
        
        self.cipher_suite = Fernet(encryption_key)
    
    def validate_token(self, token: str) -> Optional[AuthToken]:
        """Validate authentication token"""
        try:
            auth_token = AuthToken.objects.get(
                token=token,
                is_active=True
            )
            
            # Check if token is expired
            if auth_token.expires_at and auth_token.expires_at < timezone.now():
                return None
            
            # Update last used timestamp
            auth_token.last_used = timezone.now()
            auth_token.save(update_fields=['last_used'])
            
            return auth_token
            
        except AuthToken.DoesNotExist:
            return None
    
    def check_scope_permission(self, auth_token: AuthToken, required_scopes: List[str]) -> bool:
        """Check if token has required scopes"""
        if not required_scopes:
            return True  # No scopes required
        
        token_scopes = set(auth_token.scopes)
        required_scopes_set = set(required_scopes)
        
        # Check if token has all required scopes
        return required_scopes_set.issubset(token_scopes)
    
    
    def get_allowed_tools(self, auth_token: AuthToken) -> List[str]:
        """Get list of tools allowed for this token based on scopes"""
        from .protocol import protocol_handler
        
        allowed_tools = []
        token_scopes = set(auth_token.scopes)
        
        for tool_name, tool_data in protocol_handler.tools.items():
            required_scopes = tool_data.get('required_scopes', [])
            
            if not required_scopes or set(required_scopes).issubset(token_scopes):
                allowed_tools.append(tool_name)
        
        return allowed_tools


class AdminAuthenticator:
    """Handle admin authentication for tenant creation and management"""
    
    def validate_admin_token(self, token: str, required_scope: str = None) -> Optional[AdminToken]:
        """Validate admin token and check scopes"""
        try:
            admin_token = AdminToken.objects.get(
                token=token,
                is_active=True
            )
            
            # Check if token is expired
            if admin_token.expires_at and admin_token.expires_at < timezone.now():
                return None
            
            # Check scope if required
            if required_scope and required_scope not in admin_token.scopes:
                return None
            
            # Update last used timestamp
            admin_token.last_used = timezone.now()
            admin_token.save(update_fields=['last_used'])
            
            return admin_token
            
        except AdminToken.DoesNotExist:
            return None
    
    def create_admin_token(self, name: str, scopes: List[str], 
                          expires_in_days: int = None, created_by: str = "") -> AdminToken:
        """Create a new admin token"""
        import secrets
        
        token = secrets.token_urlsafe(32)
        
        expires_at = None
        if expires_in_days:
            expires_at = timezone.now() + timedelta(days=expires_in_days)
        
        admin_token = AdminToken.objects.create(
            token=token,
            name=name,
            scopes=scopes,
            expires_at=expires_at,
            created_by=created_by,
            is_active=True
        )
        
        return admin_token


class AdminAuthMiddleware:
    """Authentication middleware for admin requests"""
    
    def __init__(self):
        self.admin_authenticator = AdminAuthenticator()
    
    def authenticate_admin_request(self, request, required_scope: str = None):
        """Authenticate admin request"""
        # Check Authorization header
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        if not auth_header.startswith('Bearer '):
            return None, "Bearer token required for admin access"
        
        token = auth_header.split(' ', 1)[1]
        
        # Validate admin token
        admin_token = self.admin_authenticator.validate_admin_token(token, required_scope)
        if not admin_token:
            return None, "Invalid or expired admin token"
        
        return admin_token, None


class MCPAuthMiddleware:
    """Authentication middleware for MCP requests"""
    
    def __init__(self):
        self.authenticator = MCPAuthenticator()
    
    def authenticate_websocket(self, scope, receive, send):
        """Authenticate WebSocket connection"""
        # Extract token from query parameters or headers
        query_string = scope.get('query_string', b'').decode()
        token = None
        tenant_id = None
        
        # Parse query parameters
        if query_string:
            params = dict(param.split('=') for param in query_string.split('&') if '=' in param)
            token = params.get('token')
            tenant_id = params.get('tenant_id')
        
        if not token:
            return None, "Authentication token required"
        
        if not tenant_id:
            return None, "Tenant ID required"
        
        # Validate token
        auth_token = self.authenticator.validate_token(token)
        if not auth_token:
            return None, "Invalid or expired token"
        
        # Verify tenant matches
        if auth_token.tenant.tenant_id != tenant_id:
            return None, "Token does not match tenant"
        
        return auth_token, None
    
    def authenticate_http(self, request):
        """Authenticate HTTP request"""
        # Check Authorization header
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        if not auth_header.startswith('Bearer '):
            return None, "Bearer token required"
        
        token = auth_header.split(' ', 1)[1]
        
        # Get tenant ID from header or request body
        tenant_id = request.META.get('HTTP_X_TENANT_ID')
        if not tenant_id and hasattr(request, 'data'):
            tenant_id = request.data.get('tenant_id')
        
        if not tenant_id:
            return None, "Tenant ID required"
        
        # Validate token
        auth_token = self.authenticator.validate_token(token)
        if not auth_token:
            return None, "Invalid or expired token"
        
        # Verify tenant matches
        if auth_token.tenant.tenant_id != tenant_id:
            return None, "Token does not match tenant"
        
        return auth_token, None


# Global instances
mcp_authenticator = MCPAuthenticator()
mcp_auth_middleware = MCPAuthMiddleware()
admin_authenticator = AdminAuthenticator()
admin_auth_middleware = AdminAuthMiddleware()
