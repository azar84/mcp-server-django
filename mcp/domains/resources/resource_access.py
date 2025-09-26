"""
Resource access provider for OpenAI agents
Bridges MCP resources to discoverable tools
"""

import json
import asyncio
from typing import Dict, Any, List
from ..base import BaseProvider, BaseTool, ProviderType


class ResourceAccessProvider(BaseProvider):
    """Provider for resource access tools"""
    
    def __init__(self):
        super().__init__(
            name="resource_access",
            provider_type=ProviderType.GENERAL,
            config={}
        )
    
    def get_tools(self) -> List[Dict[str, Any]]:
        """Return resource access tools"""
        return [
            {
                'name': 'get_resource',
                'tool_class': GetResourceTool,
                'description': 'Fetch a tenant-scoped knowledge resource by URI (e.g., tenant://company-policies, kb://faq/general.md). Returns the full text content of documents, PDFs, or other files.',
                'input_schema': {
                    'type': 'object',
                    'properties': {
                        'uri': {
                            'type': 'string',
                            'description': 'Resource URI to fetch (e.g., "tenant://company-policies", "kb://faq/general.md")',
                            'examples': ['tenant://company-policies', 'tenant://user-manual', 'kb://faq/general.md']
                        }
                    },
                    'required': ['uri'],
                    'additionalProperties': False
                },
                'required_scopes': ['basic', 'read']
            },
            {
                'name': 'search_documents',
                'tool_class': SearchDocumentsTool,
                'description': 'Search over this tenant\'s knowledge base and documents. Returns matching resources with their URIs that you can then read with get_resource.',
                'input_schema': {
                    'type': 'object',
                    'properties': {
                        'query': {
                            'type': 'string',
                            'description': 'Search query to find relevant documents',
                            'examples': ['work from home policy', 'contact information', 'pricing']
                        },
                        'top_k': {
                            'type': 'integer',
                            'description': 'Maximum number of results to return',
                            'minimum': 1,
                            'maximum': 20,
                            'default': 5
                        }
                    },
                    'required': ['query'],
                    'additionalProperties': False
                },
                'required_scopes': ['basic', 'read']
            }
        ]
    
    def get_required_credentials(self) -> List[str]:
        """No special credentials required for resource access"""
        return []
    
    async def validate_credentials(self, credentials: Dict[str, str]) -> bool:
        """Always valid - uses tenant authentication"""
        return True


class GetResourceTool(BaseTool):
    """Tool to fetch resource content by URI"""
    
    async def _execute_with_credentials(self, arguments: Dict[str, Any], context: Dict[str, Any], config: Dict[str, Any]) -> str:
        """Execute the get_resource tool"""
        uri = arguments.get('uri')
        if not uri:
            return json.dumps({
                'error': 'Missing required parameter: uri',
                'example': 'Use uri like "tenant://company-policies" or "kb://faq/general.md"'
            })
        
        tenant = context.get('tenant')
        auth_token = context.get('auth_token')
        
        if not tenant:
            return json.dumps({
                'error': 'Authentication required',
                'message': 'This tool requires tenant authentication'
            })
        
        try:
            # Import here to avoid circular imports
            from ...resources.onedrive import onedrive_resource
            from ...resources.knowledge_base import kb_resource
            import asyncio
            
            # Try OneDrive/tenant resources first using asyncio.run to avoid threading issues on Heroku
            if onedrive_resource.can_handle(uri):
                resource_data = asyncio.run(onedrive_resource.resolve_resource(uri, tenant, auth_token))
            else:
                # Fallback to knowledge base resources (global)
                resource_data = kb_resource.resolve_resource(uri)
            
            if resource_data is None:
                # List available resources to help the user using asyncio.run to avoid threading issues on Heroku  
                available_resources = asyncio.run(onedrive_resource.list_resources(tenant))
                available_uris = [r['uri'] for r in available_resources] if available_resources else []
                
                return json.dumps({
                    'error': f'Resource not found: {uri}',
                    'available_resources': available_uris,
                    'suggestion': 'Use search_documents tool to find the right URI first'
                })
            
            # Handle error responses from resource handlers
            if 'error' in resource_data:
                return json.dumps({
                    'error': resource_data['error'],
                    'uri': uri
                })
            
            # Return successful resource data
            content = resource_data.get('content', '')
            
            return json.dumps({
                'success': True,
                'uri': resource_data.get('uri', uri),
                'name': resource_data.get('name', 'Unknown'),
                'description': resource_data.get('description', ''),
                'content': content,
                'content_length': len(content),
                'mime_type': resource_data.get('mime_type', 'text/plain'),
                'tags': resource_data.get('tags', []),
                'source': resource_data.get('source', 'Unknown')
            })
            
        except Exception as e:
            return json.dumps({
                'error': f'Failed to fetch resource: {str(e)}',
                'uri': uri,
                'suggestion': 'Check if the URI is correct and the resource exists'
            })


