"""
OneDrive resource handler for tenant-specific file access
Handles resources like onedrive://filename or tenant://resource-name
"""

import re
import requests
from typing import Dict, Any, List, Optional
from channels.db import database_sync_to_async


class OneDriveResourceHandler:
    """Handles OneDrive file access for tenant resources"""
    
    def __init__(self):
        self.supported_schemes = ['onedrive', 'tenant']
    
    def can_handle(self, resource_uri: str) -> bool:
        """Check if this handler can process the resource URI"""
        return any(resource_uri.startswith(f'{scheme}://') for scheme in self.supported_schemes)
    
    async def resolve_resource(self, resource_uri: str, tenant, auth_token) -> Optional[Dict[str, Any]]:
        """
        Resolve a tenant resource URI
        Examples:
        - tenant://policy-document
        - tenant://faq-general
        - onedrive://shared-file-link
        """
        if resource_uri.startswith('tenant://'):
            return await self._resolve_tenant_resource(resource_uri, tenant)
        elif resource_uri.startswith('onedrive://'):
            return await self._resolve_onedrive_direct(resource_uri, tenant)
        
        return None
    
    async def _resolve_tenant_resource(self, resource_uri: str, tenant) -> Optional[Dict[str, Any]]:
        """Resolve tenant resource by name"""
        # Extract resource name from URI
        resource_name = resource_uri[9:]  # Remove 'tenant://'
        
        @database_sync_to_async
        def get_tenant_resource(tenant, name):
            from ..models import TenantResource
            try:
                return TenantResource.objects.get(
                    tenant=tenant,
                    name=name,
                    is_active=True
                )
            except TenantResource.DoesNotExist:
                return None
        
        resource = await get_tenant_resource(tenant, resource_name)
        if not resource:
            return {
                'error': f'Resource not found: {resource_name}',
                'available_resources': await self._list_tenant_resources(tenant)
            }
        
        # Handle different resource types
        if resource.resource_type == 'onedrive':
            return await self._fetch_onedrive_content(resource.resource_uri, resource)
        elif resource.resource_type == 'url':
            return await self._fetch_url_content(resource.resource_uri, resource)
        elif resource.resource_type == 'text':
            return {
                'type': 'resource',
                'uri': resource_uri,
                'name': resource.name,
                'description': resource.description,
                'content': resource.resource_uri,  # For text type, URI contains the content
                'mime_type': 'text/plain',
                'tags': resource.tags,
                'last_modified': resource.updated_at.isoformat()
            }
        
        return None
    
    async def _resolve_onedrive_direct(self, resource_uri: str, tenant) -> Optional[Dict[str, Any]]:
        """Resolve OneDrive link directly"""
        onedrive_url = resource_uri[11:]  # Remove 'onedrive://'
        return await self._fetch_onedrive_content(onedrive_url, None)
    
    async def _fetch_onedrive_content(self, onedrive_url: str, resource=None) -> Dict[str, Any]:
        """Fetch content from OneDrive share link"""
        try:
            # Convert OneDrive share link to direct download link
            direct_url = self._convert_onedrive_link(onedrive_url)
            
            if not direct_url:
                return {
                    'error': 'Invalid OneDrive share link format',
                    'provided_url': onedrive_url
                }
            
            # Fetch the content
            response = requests.get(direct_url, timeout=30)
            
            if response.status_code == 200:
                content_type = response.headers.get('content-type', 'text/plain')
                raw_content = response.content  # Get bytes for binary files
                
                # Handle different content types
                if 'application/pdf' in content_type or content_type == 'application/octet-stream':
                    # Extract text from PDF
                    try:
                        import PyPDF2
                        import io
                        
                        pdf_reader = PyPDF2.PdfReader(io.BytesIO(raw_content))
                        extracted_text = []
                        
                        for page_num in range(len(pdf_reader.pages)):
                            page = pdf_reader.pages[page_num]
                            extracted_text.append(page.extract_text())
                        
                        content = '\n\n'.join(extracted_text)
                        actual_mime_type = 'text/plain'  # Since we extracted text
                        
                    except ImportError:
                        # PyPDF2 not available, try basic text extraction
                        try:
                            content = raw_content.decode('utf-8', errors='ignore')
                            actual_mime_type = 'text/plain'
                        except:
                            content = f"PDF file detected ({len(raw_content)} bytes) but text extraction not available. Install PyPDF2 for PDF text extraction."
                            actual_mime_type = content_type
                    except Exception as e:
                        content = f"PDF text extraction failed: {str(e)}. Raw content: {len(raw_content)} bytes."
                        actual_mime_type = content_type
                else:
                    # Handle text files
                    try:
                        content = raw_content.decode('utf-8', errors='ignore')
                        actual_mime_type = content_type
                    except:
                        content = response.text
                        actual_mime_type = content_type
                
                return {
                    'type': 'resource',
                    'uri': f'onedrive://{onedrive_url}',
                    'name': resource.name if resource else 'OneDrive File',
                    'description': resource.description if resource else 'File from OneDrive',
                    'content': content,
                    'mime_type': actual_mime_type,
                    'size': len(content),
                    'tags': resource.tags if resource else [],
                    'source': 'OneDrive'
                }
            else:
                return {
                    'error': f'Failed to fetch OneDrive content (HTTP {response.status_code})',
                    'url': onedrive_url
                }
                
        except Exception as e:
            return {
                'error': f'OneDrive access error: {str(e)}',
                'url': onedrive_url
            }
    
    async def _fetch_url_content(self, url: str, resource) -> Dict[str, Any]:
        """Fetch content from a regular URL"""
        try:
            response = requests.get(url, timeout=30)
            
            if response.status_code == 200:
                content = response.text
                
                return {
                    'type': 'resource',
                    'uri': f'url://{url}',
                    'name': resource.name,
                    'description': resource.description,
                    'content': content,
                    'mime_type': response.headers.get('content-type', 'text/plain'),
                    'size': len(content),
                    'tags': resource.tags,
                    'source': 'Web URL'
                }
            else:
                return {
                    'error': f'Failed to fetch URL content (HTTP {response.status_code})',
                    'url': url
                }
                
        except Exception as e:
            return {
                'error': f'URL access error: {str(e)}',
                'url': url
            }
    
    def _convert_onedrive_link(self, share_url: str) -> Optional[str]:
        """Convert OneDrive/SharePoint share link to direct download link"""
        try:
            # Handle SharePoint URLs (like your HiQSense URL)
            if 'sharepoint.com' in share_url:
                # For SharePoint business files, try adding download=1 parameter
                if '?' in share_url:
                    return f"{share_url}&download=1"
                else:
                    return f"{share_url}?download=1"
            
            # Handle traditional OneDrive URLs
            elif '1drv.ms' in share_url or 'onedrive.live.com' in share_url:
                if '?id=' in share_url:
                    return share_url.replace('?id=', '/download?id=')
                elif '/view' in share_url:
                    return share_url.replace('/view.aspx', '/download.aspx')
                elif '/edit' in share_url:
                    return share_url.replace('/edit.aspx', '/download.aspx')
            
            # If no conversion pattern matches, try the URL as-is
            return share_url
            
        except Exception as e:
            # Log the error for debugging
            print(f"OneDrive link conversion error: {e}")
            return None
    
    async def _list_tenant_resources(self, tenant) -> List[str]:
        """List available resource names for a tenant"""
        @database_sync_to_async
        def get_resource_names(tenant):
            from ..models import TenantResource
            return list(TenantResource.objects.filter(
                tenant=tenant,
                is_active=True
            ).values_list('name', flat=True))
        
        return await get_resource_names(tenant)
    
    def list_resources(self, tenant, path: str = '') -> List[Dict[str, Any]]:
        """List all resources available to a tenant"""
        from ..models import TenantResource
        
        # Use direct database query instead of async wrapper to avoid threading issues with asyncio.run
        resources_data = list(TenantResource.objects.filter(
            tenant=tenant,
            is_active=True
        ).values(
            'name', 'resource_type', 'description', 'tags', 'updated_at'
        ))
        
        resources = []
        for res in resources_data:
            resources.append({
                'type': 'resource',
                'uri': f'tenant://{res["name"]}',
                'name': res['name'],
                'resource_type': res['resource_type'],
                'description': res['description'],
                'tags': res['tags'],
                'last_modified': res['updated_at'].isoformat()
            })
        
        return resources


# Global OneDrive resource handler instance
onedrive_resource = OneDriveResourceHandler()
