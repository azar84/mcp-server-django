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
from .models import Tenant, AuthToken, AdminToken
from .auth import mcp_authenticator, admin_auth_middleware
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
        """Create a new tenant (requires admin token)"""
        try:
            # Authenticate admin request
            admin_token, error_message = admin_auth_middleware.authenticate_admin_request(
                request, required_scope='admin'
            )
            if not admin_token:
                return Response({
                    'error': f'Admin authentication required: {error_message}',
                    'required_scope': 'admin'
                }, status=status.HTTP_401_UNAUTHORIZED)
            
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
                },
                'created_by_admin_token': admin_token.name
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            return Response({
                'error': f'Failed to create tenant: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def delete(self, request, tenant_id):
        """Delete a tenant"""
        try:
            tenant = get_object_or_404(Tenant, tenant_id=tenant_id)
            
            # Check if tenant has active tokens or sessions
            active_tokens = tenant.authtoken_set.filter(is_active=True).count()
            active_sessions = tenant.mcpsession_set.filter(is_active=True).count()
            
            if active_tokens > 0 or active_sessions > 0:
                return Response({
                    'error': f'Cannot delete tenant with active tokens ({active_tokens}) or sessions ({active_sessions})',
                    'tenant_id': tenant_id,
                    'tenant_name': tenant.name,
                    'active_tokens': active_tokens,
                    'active_sessions': active_sessions,
                    'suggestion': 'Deactivate all tokens and sessions first, or set tenant to inactive instead'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Store tenant info before deletion for response
            tenant_name = tenant.name
            
            # Delete the tenant (this will cascade delete related objects)
            tenant.delete()
            
            return Response({
                'message': f'Tenant {tenant_name} deleted successfully',
                'deleted_tenant_id': tenant_id,
                'deleted_tenant_name': tenant_name
            })
            
        except Exception as e:
            return Response({
                'error': f'Failed to delete tenant: {str(e)}'
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
                    'id': auth_token.id,  # Token ID for reference
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
    
    def delete(self, request, token_id=None):
        """Deactivate a token by ID or by token string + tenant_id"""
        try:
            # Check if token_id is provided in URL (admin interface)
            if token_id:
                auth_token = get_object_or_404(AuthToken, id=token_id)
            else:
                # Check if token and tenant_id are provided in request body (external apps)
                token_string = request.data.get('token')
                tenant_id = request.data.get('tenant_id')
                
                if not token_string or not tenant_id:
                    return Response({
                        'error': 'Either token_id in URL or both token and tenant_id in request body are required'
                    }, status=status.HTTP_400_BAD_REQUEST)
                
                try:
                    tenant = Tenant.objects.get(tenant_id=tenant_id)
                    auth_token = AuthToken.objects.get(token=token_string, tenant=tenant)
                except Tenant.DoesNotExist:
                    return Response({
                        'error': 'Tenant not found'
                    }, status=status.HTTP_404_NOT_FOUND)
                except AuthToken.DoesNotExist:
                    return Response({
                        'error': 'Token not found for this tenant'
                    }, status=status.HTTP_404_NOT_FOUND)
            
            # Deactivate the token
            auth_token.is_active = False
            auth_token.save()
            
            return Response({
                'message': 'Token deactivated successfully',
                'token_info': {
                    'token_preview': auth_token.token[:8] + '...',
                    'tenant_id': auth_token.tenant.tenant_id,
                    'tenant_name': auth_token.tenant.name,
                    'deactivated_at': auth_token.updated_at.isoformat()
                }
            })
            
        except Exception as e:
            return Response({
                'error': f'Failed to deactivate token: {str(e)}'
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


class MSBookingsCredentialsView(APIView):
    """Manage MS Bookings credentials for tokens"""
    
    def get(self, request, token_id=None):
        """List MS Bookings credentials or get specific one"""
        try:
            # Authenticate admin request
            admin_token, error_message = admin_auth_middleware.authenticate_admin_request(
                request, required_scope='admin'
            )
            if not admin_token:
                return Response({
                    'error': f'Admin authentication required: {error_message}',
                    'required_scope': 'admin'
                }, status=status.HTTP_401_UNAUTHORIZED)
            if token_id:
                # Get specific credential by token ID
                auth_token = get_object_or_404(AuthToken, id=token_id)
                try:
                    ms_credential = auth_token.ms_bookings_credential
                    return Response({
                        'credential': {
                            'id': ms_credential.id,
                            'token_id': auth_token.id,
                            'token_preview': auth_token.token[:8] + '...',
                            'tenant_id': auth_token.tenant.tenant_id,
                            'tenant_name': auth_token.tenant.name,
                            'azure_tenant_id': ms_credential.azure_tenant_id,
                            'business_id': ms_credential.business_id,
                            'service_id': ms_credential.service_id,
                            'staff_ids': ms_credential.staff_ids,
                            'is_active': ms_credential.is_active,
                            'azure_credentials_status': '✅ Configured' if ms_credential.has_valid_azure_credentials() else '❌ Missing',
                            'configuration_status': '✅ Configured' if ms_credential.has_valid_configuration() else '❌ Not configured',
                            'created_at': ms_credential.created_at.isoformat(),
                            'updated_at': ms_credential.updated_at.isoformat()
                        }
                    })
                except:
                    return Response({
                        'error': 'MS Bookings credential not found for this token',
                        'token_id': token_id,
                        'token_preview': auth_token.token[:8] + '...'
                    }, status=status.HTTP_404_NOT_FOUND)
            else:
                # List all MS Bookings credentials
                from .models import MSBookingsCredential
                credentials = MSBookingsCredential.objects.select_related('auth_token', 'auth_token__tenant').all()
                data = []
                
                for cred in credentials:
                    data.append({
                        'id': cred.id,
                        'token_id': cred.auth_token.id,
                        'token_preview': cred.auth_token.token[:8] + '...',
                        'tenant_id': cred.auth_token.tenant.tenant_id,
                        'tenant_name': cred.auth_token.tenant.name,
                        'azure_tenant_id': cred.azure_tenant_id,
                        'business_id': cred.business_id,
                        'service_id': cred.service_id,
                        'staff_ids': cred.staff_ids,
                        'is_active': cred.is_active,
                        'azure_credentials_status': '✅ Configured' if cred.has_valid_azure_credentials() else '❌ Missing',
                        'configuration_status': '✅ Configured' if cred.has_valid_configuration() else '❌ Not configured',
                        'created_at': cred.created_at.isoformat(),
                        'updated_at': cred.updated_at.isoformat()
                    })
                
                return Response({
                    'credentials': data,
                    'total_count': len(data)
                })
                
        except Exception as e:
            return Response({
                'error': f'Failed to retrieve MS Bookings credentials: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def post(self, request):
        """Create MS Bookings credential for a token"""
        try:
            # Authenticate admin request
            admin_token, error_message = admin_auth_middleware.authenticate_admin_request(
                request, required_scope='admin'
            )
            if not admin_token:
                return Response({
                    'error': f'Admin authentication required: {error_message}',
                    'required_scope': 'admin'
                }, status=status.HTTP_401_UNAUTHORIZED)
            from .models import MSBookingsCredential
            
            token_id = request.data.get('token_id')
            azure_tenant_id = request.data.get('azure_tenant_id', '')
            business_id = request.data.get('business_id', '')
            service_id = request.data.get('service_id', '')
            staff_ids = request.data.get('staff_ids', [])
            
            if not token_id:
                return Response({
                    'error': 'token_id is required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Get the auth token
            auth_token = get_object_or_404(AuthToken, id=token_id)
            
            # Check if credential already exists
            if hasattr(auth_token, 'ms_bookings_credential'):
                return Response({
                    'error': 'MS Bookings credential already exists for this token',
                    'token_id': token_id,
                    'existing_credential_id': auth_token.ms_bookings_credential.id
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Create the credential
            ms_credential = MSBookingsCredential.objects.create(
                auth_token=auth_token,
                azure_tenant_id=azure_tenant_id,
                business_id=business_id,
                service_id=service_id,
                staff_ids=staff_ids,
                is_active=True
            )
            
            return Response({
                'message': f'MS Bookings credential created for token {auth_token.token[:8]}...',
                'credential': {
                    'id': ms_credential.id,
                    'token_id': auth_token.id,
                    'token_preview': auth_token.token[:8] + '...',
                    'tenant_id': auth_token.tenant.tenant_id,
                    'tenant_name': auth_token.tenant.name,
                    'azure_tenant_id': ms_credential.azure_tenant_id,
                    'business_id': ms_credential.business_id,
                    'service_id': ms_credential.service_id,
                    'staff_ids': ms_credential.staff_ids,
                    'is_active': ms_credential.is_active,
                    'azure_credentials_status': '✅ Configured' if ms_credential.has_valid_azure_credentials() else '❌ Missing',
                    'configuration_status': '✅ Configured' if ms_credential.has_valid_configuration() else '❌ Not configured',
                    'created_at': ms_credential.created_at.isoformat(),
                    'updated_at': ms_credential.updated_at.isoformat()
                }
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            return Response({
                'error': f'Failed to create MS Bookings credential: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def put(self, request, token_id):
        """Update MS Bookings credential for a token"""
        try:
            # Authenticate admin request
            admin_token, error_message = admin_auth_middleware.authenticate_admin_request(
                request, required_scope='admin'
            )
            if not admin_token:
                return Response({
                    'error': f'Admin authentication required: {error_message}',
                    'required_scope': 'admin'
                }, status=status.HTTP_401_UNAUTHORIZED)
            auth_token = get_object_or_404(AuthToken, id=token_id)
            
            try:
                ms_credential = auth_token.ms_bookings_credential
            except:
                return Response({
                    'error': 'MS Bookings credential not found for this token',
                    'token_id': token_id,
                    'token_preview': auth_token.token[:8] + '...'
                }, status=status.HTTP_404_NOT_FOUND)
            
            # Update fields if provided
            if 'azure_tenant_id' in request.data:
                ms_credential.azure_tenant_id = request.data['azure_tenant_id']
            if 'business_id' in request.data:
                ms_credential.business_id = request.data['business_id']
            if 'service_id' in request.data:
                ms_credential.service_id = request.data['service_id']
            if 'staff_ids' in request.data:
                ms_credential.staff_ids = request.data['staff_ids']
            if 'is_active' in request.data:
                ms_credential.is_active = request.data['is_active']
            
            ms_credential.save()
            
            return Response({
                'message': f'MS Bookings credential updated for token {auth_token.token[:8]}...',
                'credential': {
                    'id': ms_credential.id,
                    'token_id': auth_token.id,
                    'token_preview': auth_token.token[:8] + '...',
                    'tenant_id': auth_token.tenant.tenant_id,
                    'tenant_name': auth_token.tenant.name,
                    'azure_tenant_id': ms_credential.azure_tenant_id,
                    'business_id': ms_credential.business_id,
                    'service_id': ms_credential.service_id,
                    'staff_ids': ms_credential.staff_ids,
                    'is_active': ms_credential.is_active,
                    'azure_credentials_status': '✅ Configured' if ms_credential.has_valid_azure_credentials() else '❌ Missing',
                    'configuration_status': '✅ Configured' if ms_credential.has_valid_configuration() else '❌ Not configured',
                    'created_at': ms_credential.created_at.isoformat(),
                    'updated_at': ms_credential.updated_at.isoformat()
                }
            })
            
        except Exception as e:
            return Response({
                'error': f'Failed to update MS Bookings credential: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def delete(self, request, token_id):
        """Delete MS Bookings credential for a token"""
        try:
            # Authenticate admin request
            admin_token, error_message = admin_auth_middleware.authenticate_admin_request(
                request, required_scope='admin'
            )
            if not admin_token:
                return Response({
                    'error': f'Admin authentication required: {error_message}',
                    'required_scope': 'admin'
                }, status=status.HTTP_401_UNAUTHORIZED)
            auth_token = get_object_or_404(AuthToken, id=token_id)
            
            try:
                ms_credential = auth_token.ms_bookings_credential
            except:
                return Response({
                    'error': 'MS Bookings credential not found for this token',
                    'token_id': token_id,
                    'token_preview': auth_token.token[:8] + '...'
                }, status=status.HTTP_404_NOT_FOUND)
            
            # Store info before deletion
            credential_id = ms_credential.id
            token_preview = auth_token.token[:8] + '...'
            tenant_name = auth_token.tenant.name
            
            # Delete the credential
            ms_credential.delete()
            
            return Response({
                'message': f'MS Bookings credential deleted for token {token_preview}',
                'deleted_credential_id': credential_id,
                'token_id': token_id,
                'token_preview': token_preview,
                'tenant_name': tenant_name
            })
            
        except Exception as e:
            return Response({
                'error': f'Failed to delete MS Bookings credential: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class AdminTokenManagementView(APIView):
    """Manage admin tokens for tenant creation and management"""
    
    def get(self, request):
        """List all admin tokens"""
        tokens = AdminToken.objects.all()
        data = []
        
        for token in tokens:
            data.append({
                'id': token.id,
                'name': token.name,
                'token_preview': token.token[:8] + '...',
                'scopes': token.scopes,
                'is_active': token.is_active,
                'expires_at': token.expires_at.isoformat() if token.expires_at else None,
                'created_at': token.created_at.isoformat(),
                'last_used': token.last_used.isoformat() if token.last_used else None,
                'created_by': token.created_by
            })
        
        return Response({
            'admin_tokens': data,
            'total_count': len(data)
        })
    
    def post(self, request):
        """Create a new admin token"""
        try:
            name = request.data.get('name')
            scopes = request.data.get('scopes', ['admin'])
            expires_in_days = request.data.get('expires_in_days', 365)
            created_by = request.data.get('created_by', 'API')
            
            if not name:
                return Response({
                    'error': 'Token name is required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Create admin token
            admin_token = admin_authenticator.create_admin_token(
                name=name,
                scopes=scopes,
                expires_in_days=expires_in_days,
                created_by=created_by
            )
            
            return Response({
                'message': f'Admin token {name} created successfully',
                'token_info': {
                    'id': admin_token.id,
                    'name': admin_token.name,
                    'token': admin_token.token,  # Return full token only on creation
                    'scopes': admin_token.scopes,
                    'expires_at': admin_token.expires_at.isoformat() if admin_token.expires_at else None,
                    'created_at': admin_token.created_at.isoformat(),
                    'created_by': admin_token.created_by
                }
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            return Response({
                'error': f'Failed to create admin token: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def delete(self, request, token_id):
        """Deactivate an admin token"""
        try:
            admin_token = get_object_or_404(AdminToken, id=token_id)
            admin_token.is_active = False
            admin_token.save()
            
            return Response({
                'message': 'Admin token deactivated successfully'
            })
            
        except Exception as e:
            return Response({
                'error': f'Failed to deactivate admin token: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
