"""
Admin views for managing tenants, tokens, and credentials
"""

from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone
from datetime import datetime, timedelta
import uuid
import secrets
from .models import Tenant, AuthToken, ClientCredential
from .auth import mcp_authenticator
from .jwt_utils import create_openai_compatible_token


class TenantManagementView(APIView):
    """Manage tenants"""
    
    def get(self, request):
        """List all tenants"""
        tenants = Tenant.objects.all()
        data = []
        
        for tenant in tenants:
            data.append({
                'tenant_id': tenant.tenant_id,
                'name': tenant.name,
                'description': tenant.description,
                'is_active': tenant.is_active,
                'created_at': tenant.created_at.isoformat(),
                'token_count': tenant.authtoken_set.filter(is_active=True).count(),
                'session_count': tenant.mcpsession_set.filter(is_active=True).count()
            })
        
        return Response({
            'tenants': data,
            'total_count': len(data)
        })
    
    def post(self, request):
        """Create a new tenant"""
        try:
            name = request.data.get('name')
            description = request.data.get('description', '')
            
            if not name:
                return Response({
                    'error': 'Tenant name is required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            tenant = Tenant.objects.create(
                tenant_id=str(uuid.uuid4()),
                name=name,
                description=description,
                is_active=True
            )
            
            return Response({
                'message': f'Tenant {name} created successfully',
                'tenant': {
                    'tenant_id': tenant.tenant_id,
                    'name': tenant.name,
                    'description': tenant.description,
                    'is_active': tenant.is_active,
                    'created_at': tenant.created_at.isoformat()
                }
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            return Response({
                'error': f'Failed to create tenant: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class TokenManagementView(APIView):
    """Manage authentication tokens"""
    
    def get(self, request):
        """List all tokens"""
        tokens = AuthToken.objects.all()
        data = []
        
        for token in tokens:
            data.append({
                'id': token.id,
                'token': token.token[:8] + '...',  # Show only first 8 chars
                'tenant_id': token.tenant.tenant_id,
                'tenant_name': token.tenant.name,
                'scopes': token.scopes,
                'is_active': token.is_active,
                'expires_at': token.expires_at.isoformat() if token.expires_at else None,
                'created_at': token.created_at.isoformat(),
                'last_used': token.last_used.isoformat() if token.last_used else None
            })
        
        return Response({
            'tokens': data,
            'total_count': len(data)
        })
    
    def post(self, request):
        """Create a new authentication token"""
        try:
            tenant_id = request.data.get('tenant_id')
            scopes = request.data.get('scopes', [])
            expires_in_days = request.data.get('expires_in_days', 30)
            
            if not tenant_id:
                return Response({
                    'error': 'Tenant ID is required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            tenant = get_object_or_404(Tenant, tenant_id=tenant_id)
            
            # Generate secure token
            token = secrets.token_urlsafe(32)
            
            # Calculate expiration
            expires_at = timezone.now() + timedelta(days=expires_in_days)
            
            auth_token = AuthToken.objects.create(
                token=token,
                tenant=tenant,
                scopes=scopes,
                expires_at=expires_at,
                is_active=True
            )
            
            return Response({
                'message': f'Token created for tenant {tenant.name}',
                'token_info': {
                    'token': token,  # Return full token only on creation
                    'tenant_id': tenant.tenant_id,
                    'tenant_name': tenant.name,
                    'scopes': scopes,
                    'expires_at': expires_at.isoformat(),
                    'created_at': auth_token.created_at.isoformat()
                }
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            return Response({
                'error': f'Failed to create token: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def delete(self, request, token_id):
        """Deactivate a token"""
        try:
            auth_token = get_object_or_404(AuthToken, id=token_id)
            auth_token.is_active = False
            auth_token.save()
            
            return Response({
                'message': 'Token deactivated successfully'
            })
            
        except Exception as e:
            return Response({
                'error': f'Failed to deactivate token: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class CredentialManagementView(APIView):
    """Manage client credentials"""
    
    def get(self, request):
        """List credentials for a tenant"""
        tenant_id = request.query_params.get('tenant_id')
        
        if not tenant_id:
            return Response({
                'error': 'Tenant ID is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        tenant = get_object_or_404(Tenant, tenant_id=tenant_id)
        credentials = ClientCredential.objects.filter(tenant=tenant, is_active=True)
        
        data = []
        for cred in credentials:
            data.append({
                'id': cred.id,
                'tool_name': cred.tool_name,
                'credential_key': cred.credential_key,
                'has_value': bool(cred.credential_value),
                'created_at': cred.created_at.isoformat(),
                'updated_at': cred.updated_at.isoformat()
            })
        
        return Response({
            'tenant_id': tenant_id,
            'tenant_name': tenant.name,
            'credentials': data,
            'total_count': len(data)
        })
    
    def post(self, request):
        """Store credential for a tenant and tool"""
        try:
            tenant_id = request.data.get('tenant_id')
            tool_name = request.data.get('tool_name')
            credential_key = request.data.get('credential_key')
            credential_value = request.data.get('credential_value')
            
            if not all([tenant_id, tool_name, credential_key, credential_value]):
                return Response({
                    'error': 'tenant_id, tool_name, credential_key, and credential_value are required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            tenant = get_object_or_404(Tenant, tenant_id=tenant_id)
            
            # Store encrypted credential
            mcp_authenticator.store_tenant_credential(
                tenant, tool_name, credential_key, credential_value
            )
            
            return Response({
                'message': f'Credential {credential_key} stored for {tool_name}',
                'tenant_id': tenant_id,
                'tool_name': tool_name,
                'credential_key': credential_key
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            return Response({
                'error': f'Failed to store credential: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def delete(self, request, credential_id):
        """Delete a credential"""
        try:
            credential = get_object_or_404(ClientCredential, id=credential_id)
            credential.is_active = False
            credential.save()
            
            return Response({
                'message': 'Credential deactivated successfully'
            })
            
        except Exception as e:
            return Response({
                'error': f'Failed to deactivate credential: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ScopeManagementView(APIView):
    """Manage available scopes"""
    
    def get(self, request):
        """Get available scopes and their descriptions"""
        from .protocol import protocol_handler
        
        # Get scopes from registered tools
        scopes = {}
        for tool_name, tool_data in protocol_handler.tools.items():
            required_scopes = tool_data.get('required_scopes', [])
            for scope in required_scopes:
                if scope not in scopes:
                    scopes[scope] = {
                        'name': scope,
                        'description': f'Access to {scope} functionality',
                        'tools': []
                    }
                scopes[scope]['tools'].append(tool_name)
        
        # Add common scope descriptions
        scope_descriptions = {
            'basic': 'Basic functionality access',
            'admin': 'Administrative access to system information',
            'files': 'File system operations',
            'web': 'Web request capabilities',
            'api': 'Secure API access with credentials'
        }
        
        for scope_name, scope_data in scopes.items():
            if scope_name in scope_descriptions:
                scope_data['description'] = scope_descriptions[scope_name]
        
        return Response({
            'scopes': list(scopes.values()),
            'total_count': len(scopes)
        })


class TenantDashboardView(APIView):
    """Dashboard view for tenant analytics"""
    
    def get(self, request, tenant_id):
        """Get dashboard data for a specific tenant"""
        tenant = get_object_or_404(Tenant, tenant_id=tenant_id)
        
        # Get tenant statistics
        active_tokens = tenant.authtoken_set.filter(is_active=True).count()
        active_sessions = tenant.mcpsession_set.filter(is_active=True).count()
        total_tool_calls = sum(
            session.mcptoolcall_set.count() 
            for session in tenant.mcpsession_set.all()
        )
        
        # Get recent tool calls
        recent_calls = []
        for session in tenant.mcpsession_set.filter(is_active=True)[:5]:
            for call in session.mcptoolcall_set.order_by('-created_at')[:10]:
                recent_calls.append({
                    'tool_name': call.tool_name,
                    'created_at': call.created_at.isoformat(),
                    'success': not bool(call.error),
                    'session_id': call.session.session_id
                })
        
        recent_calls.sort(key=lambda x: x['created_at'], reverse=True)
        
        return Response({
            'tenant': {
                'tenant_id': tenant.tenant_id,
                'name': tenant.name,
                'description': tenant.description,
                'is_active': tenant.is_active,
                'created_at': tenant.created_at.isoformat()
            },
            'statistics': {
                'active_tokens': active_tokens,
                'active_sessions': active_sessions,
                'total_tool_calls': total_tool_calls,
                'credentials_count': tenant.clientcredential_set.filter(is_active=True).count()
            },
            'recent_calls': recent_calls[:20]
        })


class OpenAITokenView(APIView):
    """Generate OpenAI-compatible JWT tokens"""
    
    def post(self, request):
        """Create an OpenAI-compatible token with embedded tenant info"""
        try:
            tenant_id = request.data.get('tenant_id')
            scopes = request.data.get('scopes', [])
            expires_in_days = request.data.get('expires_in_days', 365)
            
            if not tenant_id:
                return Response({
                    'error': 'tenant_id is required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Get tenant
            try:
                tenant = Tenant.objects.get(tenant_id=tenant_id, is_active=True)
            except Tenant.DoesNotExist:
                return Response({
                    'error': 'Tenant not found or inactive'
                }, status=status.HTTP_404_NOT_FOUND)
            
            # Create OpenAI-compatible JWT token
            token_data = create_openai_compatible_token(
                tenant=tenant,
                scopes=scopes,
                expires_in_days=expires_in_days
            )
            
            # Create AuthToken record with the token secret (for database lookup)
            auth_token = AuthToken.objects.create(
                token=token_data['token_secret'],  # Store the secret for lookup
                tenant=tenant,
                scopes=scopes,
                expires_at=timezone.now() + timedelta(days=expires_in_days),
                is_active=True
            )
            
            return Response({
                'message': f'OpenAI-compatible token created for tenant {tenant.name}',
                'token_info': {
                    'jwt_token': token_data['jwt_token'],  # This is what you give to OpenAI
                    'tenant_id': tenant.tenant_id,
                    'tenant_name': tenant.name,
                    'scopes': scopes,
                    'expires_at': auth_token.expires_at.isoformat(),
                    'created_at': auth_token.created_at.isoformat(),
                    'usage_note': 'Use jwt_token as the Bearer token in OpenAI Realtime'
                }
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            return Response({
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