class SearchDocumentsTool(BaseTool):
    """Tool to search for resources"""
    
    async def _execute_with_credentials(self, arguments: Dict[str, Any], context: Dict[str, Any], config: Dict[str, Any]) -> str:
        """Execute the search_documents tool"""
        query = arguments.get('query')
        top_k = arguments.get('top_k', 5)
        
        if not query:
            return json.dumps({
                'error': 'Missing required parameter: query',
                'example': 'Use query like "work from home policy" or "contact information"'
            })
        
        tenant = context.get('tenant')
        if not tenant:
            return json.dumps({
                'error': 'Authentication required',
                'message': 'This tool requires tenant authentication'
            })
        
        try:
            # Import here to avoid circular imports
            from ...resources.onedrive import onedrive_resource
            from ...resources.knowledge_base import kb_resource
            import asyncio
            
            # Get all tenant resources using asyncio.run to avoid threading issues on Heroku
            tenant_resources = asyncio.run(onedrive_resource.list_resources(tenant))
            
            # Get global knowledge base resources
            kb_resources = kb_resource.list_resources()
            
            # Combine all resources
            all_resources = tenant_resources + [
                {
                    'type': 'resource',
                    'uri': f'kb://{r["name"]}',
                    'name': r['name'],
                    'description': f'Knowledge base: {r["name"]}',
                    'tags': ['kb', 'global'],
                    'resource_type': 'knowledge_base'
                } for r in kb_resources if r['type'] == 'file'
            ]
            
            if not all_resources:
                return json.dumps({
                    'message': 'No documents available to search',
                    'suggestion': 'Add resources in the Django admin panel',
                    'results': []
                })
            
            # Simple text-based search (you could enhance this with vector search)
            query_lower = query.lower()
            scored_resources = []
            
            for resource in all_resources:
                score = 0
                searchable_text = f"{resource.get('name', '')} {resource.get('description', '')} {' '.join(resource.get('tags', []))}".lower()
                
                # Simple scoring based on query terms
                query_terms = query_lower.split()
                for term in query_terms:
                    if term in searchable_text:
                        score += searchable_text.count(term)
                
                if score > 0:
                    scored_resources.append({
                        'resource': resource,
                        'score': score,
                        'relevance': 'high' if score >= 3 else 'medium' if score >= 2 else 'low'
                    })
            
            # Sort by score and limit results
            scored_resources.sort(key=lambda x: x['score'], reverse=True)
            top_results = scored_resources[:top_k]
            
            if not top_results:
                return json.dumps({
                    'message': f'No documents found matching "{query}"',
                    'available_resources': [r['name'] for r in all_resources[:5]],
                    'suggestion': 'Try broader search terms or check available resources',
                    'results': []
                })
            
            # Format results for the agent
            results = []
            for result in top_results:
                resource = result['resource']
                results.append({
                    'uri': resource['uri'],
                    'name': resource.get('name', 'Unknown'),
                    'description': resource.get('description', ''),
                    'tags': resource.get('tags', []),
                    'resource_type': resource.get('resource_type', 'unknown'),
                    'relevance': result['relevance'],
                    'score': result['score']
                })
            
            return json.dumps({
                'success': True,
                'query': query,
                'total_results': len(results),
                'results': results,
                'instruction': 'Use get_resource tool with the URI to read the full content of any document'
            })
            
        except Exception as e:
            return json.dumps({
                'error': f'Search failed: {str(e)}',
                'query': query,
                'suggestion': 'Try a simpler search query or check if resources are available'
            })
